from __future__ import annotations

import argparse

from intelligent_brain_company.domain.models import IdeaBrief
from intelligent_brain_company.services.planning import PlanningOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tobeceo-plan",
        description="Generate a draft company-style execution plan from an idea.",
    )
    parser.add_argument("idea", help="Short project or business idea title.")
    parser.add_argument("--summary", default="", help="Optional idea summary.")
    parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Constraint or user requirement. Can be provided multiple times.",
    )
    parser.add_argument(
        "--metric",
        action="append",
        default=[],
        help="Success metric. Can be provided multiple times.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    brief = IdeaBrief(
        title=args.idea,
        summary=args.summary,
        user_constraints=args.constraint,
        success_metrics=args.metric,
    )

    orchestrator = PlanningOrchestrator()
    plan = orchestrator.build_plan(brief)
    print(orchestrator.render_plan(plan))


if __name__ == "__main__":
    main()