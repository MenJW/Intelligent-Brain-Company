from __future__ import annotations

from difflib import unified_diff

from flask import current_app, jsonify, request

from intelligent_brain_company.api import planning_bp
from intelligent_brain_company.domain.models import Stage, UserIntervention
from intelligent_brain_company.domain.project_state import ProjectStatus, TaskRecord


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

        plan = orchestrator.build_plan(project.idea, project.interventions)
        markdown = orchestrator.render_stage(plan, next_stage)
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
    orchestrator = current_app.extensions["planning_orchestrator"]
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

    task = TaskRecord.create(kind="regenerate_plan", project_id=project_id)
    task.mark_running()
    task_store.save_task(task)

    try:
        plan = orchestrator.build_plan(project.idea, project.interventions)
        markdown = orchestrator.render_plan(plan)
        version = project.register_plan(plan, markdown)
        project_store.save_project(project)
        task.mark_completed({"project_id": project_id, "version_id": version.version_id})
        task_store.save_task(task)
        return jsonify(
            {
                "success": True,
                "data": {
                    "task": task.to_dict(),
                    "project": project.to_dict(),
                    "latest_plan": version.to_dict(),
                },
            }
        )
    except Exception as exc:
        task.mark_failed(str(exc))
        task_store.save_task(task)
        return jsonify({"success": False, "error": str(exc), "task": task.to_dict()}), 500


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
    return jsonify(
        {
            "success": True,
            "data": {
                "agent": agent,
                "history": [turn.to_dict() for turn in project.get_conversation(agent)],
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

    reply, used_llm, suggested_stage, suggested_impact, can_promote = chat_agent.reply(project, agent, message)
    turn = project.append_conversation(
        agent=agent,
        user_message=message,
        assistant_message=reply,
        used_llm=used_llm,
        suggested_stage=suggested_stage,
        suggested_impact=suggested_impact,
        can_promote_to_intervention=can_promote,
    )
    project_store.save_project(project)
    return jsonify(
        {
            "success": True,
            "data": {
                "agent": agent,
                "turn": turn.to_dict(),
                "history": [item.to_dict() for item in project.get_conversation(agent)],
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
    task_store = current_app.extensions["task_store"]
    orchestrator = current_app.extensions["planning_orchestrator"]
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
        speaker=payload.get("speaker", turn.agent),
        message=turn.user_message,
        impact=payload.get("impact", turn.suggested_impact),
    )
    project.add_intervention(intervention)
    project_store.save_project(project)

    task = TaskRecord.create(kind="promote_chat_to_intervention", project_id=project_id)
    task.mark_running()
    task_store.save_task(task)

    try:
        plan = orchestrator.build_plan(project.idea, project.interventions)
        markdown = orchestrator.render_plan(plan)
        version = project.register_plan(plan, markdown)
        project_store.save_project(project)
        task.mark_completed({"project_id": project_id, "version_id": version.version_id, "turn_id": turn.turn_id})
        task_store.save_task(task)
        return jsonify(
            {
                "success": True,
                "data": {
                    "task": task.to_dict(),
                    "project": project.to_dict(),
                    "latest_plan": version.to_dict(),
                    "promoted_turn": turn.to_dict(),
                },
            }
        )
    except Exception as exc:
        task.mark_failed(str(exc))
        task_store.save_task(task)
        return jsonify({"success": False, "error": str(exc), "task": task.to_dict()}), 500