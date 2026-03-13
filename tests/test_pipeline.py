import pytest

from intelligent_brain_company.domain.models import IdeaBrief
from intelligent_brain_company.services.planning import PlanningOrchestrator
from intelligent_brain_company.workflows.pipeline import DEPARTMENT_DEPENDENCIES


@pytest.fixture(autouse=True)
def disable_llm_env(monkeypatch):
    monkeypatch.setenv("IBC_LLM_API_KEY", "")
    monkeypatch.setenv("IBC_LLM_BASE_URL", "")
    monkeypatch.setenv("IBC_LLM_MODEL", "")


class _RoundtableLLMStub:
    def generate_json(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2):
        marker = "Employee name: "
        if marker not in user_prompt:
            return None
        name = user_prompt.split(marker, 1)[1].split("\n", 1)[0].strip()
        return {"statement": f"{name} proposes a unique dependency mitigation checklist."}


class _RoundtableLLMNoneStub:
    def generate_json(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2):
        return None


def test_pipeline_generates_selected_solution_for_each_department() -> None:
    orchestrator = PlanningOrchestrator()
    plan = orchestrator.build_plan(
        IdeaBrief(
            title="Electric Tricycle",
            summary="A short-distance cargo vehicle for local merchants.",
            user_constraints=["Target affordable operations", "Fast pilot launch"],
        )
    )

    assert len(plan.selected_solutions) == 5
    assert plan.board_decision.conditions
    assert plan.scorecard is not None
    assert plan.scorecard.recommendation in {"Go", "Maybe", "No-Go"}


def test_pipeline_renders_markdown_output() -> None:
    orchestrator = PlanningOrchestrator()
    plan = orchestrator.build_plan(IdeaBrief(title="Neighborhood Delivery Robot"))
    output = orchestrator.render_plan(plan)

    assert "# Project Plan" in output
    assert "## Executive Verdict" in output
    assert "## Cross-Department Roundtable Discussions" in output
    assert "## Board Decision" in output


def test_each_department_has_3_to_5_team_members_with_named_owners() -> None:
    orchestrator = PlanningOrchestrator()
    plan = orchestrator.build_plan(IdeaBrief(title="Portable Cold Chain Box"))

    for solutions in plan.department_solutions.values():
        assert solutions
        owner_names = solutions[0].artifacts.get("team_owners")
        assert isinstance(owner_names, list)
        assert 3 <= len(owner_names) <= 5


def test_roundtable_logs_include_all_relevant_employees() -> None:
    orchestrator = PlanningOrchestrator()
    plan = orchestrator.build_plan(IdeaBrief(title="Compact Cargo EV"))

    for review in plan.roundtable_reviews:
        base_department_count = len(plan.department_solutions[review.department][0].artifacts.get("team_owners", []))
        assert len(review.participant_profiles) >= base_department_count
        assert len(review.participant_profiles) <= (
            base_department_count
            + sum(
                len(plan.department_solutions[department][0].artifacts.get("team_owners", []))
                for department in DEPARTMENT_DEPENDENCIES[review.department]
            )
        )
        assert len(review.discussion_log) == len(review.participant_profiles)


def test_roundtable_logs_use_llm_per_employee_when_available() -> None:
    orchestrator = PlanningOrchestrator()
    orchestrator.pipeline.llm_client = _RoundtableLLMStub()
    plan = orchestrator.build_plan(IdeaBrief(title="LLM Roundtable Voice"))

    for review in plan.roundtable_reviews:
        assert review.discussion_log
        for line in review.discussion_log:
            assert "said:" in line
            assert "unique dependency mitigation checklist" in line


def test_roundtable_logs_fallback_when_llm_unavailable() -> None:
    orchestrator = PlanningOrchestrator()
    orchestrator.pipeline.llm_client = _RoundtableLLMNoneStub()
    plan = orchestrator.build_plan(IdeaBrief(title="Fallback Roundtable Voice"))

    for review in plan.roundtable_reviews:
        assert review.discussion_log
        for line in review.discussion_log:
            assert "raised" in line