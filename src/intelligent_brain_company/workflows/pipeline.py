from __future__ import annotations

from statistics import mean

from intelligent_brain_company.agents.runtime import BoardAgent, DepartmentAgent, ResearchAgent
from intelligent_brain_company.domain.models import (
    BoardDecision,
    Department,
    DepartmentSolution,
    IdeaBrief,
    ProjectPlan,
    ResearchAssessment,
    RoundtableReview,
    Stage,
    UserIntervention,
)


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
    ) -> None:
        self.research_agent = research_agent or ResearchAgent()
        self.board_agent = board_agent or BoardAgent()
        self.department_agents = department_agents or {}

    def run(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention] | None = None,
    ) -> ProjectPlan:
        active_interventions = interventions or []
        fallback_research = self._build_default_research(brief, active_interventions)
        research = self.research_agent.analyze(brief, active_interventions, fallback_research)
        department_solutions = self._generate_department_solutions(brief, active_interventions)
        roundtable_reviews = self._run_roundtables(department_solutions, active_interventions)
        selected_solutions = self._select_solutions(department_solutions)
        fallback_board = self._build_default_board_review(brief, selected_solutions, research, active_interventions)
        board_decision = self.board_agent.review(
            brief,
            research,
            selected_solutions,
            active_interventions,
            fallback_board,
        )
        return ProjectPlan(
            idea=brief,
            research=research,
            department_solutions=department_solutions,
            roundtable_reviews=roundtable_reviews,
            selected_solutions=selected_solutions,
            board_decision=board_decision,
            interventions=active_interventions,
        )

    def render_markdown(self, plan: ProjectPlan) -> str:
        lines: list[str] = []
        lines.append(f"# Project Plan: {plan.idea.title}")
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
            agent = self.department_agents.get(department)
            resolved[department] = agent.plan(brief, interventions, solutions) if agent else solutions
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
        reviews: list[RoundtableReview] = []
        for department, solutions in department_solutions.items():
            for solution in solutions:
                concerns = [
                    "Validate upstream dependencies before locking architecture.",
                    "Ensure assumptions remain compatible with target launch timing.",
                ]
                if self._has_stage_intervention(interventions, Stage.ROUNDTABLE):
                    concerns.append("User intervention requires explicit revalidation of tradeoffs.")
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
                    )
                )
        return reviews

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

    def _constraint_text(self, brief: IdeaBrief, interventions: list[UserIntervention]) -> str:
        parts: list[str] = []
        if brief.user_constraints:
            parts.extend(brief.user_constraints)
        parts.extend(intervention.impact for intervention in interventions)
        return ", ".join(parts) if parts else "speed, cost discipline, and market fit"

    def _has_stage_intervention(self, interventions: list[UserIntervention], stage: Stage) -> bool:
        return any(intervention.stage == stage for intervention in interventions)