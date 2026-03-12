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


def _normalize_language(language: str | None) -> str:
    return language if language in {"zh-CN", "en-US"} else "en-US"


def _is_zh(language: str | None) -> bool:
    return _normalize_language(language) == "zh-CN"


EMPLOYEE_NAME_ZH = {
    "Maya Chen": "陈思雨",
    "David Okoro": "李承泽",
    "Amara Osei": "王安雅",
    "Luca Neri": "赵景行",
    "Noah Bennett": "周彦霖",
    "Sofia Martins": "林若彤",
    "Priya Raman": "许嘉宁",
    "Ethan Cole": "孙启航",
    "Iris Novak": "吴清妍",
    "Kenji Watanabe": "郭明远",
    "Marta Silva": "何诗妍",
    "Felix Park": "郑亦辰",
    "Elena Rossi": "沈知夏",
    "Haruto Sato": "叶子昂",
    "Amina Farouk": "唐语薇",
    "Jonas Weber": "顾闻舟",
    "Camila Duarte": "宋可欣",
    "Leah Kim": "韩以宁",
    "Mateo Alvarez": "陆泽宇",
    "Rina Takahashi": "高若琳",
    "Oliver Grant": "梁书豪",
    "Nadia Ibrahim": "冯雨桐",
    "Grace Liu": "许知微",
    "Tomas Novak": "曹景川",
    "Yuna Choi": "崔安然",
    "Marco Bellini": "彭远航",
}

CAPABILITY_FOCUS_ZH = {
    "demand signal validation": "需求信号验证",
    "trend mapping": "趋势映射",
    "market timing": "市场时机判断",
    "voice-of-customer clustering": "用户声音聚类",
    "feedback conflict resolution": "反馈冲突消解",
    "priority synthesis": "优先级综合判断",
    "assumption stress test": "假设压力测试",
    "scenario breakdown": "场景拆解",
    "risk exposure ranking": "风险暴露排序",
    "decision memo writing": "决策备忘录撰写",
    "executive summary": "高层摘要提炼",
    "narrative framing": "叙事框架构建",
    "firmware constraints": "固件约束分析",
    "board-level tradeoffs": "板级权衡决策",
    "sensor integration": "传感器集成",
    "prototype decomposition": "原型拆解",
    "build-measure loop": "构建-测量循环",
    "manufacturability precheck": "可制造性预检查",
    "stress profile design": "压力工况设计",
    "failure prediction": "故障预测",
    "uptime risk control": "在线率风险控制",
    "compliance checkpointing": "合规检查点管理",
    "release criteria": "发布准入标准",
    "evidence review": "证据审查",
    "service boundary design": "服务边界设计",
    "API contracts": "API 契约设计",
    "data consistency": "数据一致性",
    "AI feature decomposition": "AI 功能拆分",
    "model integration": "模型集成",
    "inference cost control": "推理成本控制",
    "CI/CD design": "CI/CD 流程设计",
    "release automation": "发布自动化",
    "observability baseline": "可观测性基线",
    "contract validation": "契约验证",
    "integration test strategy": "集成测试策略",
    "error-path analysis": "异常路径分析",
    "interaction architecture": "交互架构设计",
    "design system structure": "设计系统结构",
    "handoff integrity": "交付衔接完整性",
    "component library": "组件库建设",
    "visual hierarchy": "视觉层级设计",
    "interface polish": "界面打磨",
    "usability protocol": "可用性研究流程",
    "persona modeling": "用户画像建模",
    "journey insight extraction": "旅程洞察提取",
    "brand consistency": "品牌一致性",
    "positioning semantics": "定位语义",
    "identity guardrails": "品牌识别护栏",
    "emotional interaction cues": "情绪化交互线索",
    "delight moments": "愉悦时刻设计",
    "micro-experience crafting": "微体验打磨",
    "acquisition loop design": "获客闭环设计",
    "funnel diagnostics": "漏斗诊断",
    "experiment sequencing": "实验节奏编排",
    "content engine planning": "内容引擎规划",
    "message architecture": "信息架构",
    "campaign narrative": "活动叙事设计",
    "cross-platform strategy": "跨平台策略",
    "engagement loops": "互动循环机制",
    "community momentum": "社区增长动能",
    "segment intelligence": "细分市场情报",
    "competitive watch": "竞品动态监测",
    "timing recommendation": "上线时机建议",
    "listing optimization": "上架页优化",
    "store conversion uplift": "商店转化提升",
    "creative test matrix": "创意测试矩阵",
    "budget governance": "预算治理",
    "cash-flow modeling": "现金流建模",
    "cost drift tracking": "成本漂移跟踪",
    "KPI diagnostics": "KPI 诊断",
    "reporting structure": "报告结构设计",
    "variance analysis": "偏差分析",
    "regulatory compliance": "监管合规",
    "contract exposure": "合同风险暴露",
    "policy risk framing": "政策风险框定",
    "board reporting": "董事会汇报",
    "capital narrative": "资本叙事",
    "decision packet drafting": "决策材料撰写",
}

TITLE_ZH = {
    "Trend Research Lead": "趋势研究负责人",
    "Feedback Synthesis Manager": "反馈综合经理",
    "Reality Validation Specialist": "现实验证专员",
    "Executive Insight Writer": "高层洞察撰写人",
    "Embedded Systems Engineer": "嵌入式系统工程师",
    "Rapid Prototype Lead": "快速原型负责人",
    "Reliability Operations Engineer": "可靠性运维工程师",
    "Hardware QA Certifier": "硬件质量认证工程师",
    "Backend Architecture Lead": "后端架构负责人",
    "Applied AI Engineer": "应用 AI 工程师",
    "DevOps Automation Engineer": "DevOps 自动化工程师",
    "API Quality Specialist": "API 质量专家",
    "UX Architecture Director": "用户体验架构总监",
    "UI Design Lead": "界面设计负责人",
    "UX Research Specialist": "用户体验研究专员",
    "Brand Guardian": "品牌守护者",
    "Experience Delight Designer": "体验惊喜设计师",
    "Growth Strategy Lead": "增长策略负责人",
    "Content Program Manager": "内容项目经理",
    "Social Strategy Specialist": "社媒策略专家",
    "Market Pulse Analyst": "市场脉搏分析师",
    "App Growth Optimization Manager": "应用增长优化经理",
    "Finance Tracking Lead": "财务跟踪负责人",
    "Business Intelligence Analyst": "商业智能分析师",
    "Compliance and Risk Counsel": "合规与风险顾问",
    "Strategic Reporting Manager": "战略报告经理",
}


def _localize_employee_name(name: str, language: str) -> str:
    if _is_zh(language):
        return EMPLOYEE_NAME_ZH.get(name, name)
    return name


def _localize_title(title: str, language: str) -> str:
    if _is_zh(language):
        return TITLE_ZH.get(title, title)
    return title


def _localize_capability_focus_items(items: tuple[str, ...] | list[str], language: str) -> list[str]:
    normalized = [str(item) for item in items]
    if not _is_zh(language):
        return normalized
    return [CAPABILITY_FOCUS_ZH.get(item, item) for item in normalized]


def _localize_team_owner_entry(entry: str, language: str) -> str:
    if not _is_zh(language):
        return entry
    text = str(entry).strip()
    match = re.match(r"^(?P<name>.+?)\s*[(（](?P<title>.+?)[)）]\s*$", text)
    if not match:
        return _localize_employee_name(text, language)
    localized_name = _localize_employee_name(match.group("name").strip(), language)
    localized_title = _localize_title(match.group("title").strip(), language)
    return f"{localized_name}（{localized_title}）"


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
        language: str = "en-US",
    ) -> ProjectPlan:
        return self.run_until(brief=brief, stage=Stage.BOARD, interventions=interventions, language=language)

    def run_until(
        self,
        brief: IdeaBrief,
        stage: Stage,
        interventions: list[UserIntervention] | None = None,
        language: str = "en-US",
    ) -> ProjectPlan:
        resolved_language = _normalize_language(language)
        active_interventions = interventions or []
        fallback_research = self._build_default_research(brief, active_interventions, language=resolved_language)
        research = self.research_agent.analyze(brief, active_interventions, fallback_research)

        needs_department_design = stage in {Stage.DEPARTMENT_DESIGN, Stage.ROUNDTABLE, Stage.SYNTHESIS, Stage.BOARD}
        needs_roundtable = stage in {Stage.ROUNDTABLE, Stage.SYNTHESIS, Stage.BOARD}
        needs_synthesis = stage in {Stage.SYNTHESIS, Stage.BOARD}
        needs_board = stage == Stage.BOARD

        department_solutions = (
            self._generate_department_solutions(brief, active_interventions, language=resolved_language)
            if needs_department_design
            else {}
        )
        roundtable_reviews = (
            self._run_roundtables(department_solutions, active_interventions, language=resolved_language)
            if needs_roundtable
            else []
        )
        selected_solutions = self._select_solutions(department_solutions) if needs_synthesis else {}

        if needs_board:
            fallback_board = self._build_default_board_review(
                brief,
                selected_solutions,
                research,
                active_interventions,
                language=resolved_language,
            )
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
                language=resolved_language,
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

    def render_markdown(self, plan: ProjectPlan, language: str = "en-US") -> str:
        resolved_language = _normalize_language(language)
        if _is_zh(resolved_language):
            lines: list[str] = []
            lines.append(f"# 项目计划: {plan.idea.title}")
            lines.append("")
            if plan.scorecard:
                recommendation_map = {"Go": "通过", "Maybe": "观望", "No-Go": "暂缓"}
                lines.append("## 综合结论")
                lines.append("")
                lines.append(f"- 建议: {recommendation_map.get(plan.scorecard.recommendation, plan.scorecard.recommendation)}")
                lines.append(f"- 摘要: {plan.scorecard.summary}")
                lines.append("- 评分卡:")
                lines.append(f"  - 市场需求: {plan.scorecard.market_demand}/10")
                lines.append(f"  - 技术可行性: {plan.scorecard.technical_feasibility}/10")
                lines.append(f"  - 执行复杂度: {plan.scorecard.execution_complexity}/10（越低越容易）")
                lines.append(f"  - MVP 时效: {plan.scorecard.time_to_mvp}/10")
                lines.append(f"  - 商业化潜力: {plan.scorecard.monetization_potential}/10")
                lines.append("")
            lines.append("## 研究评估")
            lines.append("")
            lines.append(f"- 客户群体: {', '.join(plan.research.customer_segments)}")
            lines.append(f"- 市场判断: {plan.research.market_size_view}")
            lines.append(f"- 竞争态势: {plan.research.competitive_landscape}")
            lines.append(f"- 建议: {plan.research.recommendation}")
            lines.append("")
            lines.append("## 入选部门方案")
            lines.append("")
            for department, solution in plan.selected_solutions.items():
                lines.append(f"### {department.value}")
                lines.append("")
                lines.append(f"- 方案: {solution.name}")
                lines.append(f"- 摘要: {solution.summary}")
                lines.append(f"- 可行性评分: {solution.feasibility_score}/10")
                if solution.assumptions:
                    lines.append(f"- 关键假设: {'；'.join(solution.assumptions)}")
                if solution.rationale:
                    lines.append(f"- 方案理由: {solution.rationale}")
                if solution.success_metrics:
                    lines.append(f"- 成功指标: {'；'.join(solution.success_metrics)}")
                if solution.artifacts:
                    for key, value in solution.artifacts.items():
                        if isinstance(value, list):
                            if key == "team_owners":
                                rendered = '；'.join(_localize_team_owner_entry(str(item), resolved_language) for item in value)
                            else:
                                rendered = '；'.join(str(item) for item in value)
                        else:
                            rendered = str(value)
                        lines.append(f"- {key.replace('_', ' ').title()}: {rendered}")
                lines.append("")
            lines.append("## 跨部门圆桌讨论")
            lines.append("")
            for review in plan.roundtable_reviews:
                lines.append(f"### {review.department.value} - {review.solution_name}")
                lines.append("")
                lines.append(f"- 决策: {review.decision}")
                if review.reviewers:
                    lines.append(f"- 评审部门: {', '.join(item.value for item in review.reviewers)}")
                if review.participant_profiles:
                    lines.append("- 参会成员:")
                    for member in review.participant_profiles:
                        focus = ", ".join(str(item) for item in member.get("capability_focus", []))
                        lines.append(
                            "  - "
                            f"{member.get('name')}（{member.get('title')}，{member.get('department')}） | "
                            f"特质: {member.get('personality')} | 关注点: {focus}"
                        )
                if review.discussion_log:
                    lines.append("- 讨论记录:")
                    for turn in review.discussion_log:
                        lines.append(f"  - {turn}")
                if review.concerns:
                    lines.append(f"- 风险点: {'；'.join(review.concerns)}")
                if review.action_items:
                    lines.append(f"- 行动项: {'；'.join(review.action_items)}")
                lines.append("")
            lines.append("## 董事会决策")
            lines.append("")
            lines.append(f"- 是否通过: {'是' if plan.board_decision.approved else '否'}")
            lines.append(f"- 开发难度: {plan.board_decision.development_difficulty}")
            lines.append(f"- 预算展望: {plan.board_decision.budget_outlook}")
            lines.append(f"- 资金节奏: {plan.board_decision.funding_cycle}")
            lines.append(f"- 决策理由: {plan.board_decision.rationale}")
            if plan.board_decision.conditions:
                lines.append(f"- 附加条件: {'；'.join(plan.board_decision.conditions)}")
            if plan.interventions:
                lines.append("")
                lines.append("## 已记录的用户干预")
                lines.append("")
                for intervention in plan.interventions:
                    lines.append(
                        f"- {intervention.stage.value}: {intervention.speaker} 表示“{intervention.message}”，预期影响“{intervention.impact}”。"
                    )
            return "\n".join(lines)

        lines: list[str] = []
        lines.append(f"# {'项目计划' if _is_zh(resolved_language) else 'Project Plan'}: {plan.idea.title}")
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

    def render_stage_markdown(self, plan: ProjectPlan, stage: Stage, language: str = "en-US") -> str:
        resolved_language = _normalize_language(language)
        if stage == Stage.INTAKE:
            if _is_zh(resolved_language):
                lines = [
                    f"# 阶段输出: {stage.value}",
                    "",
                    "## Intake 需求录入",
                    "",
                    f"- 项目标题: {plan.idea.title}",
                    f"- 项目摘要: {plan.idea.summary or '暂无'}",
                    f"- 约束条件: {'；'.join(plan.idea.user_constraints) if plan.idea.user_constraints else '暂无'}",
                    f"- 成功指标: {'；'.join(plan.idea.success_metrics) if plan.idea.success_metrics else '暂无'}",
                ]
                return "\n".join(lines)
            lines = [
                f"# Stage Output: {stage.value}",
                "",
                "## Intake Brief",
                "",
                f"- Project title: {plan.idea.title}",
                f"- Summary: {plan.idea.summary or 'N/A'}",
                f"- Constraints: {'; '.join(plan.idea.user_constraints) if plan.idea.user_constraints else 'N/A'}",
                f"- Success metrics: {'; '.join(plan.idea.success_metrics) if plan.idea.success_metrics else 'N/A'}",
            ]
            return "\n".join(lines)

        if stage == Stage.RESEARCH:
            if _is_zh(resolved_language):
                lines = [
                    f"# 阶段输出: {stage.value}",
                    "",
                    "## 研究评估",
                    "",
                    f"- 客户群体: {', '.join(plan.research.customer_segments)}",
                    f"- 市场判断: {plan.research.market_size_view}",
                    f"- 竞争态势: {plan.research.competitive_landscape}",
                    f"- 关键风险: {'；'.join(plan.research.key_risks)}",
                    f"- 建议: {plan.research.recommendation}",
                ]
                return "\n".join(lines)
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
            if _is_zh(resolved_language):
                lines = [
                    f"# 阶段输出: {stage.value}",
                    "",
                    "## 部门讨论",
                    "",
                ]
                for department, solutions in plan.department_solutions.items():
                    lines.append(f"### {department.value}")
                    owners = solutions[0].artifacts.get("team_owners", []) if solutions else []
                    if owners:
                        lines.append(
                            f"- 团队: {'；'.join(_localize_team_owner_entry(str(item), resolved_language) for item in owners)}"
                        )
                    for solution in solutions:
                        lines.append(
                            f"- {solution.name}: {solution.summary}（可行性 {solution.feasibility_score}/10）"
                        )
                    lines.append("")
                return "\n".join(lines)
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
            if _is_zh(resolved_language):
                lines = [
                    f"# 阶段输出: {stage.value}",
                    "",
                    "## 跨部门圆桌评审",
                    "",
                ]
                for review in plan.roundtable_reviews:
                    lines.append(f"### {review.department.value} - {review.solution_name}")
                    lines.append(f"- 结论: {review.decision}")
                    if review.participant_profiles:
                        lines.append(
                            f"- 参与成员: {', '.join(str(item.get('name')) for item in review.participant_profiles)}"
                        )
                    if review.discussion_log:
                        lines.append("- 讨论记录:")
                        for turn in review.discussion_log:
                            lines.append(f"  - {turn}")
                    lines.append("")
                return "\n".join(lines)
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
            if _is_zh(resolved_language):
                lines = [
                    f"# 阶段输出: {stage.value}",
                    "",
                    "## 入选方案综合",
                    "",
                ]
                for department, solution in plan.selected_solutions.items():
                    lines.append(f"- {department.value}: {solution.name} | {solution.summary}")
                return "\n".join(lines)
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
            if _is_zh(resolved_language):
                recommendation = plan.scorecard.recommendation if plan.scorecard else "N/A"
                recommendation_map = {"Go": "通过", "Maybe": "观望", "No-Go": "暂缓"}
                lines = [
                    f"# 阶段输出: {stage.value}",
                    "",
                    "## 董事会决策",
                    "",
                    f"- 是否通过: {'是' if plan.board_decision.approved else '否'}",
                    f"- 开发难度: {plan.board_decision.development_difficulty}",
                    f"- 预算展望: {plan.board_decision.budget_outlook}",
                    f"- 资金节奏: {plan.board_decision.funding_cycle}",
                    f"- 决策理由: {plan.board_decision.rationale}",
                    f"- 条件: {'；'.join(plan.board_decision.conditions)}",
                    "",
                    "## 评分卡",
                    "",
                    f"- 建议: {recommendation_map.get(recommendation, recommendation)}",
                    f"- 摘要: {plan.scorecard.summary if plan.scorecard else '暂无'}",
                ]
                return "\n".join(lines)
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

        return self.render_markdown(plan, language=resolved_language)

    def _build_default_research(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention],
        language: str = "en-US",
    ) -> ResearchAssessment:
        resolved_language = _normalize_language(language)
        constraints = self._constraint_text(brief, interventions, language=resolved_language)
        if _is_zh(resolved_language):
            customer_segments = [
                "价格敏感型早期用户",
                "中小商家经营者",
                "区域分销商或服务商",
            ]
            if "consumer" in brief.title.lower() or "user" in brief.summary.lower():
                customer_segments.insert(0, "大众消费者")

            recommendation = "建议进入部门方案阶段，并重点验证定价、合规与供应链假设。"
            return ResearchAssessment(
                customer_segments=customer_segments,
                market_size_view=f"若团队能满足这些约束条件，则存在从细分市场走向主流市场的机会：{constraints}。",
                competitive_landscape="预计将面对分散型存量玩家、低价替代方案，以及少量品牌能力更强的高端竞争者。",
                key_risks=[
                    "需求验证不足可能导致过度乐观。",
                    "监管或认证要求可能拖慢上线节奏。",
                    "若前期架构缺乏约束，成本结构可能失控。",
                ],
                recommendation=recommendation,
            )

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
        language: str = "en-US",
    ) -> dict[Department, list[DepartmentSolution]]:
        resolved_language = _normalize_language(language)
        teams = department_teams()
        context = self._constraint_text(brief, interventions, language=resolved_language)
        if _is_zh(resolved_language):
            fallback_solutions = {
                Department.HARDWARE: self._build_solution_set(
                    department=Department.HARDWARE,
                    base_name="平台方案",
                    base_summary=f"围绕 {brief.title} 设计的硬件架构，重点满足 {context}",
                    assumptions=["核心组件至少保持双供应商可得。", "原型迭代周期可控制在 12 周以内。"],
                    base_score=8,
                    language=resolved_language,
                ),
                Department.SOFTWARE: self._build_solution_set(
                    department=Department.SOFTWARE,
                    base_name="控制栈",
                    base_summary=f"支撑 {brief.title} 的软件控制与服务层", 
                    assumptions=["首版可选配遥测能力。", "核心控制逻辑可与用户侧系统解耦。"],
                    base_score=7,
                    language=resolved_language,
                ),
                Department.DESIGN: self._build_solution_set(
                    department=Department.DESIGN,
                    base_name="体验方案",
                    base_summary=f"与 {brief.title} 对齐的交互和产品形态决策",
                    assumptions=["用户舒适度与信任感可优先于功能数量。", "首发版本应优先保证清晰可理解。"],
                    base_score=8,
                    language=resolved_language,
                ),
                Department.MARKETING: self._build_solution_set(
                    department=Department.MARKETING,
                    base_name="市场进入",
                    base_summary=f"面向 {brief.title} 的需求启动与渠道策略",
                    assumptions=["存在可切入的楔形细分市场。", "早期合作渠道可优于纯买量获客。"],
                    base_score=7,
                    language=resolved_language,
                ),
                Department.FINANCE: self._build_solution_set(
                    department=Department.FINANCE,
                    base_name="资金计划",
                    base_summary=f"服务于 {brief.title} 的预算、定价与融资结构",
                    assumptions=["试点批次后单位经济性可改善。", "营运资金是早期主要财务约束。"],
                    base_score=8,
                    language=resolved_language,
                ),
            }
        else:
            fallback_solutions = {
                Department.HARDWARE: self._build_solution_set(
                    department=Department.HARDWARE,
                    base_name="Platform",
                    base_summary=f"Physical architecture for {brief.title} optimized around {context}",
                    assumptions=["Core components remain available through two suppliers.", "Prototype cycles can be completed in under 12 weeks."],
                    base_score=8,
                    language=resolved_language,
                ),
                Department.SOFTWARE: self._build_solution_set(
                    department=Department.SOFTWARE,
                    base_name="Control Stack",
                    base_summary=f"Digital control and service layer supporting {brief.title}",
                    assumptions=["Telemetry is optional in the first release.", "Core control logic can be isolated from user-facing software."],
                    base_score=7,
                    language=resolved_language,
                ),
                Department.DESIGN: self._build_solution_set(
                    department=Department.DESIGN,
                    base_name="Experience Concept",
                    base_summary=f"Interaction and product form decisions aligned to {brief.title}",
                    assumptions=["User comfort and trust can outweigh feature count.", "The first release should prioritize clarity over novelty."],
                    base_score=8,
                    language=resolved_language,
                ),
                Department.MARKETING: self._build_solution_set(
                    department=Department.MARKETING,
                    base_name="Go-To-Market",
                    base_summary=f"Demand creation and channel strategy for {brief.title}",
                    assumptions=["A clear wedge market exists.", "Partnership channels can outperform pure paid acquisition early."],
                    base_score=7,
                    language=resolved_language,
                ),
                Department.FINANCE: self._build_solution_set(
                    department=Department.FINANCE,
                    base_name="Capital Plan",
                    base_summary=f"Budget, pricing, and funding structure for {brief.title}",
                    assumptions=["Unit economics improve after the pilot batch.", "Working capital is the main early financial constraint."],
                    base_score=8,
                    language=resolved_language,
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
                            _localize_team_owner_entry(f"{member.name} ({member.title})", resolved_language)
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
        language: str = "en-US",
    ) -> list[DepartmentSolution]:
        resolved_language = _normalize_language(language)
        solutions: list[DepartmentSolution] = []
        if _is_zh(resolved_language):
            patterns = (
                ("A", "平衡且偏执行", 0),
                ("B", "低成本且更易落地", -1),
                ("C", "上限更高且更有差异化", 1),
            )
        else:
            patterns = (
                ("A", "balanced and execution-focused", 0),
                ("B", "lower-cost and easier to launch", -1),
                ("C", "higher-upside and more differentiated", 1),
            )
        for suffix, variant, delta in patterns:
            artifacts = self._default_artifacts_for_department(department, suffix, language=resolved_language)
            if _is_zh(resolved_language):
                summary = f"{base_summary}；该变体特征为{variant}。"
                rationale = f"{department.value} 方向的 {suffix} 方案在当前约束下平衡了执行风险与收益。"
                implementation_steps = [
                    "与跨部门干系人澄清关键假设。",
                    "构建有限范围试点。",
                    "在放量前评估运营表现。",
                ]
                success_metrics = [
                    "试点里程碑按期达成。",
                    "成本保持在目标范围内。",
                ]
            else:
                summary = f"{base_summary}; variant is {variant}."
                rationale = f"{department.value.title()} option {suffix} balances the current constraint set against execution risk."
                implementation_steps = [
                    "Clarify assumptions with cross-functional stakeholders.",
                    "Build a limited-scope pilot.",
                    "Measure operational performance before scale-up.",
                ]
                success_metrics = [
                    "Pilot milestones hit on time.",
                    "Cost envelope remains within target.",
                ]
            solutions.append(
                DepartmentSolution(
                    department=department,
                    name=f"{base_name} {suffix}",
                    summary=summary,
                    feasibility_score=max(1, min(10, base_score + delta)),
                    dependencies=DEPARTMENT_DEPENDENCIES.get(department, []),
                    assumptions=assumptions,
                    rationale=rationale,
                    implementation_steps=implementation_steps,
                    success_metrics=success_metrics,
                    artifacts=artifacts,
                )
            )
        return solutions

    def _default_artifacts_for_department(self, department: Department, suffix: str, language: str = "en-US") -> dict[str, object]:
        resolved_language = _normalize_language(language)
        if _is_zh(resolved_language):
            if department == Department.HARDWARE:
                return {
                    "bom_targets": [f"核心动力总成层级 {suffix}", "车架底盘成本护栏", "电池包采购区间"],
                    "manufacturing_notes": ["原型优先模块化装配", "试制阶段降低模具投入"],
                    "certification_path": "量产模具投入前完成本地合规验证",
                    "supply_chain_risks": ["电池交期", "电机控制器双供应"],
                }
            if department == Department.SOFTWARE:
                return {
                    "interface_boundaries": ["车辆控制 API", "遥测接入 API", "运营端服务边界"],
                    "system_components": ["嵌入式控制器", "车队服务", "运营看板"],
                    "data_flows": ["车辆到遥测", "看板到诊断", "运营端到告警"],
                    "operational_risks": ["固件升级回滚", "离线模式薄弱"],
                }
            if department == Department.DESIGN:
                return {
                    "design_constraints": ["上下车便捷", "免工具维护可达", "高可信外观"],
                    "ergonomic_targets": ["降低搬运负担", "控制区域触达清晰"],
                    "safety_cues": ["制动意图可见", "电池状态可视化"],
                    "serviceability_rules": ["外覆盖件可替换", "电池快拆可达"],
                }
            if department == Department.MARKETING:
                return {
                    "channel_budget": ["经销商赋能 40%", "线下演示 35%", "数字获客 25%"],
                    "wedge_segments": ["本地商户", "末端配送车队"],
                    "launch_narrative": "以实用可靠降低运营成本",
                    "partnership_plan": ["区域经销伙伴", "电池服务伙伴"],
                }
            if department == Department.FINANCE:
                return {
                    "capital_envelope": ["原型预算上限", "试点批次储备", "营运资金缓冲"],
                    "pricing_logic": "以小车队快速回本为定价锚点",
                    "unit_economics": ["试点后毛利水平", "服务收入附着率"],
                    "downside_controls": ["分阶段拨付", "供应商付款控制"],
                }
            return {}
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
        language: str = "en-US",
    ) -> list[RoundtableReview]:
        resolved_language = _normalize_language(language)
        teams = department_teams()
        reviews: list[RoundtableReview] = []
        for department, solutions in department_solutions.items():
            for solution in solutions:
                if _is_zh(resolved_language):
                    concerns = [
                        "锁定架构前需完成上游依赖验证。",
                        "确保关键假设与目标上线节奏保持一致。",
                    ]
                else:
                    concerns = [
                        "Validate upstream dependencies before locking architecture.",
                        "Ensure assumptions remain compatible with target launch timing.",
                    ]
                if self._has_stage_intervention(interventions, Stage.ROUNDTABLE):
                    concerns.append(
                        "用户干预要求重新验证关键权衡。"
                        if _is_zh(resolved_language)
                        else "User intervention requires explicit revalidation of tradeoffs."
                    )
                all_participants = self._build_participant_profiles(
                    teams,
                    self._solution_team_departments(solution),
                    language=resolved_language,
                )
                participant_profiles = self._select_relevant_participants(solution, all_participants)
                discussion_log = self._build_roundtable_discussion(solution, participant_profiles, language=resolved_language)
                reviews.append(
                    RoundtableReview(
                        department=department,
                        solution_name=solution.name,
                        reviewers=solution.dependencies,
                        decision=(
                            "带修订推进" if solution.feasibility_score < 8 else "推进"
                        ) if _is_zh(resolved_language) else (
                            "advance with revisions" if solution.feasibility_score < 8 else "advance"
                        ),
                        concerns=concerns,
                        action_items=(
                            [
                                "沉淀依赖假设并形成文档。",
                                "量化成本与周期影响并同步董事会材料。",
                            ]
                            if _is_zh(resolved_language)
                            else [
                                "Document dependency assumptions.",
                                "Quantify cost and timing impact for the board pack.",
                            ]
                        ),
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
        language: str = "en-US",
    ) -> list[dict[str, object]]:
        resolved_language = _normalize_language(language)
        participants: list[dict[str, object]] = []
        for department in departments:
            for member in teams.get(department, ()):
                participants.append(
                    {
                        "employee_id": member.employee_id,
                        "name": _localize_employee_name(member.name, resolved_language),
                        "title": _localize_title(member.title, resolved_language),
                        "department": member.department.value,
                        "personality": member.personality,
                        "capability_focus": _localize_capability_focus_items(member.capability_focus, resolved_language),
                        "capability_focus_source": list(member.capability_focus),
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
            capability_focus = member.get("capability_focus_source", member.get("capability_focus", []))
            if self._capability_matches_solution(solution_text, capability_focus):
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
        language: str = "en-US",
    ) -> list[str]:
        resolved_language = _normalize_language(language)
        lines: list[str] = []
        if not participants:
            return lines
        focus_area = solution.success_metrics[0] if solution.success_metrics else ("交付可靠性" if _is_zh(resolved_language) else "delivery reliability")
        for member in participants:
            generated = self._build_roundtable_line_with_llm(solution, member, focus_area, language=resolved_language)
            if generated:
                lines.append(generated)
                continue
            lines.append(self._build_roundtable_line_fallback(solution, member, focus_area, language=resolved_language))
        return lines

    def _build_roundtable_line_with_llm(
        self,
        solution: DepartmentSolution,
        member: dict[str, object],
        focus_area: str,
        language: str = "en-US",
    ) -> str | None:
        if self.llm_client is None:
            return None

        resolved_language = _normalize_language(language)

        if _is_zh(resolved_language):
            system_prompt = (
                "你是一名参与跨部门圆桌会的员工。"
                "返回严格 JSON，键为 statement。"
                "请用中文输出一条简洁、具体、可执行的发言。"
            )
        else:
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
        if _is_zh(resolved_language):
            return f"{member.get('name')}（{member.get('title')}）表示：{text}"
        return f"{member.get('name')} ({member.get('title')}) said: {text}"

    def _build_roundtable_line_fallback(
        self,
        solution: DepartmentSolution,
        member: dict[str, object],
        focus_area: str,
        language: str = "en-US",
    ) -> str:
        resolved_language = _normalize_language(language)
        focus_list = [str(item) for item in member.get("capability_focus", [])]
        primary_focus = focus_list[0] if focus_list else ("跨部门风险校验" if _is_zh(resolved_language) else "cross-functional risk checks")
        if _is_zh(resolved_language):
            return (
                f"{member.get('name')}（{member.get('title')}）提出需要关注 {primary_focus}，"
                f"并建议团队在推进 {solution.name} 时优先保障 {focus_area}。"
            )
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
        language: str = "en-US",
    ) -> BoardDecision:
        resolved_language = _normalize_language(language)
        average_score = mean(solution.feasibility_score for solution in selected_solutions.values())
        intervention_penalty = 0.5 if self._has_stage_intervention(interventions, Stage.BOARD) else 0.0
        effective_score = average_score - intervention_penalty
        approved = effective_score >= 7.5

        if _is_zh(resolved_language):
            rationale = (
                f"针对 {brief.title} 的方案组合具备基本跨部门一致性。"
                f"研究结论为：{research.recommendation}"
            )
            if interventions:
                rationale += " 已记录用户干预，后续版本应持续可追溯。"
        else:
            rationale = (
                f"The portfolio for {brief.title} shows sufficient cross-functional coherence. "
                f"Research recommendation is: {research.recommendation}"
            )
            if interventions:
                rationale += " User interventions are recorded and should stay visible in later revisions."

        return BoardDecision(
            approved=approved,
            development_difficulty=("中" if effective_score >= 8 else "中高") if _is_zh(resolved_language) else ("medium" if effective_score >= 8 else "medium-high"),
            budget_outlook=("分阶段交付下可控" if effective_score >= 7.5 else "对范围漂移较敏感") if _is_zh(resolved_language) else ("manageable with phased delivery" if effective_score >= 7.5 else "sensitive to scope drift"),
            funding_cycle=("先试点投入，再按里程碑扩张") if _is_zh(resolved_language) else ("pilot funding then milestone-based expansion"),
            rationale=rationale,
            conditions=(
                [
                    "首发版本需收敛范围。",
                    "在扩大资本投入前先完成需求验证。",
                    "将用户干预纳入正式变更管理。",
                ]
                if _is_zh(resolved_language)
                else [
                    "Keep scope narrow for the first release.",
                    "Validate demand before committing to large capital outlays.",
                    "Track user interventions as formal change requests.",
                ]
            ),
        )

    def _build_scorecard(
        self,
        brief: IdeaBrief,
        research: ResearchAssessment,
        selected_solutions: dict[Department, DepartmentSolution],
        board_decision: BoardDecision,
        interventions: list[UserIntervention],
        language: str = "en-US",
    ) -> PlanScorecard:
        resolved_language = _normalize_language(language)
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

        if _is_zh(resolved_language):
            recommendation_text = {"Go": "通过", "Maybe": "观望", "No-Go": "暂缓"}.get(recommendation, recommendation)
            status = "较强" if weighted_score >= 7.5 else "中等" if weighted_score >= 6.2 else "偏弱"
            summary = (
                f"{brief.title} 当前综合建议为{recommendation_text}，"
                f"主要因为需求与跨部门可行性表现{status}，"
                f"且董事会条件为{board_decision.budget_outlook}。"
            )
        else:
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

    def _constraint_text(self, brief: IdeaBrief, interventions: list[UserIntervention], language: str = "en-US") -> str:
        resolved_language = _normalize_language(language)
        parts: list[str] = []
        if brief.user_constraints:
            parts.extend(brief.user_constraints)
        parts.extend(intervention.impact for intervention in interventions)
        if parts:
            return ", ".join(parts)
        return "速度、成本纪律与市场匹配" if _is_zh(resolved_language) else "speed, cost discipline, and market fit"

    def _has_stage_intervention(self, interventions: list[UserIntervention], stage: Stage) -> bool:
        return any(intervention.stage == stage for intervention in interventions)