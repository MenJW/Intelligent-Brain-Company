from __future__ import annotations

from dataclasses import dataclass
import re

from intelligent_brain_company.agents.contracts import department_contract_prompt, parse_department_solutions
from intelligent_brain_company.agents.registry import AgentProfile, department_teams
from intelligent_brain_company.domain.models import (
    BoardDecision,
    Department,
    DepartmentSolution,
    IdeaBrief,
    ResearchAssessment,
    Stage,
    UserIntervention,
)
from intelligent_brain_company.domain.project_state import ProjectRecord
from intelligent_brain_company.services.llm_client import LLMClient


def _constraints_text(brief: IdeaBrief, interventions: list[UserIntervention]) -> str:
    parts = list(brief.user_constraints)
    parts.extend(item.impact for item in interventions)
    return ", ".join(parts) if parts else "speed, cost discipline, and market fit"


def _department_context(solutions: dict[Department, DepartmentSolution] | None = None) -> str:
    if not solutions:
        return "No selected departmental solutions yet."
    lines = []
    for department, solution in solutions.items():
        lines.append(f"- {department.value}: {solution.name} | {solution.summary}")
    return "\n".join(lines)


def _suggested_stage_for_agent(agent_key: str) -> str:
    mapping = {
        "research": Department.RESEARCH.value,
        "hardware": Stage.DEPARTMENT_DESIGN.value,
        "software": Stage.DEPARTMENT_DESIGN.value,
        "design": Stage.DEPARTMENT_DESIGN.value,
        "marketing": Stage.DEPARTMENT_DESIGN.value,
        "finance": Stage.DEPARTMENT_DESIGN.value,
        "board": Stage.BOARD.value,
    }
    return mapping.get(agent_key, Stage.RESEARCH.value)


def _department_for_agent(agent_key: str) -> Department | None:
    if agent_key == Department.RESEARCH.value:
        return Department.RESEARCH
    try:
        return Department(agent_key)
    except ValueError:
        return None


def _normalize_identity(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _extract_employee_mention(message: str) -> str | None:
    match = re.search(r"@([A-Za-z0-9_\-\.]+)", message)
    if not match:
        return None
    return match.group(1)


def _resolve_employee(agent_key: str, message: str) -> tuple[AgentProfile | None, str]:
    mention = _extract_employee_mention(message)
    if not mention:
        return None, message.strip()

    department = _department_for_agent(agent_key)
    if department is None:
        return None, message.strip()

    teams = department_teams()
    members = teams.get(department, ())
    if not members:
        return None, message.strip()

    mention_key = _normalize_identity(mention)
    matched: AgentProfile | None = None
    for member in members:
        first_name = member.name.split(" ", 1)[0]
        identities = (
            _normalize_identity(member.employee_id),
            _normalize_identity(member.name),
            _normalize_identity(first_name),
        )
        if mention_key in identities:
            matched = member
            break

    cleaned = re.sub(r"@([A-Za-z0-9_\-\.]+)", "", message, count=1).strip()
    return matched, cleaned or message.strip()


def _normalize_language(language: str | None) -> str:
    if language in {"zh-CN", "en-US"}:
        return str(language)
    return "zh-CN"


def _is_zh(language: str) -> bool:
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


def _display_employee_name(name: str, language: str) -> str:
    if _is_zh(language):
        return EMPLOYEE_NAME_ZH.get(name, name)
    return name


def _display_title(title: str, language: str) -> str:
    if _is_zh(language):
        return TITLE_ZH.get(title, title)
    return title


def _display_focus(focus: str, language: str) -> str:
    if _is_zh(language):
        return CAPABILITY_FOCUS_ZH.get(focus, focus)
    return focus


@dataclass(slots=True)
class ResearchAgent:
    llm_client: LLMClient | None = None

    def analyze(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention],
        fallback: ResearchAssessment,
    ) -> ResearchAssessment:
        if self.llm_client is None:
            return fallback

        system_prompt = (
            "You are the head of an AI venture research team. "
            "Return strict JSON with keys: customer_segments, market_size_view, competitive_landscape, key_risks, recommendation."
        )
        user_prompt = (
            f"Idea title: {brief.title}\n"
            f"Idea summary: {brief.summary or 'N/A'}\n"
            f"Constraints and intervention impact: {_constraints_text(brief, interventions)}\n"
            f"Success metrics: {', '.join(brief.success_metrics) or 'N/A'}\n"
            "Write a grounded early-stage feasibility assessment for a multidisciplinary product company."
        )
        data = self.llm_client.generate_json(system_prompt, user_prompt)
        if not data:
            return fallback
        try:
            return ResearchAssessment(
                customer_segments=list(data["customer_segments"]),
                market_size_view=str(data["market_size_view"]),
                competitive_landscape=str(data["competitive_landscape"]),
                key_risks=[str(item) for item in data["key_risks"]],
                recommendation=str(data["recommendation"]),
            )
        except (KeyError, TypeError, ValueError):
            return fallback


@dataclass(slots=True)
class BoardAgent:
    llm_client: LLMClient | None = None

    def review(
        self,
        brief: IdeaBrief,
        research: ResearchAssessment,
        selected_solutions: dict[Department, DepartmentSolution],
        interventions: list[UserIntervention],
        fallback: BoardDecision,
    ) -> BoardDecision:
        if self.llm_client is None:
            return fallback

        solution_lines = []
        for department, solution in selected_solutions.items():
            solution_lines.append(
                f"- {department.value}: {solution.name}; score={solution.feasibility_score}; summary={solution.summary}"
            )
        system_prompt = (
            "You are the board of an AI-native product company. "
            "Return strict JSON with keys: approved, development_difficulty, budget_outlook, funding_cycle, rationale, conditions."
        )
        user_prompt = (
            f"Idea: {brief.title}\n"
            f"Summary: {brief.summary or 'N/A'}\n"
            f"Research recommendation: {research.recommendation}\n"
            f"Key risks: {'; '.join(research.key_risks)}\n"
            f"User constraints and interventions: {_constraints_text(brief, interventions)}\n"
            "Selected departmental solutions:\n"
            + "\n".join(solution_lines)
            + "\nAssess whether the company should approve this plan now, considering difficulty, cost, and funding cadence."
        )
        data = self.llm_client.generate_json(system_prompt, user_prompt)
        if not data:
            return fallback
        try:
            return BoardDecision(
                approved=bool(data["approved"]),
                development_difficulty=str(data["development_difficulty"]),
                budget_outlook=str(data["budget_outlook"]),
                funding_cycle=str(data["funding_cycle"]),
                rationale=str(data["rationale"]),
                conditions=[str(item) for item in data["conditions"]],
            )
        except (KeyError, TypeError, ValueError):
            return fallback


@dataclass(slots=True)
class DepartmentAgent:
    department: Department
    llm_client: LLMClient | None = None

    def plan(
        self,
        brief: IdeaBrief,
        interventions: list[UserIntervention],
        fallback: list[DepartmentSolution],
        team_members: tuple[AgentProfile, ...] = (),
    ) -> list[DepartmentSolution]:
        if self.llm_client is None:
            return fallback

        team_context = "\n".join(
            (
                f"- {member.name} ({member.title}): personality={member.personality}; "
                f"focus={', '.join(member.capability_focus)}; inspired_by={member.inspired_by}"
            )
            for member in team_members
        )
        system_prompt = department_contract_prompt(self.department)
        user_prompt = (
            f"Idea title: {brief.title}\n"
            f"Idea summary: {brief.summary or 'N/A'}\n"
            f"Constraints and intervention impact: {_constraints_text(brief, interventions)}\n"
            f"Success metrics: {', '.join(brief.success_metrics) or 'N/A'}\n"
            "Department employee roster (all members must contribute to the final plan):\n"
            f"{team_context or '- no explicit roster provided'}\n"
            "Return practical, differentiated options with realistic execution tradeoffs. "
            "Make artifacts specific and actionable rather than generic labels. "
            "Add one team ownership artifact containing all roster members and their responsibility split."
        )
        data = self.llm_client.generate_json(system_prompt, user_prompt)
        if not data:
            return fallback
        return parse_department_solutions(self.department, data, fallback)


@dataclass(slots=True)
class ChatAgent:
    llm_client: LLMClient | None = None

    def reply(
        self,
        project: ProjectRecord,
        agent_key: str,
        message: str,
        language: str | None = None,
    ) -> tuple[str, bool, str, str, bool, str | None]:
        resolved_language = _normalize_language(language or project.conversation_language)
        employee, cleaned_message = _resolve_employee(agent_key, message)
        if employee is not None:
            return self._reply_as_employee(project, agent_key, employee, cleaned_message, resolved_language)

        fallback = self._fallback_reply(project, agent_key, message, resolved_language)
        if self.llm_client is None:
            return (
                fallback,
                False,
                _suggested_stage_for_agent(agent_key),
                self._default_impact(agent_key, resolved_language),
                True,
                None,
            )

        system_prompt = (
            "You are an internal expert inside an AI-native company. "
            "Return strict JSON with keys: reply, follow_up_questions, updated_assumptions, suggested_stage, suggested_impact, can_promote_to_intervention. "
            "Be concise and operational. "
            f"Always write all natural-language fields in {'Simplified Chinese' if _is_zh(resolved_language) else 'English'}."
        )
        user_prompt = (
            f"Agent role: {agent_key}\n"
            f"Project: {project.name}\n"
            f"Idea: {project.idea.title}\n"
            f"Summary: {project.idea.summary or 'N/A'}\n"
            f"Constraints: {', '.join(project.idea.user_constraints) or 'N/A'}\n"
            f"Interventions: {'; '.join(item.message for item in project.interventions) or 'None'}\n"
            f"Latest selected solutions:\n{_department_context(project.latest_plan.selected_solutions if project.latest_plan else None)}\n"
            f"User message: {message}"
        )
        data = self.llm_client.generate_json(system_prompt, user_prompt, temperature=0.4)
        if not data:
            return (
                fallback,
                False,
                _suggested_stage_for_agent(agent_key),
                self._default_impact(agent_key, resolved_language),
                True,
                None,
            )
        try:
            reply = str(data["reply"])
            follow_ups = [str(item) for item in data.get("follow_up_questions", [])]
            assumptions = [str(item) for item in data.get("updated_assumptions", [])]
            suffix = []
            if follow_ups:
                if _is_zh(resolved_language):
                    suffix.append("后续问题: " + " | ".join(follow_ups[:2]))
                else:
                    suffix.append("Follow-up questions: " + " | ".join(follow_ups[:2]))
            if assumptions:
                if _is_zh(resolved_language):
                    suffix.append("更新假设: " + " | ".join(assumptions[:2]))
                else:
                    suffix.append("Updated assumptions: " + " | ".join(assumptions[:2]))
            suggested_stage = str(data.get("suggested_stage", _suggested_stage_for_agent(agent_key)))
            suggested_impact = str(data.get("suggested_impact", self._default_impact(agent_key, resolved_language)))
            can_promote = bool(data.get("can_promote_to_intervention", True))
            response_text = reply + ("\n\n" + "\n".join(suffix) if suffix else "")
            return (response_text, True, suggested_stage, suggested_impact, can_promote, None)
        except (KeyError, TypeError, ValueError):
            return (
                fallback,
                False,
                _suggested_stage_for_agent(agent_key),
                self._default_impact(agent_key, resolved_language),
                True,
                None,
            )

    def _reply_as_employee(
        self,
        project: ProjectRecord,
        agent_key: str,
        employee: AgentProfile,
        message: str,
        language: str,
    ) -> tuple[str, bool, str, str, bool, str | None]:
        fallback = self._fallback_employee_reply(project, employee, message, language)
        default_stage = _suggested_stage_for_agent(agent_key)
        employee_name = _display_employee_name(employee.name, language)
        focus = _display_focus(employee.capability_focus[0], language) if employee.capability_focus else (
            "执行质量" if _is_zh(language) else "execution quality"
        )
        if _is_zh(language):
            default_impact = (
                f"采纳 {employee_name}({employee.employee_id}) 的建议，"
                f"更新 {employee.department.value} 方案的 {focus} 假设"
            )
        else:
            default_impact = (
                f"Adopt input from {employee.name} ({employee.employee_id}) and "
                f"update {employee.department.value} assumptions around {employee.capability_focus[0]}"
            )
        if self.llm_client is None:
            return fallback, False, default_stage, default_impact, True, employee.name

        system_prompt = (
            "You are a specific employee replying inside an AI-native company roundtable. "
            "Return strict JSON with keys: reply, suggested_stage, suggested_impact, can_promote_to_intervention. "
            "Be concrete and role-consistent. "
            f"Always write all natural-language fields in {'Simplified Chinese' if _is_zh(language) else 'English'}."
        )
        user_prompt = (
            f"Employee ID: {employee.employee_id}\n"
            f"Employee name: {employee.name}\n"
            f"Employee title: {employee.title}\n"
            f"Employee department: {employee.department.value}\n"
            f"Employee personality: {employee.personality}\n"
            f"Employee focus: {', '.join(employee.capability_focus)}\n"
            f"Project: {project.name}\n"
            f"Idea: {project.idea.title}\n"
            f"Idea summary: {project.idea.summary or 'N/A'}\n"
            f"Constraints: {', '.join(project.idea.user_constraints) or 'N/A'}\n"
            f"Latest selected solutions:\n{_department_context(project.latest_plan.selected_solutions if project.latest_plan else None)}\n"
            f"User message to this employee: {message}"
        )
        data = self.llm_client.generate_json(system_prompt, user_prompt, temperature=0.45)
        if not data:
            return fallback, False, default_stage, default_impact, True, employee.name

        try:
            reply = str(data["reply"])
            suggested_stage = str(data.get("suggested_stage", default_stage))
            suggested_impact = str(data.get("suggested_impact", default_impact))
            can_promote = bool(data.get("can_promote_to_intervention", True))
            return reply, True, suggested_stage, suggested_impact, can_promote, employee.name
        except (KeyError, TypeError, ValueError):
            return fallback, False, default_stage, default_impact, True, employee.name

    def _fallback_employee_reply(self, project: ProjectRecord, employee: AgentProfile, message: str, language: str) -> str:
        focus = _display_focus(employee.capability_focus[0], language) if employee.capability_focus else (
            "执行质量" if _is_zh(language) else "execution quality"
        )
        employee_name = _display_employee_name(employee.name, language)
        employee_title = _display_title(employee.title, language)
        context = ""
        if project.latest_plan and employee.department in project.latest_plan.selected_solutions:
            solution = project.latest_plan.selected_solutions[employee.department]
            if _is_zh(language):
                context = f"当前该部门主推方案是 {solution.name}。"
            else:
                context = f"The department's current lead solution is {solution.name}: {solution.summary}. "
        if _is_zh(language):
            return (
                f"{employee_name}（{employee_title}）回复：基于我的职责，我会优先关注 {focus}。"
                f"{context}"
                f"针对你的问题“{message}”，建议先给出可执行的验证步骤和验收标准。"
            )
        return (
            f"{employee.name} ({employee.title}) response: I would prioritize {focus} based on my role. "
            f"{context}"
            f"For your question \"{message}\", start with concrete validation steps and clear acceptance criteria."
        )

    def _default_impact(self, agent_key: str, language: str) -> str:
        if agent_key == "board":
            return "调整董事会约束条件并重新审核批准结论" if _is_zh(language) else "Adjust board constraints and re-evaluate approval"
        if agent_key == "research":
            return (
                "重新校准目标用户、竞争对照和需求验证结论"
                if _is_zh(language)
                else "Recalibrate target users, competitive benchmark, and demand validation"
            )
        if _is_zh(language):
            return f"更新 {agent_key} 部门方案假设和交付边界"
        return f"Update {agent_key} solution assumptions and delivery boundaries"

    def _fallback_reply(self, project: ProjectRecord, agent_key: str, message: str, language: str) -> str:
        if agent_key == Department.RESEARCH.value and project.latest_plan:
            research = project.latest_plan.research
            if _is_zh(language):
                risk_count = len(research.key_risks)
                return (
                    "研究组当前判断是：建议进入部门方案设计，并优先验证价格、合规与供应链等关键假设。"
                    f"目前识别到 {risk_count} 个主要风险点。"
                    f"结合你的问题“{message}”，建议先补强需求验证和竞争对照。\n\n"
                    f"建议干预阶段: {Stage.RESEARCH.value}\n建议影响: 重新校准目标用户、竞争对照和需求验证结论"
                )
            return (
                f"Research team's current assessment: {research.recommendation}. "
                f"Top risks: {'; '.join(research.key_risks[:3])}. "
                f"For your question \"{message}\", strengthen demand validation and competitor benchmarking first.\n\n"
                f"Suggested intervention stage: {Stage.RESEARCH.value}\n"
                f"Suggested impact: Recalibrate target users, competitive benchmark, and demand validation"
            )
        if agent_key == "board" and project.latest_plan:
            board = project.latest_plan.board_decision
            if _is_zh(language):
                approval_text = "批准" if board.approved else "暂缓"
                return (
                    f"董事会当前结论是：{approval_text}。"
                    "建议你重点检查预算结构、交付风险和里程碑可控性，再决定是否调整当前决议。\n\n"
                    f"建议干预阶段: {Stage.BOARD.value}\n建议影响: 调整董事会约束条件并重新审核批准结论"
                )
            return (
                f"Board's current decision: {'approved' if board.approved else 'deferred'}. "
                f"Rationale: {board.rationale}. "
                f"Current conditions: {'; '.join(board.conditions[:3])}.\n\n"
                f"Suggested intervention stage: {Stage.BOARD.value}\n"
                f"Suggested impact: Adjust board constraints and re-evaluate approval"
            )
        try:
            department = Department(agent_key)
        except ValueError:
            if _is_zh(language):
                return f"已记录你的问题：{message}。当前没有匹配到该角色，请选择研究组、董事会或具体部门。"
            return (
                f"Your question has been recorded: {message}. "
                "No matching role was found. Please select research, board, or a specific department."
            )

        if project.latest_plan and department in project.latest_plan.selected_solutions:
            solution = project.latest_plan.selected_solutions[department]
            if _is_zh(language):
                return (
                    f"{department.value} 部门当前主推方案是 {solution.name}。"
                    f"当前已沉淀 {len(solution.assumptions)} 条关键假设。"
                    f"对于你的问题“{message}”，建议围绕该方案的可行性和依赖关系继续细化。\n\n"
                    f"建议干预阶段: {Stage.DEPARTMENT_DESIGN.value}\n建议影响: 更新 {department.value} 部门方案假设和交付边界"
                )
            return (
                f"The {department.value} department's current lead solution is {solution.name}. "
                f"Summary: {solution.summary}. "
                f"Key assumptions: {'; '.join(solution.assumptions[:3]) or 'N/A'}. "
                f"For your question \"{message}\", continue refining feasibility and dependency management.\n\n"
                f"Suggested intervention stage: {Stage.DEPARTMENT_DESIGN.value}\n"
                f"Suggested impact: Update {department.value} solution assumptions and delivery boundaries"
            )
        if _is_zh(language):
            return f"{department.value} 部门尚未形成已选方案。你的问题“{message}”已纳入后续评估。"
        return (
            f"The {department.value} department does not have a selected solution yet. "
            f"Your question \"{message}\" has been added to upcoming evaluations."
        )