from intelligent_brain_company.agents.contracts import parse_department_solutions
from intelligent_brain_company.domain.models import Department, DepartmentSolution


def _fallback() -> list[DepartmentSolution]:
    return [
        DepartmentSolution(
            department=Department.HARDWARE,
            name="平台方案 A",
            summary="fallback summary",
            feasibility_score=6,
            dependencies=[Department.DESIGN],
            assumptions=["fallback assumption"],
            rationale="fallback rationale",
            implementation_steps=["fallback step"],
            success_metrics=["fallback metric"],
            artifacts={"bom_targets": ["fallback bom"]},
        )
    ]


def test_parse_department_solutions_supports_nested_and_alias_keys() -> None:
    data = {
        "data": {
            "options": [
                {
                    "title": "硬件方案 Alpha",
                    "description": "核心结构重构，先验证关键负载场景",
                    "可行性评分": "7/10",
                    "依赖": "design, finance",
                    "关键假设": "供应链稳定；关键部件可替代",
                    "方案依据": "先聚焦高价值工况，降低一次性复杂度",
                    "执行步骤": "先做 2 周验证样机；再做 1 个真实场景试点",
                    "成功指标": "样机通过率>85%；单位成本不超预算",
                    "bom_targets": ["电机与控制器成本上限"],
                }
            ]
        }
    }
    parsed = parse_department_solutions(Department.HARDWARE, data, _fallback())
    assert parsed
    first = parsed[0]
    assert first.name == "硬件方案 Alpha"
    assert first.feasibility_score == 7
    assert first.dependencies
    assert first.assumptions
    assert first.implementation_steps
    assert first.success_metrics
    assert first.artifacts.get("bom_targets")
