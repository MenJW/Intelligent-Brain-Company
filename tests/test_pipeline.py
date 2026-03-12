from intelligent_brain_company.domain.models import IdeaBrief
from intelligent_brain_company.services.planning import PlanningOrchestrator
from intelligent_brain_company.workflows.pipeline import DEPARTMENT_DEPENDENCIES


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
        dependency_count = sum(
            len(plan.department_solutions[department][0].artifacts.get("team_owners", []))
            for department in DEPARTMENT_DEPENDENCIES[review.department]
        )
        base_department_count = len(plan.department_solutions[review.department][0].artifacts.get("team_owners", []))
        expected_minimum = base_department_count + dependency_count

        assert len(review.participant_profiles) >= expected_minimum
        assert len(review.discussion_log) == len(review.participant_profiles)