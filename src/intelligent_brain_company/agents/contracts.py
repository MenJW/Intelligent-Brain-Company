from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligent_brain_company.domain.models import Department, DepartmentSolution


@dataclass(frozen=True, slots=True)
class DepartmentContract:
    department: Department
    focus: str
    prompt_template: str
    artifact_keys: tuple[str, ...]
    solution_count: int = 3

    @property
    def json_schema_note(self) -> str:
        artifact_text = ", ".join(self.artifact_keys)
        return (
            "Return JSON with key 'solutions'. Each solution must include: "
            "name, summary, feasibility_score, dependencies, assumptions, rationale, implementation_steps, success_metrics, artifacts. "
            f"Inside artifacts include these keys: {artifact_text}."
        )


DEPARTMENT_CONTRACTS: dict[Department, DepartmentContract] = {
    Department.HARDWARE: DepartmentContract(
        department=Department.HARDWARE,
        focus="physical architecture, supply chain, manufacturability, certification, reliability",
        prompt_template=(
            "Design hardware paths for a new product. Emphasize BOM structure, manufacturability, certification, "
            "spare parts strategy, and prototype risk."
        ),
        artifact_keys=("bom_targets", "manufacturing_notes", "certification_path", "supply_chain_risks", "team_owners"),
    ),
    Department.SOFTWARE: DepartmentContract(
        department=Department.SOFTWARE,
        focus="embedded logic, control stack, apps, telemetry, integration risk, maintainability",
        prompt_template=(
            "Design software options with clear service boundaries, interface contracts, control stack responsibilities, "
            "data flow, and operational risk."
        ),
        artifact_keys=("interface_boundaries", "system_components", "data_flows", "operational_risks", "team_owners"),
    ),
    Department.DESIGN: DepartmentContract(
        department=Department.DESIGN,
        focus="industrial design, user flow, safety cues, ergonomics, serviceability",
        prompt_template=(
            "Design product and experience directions that explicitly list design constraints, ergonomic goals, "
            "serviceability rules, and safety cues."
        ),
        artifact_keys=("design_constraints", "ergonomic_targets", "safety_cues", "serviceability_rules", "team_owners"),
    ),
    Department.MARKETING: DepartmentContract(
        department=Department.MARKETING,
        focus="positioning, wedge market, launch narrative, channels, conversion economics",
        prompt_template=(
            "Design go-to-market options with wedge segments, channel budget splits, launch narrative, partnership plan, "
            "and conversion assumptions."
        ),
        artifact_keys=("channel_budget", "wedge_segments", "launch_narrative", "partnership_plan", "team_owners"),
    ),
    Department.FINANCE: DepartmentContract(
        department=Department.FINANCE,
        focus="capital envelope, pricing, unit economics, cash cycle, risk containment",
        prompt_template=(
            "Design finance options with capital envelope, pricing logic, unit economics assumptions, funding sequence, "
            "and downside controls."
        ),
        artifact_keys=("capital_envelope", "pricing_logic", "unit_economics", "downside_controls", "team_owners"),
    ),
}


def department_contract_prompt(department: Department) -> str:
    contract = DEPARTMENT_CONTRACTS[department]
    return (
        f"You lead the {department.value} department. Focus on {contract.focus}. "
        f"{contract.prompt_template} Generate exactly {contract.solution_count} viable options. {contract.json_schema_note}"
    )


def parse_department_solutions(
    department: Department,
    data: dict[str, Any],
    fallback: list[DepartmentSolution],
) -> list[DepartmentSolution]:
    try:
        raw_solutions = list(data["solutions"])
    except (KeyError, TypeError, ValueError):
        return fallback

    parsed: list[DepartmentSolution] = []
    for raw in raw_solutions[: DEPARTMENT_CONTRACTS[department].solution_count]:
        try:
            parsed.append(
                DepartmentSolution(
                    department=department,
                    name=str(raw["name"]),
                    summary=str(raw["summary"]),
                    feasibility_score=max(1, min(10, int(raw["feasibility_score"]))),
                    dependencies=[Department(item) for item in raw.get("dependencies", [])],
                    assumptions=[str(item) for item in raw.get("assumptions", [])],
                    rationale=str(raw.get("rationale", "")),
                    implementation_steps=[str(item) for item in raw.get("implementation_steps", [])],
                    success_metrics=[str(item) for item in raw.get("success_metrics", [])],
                    artifacts={key: raw.get("artifacts", {}).get(key) for key in DEPARTMENT_CONTRACTS[department].artifact_keys},
                )
            )
        except (KeyError, TypeError, ValueError):
            return fallback
    return parsed or fallback