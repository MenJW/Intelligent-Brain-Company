from __future__ import annotations

from intelligent_brain_company.agents.runtime import BoardAgent, DepartmentAgent, ResearchAgent
from intelligent_brain_company.config import AppConfig
from intelligent_brain_company.domain.models import Department, IdeaBrief, ProjectPlan, Stage, UserIntervention
from intelligent_brain_company.services.llm_client import LLMClient
from intelligent_brain_company.workflows.pipeline import CompanyPipeline


class PlanningOrchestrator:
    def __init__(self, pipeline: CompanyPipeline | None = None, config: AppConfig | None = None) -> None:
        if pipeline is not None:
            self.pipeline = pipeline
            return

        app_config = config or AppConfig.from_env()
        llm_client = LLMClient.from_config(app_config)
        department_agents = {
            department: DepartmentAgent(department=department, llm_client=llm_client)
            for department in (
                Department.HARDWARE,
                Department.SOFTWARE,
                Department.DESIGN,
                Department.MARKETING,
                Department.FINANCE,
            )
        }
        self.pipeline = CompanyPipeline(
            research_agent=ResearchAgent(llm_client=llm_client),
            board_agent=BoardAgent(llm_client=llm_client),
            department_agents=department_agents,
            llm_client=llm_client,
        )

    def build_plan(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention] | None = None,
    ) -> ProjectPlan:
        return self.pipeline.run(brief=brief, interventions=interventions)

    def build_plan_for_stage(
        self,
        brief: IdeaBrief,
        stage: Stage,
        interventions: list[UserIntervention] | None = None,
    ) -> ProjectPlan:
        return self.pipeline.run_until(brief=brief, stage=stage, interventions=interventions)

    def render_plan(self, plan: ProjectPlan) -> str:
        return self.pipeline.render_markdown(plan)

    def render_stage(self, plan: ProjectPlan, stage: Stage) -> str:
        return self.pipeline.render_stage_markdown(plan, stage)