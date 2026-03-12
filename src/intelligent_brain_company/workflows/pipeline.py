from __future__ import annotations

import re
from statistics import mean

from intelligent_brain_company.agents.registry import AgentProfile, department_teams
from intelligent_brain_company.agents.runtime import BoardAgent, DepartmentAgent, ResearchAgent
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
from intelligent_brain_company.services.llm_client import LLMClient


DEPARTMENT_DEPENDENCIES: dict[Department, list[Department]] = {
    Department.HARDWARE: [Department.DESIGN, Department.FINANCE],
    Department.SOFTWARE: [Department.HARDWARE, Department.DESIGN],
    Department.DESIGN: [Department.HARDWARE, Department.MARKETING],
    Department.MARKETING: [Department.DESIGN, Department.FINANCE],
    Department.FINANCE: [Department.HARDWARE, Department.MARKETING],
}

LLM_ENABLED_DEPARTMENTS = (
    Department.HARDWARE,
    Department.SOFTWARE,
    Department.DESIGN,
    Department.MARKETING,
    Department.FINANCE,
)


class CompanyPipeline:
    """Deterministic MVP pipeline.

    The long-term design expects each stage to be replaced by live model-backed
    agents. For now, the workflow stays deterministic so the project has a
    stable executable contract and test surface.
    """

    def __init__(
        self,
        research_agent: ResearchAgent | None = None,
        board_agent: BoardAgent | None = None,
        department_agents: dict[Department, DepartmentAgent] | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.research_agent = research_agent or ResearchAgent()
        self.board_agent = board_agent or BoardAgent()
        self.department_agents = department_agents or {}
        self.llm_client = llm_client

    def run(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention] | None = None,
    ) -> ProjectPlan:
        return self.run_until(brief=brief, stage=Stage.BOARD, interventions=interventions)

    def run_until(
        self,
        brief: IdeaBrief,
        stage: Stage,
        interventions: list[UserIntervention] | None = None,
    ) -> ProjectPlan:
        active_interventions = interventions or []
        fallback_research = self._build_default_research(brief, active_interventions)
        research = self.research_agent.analyze(brief, active_interventions, fallback_research)

        needs_department_design = stage in {Stage.DEPARTMENT_DESIGN, Stage.ROUNDTABLE, Stage.SYNTHESIS, Stage.BOARD}
        needs_roundtable = stage in {Stage.ROUNDTABLE, Stage.SYNTHESIS, Stage.BOARD}
        needs_synthesis = stage in {Stage.SYNTHESIS, Stage.BOARD}
        needs_board = stage == Stage.BOARD

        department_solutions = (
            self._generate_department_solutions(brief, active_interventions)
            if needs_department_design
            else {}
        )
        roundtable_reviews = (
            self._run_roundtables(department_solutions, active_interventions)
            if needs_roundtable
            else []
        )
        selected_solutions = self._select_solutions(department_solutions) if needs_synthesis else {}

        if needs_board:
            fallback_board = self._build_default_board_review(brief, selected_solutions, research, active_interventions)
            board_decision = self.board_agent.review(
                brief,
                research,
                selected_solutions,
                active_interventions,
                fallback_board,
            )
            scorecard = self._build_scorecard(
                brief,
                research,
                selected_solutions,
                board_decision,
                active_interventions,
            )
        else:
            board_decision = self._build_pending_board_decision(stage)
            scorecard = None

        return ProjectPlan(
            idea=brief,
            research=research,
            department_solutions=department_solutions,
            roundtable_reviews=roundtable_reviews,
            selected_solutions=selected_solutions,
            board_decision=board_decision,
            scorecard=scorecard,
            interventions=active_interventions,
        )

    def _build_pending_board_decision(self, stage: Stage) -> BoardDecision:
        return BoardDecision(
            approved=False,
            development_difficulty="pending",
            budget_outlook="pending",
            funding_cycle="pending",
            rationale=f"Board decision is pending until board stage. Current stage: {stage.value}.",
            conditions=[],
        )

    def render_markdown(self, plan: ProjectPlan) -> str:
        lines: list[str] = []
        lines.append(f"# Project Plan: {plan.idea.title}")
        lines.append("")
        if plan.scorecard:
            lines.append("## Executive Verdict")
            lines.append("")
            lines.append(f"- Recommendation: {plan.scorecard.recommendation}")
            lines.append(f"- Summary: {plan.scorecard.summary}")
            lines.append("- Scorecard:")
            lines.append(f"  - Market demand: {plan.scorecard.market_demand}/10")
            lines.append(f"  - Technical feasibility: {plan.scorecard.technical_feasibility}/10")
            lines.append(f"  - Execution complexity: {plan.scorecard.execution_complexity}/10 (lower is easier)")
            lines.append(f"  - Time to MVP: {plan.scorecard.time_to_mvp}/10")
            lines.append(f"  - Monetization potential: {plan.scorecard.monetization_potential}/10")
            lines.append("")
        lines.append("## Research Assessment")
        lines.append("")
        lines.append(f"- Customer segments: {', '.join(plan.research.customer_segments)}")
        lines.append(f"- Market view: {plan.research.market_size_view}")
        lines.append(f"- Competition: {plan.research.competitive_landscape}")
        lines.append(f"- Recommendation: {plan.research.recommendation}")
        lines.append("")
        lines.append("## Selected Department Solutions")
        lines.append("")
        for department, solution in plan.selected_solutions.items():
            lines.append(f"### {department.value.title()}")
            lines.append("")
            lines.append(f"- Solution: {solution.name}")
            lines.append(f"- Summary: {solution.summary}")
            lines.append(f"- Feasibility score: {solution.feasibility_score}/10")
            if solution.assumptions:
                lines.append(f"- Assumptions: {'; '.join(solution.assumptions)}")
            if solution.rationale:
                lines.append(f"- Rationale: {solution.rationale}")
            if solution.success_metrics:
                lines.append(f"- Success metrics: {'; '.join(solution.success_metrics)}")
            if solution.artifacts:
                for key, value in solution.artifacts.items():
                    if isinstance(value, list):
                        rendered = '; '.join(str(item) for item in value)
                    else:
                        rendered = str(value)
                    lines.append(f"- {key.replace('_', ' ').title()}: {rendered}")
            lines.append("")
        lines.append("## Cross-Department Roundtable Discussions")
        lines.append("")
        for review in plan.roundtable_reviews:
            lines.append(f"### {review.department.value.title()} - {review.solution_name}")
            lines.append("")
            lines.append(f"- Decision: {review.decision}")
            if review.reviewers:
                lines.append(f"- Reviewing departments: {', '.join(item.value for item in review.reviewers)}")
            if review.participant_profiles:
                lines.append("- Participants:")
                for member in review.participant_profiles:
                    focus = ", ".join(str(item) for item in member.get("capability_focus", []))
                    lines.append(
                        "  - "
                        f"{member.get('name')} ({member.get('title')}, {member.get('department')}) | "
                        f"personality: {member.get('personality')} | focus: {focus}"
                    )
            if review.discussion_log:
                lines.append("- Discussion log:")
                for turn in review.discussion_log:
                    lines.append(f"  - {turn}")
            if review.concerns:
                lines.append(f"- Concerns: {'; '.join(review.concerns)}")
            if review.action_items:
                lines.append(f"- Action items: {'; '.join(review.action_items)}")
            lines.append("")
        lines.append("## Board Decision")
        lines.append("")
        lines.append(f"- Approved: {'yes' if plan.board_decision.approved else 'no'}")
        lines.append(f"- Difficulty: {plan.board_decision.development_difficulty}")
        lines.append(f"- Budget outlook: {plan.board_decision.budget_outlook}")
        lines.append(f"- Funding cycle: {plan.board_decision.funding_cycle}")
        lines.append(f"- Rationale: {plan.board_decision.rationale}")
        if plan.board_decision.conditions:
            lines.append(f"- Conditions: {'; '.join(plan.board_decision.conditions)}")
        if plan.interventions:
            lines.append("")
            lines.append("## Recorded User Interventions")
            lines.append("")
            for intervention in plan.interventions:
                lines.append(
                    f"- {intervention.stage.value}: {intervention.speaker} said '{intervention.message}' and expected '{intervention.impact}'."
                )
        return "\n".join(lines)

    def render_stage_markdown(self, plan: ProjectPlan, stage: Stage) -> str:
        if stage == Stage.RESEARCH:
            lines = [
                f"# Stage Output: {stage.value}",
                "",
                "## Research Assessment",
                "",
                f"- Customer segments: {', '.join(plan.research.customer_segments)}",
                f"- Market view: {plan.research.market_size_view}",
                f"- Competition: {plan.research.competitive_landscape}",
                f"- Key risks: {'; '.join(plan.research.key_risks)}",
                f"- Recommendation: {plan.research.recommendation}",
            ]
            return "\n".join(lines)

        if stage == Stage.DEPARTMENT_DESIGN:
            lines = [
                f"# Stage Output: {stage.value}",
                "",
                "## Department Discussions",
                "",
            ]
            for department, solutions in plan.department_solutions.items():
                lines.append(f"### {department.value.title()}")
                owners = solutions[0].artifacts.get("team_owners", []) if solutions else []
                if owners:
                    lines.append(f"- Team: {'; '.join(str(item) for item in owners)}")
                for solution in solutions:
                    lines.append(
                        f"- {solution.name}: {solution.summary} (score {solution.feasibility_score}/10)"
                    )
                lines.append("")
            return "\n".join(lines)

        if stage == Stage.ROUNDTABLE:
            lines = [
                f"# Stage Output: {stage.value}",
                "",
                "## Cross-Department Roundtable",
                "",
            ]
            for review in plan.roundtable_reviews:
                lines.append(f"### {review.department.value.title()} - {review.solution_name}")
                lines.append(f"- Decision: {review.decision}")
                if review.participant_profiles:
                    lines.append(
                        f"- Responding participants: {', '.join(str(item.get('name')) for item in review.participant_profiles)}"
                    )
                if review.discussion_log:
                    lines.append("- Discussion:")
                    for turn in review.discussion_log:
                        lines.append(f"  - {turn}")
                lines.append("")
            return "\n".join(lines)

        if stage == Stage.SYNTHESIS:
            lines = [
                f"# Stage Output: {stage.value}",
                "",
                "## Selected Solution Synthesis",
                "",
            ]
            for department, solution in plan.selected_solutions.items():
                lines.append(f"- {department.value}: {solution.name} | {solution.summary}")
            return "\n".join(lines)

        if stage == Stage.BOARD:
            lines = [
                f"# Stage Output: {stage.value}",
                "",
                "## Board Decision",
                "",
                f"- Approved: {'yes' if plan.board_decision.approved else 'no'}",
                f"- Difficulty: {plan.board_decision.development_difficulty}",
                f"- Budget outlook: {plan.board_decision.budget_outlook}",
                f"- Funding cycle: {plan.board_decision.funding_cycle}",
                f"- Rationale: {plan.board_decision.rationale}",
                f"- Conditions: {'; '.join(plan.board_decision.conditions)}",
                "",
                "## Scorecard",
                "",
                f"- Recommendation: {plan.scorecard.recommendation if plan.scorecard else 'N/A'}",
                f"- Summary: {plan.scorecard.summary if plan.scorecard else 'N/A'}",
            ]
            return "\n".join(lines)

        return self.render_markdown(plan)

    def _build_default_research(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention],
    ) -> ResearchAssessment:
        constraints = self._constraint_text(brief, interventions)
        customer_segments = [
            "price-sensitive early adopters",
            "small business operators",
            "regional distributors or service providers",
        ]
        if "consumer" in brief.title.lower() or "user" in brief.summary.lower():
            customer_segments.insert(0, "mainstream consumer buyers")

        recommendation = "Proceed to departmental planning with targeted validation of pricing, regulation, and supply chain assumptions."
        return ResearchAssessment(
            customer_segments=customer_segments,
            market_size_view=f"Promising niche-to-mainstream opportunity if the team can satisfy these constraints: {constraints}.",
            competitive_landscape="Expect fragmented incumbents, cheaper low-end substitutes, and a few premium competitors with stronger branding.",
            key_risks=[
                "Weak demand validation can create false optimism.",
                "Regulatory or certification constraints may slow launch.",
                "Cost structure may drift if early architecture choices are not disciplined.",
            ],
            recommendation=recommendation,
        )

    def _generate_department_solutions(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention],
    ) -> dict[Department, list[DepartmentSolution]]:
        teams = department_teams()
        context = self._constraint_text(brief, interventions)
        fallback_solutions = {
            Department.HARDWARE: self._build_solution_set(
                department=Department.HARDWARE,
                base_name="Platform",
                base_summary=f"Physical architecture for {brief.title} optimized around {context}",
                assumptions=["Core components remain available through two suppliers.", "Prototype cycles can be completed in under 12 weeks."],
                base_score=8,
            ),
            Department.SOFTWARE: self._build_solution_set(
                department=Department.SOFTWARE,
                base_name="Control Stack",
                base_summary=f"Digital control and service layer supporting {brief.title}",
                assumptions=["Telemetry is optional in the first release.", "Core control logic can be isolated from user-facing software."],
                base_score=7,
            ),
            Department.DESIGN: self._build_solution_set(
                department=Department.DESIGN,
                base_name="Experience Concept",
                base_summary=f"Interaction and product form decisions aligned to {brief.title}",
                assumptions=["User comfort and trust can outweigh feature count.", "The first release should prioritize clarity over novelty."],
                base_score=8,
            ),
            Department.MARKETING: self._build_solution_set(
                department=Department.MARKETING,
                base_name="Go-To-Market",
                base_summary=f"Demand creation and channel strategy for {brief.title}",
                assumptions=["A clear wedge market exists.", "Partnership channels can outperform pure paid acquisition early."],
                base_score=7,
            ),
            Department.FINANCE: self._build_solution_set(
                department=Department.FINANCE,
                base_name="Capital Plan",
                base_summary=f"Budget, pricing, and funding structure for {brief.title}",
                assumptions=["Unit economics improve after the pilot batch.", "Working capital is the main early financial constraint."],
                base_score=8,
            ),
        }
        resolved: dict[Department, list[DepartmentSolution]] = {}
        for department, solutions in fallback_solutions.items():
            team_members = teams.get(department, ())
            enriched_fallback = [
                DepartmentSolution(
                    department=solution.department,
                    name=solution.name,
                    summary=solution.summary,
                    feasibility_score=solution.feasibility_score,
                    dependencies=list(solution.dependencies),
                    assumptions=list(solution.assumptions),
                    rationale=solution.rationale,
                    implementation_steps=list(solution.implementation_steps),
                    success_metrics=list(solution.success_metrics),
                    artifacts={
                        **solution.artifacts,
                        "team_owners": [
                            f"{member.name} ({member.title})"
                            for member in team_members
                        ],
                    },
                )
                for solution in solutions
            ]
            agent = self.department_agents.get(department)
            resolved[department] = (
                agent.plan(brief, interventions, enriched_fallback, team_members)
                if agent
                else enriched_fallback
            )
        return resolved

    def _build_solution_set(
        self,
        department: Department,
        base_name: str,
        base_summary: str,
        assumptions: list[str],
        base_score: int,
    ) -> list[DepartmentSolution]:
        solutions: list[DepartmentSolution] = []
        patterns = (
            ("A", "balanced and execution-focused", 0),
            ("B", "lower-cost and easier to launch", -1),
            ("C", "higher-upside and more differentiated", 1),
        )
        for suffix, variant, delta in patterns:
            artifacts = self._default_artifacts_for_department(department, suffix)
            solutions.append(
                DepartmentSolution(
                    department=department,
                    name=f"{base_name} {suffix}",
                    summary=f"{base_summary}; variant is {variant}.",
                    feasibility_score=max(1, min(10, base_score + delta)),
                    dependencies=DEPARTMENT_DEPENDENCIES.get(department, []),
                    assumptions=assumptions,
                    rationale=f"{department.value.title()} option {suffix} balances the current constraint set against execution risk.",
                    implementation_steps=[
                        "Clarify assumptions with cross-functional stakeholders.",
                        "Build a limited-scope pilot.",
                        "Measure operational performance before scale-up.",
                    ],
                    success_metrics=[
                        "Pilot milestones hit on time.",
                        "Cost envelope remains within target.",
                    ],
                    artifacts=artifacts,
                )
            )
        return solutions

    def _default_artifacts_for_department(self, department: Department, suffix: str) -> dict[str, object]:
        if department == Department.HARDWARE:
            return {
                "bom_targets": [f"core powertrain tier {suffix}", "frame and chassis cost guardrail", "battery pack sourcing envelope"],
                "manufacturing_notes": ["prototype with modular assembly", "keep tooling low for pilot run"],
                "certification_path": "validate local compliance before volume tooling",
                "supply_chain_risks": ["battery lead time", "motor controller dual sourcing"],
            }
        if department == Department.SOFTWARE:
            return {
                "interface_boundaries": ["vehicle control API", "telemetry ingestion API", "operator app service boundary"],
                "system_components": ["embedded controller", "fleet service", "operator dashboard"],
                "data_flows": ["vehicle to telemetry", "dashboard to diagnostics", "operator app to alerts"],
                "operational_risks": ["firmware upgrade rollback", "weak offline mode"],
            }
        if department == Department.DESIGN:
            return {
                "design_constraints": ["easy ingress and egress", "tool-free service access", "high visual trust"],
                "ergonomic_targets": ["reduced lifting strain", "clear control reach"],
                "safety_cues": ["visible braking intent", "battery status visibility"],
                "serviceability_rules": ["replaceable outer panels", "fast battery access"],
            }
        if department == Department.MARKETING:
            return {
                "channel_budget": ["dealer enablement 40%", "field demos 35%", "digital acquisition 25%"],
                "wedge_segments": ["local merchants", "last-mile service fleets"],
                "launch_narrative": "lower operating cost with practical reliability",
                "partnership_plan": ["regional dealers", "battery service partners"],
            }
        if department == Department.FINANCE:
            return {
                "capital_envelope": ["prototype budget cap", "pilot batch reserve", "working capital buffer"],
                "pricing_logic": "target rapid payback for small fleet operators",
                "unit_economics": ["gross margin after pilot", "service revenue attachment"],
                "downside_controls": ["stage-gated spend", "supplier payment controls"],
            }
        return {}

    def _run_roundtables(
        self,
        department_solutions: dict[Department, list[DepartmentSolution]],
        interventions: list[UserIntervention],
    ) -> list[RoundtableReview]:
        teams = department_teams()
        reviews: list[RoundtableReview] = []
        for department, solutions in department_solutions.items():
            for solution in solutions:
                concerns = [
                    "Validate upstream dependencies before locking architecture.",
                    "Ensure assumptions remain compatible with target launch timing.",
                ]
                if self._has_stage_intervention(interventions, Stage.ROUNDTABLE):
                    concerns.append("User intervention requires explicit revalidation of tradeoffs.")
                all_participants = self._build_participant_profiles(teams, self._solution_team_departments(solution))
                participant_profiles = self._select_relevant_participants(solution, all_participants)
                discussion_log = self._build_roundtable_discussion(solution, participant_profiles)
                reviews.append(
                    RoundtableReview(
                        department=department,
                        solution_name=solution.name,
                        reviewers=solution.dependencies,
                        decision="advance with revisions" if solution.feasibility_score < 8 else "advance",
                        concerns=concerns,
                        action_items=[
                            "Document dependency assumptions.",
                            "Quantify cost and timing impact for the board pack.",
                        ],
                        participant_profiles=participant_profiles,
                        discussion_log=discussion_log,
                    )
                )
        return reviews

    def _solution_team_departments(self, solution: DepartmentSolution) -> list[Department]:
        seen: list[Department] = [solution.department]
        for item in solution.dependencies:
            if item not in seen:
                seen.append(item)
        return seen

    def _build_participant_profiles(
        self,
        teams: dict[Department, tuple[AgentProfile, ...]],
        departments: list[Department],
    ) -> list[dict[str, object]]:
        participants: list[dict[str, object]] = []
        for department in departments:
            for member in teams.get(department, ()):
                participants.append(
                    {
                        "employee_id": member.employee_id,
                        "name": member.name,
                        "title": member.title,
                        "department": member.department.value,
                        "personality": member.personality,
                        "capability_focus": list(member.capability_focus),
                        "inspired_by": member.inspired_by,
                    }
                )
        return participants

    def _select_relevant_participants(
        self,
        solution: DepartmentSolution,
        participants: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        solution_text = self._solution_text_blob(solution)
        selected: list[dict[str, object]] = []
        for member in participants:
            member_department = str(member.get("department", ""))
            if member_department == solution.department.value:
                selected.append(member)
                continue
            if self._capability_matches_solution(solution_text, member.get("capability_focus", [])):
                selected.append(member)
        return selected

    def _solution_text_blob(self, solution: DepartmentSolution) -> str:
        parts: list[str] = [solution.name, solution.summary, solution.rationale]
        parts.extend(solution.assumptions)
        parts.extend(solution.implementation_steps)
        parts.extend(solution.success_metrics)
        parts.extend(item.value for item in solution.dependencies)
        for key, value in solution.artifacts.items():
            parts.append(str(key))
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
            else:
                parts.append(str(value))
        return " ".join(parts).lower()

    def _capability_matches_solution(self, solution_text: str, capability_focus: object) -> bool:
        if not isinstance(capability_focus, list):
            return False
        stop_words = {
            "and",
            "for",
            "with",
            "from",
            "into",
            "over",
            "under",
            "across",
            "design",
            "strategy",
            "analysis",
            "management",
        }
        for phrase in capability_focus:
            for token in re.split(r"[^a-z0-9]+", str(phrase).lower()):
                if len(token) < 5 or token in stop_words:
                    continue
                if token in solution_text:
                    return True
        return False

    def _build_roundtable_discussion(
        self,
        solution: DepartmentSolution,
        participants: list[dict[str, object]],
    ) -> list[str]:
        lines: list[str] = []
        if not participants:
            return lines
        focus_area = solution.success_metrics[0] if solution.success_metrics else "delivery reliability"
        for member in participants:
            generated = self._build_roundtable_line_with_llm(solution, member, focus_area)
            if generated:
                lines.append(generated)
                continue
            lines.append(self._build_roundtable_line_fallback(solution, member, focus_area))
        return lines

    def _build_roundtable_line_with_llm(
        self,
        solution: DepartmentSolution,
        member: dict[str, object],
        focus_area: str,
    ) -> str | None:
        if self.llm_client is None:
            return None

        system_prompt = (
            "You are a single employee in a cross-functional roundtable. "
            "Return strict JSON with key: statement. "
            "Write exactly one concise statement in English, practical and specific."
        )
        user_prompt = (
            f"Employee name: {member.get('name')}\n"
            f"Employee title: {member.get('title')}\n"
            f"Employee department: {member.get('department')}\n"
            f"Employee personality: {member.get('personality')}\n"
            f"Employee focus areas: {', '.join(str(item) for item in member.get('capability_focus', []))}\n"
            f"Solution department: {solution.department.value}\n"
            f"Solution name: {solution.name}\n"
            f"Solution summary: {solution.summary}\n"
            f"Solution dependencies: {', '.join(item.value for item in solution.dependencies) or 'none'}\n"
            f"Roundtable focus to preserve: {focus_area}\n"
            "The statement should reflect this employee's personality and role, include one concrete concern "
            "or recommendation, and reference the solution context."
        )
        data = self.llm_client.generate_json(system_prompt, user_prompt, temperature=0.5)
        if not data:
            return None
        text = str(data.get("statement", "")).strip()
        if not text:
            return None
        return f"{member.get('name')} ({member.get('title')}) said: {text}"

    def _build_roundtable_line_fallback(
        self,
        solution: DepartmentSolution,
        member: dict[str, object],
        focus_area: str,
    ) -> str:
        focus_list = [str(item) for item in member.get("capability_focus", [])]
        primary_focus = focus_list[0] if focus_list else "cross-functional risk checks"
        return (
            f"{member.get('name')} ({member.get('title')}) raised {primary_focus} implications for "
            f"{solution.name} and asked the team to preserve {focus_area}."
        )

    def _select_solutions(
        self,
        department_solutions: dict[Department, list[DepartmentSolution]],
    ) -> dict[Department, DepartmentSolution]:
        selected: dict[Department, DepartmentSolution] = {}
        for department, solutions in department_solutions.items():
            selected[department] = max(solutions, key=lambda item: item.feasibility_score)
        return selected

    def _build_default_board_review(
        self,
        brief: IdeaBrief,
        selected_solutions: dict[Department, DepartmentSolution],
        research: ResearchAssessment,
        interventions: list[UserIntervention],
    ) -> BoardDecision:
        average_score = mean(solution.feasibility_score for solution in selected_solutions.values())
        intervention_penalty = 0.5 if self._has_stage_intervention(interventions, Stage.BOARD) else 0.0
        effective_score = average_score - intervention_penalty
        approved = effective_score >= 7.5

        rationale = (
            f"The portfolio for {brief.title} shows sufficient cross-functional coherence. "
            f"Research recommendation is: {research.recommendation}"
        )
        if interventions:
            rationale += " User interventions are recorded and should stay visible in later revisions."

        return BoardDecision(
            approved=approved,
            development_difficulty="medium" if effective_score >= 8 else "medium-high",
            budget_outlook="manageable with phased delivery" if effective_score >= 7.5 else "sensitive to scope drift",
            funding_cycle="pilot funding then milestone-based expansion",
            rationale=rationale,
            conditions=[
                "Keep scope narrow for the first release.",
                "Validate demand before committing to large capital outlays.",
                "Track user interventions as formal change requests.",
            ],
        )

    def _build_scorecard(
        self,
        brief: IdeaBrief,
        research: ResearchAssessment,
        selected_solutions: dict[Department, DepartmentSolution],
        board_decision: BoardDecision,
        interventions: list[UserIntervention],
    ) -> PlanScorecard:
        average_score = mean(solution.feasibility_score for solution in selected_solutions.values())
        intervention_penalty = min(2, len(interventions))
        risk_penalty = min(2, len(research.key_risks) // 2)
        constraint_bonus = 1 if brief.user_constraints else 0

        market_demand = max(1, min(10, round(7 + constraint_bonus - risk_penalty)))
        technical_feasibility = max(1, min(10, round(average_score)))
        execution_complexity = max(1, min(10, round(11 - average_score + intervention_penalty)))
        time_to_mvp = max(1, min(10, round(average_score - intervention_penalty + 1)))
        monetization_potential = max(1, min(10, round((market_demand + selected_solutions[Department.MARKETING].feasibility_score + selected_solutions[Department.FINANCE].feasibility_score) / 3)))

        weighted_score = (
            market_demand * 0.25
            + technical_feasibility * 0.25
            + (11 - execution_complexity) * 0.2
            + time_to_mvp * 0.15
            + monetization_potential * 0.15
        )
        if weighted_score >= 7.5 and board_decision.approved:
            recommendation = "Go"
        elif weighted_score >= 6.2:
            recommendation = "Maybe"
        else:
            recommendation = "No-Go"

        summary = (
            f"{brief.title} currently reads as {recommendation.lower()} because demand and cross-functional feasibility are "
            f"{'strong' if weighted_score >= 7.5 else 'mixed' if weighted_score >= 6.2 else 'weak'}, "
            f"while board conditions remain {board_decision.budget_outlook}."
        )
        return PlanScorecard(
            market_demand=market_demand,
            technical_feasibility=technical_feasibility,
            execution_complexity=execution_complexity,
            time_to_mvp=time_to_mvp,
            monetization_potential=monetization_potential,
            recommendation=recommendation,
            summary=summary,
        )

    def _constraint_text(self, brief: IdeaBrief, interventions: list[UserIntervention]) -> str:
        parts: list[str] = []
        if brief.user_constraints:
            parts.extend(brief.user_constraints)
        parts.extend(intervention.impact for intervention in interventions)
        return ", ".join(parts) if parts else "speed, cost discipline, and market fit"

    def _has_stage_intervention(self, interventions: list[UserIntervention], stage: Stage) -> bool:
        return any(intervention.stage == stage for intervention in interventions)