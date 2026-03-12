from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from intelligent_brain_company.domain.models import (
    BoardDecision,
    Department,
    DepartmentSolution,
    IdeaBrief,
    PlanScorecard,
    ProjectPlan,
    ResearchAssessment,
    RoundtableReview,
    Stage,
    UserIntervention,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_project_plan(plan: ProjectPlan) -> dict[str, Any]:
    return {
        "idea": asdict(plan.idea),
        "research": asdict(plan.research),
        "department_solutions": {
            department.value: [asdict(solution) for solution in solutions]
            for department, solutions in plan.department_solutions.items()
        },
        "roundtable_reviews": [asdict(review) for review in plan.roundtable_reviews],
        "selected_solutions": {
            department.value: asdict(solution)
            for department, solution in plan.selected_solutions.items()
        },
        "board_decision": asdict(plan.board_decision),
        "scorecard": asdict(plan.scorecard) if plan.scorecard else None,
        "interventions": [asdict(item) for item in plan.interventions],
    }


def deserialize_department_solution(data: dict[str, Any]) -> DepartmentSolution:
    return DepartmentSolution(
        department=Department(data["department"]),
        name=data["name"],
        summary=data["summary"],
        feasibility_score=data["feasibility_score"],
        dependencies=[Department(item) for item in data.get("dependencies", [])],
        assumptions=data.get("assumptions", []),
        rationale=data.get("rationale", ""),
        implementation_steps=data.get("implementation_steps", []),
        success_metrics=data.get("success_metrics", []),
        artifacts=data.get("artifacts", {}),
    )


def deserialize_project_plan(data: dict[str, Any]) -> ProjectPlan:
    return ProjectPlan(
        idea=IdeaBrief(**data["idea"]),
        research=ResearchAssessment(**data["research"]),
        department_solutions={
            Department(department): [deserialize_department_solution(solution) for solution in solutions]
            for department, solutions in data.get("department_solutions", {}).items()
        },
        roundtable_reviews=[
            RoundtableReview(
                department=Department(review["department"]),
                solution_name=review["solution_name"],
                reviewers=[Department(item) for item in review.get("reviewers", [])],
                decision=review["decision"],
                concerns=review.get("concerns", []),
                action_items=review.get("action_items", []),
                participant_profiles=review.get("participant_profiles", []),
                discussion_log=review.get("discussion_log", []),
            )
            for review in data.get("roundtable_reviews", [])
        ],
        selected_solutions={
            Department(department): deserialize_department_solution(solution)
            for department, solution in data.get("selected_solutions", {}).items()
        },
        board_decision=BoardDecision(**data["board_decision"]),
        scorecard=PlanScorecard(**data["scorecard"]) if data.get("scorecard") else None,
        interventions=[
            UserIntervention(
                stage=Stage(item["stage"]),
                speaker=item["speaker"],
                message=item["message"],
                impact=item["impact"],
            )
            for item in data.get("interventions", [])
        ],
    )


class ProjectStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class ConversationTurn:
    turn_id: str
    agent: str
    user_message: str
    assistant_message: str
    created_at: str
    used_llm: bool = False
    suggested_stage: str = Stage.RESEARCH.value
    suggested_impact: str = "revise downstream conclusions"
    can_promote_to_intervention: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationTurn":
        return cls(
            turn_id=data.get("turn_id", f"turn_{uuid4().hex[:12]}"),
            agent=data["agent"],
            user_message=data["user_message"],
            assistant_message=data["assistant_message"],
            created_at=data["created_at"],
            used_llm=bool(data.get("used_llm", False)),
            suggested_stage=data.get("suggested_stage", Stage.RESEARCH.value),
            suggested_impact=data.get("suggested_impact", "revise downstream conclusions"),
            can_promote_to_intervention=bool(data.get("can_promote_to_intervention", True)),
        )


STAGE_SEQUENCE = [
    Stage.INTAKE,
    Stage.RESEARCH,
    Stage.DEPARTMENT_DESIGN,
    Stage.ROUNDTABLE,
    Stage.SYNTHESIS,
    Stage.BOARD,
]

PLANNING_EXECUTION_SEQUENCE = [
    Stage.RESEARCH,
    Stage.DEPARTMENT_DESIGN,
    Stage.ROUNDTABLE,
    Stage.SYNTHESIS,
    Stage.BOARD,
]


@dataclass(slots=True)
class PlanVersion:
    version_id: str
    created_at: str
    stage: Stage
    summary: str
    markdown: str
    approved: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanVersion":
        return cls(
            version_id=data["version_id"],
            created_at=data["created_at"],
            stage=Stage(data["stage"]),
            summary=data["summary"],
            markdown=data["markdown"],
            approved=data["approved"],
        )


@dataclass(slots=True)
class ProjectRecord:
    project_id: str
    name: str
    idea: IdeaBrief
    status: ProjectStatus
    current_stage: Stage
    created_at: str
    updated_at: str
    interventions: list[UserIntervention] = field(default_factory=list)
    plans: list[PlanVersion] = field(default_factory=list)
    latest_plan: ProjectPlan | None = None
    latest_plan_markdown: str = ""
    conversations: dict[str, list[ConversationTurn]] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def create(cls, name: str, idea: IdeaBrief) -> "ProjectRecord":
        now = utc_now()
        return cls(
            project_id=f"proj_{uuid4().hex[:12]}",
            name=name,
            idea=idea,
            status=ProjectStatus.CREATED,
            current_stage=Stage.INTAKE,
            created_at=now,
            updated_at=now,
        )

    def touch(self) -> None:
        self.updated_at = utc_now()

    def next_stage_to_run(self) -> Stage | None:
        if self.current_stage == Stage.INTAKE:
            return Stage.RESEARCH
        try:
            index = PLANNING_EXECUTION_SEQUENCE.index(self.current_stage)
        except ValueError:
            return Stage.RESEARCH
        if index >= len(PLANNING_EXECUTION_SEQUENCE) - 1:
            return None
        return PLANNING_EXECUTION_SEQUENCE[index + 1]

    def register_stage_snapshot(self, plan: ProjectPlan, markdown: str, stage: Stage) -> PlanVersion:
        summary = (
            plan.board_decision.rationale
            if stage == Stage.BOARD
            else f"{stage.value.replace('_', ' ').title()} output generated"
        )
        plan_version = PlanVersion(
            version_id=f"plan_{uuid4().hex[:12]}",
            created_at=utc_now(),
            stage=stage,
            summary=summary,
            markdown=markdown,
            approved=plan.board_decision.approved if stage == Stage.BOARD else False,
        )
        self.latest_plan = plan
        self.latest_plan_markdown = markdown
        self.plans.append(plan_version)
        self.current_stage = stage
        if stage == Stage.BOARD:
            self.status = ProjectStatus.COMPLETED if plan.board_decision.approved else ProjectStatus.REVIEWING
        else:
            self.status = ProjectStatus.PLANNING
        self.touch()
        return plan_version

    def register_plan(self, plan: ProjectPlan, markdown: str) -> PlanVersion:
        return self.register_stage_snapshot(plan=plan, markdown=markdown, stage=Stage.BOARD)

    def add_intervention(self, intervention: UserIntervention) -> None:
        self.interventions.append(intervention)
        self.current_stage = intervention.stage
        self.status = ProjectStatus.REVIEWING
        self.touch()

    def get_plan_version(self, version_id: str) -> PlanVersion | None:
        for version in self.plans:
            if version.version_id == version_id:
                return version
        return None

    def append_conversation(
        self,
        agent: str,
        user_message: str,
        assistant_message: str,
        used_llm: bool,
        suggested_stage: str,
        suggested_impact: str,
        can_promote_to_intervention: bool = True,
    ) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=f"turn_{uuid4().hex[:12]}",
            agent=agent,
            user_message=user_message,
            assistant_message=assistant_message,
            created_at=utc_now(),
            used_llm=used_llm,
            suggested_stage=suggested_stage,
            suggested_impact=suggested_impact,
            can_promote_to_intervention=can_promote_to_intervention,
        )
        self.conversations.setdefault(agent, []).append(turn)
        self.touch()
        return turn

    def get_conversation(self, agent: str) -> list[ConversationTurn]:
        return self.conversations.get(agent, [])

    def find_turn(self, turn_id: str) -> ConversationTurn | None:
        for turns in self.conversations.values():
            for turn in turns:
                if turn.turn_id == turn_id:
                    return turn
        return None

    def build_stage_progress(self) -> list[dict[str, Any]]:
        current_index = STAGE_SEQUENCE.index(self.current_stage)

        result: list[dict[str, Any]] = []
        for index, stage in enumerate(STAGE_SEQUENCE):
            if index < current_index:
                status = "completed"
            elif index == current_index:
                if stage == Stage.BOARD and self.status == ProjectStatus.COMPLETED:
                    status = "completed"
                else:
                    status = "current"
            else:
                status = "pending"
            result.append(
                {
                    "stage": stage.value,
                    "label": stage.value.replace("_", " ").title(),
                    "status": status,
                }
            )
        return result

    def build_timeline(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = [
            {
                "timestamp": self.created_at,
                "type": "project_created",
                "title": "Project created",
                "detail": self.name,
            }
        ]
        for index, version in enumerate(self.plans, start=1):
            events.append(
                {
                    "timestamp": version.created_at,
                    "type": "plan_version",
                    "title": f"Plan version {index}",
                    "detail": version.summary,
                    "version_id": version.version_id,
                }
            )
        for intervention in self.interventions:
            events.append(
                {
                    "timestamp": self.updated_at,
                    "type": "intervention",
                    "title": f"Intervention at {intervention.stage.value}",
                    "detail": f"{intervention.speaker}: {intervention.message}",
                }
            )
        for agent, turns in self.conversations.items():
            for turn in turns:
                events.append(
                    {
                        "timestamp": turn.created_at,
                        "type": "chat",
                        "title": f"Chat with {agent}",
                        "detail": turn.user_message,
                        "turn_id": turn.turn_id,
                    }
                )
        events.sort(key=lambda item: item["timestamp"])
        return events

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "idea": asdict(self.idea),
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "interventions": [asdict(item) for item in self.interventions],
            "plans": [item.to_dict() for item in self.plans],
            "latest_plan": serialize_project_plan(self.latest_plan) if self.latest_plan else None,
            "latest_plan_markdown": self.latest_plan_markdown,
            "conversations": {
                agent: [turn.to_dict() for turn in turns]
                for agent, turns in self.conversations.items()
            },
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectRecord":
        latest_plan_data = data.get("latest_plan")
        latest_plan = None
        if latest_plan_data:
            latest_plan = deserialize_project_plan(latest_plan_data)
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            idea=IdeaBrief(**data["idea"]),
            status=ProjectStatus(data["status"]),
            current_stage=Stage(data["current_stage"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            interventions=[UserIntervention(stage=Stage(item["stage"]), speaker=item["speaker"], message=item["message"], impact=item["impact"]) for item in data.get("interventions", [])],
            plans=[PlanVersion.from_dict(item) for item in data.get("plans", [])],
            latest_plan=latest_plan,
            latest_plan_markdown=data.get("latest_plan_markdown", ""),
            conversations={
                agent: [ConversationTurn.from_dict(turn) for turn in turns]
                for agent, turns in data.get("conversations", {}).items()
            },
            error=data.get("error"),
        )


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    kind: str
    project_id: str
    status: TaskStatus
    created_at: str
    updated_at: str
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def create(cls, kind: str, project_id: str) -> "TaskRecord":
        now = utc_now()
        return cls(
            task_id=f"task_{uuid4().hex[:12]}",
            kind=kind,
            project_id=project_id,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.updated_at = utc_now()

    def mark_completed(self, result: dict[str, Any]) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.updated_at = utc_now()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "project_id": self.project_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        return cls(
            task_id=data["task_id"],
            kind=data["kind"],
            project_id=data["project_id"],
            status=TaskStatus(data["status"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            result=data.get("result", {}),
            error=data.get("error"),
        )