from __future__ import annotations

from dataclasses import dataclass
import json
import re
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


def _coerce_text_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parts = [item.strip().lstrip("- ") for item in text.replace("\r", "\n").replace(";", "\n").replace("；", "\n").split("\n")]
        parsed = [item for item in parts if item]
        return parsed or [text]
    return []


def _coerce_dependencies(value: Any) -> list[Department]:
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    elif isinstance(value, str):
        raw_items = [item.strip() for item in value.replace("；", ",").replace(";", ",").split(",") if item.strip()]
    else:
        return []

    result: list[Department] = []
    for item in raw_items:
        try:
            result.append(Department(str(item)))
        except ValueError:
            continue
    return result


_DEPARTMENT_ALIAS = {
    "hardware": "hardware",
    "硬件": "hardware",
    "software": "software",
    "软件": "software",
    "design": "design",
    "设计": "design",
    "marketing": "marketing",
    "市场": "marketing",
    "营销": "marketing",
    "finance": "finance",
    "财务": "finance",
    "research": "research",
    "研究": "research",
}


def _as_json_object(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _normalize_score(value: Any, default: int) -> int:
    if isinstance(value, (int, float)):
        return max(1, min(10, int(value)))
    text = str(value or "").strip()
    if not text:
        return default
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return default
    try:
        return max(1, min(10, int(float(match.group(0)))))
    except ValueError:
        return default


def _extract_solutions_container(data: Any, department: Department, depth: int = 0) -> list[Any]:
    if depth > 4:
        return []
    payload = _as_json_object(data)

    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    # direct candidates
    for key in ("solutions", "options", "plans", "items"):
        if key in payload:
            return _extract_solutions_container(payload[key], department, depth + 1)

    # department keyed map
    for dept_key, dept_value in payload.items():
        normalized = _DEPARTMENT_ALIAS.get(str(dept_key).strip().lower())
        if normalized == department.value:
            return _extract_solutions_container(dept_value, department, depth + 1)

    # wrapper candidates
    for key in ("data", "result", "output", "response", "content"):
        if key in payload:
            nested = _extract_solutions_container(payload[key], department, depth + 1)
            if nested:
                return nested

    # dict of named solutions
    if payload and all(isinstance(item, dict) for item in payload.values()):
        return list(payload.values())

    return []


def _pick(raw: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return default


def parse_department_solutions(
    department: Department,
    data: dict[str, Any],
    fallback: list[DepartmentSolution],
) -> list[DepartmentSolution]:
    raw_solutions = _extract_solutions_container(data, department)
    if not raw_solutions:
        return fallback

    parsed: list[DepartmentSolution] = []
    for raw in raw_solutions[: DEPARTMENT_CONTRACTS[department].solution_count]:
        try:
            if isinstance(raw, str):
                raw = _as_json_object(raw)
            if not isinstance(raw, dict):
                continue
            raw_artifacts = raw.get("artifacts", {}) if isinstance(raw, dict) else {}
            if not isinstance(raw_artifacts, dict):
                raw_artifacts = {}
            fallback_solution = fallback[len(parsed)] if len(parsed) < len(fallback) else fallback[-1]

            # accept artifact keys both nested and top-level
            merged_artifacts = dict(raw_artifacts)
            for key in DEPARTMENT_CONTRACTS[department].artifact_keys:
                if key not in merged_artifacts and key in raw:
                    merged_artifacts[key] = raw[key]

            parsed.append(
                DepartmentSolution(
                    department=department,
                    name=str(_pick(raw, "name", "title", "方案名", "方案", default=fallback_solution.name)),
                    summary=str(_pick(raw, "summary", "description", "desc", "方案描述", default=fallback_solution.summary)),
                    feasibility_score=_normalize_score(
                        _pick(raw, "feasibility_score", "score", "feasibility", "可行性", "可行性评分", default=fallback_solution.feasibility_score),
                        fallback_solution.feasibility_score,
                    ),
                    dependencies=_coerce_dependencies(_pick(raw, "dependencies", "depends_on", "依赖", default=None)) or list(fallback_solution.dependencies),
                    assumptions=_coerce_text_list(_pick(raw, "assumptions", "hypotheses", "关键假设", default=None)) or list(fallback_solution.assumptions),
                    rationale=str(_pick(raw, "rationale", "reason", "依据", "方案依据", default=fallback_solution.rationale)),
                    implementation_steps=_coerce_text_list(_pick(raw, "implementation_steps", "steps", "执行步骤", "行动项", default=None)) or list(fallback_solution.implementation_steps),
                    success_metrics=_coerce_text_list(_pick(raw, "success_metrics", "metrics", "成功指标", default=None)) or list(fallback_solution.success_metrics),
                    artifacts={
                        key: (merged_artifacts.get(key) if merged_artifacts.get(key) is not None else fallback_solution.artifacts.get(key))
                        for key in DEPARTMENT_CONTRACTS[department].artifact_keys
                    },
                )
            )
        except (TypeError, ValueError):
            continue

    if not parsed:
        return fallback

    while len(parsed) < DEPARTMENT_CONTRACTS[department].solution_count and len(parsed) < len(fallback):
        parsed.append(fallback[len(parsed)])

    return parsed