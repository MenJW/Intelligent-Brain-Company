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

    def reply(self, project: ProjectRecord, agent_key: str, message: str) -> tuple[str, bool, str, str, bool, str | None]:
        employee, cleaned_message = _resolve_employee(agent_key, message)
        if employee is not None:
            return self._reply_as_employee(project, agent_key, employee, cleaned_message)

        fallback = self._fallback_reply(project, agent_key, message)
        if self.llm_client is None:
            return fallback, False, _suggested_stage_for_agent(agent_key), self._default_impact(agent_key), True, None

        system_prompt = (
            "You are an internal expert inside an AI-native company. "
            "Return strict JSON with keys: reply, follow_up_questions, updated_assumptions, suggested_stage, suggested_impact, can_promote_to_intervention. "
            "Be concise and operational."
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
            return fallback, False, _suggested_stage_for_agent(agent_key), self._default_impact(agent_key), True, None
        try:
            reply = str(data["reply"])
            follow_ups = [str(item) for item in data.get("follow_up_questions", [])]
            assumptions = [str(item) for item in data.get("updated_assumptions", [])]
            suffix = []
            if follow_ups:
                suffix.append("后续问题: " + " | ".join(follow_ups[:2]))
            if assumptions:
                suffix.append("更新假设: " + " | ".join(assumptions[:2]))
            suggested_stage = str(data.get("suggested_stage", _suggested_stage_for_agent(agent_key)))
            suggested_impact = str(data.get("suggested_impact", "revise downstream conclusions"))
            can_promote = bool(data.get("can_promote_to_intervention", True))
            response_text = reply + ("\n\n" + "\n".join(suffix) if suffix else "")
            return (response_text, True, suggested_stage, suggested_impact, can_promote, None)
        except (KeyError, TypeError, ValueError):
            return fallback, False, _suggested_stage_for_agent(agent_key), self._default_impact(agent_key), True, None

    def _reply_as_employee(
        self,
        project: ProjectRecord,
        agent_key: str,
        employee: AgentProfile,
        message: str,
    ) -> tuple[str, bool, str, str, bool, str | None]:
        fallback = self._fallback_employee_reply(project, employee, message)
        default_stage = _suggested_stage_for_agent(agent_key)
        default_impact = (
            f"采纳 {employee.name}({employee.employee_id}) 的建议，"
            f"更新 {employee.department.value} 方案的 {employee.capability_focus[0]} 假设"
        )
        if self.llm_client is None:
            return fallback, False, default_stage, default_impact, True, employee.name

        system_prompt = (
            "You are a specific employee replying inside an AI-native company roundtable. "
            "Return strict JSON with keys: reply, suggested_stage, suggested_impact, can_promote_to_intervention. "
            "Be concrete and role-consistent."
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

    def _fallback_employee_reply(self, project: ProjectRecord, employee: AgentProfile, message: str) -> str:
        focus = employee.capability_focus[0] if employee.capability_focus else "execution quality"
        context = ""
        if project.latest_plan and employee.department in project.latest_plan.selected_solutions:
            solution = project.latest_plan.selected_solutions[employee.department]
            context = f"当前该部门主推方案是 {solution.name}，摘要：{solution.summary}。"
        return (
            f"{employee.name}（{employee.title}）回复：基于我的职责，我会优先关注 {focus}。"
            f"{context}"
            f"针对你的问题“{message}”，建议先给出可执行的验证步骤和验收标准。"
        )

    def _default_impact(self, agent_key: str) -> str:
        if agent_key == "board":
            return "调整董事会约束条件并重新审核批准结论"
        if agent_key == "research":
            return "重新校准目标用户、竞争对照和需求验证结论"
        return f"更新 {agent_key} 部门方案假设和交付边界"

    def _fallback_reply(self, project: ProjectRecord, agent_key: str, message: str) -> str:
        if agent_key == Department.RESEARCH.value and project.latest_plan:
            research = project.latest_plan.research
            return (
                f"研究组当前判断是：{research.recommendation}。"
                f"主要风险包括：{'；'.join(research.key_risks[:3])}。"
                f"结合你的问题“{message}”，建议先补强需求验证和竞争对照。\n\n"
                f"建议干预阶段: {Stage.RESEARCH.value}\n建议影响: 重新校准目标用户、竞争对照和需求验证结论"
            )
        if agent_key == "board" and project.latest_plan:
            board = project.latest_plan.board_decision
            return (
                f"董事会当前结论是：{'批准' if board.approved else '暂缓'}。"
                f"理由：{board.rationale}。"
                f"当前条件：{'；'.join(board.conditions[:3])}。\n\n"
                f"建议干预阶段: {Stage.BOARD.value}\n建议影响: 调整董事会约束条件并重新审核批准结论"
            )
        try:
            department = Department(agent_key)
        except ValueError:
            return f"已记录你的问题：{message}。当前没有匹配到该角色，请选择研究组、董事会或具体部门。"

        if project.latest_plan and department in project.latest_plan.selected_solutions:
            solution = project.latest_plan.selected_solutions[department]
            return (
                f"{department.value} 部门当前主推方案是 {solution.name}。"
                f"摘要：{solution.summary}。"
                f"关键假设：{'；'.join(solution.assumptions[:3]) or '暂无'}。"
                f"对于你的问题“{message}”，建议围绕该方案的可行性和依赖关系继续细化。\n\n"
                f"建议干预阶段: {Stage.DEPARTMENT_DESIGN.value}\n建议影响: 更新 {department.value} 部门方案假设和交付边界"
            )
        return f"{department.value} 部门尚未形成已选方案。你的问题“{message}”已纳入后续评估。"