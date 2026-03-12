from __future__ import annotations

from difflib import unified_diff
import re

from flask import current_app, jsonify, request

from intelligent_brain_company.agents.registry import department_teams
from intelligent_brain_company.api import planning_bp
from intelligent_brain_company.domain.models import Department, Stage, UserIntervention
from intelligent_brain_company.domain.project_state import ProjectStatus, TaskRecord


DEPARTMENT_AGENT_KEYS = {"hardware", "software", "design", "marketing", "finance"}
SUPPORTED_CONVERSATION_LANGUAGES = {"zh-CN", "en-US"}


def _normalize_conversation_language(language: str | None, fallback: str = "zh-CN") -> str:
    if not language:
        return fallback if fallback in SUPPORTED_CONVERSATION_LANGUAGES else "zh-CN"
    value = str(language).strip()
    if value in SUPPORTED_CONVERSATION_LANGUAGES:
        return value
    return fallback if fallback in SUPPORTED_CONVERSATION_LANGUAGES else "zh-CN"


def _project_language(project) -> str:
    return _normalize_conversation_language(getattr(project, "conversation_language", None), fallback="zh-CN")


def _visible_stages_for_agent(agent: str) -> set[Stage]:
    if agent == "research":
        return {Stage.RESEARCH}
    if agent == "board":
        return {Stage.SYNTHESIS, Stage.BOARD}
    if agent in DEPARTMENT_AGENT_KEYS:
        return {Stage.DEPARTMENT_DESIGN, Stage.ROUNDTABLE, Stage.SYNTHESIS}
    return {Stage.RESEARCH, Stage.DEPARTMENT_DESIGN, Stage.ROUNDTABLE, Stage.SYNTHESIS, Stage.BOARD}


def _build_stage_replay_history(project, agent: str) -> list[dict]:
    # Department agents should focus on role-specific dialogue and employee statements.
    # Stage markdown at these phases often contains all departments and causes noisy history.
    if agent in DEPARTMENT_AGENT_KEYS:
        return []
    visible_stages = _visible_stages_for_agent(agent)
    history: list[dict] = []
    for version in project.plans:
        if version.stage not in visible_stages:
            continue
        history.append(
            {
                "turn_id": f"replay_{version.version_id}",
                "agent": agent,
                "user_message": "",
                "assistant_message": version.markdown,
                "created_at": version.created_at,
                "used_llm": False,
                "suggested_stage": version.stage.value,
                "suggested_impact": "历史环节回看",
                "can_promote_to_intervention": False,
                "source": "stage_review",
                "speaker": "阶段评审回放",
            }
        )
    return history


def _build_employee_discussion_history(project, agent: str) -> list[dict]:
    if project.latest_plan is None:
        return []

    roundtable_timestamps = [
        version.created_at
        for version in project.plans
        if version.stage == Stage.ROUNDTABLE
    ]
    fallback_timestamp = roundtable_timestamps[-1] if roundtable_timestamps else project.updated_at

    history: list[dict] = []
    for review_index, review in enumerate(project.latest_plan.roundtable_reviews):
        if agent in DEPARTMENT_AGENT_KEYS and review.department.value != agent:
            continue
        for index, line in enumerate(review.discussion_log):
            speaker = "员工"
            speaker_title = ""
            match = re.match(r"^(?P<name>.+?)[(（](?P<title>.+?)[)）]\s*(said:|表示：)", line)
            if match:
                speaker = match.group("name").strip()
                speaker_title = match.group("title").strip()
            elif " (" in line:
                speaker = line.split(" (", 1)[0].strip()
            history.append(
                {
                    "turn_id": f"discussion_{review.department.value}_{review_index}_{index}",
                    "agent": agent,
                    "user_message": "",
                    "assistant_message": line,
                    "created_at": fallback_timestamp,
                    "used_llm": False,
                    "suggested_stage": Stage.ROUNDTABLE.value,
                    "suggested_impact": "跨部门评审员工发言",
                    "can_promote_to_intervention": False,
                    "source": "employee_statement",
                    "speaker": speaker,
                    "speaker_title": speaker_title,
                }
            )
    return history


@planning_bp.route("/api/planning/generate", methods=["POST"])
def generate_plan():
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project_store = current_app.extensions["project_store"]
    task_store = current_app.extensions["task_store"]
    orchestrator = current_app.extensions["planning_orchestrator"]

    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    task = TaskRecord.create(kind="generate_plan", project_id=project_id)
    task.mark_running()
    task_store.save_task(task)

    try:
        next_stage = project.next_stage_to_run()
        if next_stage is None:
            task.mark_completed({"project_id": project_id, "message": "all stages completed"})
            task_store.save_task(task)
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "task": task.to_dict(),
                        "project": project.to_dict(),
                        "latest_plan": project.plans[-1].to_dict() if project.plans else None,
                        "executed_stage": None,
                        "has_next_stage": False,
                    },
                }
            )

        project.status = ProjectStatus.PLANNING
        project.touch()
        project_store.save_project(project)

        language = _project_language(project)
        plan = orchestrator.build_plan_for_stage(project.idea, next_stage, project.interventions, language=language)
        markdown = orchestrator.render_stage(plan, next_stage, language=language)
        version = project.register_stage_snapshot(plan, markdown, next_stage)
        project_store.save_project(project)

        task.mark_completed(
            {
                "project_id": project_id,
                "version_id": version.version_id,
                "executed_stage": next_stage.value,
            }
        )
        task_store.save_task(task)
        return jsonify(
            {
                "success": True,
                "data": {
                    "task": task.to_dict(),
                    "project": project.to_dict(),
                    "latest_plan": version.to_dict(),
                    "executed_stage": next_stage.value,
                    "has_next_stage": project.next_stage_to_run() is not None,
                },
            }
        )
    except Exception as exc:
        project.status = ProjectStatus.FAILED
        project.error = str(exc)
        project.touch()
        project_store.save_project(project)
        task.mark_failed(str(exc))
        task_store.save_task(task)
        return jsonify({"success": False, "error": str(exc), "task": task.to_dict()}), 500


@planning_bp.route("/api/planning/interventions", methods=["POST"])
def add_intervention_and_regenerate():
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project_store = current_app.extensions["project_store"]
    task_store = current_app.extensions["task_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    stage_value = payload.get("stage", Stage.RESEARCH.value)
    intervention = UserIntervention(
        stage=Stage(stage_value),
        speaker=payload.get("speaker", "user"),
        message=payload.get("message", ""),
        impact=payload.get("impact", "revise downstream conclusions"),
    )
    project.add_intervention(intervention)
    project_store.save_project(project)

    task = TaskRecord.create(kind="record_intervention", project_id=project_id)
    task.mark_completed({"project_id": project_id, "auto_regenerated": False})
    task_store.save_task(task)

    return jsonify(
        {
            "success": True,
            "data": {
                "task": task.to_dict(),
                "project": project.to_dict(),
                "auto_regenerated": False,
            },
        }
    )


@planning_bp.route("/api/projects/<project_id>/chat/employees", methods=["GET"])
def get_chat_employees(project_id: str):
    agent = request.args.get("agent", "research")

    project_store = current_app.extensions["project_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    if agent not in DEPARTMENT_AGENT_KEYS:
        return jsonify({"success": True, "data": {"agent": agent, "employees": []}})

    department = Department(agent)
    team = department_teams().get(department, ())
    employees = []
    for member in team:
        first_name = member.name.split(" ", 1)[0]
        employees.append(
            {
                "employee_id": member.employee_id,
                "name": member.name,
                "title": member.title,
                "mention_key": first_name,
                "department": member.department.value,
            }
        )

    return jsonify(
        {
            "success": True,
            "data": {
                "agent": agent,
                "employees": employees,
            },
        }
    )


@planning_bp.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    task_store = current_app.extensions["task_store"]
    task = task_store.get_task(task_id)
    if task is None:
        return jsonify({"success": False, "error": "task not found"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@planning_bp.route("/api/projects/<project_id>/timeline", methods=["GET"])
def get_project_timeline(project_id: str):
    project_store = current_app.extensions["project_store"]
    task_store = current_app.extensions["task_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    timeline = project.build_timeline()
    for task in task_store.list_tasks_for_project(project_id):
        timeline.append(
            {
                "timestamp": task.updated_at,
                "type": "task",
                "title": task.kind,
                "detail": task.status.value,
                "task_id": task.task_id,
            }
        )
    timeline.sort(key=lambda item: item["timestamp"])
    return jsonify({"success": True, "data": timeline})


@planning_bp.route("/api/projects/<project_id>/progress", methods=["GET"])
def get_project_progress(project_id: str):
    project_store = current_app.extensions["project_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404
    return jsonify(
        {
            "success": True,
            "data": {
                "project_id": project.project_id,
                "status": project.status.value,
                "current_stage": project.current_stage.value,
                "stages": project.build_stage_progress(),
            },
        }
    )


@planning_bp.route("/api/projects/<project_id>/plans/<version_id>", methods=["GET"])
def get_plan_version(project_id: str, version_id: str):
    project_store = current_app.extensions["project_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404
    version = project.get_plan_version(version_id)
    if version is None:
        return jsonify({"success": False, "error": "plan version not found"}), 404
    return jsonify({"success": True, "data": version.to_dict()})


@planning_bp.route("/api/projects/<project_id>/plans/diff", methods=["GET"])
def get_plan_diff(project_id: str):
    from_version = request.args.get("from")
    to_version = request.args.get("to")
    if not from_version or not to_version:
        return jsonify({"success": False, "error": "from and to query params are required"}), 400

    project_store = current_app.extensions["project_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    left = project.get_plan_version(from_version)
    right = project.get_plan_version(to_version)
    if left is None or right is None:
        return jsonify({"success": False, "error": "plan version not found"}), 404

    diff_lines = list(
        unified_diff(
            left.markdown.splitlines(),
            right.markdown.splitlines(),
            fromfile=left.version_id,
            tofile=right.version_id,
            lineterm="",
        )
    )
    return jsonify(
        {
            "success": True,
            "data": {
                "from": left.to_dict(),
                "to": right.to_dict(),
                "diff": "\n".join(diff_lines),
            },
        }
    )


@planning_bp.route("/api/projects/<project_id>/chat", methods=["GET"])
def get_project_chat(project_id: str):
    agent = request.args.get("agent", "research")
    project_store = current_app.extensions["project_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    manual_history = [
        {
            **turn.to_dict(),
            "source": "chat",
            "speaker": turn.responder or agent,
        }
        for turn in project.get_conversation(agent)
    ]
    stage_replay_history = _build_stage_replay_history(project, agent)
    employee_discussions = _build_employee_discussion_history(project, agent)
    combined_history = sorted(
        [*stage_replay_history, *employee_discussions, *manual_history],
        key=lambda item: item["created_at"],
    )

    return jsonify(
        {
            "success": True,
            "data": {
                "agent": agent,
                "language": project.conversation_language,
                "history": combined_history,
            },
        }
    )


@planning_bp.route("/api/projects/<project_id>/chat", methods=["POST"])
def post_project_chat(project_id: str):
    payload = request.get_json(silent=True) or {}
    agent = str(payload.get("agent", "research"))
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    project_store = current_app.extensions["project_store"]
    chat_agent = current_app.extensions["chat_agent"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    language = _normalize_conversation_language(payload.get("language"), fallback=project.conversation_language)
    if project.conversation_language != language:
        project.conversation_language = language

    reply, used_llm, suggested_stage, suggested_impact, can_promote, responder = chat_agent.reply(
        project,
        agent,
        message,
        language=project.conversation_language,
    )
    turn = project.append_conversation(
        agent=agent,
        user_message=message,
        assistant_message=reply,
        responder=responder,
        used_llm=used_llm,
        language=project.conversation_language,
        suggested_stage=suggested_stage,
        suggested_impact=suggested_impact,
        can_promote_to_intervention=can_promote,
    )
    project_store.save_project(project)

    manual_history = [
        {
            **item.to_dict(),
            "source": "chat",
            "speaker": item.responder or agent,
        }
        for item in project.get_conversation(agent)
    ]
    stage_replay_history = _build_stage_replay_history(project, agent)
    employee_discussions = _build_employee_discussion_history(project, agent)
    combined_history = sorted(
        [*stage_replay_history, *employee_discussions, *manual_history],
        key=lambda item: item["created_at"],
    )

    return jsonify(
        {
            "success": True,
            "data": {
                "agent": agent,
                "language": project.conversation_language,
                "turn": {**turn.to_dict(), "source": "chat", "speaker": turn.responder or agent},
                "history": combined_history,
            },
        }
    )


@planning_bp.route("/api/projects/<project_id>/chat/promote", methods=["POST"])
def promote_chat_to_intervention(project_id: str):
    payload = request.get_json(silent=True) or {}
    turn_id = payload.get("turn_id")
    if not turn_id:
        return jsonify({"success": False, "error": "turn_id is required"}), 400

    project_store = current_app.extensions["project_store"]
    project = project_store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    turn = project.find_turn(turn_id)
    if turn is None:
        return jsonify({"success": False, "error": "turn not found"}), 404
    if not turn.can_promote_to_intervention:
        return jsonify({"success": False, "error": "turn cannot be promoted"}), 400

    intervention = UserIntervention(
        stage=Stage(payload.get("stage", turn.suggested_stage)),
        speaker=payload.get("speaker", turn.responder or turn.agent),
        message=turn.user_message,
        impact=payload.get("impact", turn.suggested_impact),
    )
    project.add_intervention(intervention)
    project_store.save_project(project)

    task = TaskRecord.create(kind="promote_chat_to_intervention", project_id=project_id)
    task.mark_completed({"project_id": project_id, "turn_id": turn.turn_id, "auto_regenerated": False})
    current_app.extensions["task_store"].save_task(task)

    return jsonify(
        {
            "success": True,
            "data": {
                "task": task.to_dict(),
                "project": project.to_dict(),
                "promoted_turn": turn.to_dict(),
                "auto_regenerated": False,
            },
        }
    )