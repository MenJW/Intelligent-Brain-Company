from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Department(str, Enum):
    RESEARCH = "research"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    DESIGN = "design"
    MARKETING = "marketing"
    FINANCE = "finance"


class Stage(str, Enum):
    INTAKE = "intake"
    RESEARCH = "research"
    DEPARTMENT_DESIGN = "department_design"
    ROUNDTABLE = "roundtable"
    SYNTHESIS = "synthesis"
    BOARD = "board"


@dataclass(slots=True)
class IdeaBrief:
    title: str
    summary: str = ""
    user_constraints: list[str] = field(default_factory=list)
    success_metrics: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UserIntervention:
    stage: Stage
    speaker: str
    message: str
    impact: str


@dataclass(slots=True)
class ResearchAssessment:
    customer_segments: list[str]
    market_size_view: str
    competitive_landscape: str
    key_risks: list[str]
    recommendation: str


@dataclass(slots=True)
class DepartmentSolution:
    department: Department
    name: str
    summary: str
    feasibility_score: int
    dependencies: list[Department] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    rationale: str = ""
    implementation_steps: list[str] = field(default_factory=list)
    success_metrics: list[str] = field(default_factory=list)
    artifacts: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RoundtableReview:
    department: Department
    solution_name: str
    reviewers: list[Department]
    decision: str
    concerns: list[str]
    action_items: list[str]


@dataclass(slots=True)
class BoardDecision:
    approved: bool
    development_difficulty: str
    budget_outlook: str
    funding_cycle: str
    rationale: str
    conditions: list[str]


@dataclass(slots=True)
class ProjectPlan:
    idea: IdeaBrief
    research: ResearchAssessment
    department_solutions: dict[Department, list[DepartmentSolution]]
    roundtable_reviews: list[RoundtableReview]
    selected_solutions: dict[Department, DepartmentSolution]
    board_decision: BoardDecision
    interventions: list[UserIntervention] = field(default_factory=list)