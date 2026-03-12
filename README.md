# Intelligent Brain Company

Intelligent Brain Company is an AI-native venture studio framework. It turns a user idea into a company-style planning workflow: research team, domain departments, cross-functional reviews, board decision, and a final execution plan.

This repository now contains the first project skeleton for that vision: a clear domain model, a deterministic MVP workflow, a CLI entry point, and planning documents for the next implementation stages.

It now also includes a minimal backend service with project persistence and HTTP APIs, so the next step can be a real product console rather than a standalone script.

Research and board stages can now use a real OpenAI-compatible LLM endpoint when configured; without credentials, the system falls back to deterministic local generation.

Hardware, software, design, marketing, and finance departments now also support structured LLM generation through explicit JSON contracts, and the console includes a direct chat panel for talking to research, board, or department agents.

Project, task, timeline, chat, and version data are now persisted in SQLite instead of per-file JSON blobs.

## Why This Project

Most multi-agent projects stop at role-playing or software-only collaboration. Your idea is stronger than that: it treats AI agents as a company with explicit departments, governance, review loops, and human intervention at any stage.

The core product thesis is:

1. A user submits an idea.
2. A research team evaluates feasibility, market demand, competition, and risk.
3. Each department generates several viable solution options.
4. Cross-functional roundtables review dependencies and tradeoffs.
5. The best departmental options are merged into one integrated plan.
6. A board-level review decides whether to proceed and under what constraints.
7. The user can intervene at any stage and change the outcome.

## MVP Scope

The current scaffold focuses on the smallest useful end-to-end slice:

- Domain objects for ideas, solutions, reviews, board decisions, and user interventions.
- A company pipeline that simulates the full planning process.
- Department registry for research, hardware, software, design, marketing, and finance.
- Structured JSON contracts for department solution generation.
- A CLI command that turns an idea into a structured draft plan.
- A Flask API for creating projects, generating plans, and recording interventions.
- A chat API and console panel for direct conversation with research, board, and department agents.
- SQLite-backed persistence for project state, task history, versions, and chat records.
- Documentation for execution roadmap and license strategy.

This is intentionally framework-light. The current implementation keeps orchestration logic independent so that you can later plug in AutoGen, CrewAI, LangGraph, Semantic Kernel, or custom model routing without rewriting the business workflow.

## Repository Structure

```text
.
├── docs/
│   ├── execution-plan.md
│   └── license-strategy.md
├── src/
│   └── intelligent_brain_company/
│       ├── api/
│       │   ├── planning.py
│       │   └── projects.py
│       ├── agents/
│       │   ├── contracts.py
│       │   ├── registry.py
│       │   └── runtime.py
│       ├── app.py
│       ├── config.py
│       ├── domain/
│       │   ├── models.py
│       │   └── project_state.py
│       ├── interfaces/
│       │   └── cli.py
│       ├── services/
│       │   ├── llm_client.py
│       │   ├── planning.py
│       │   ├── project_store.py
│       │   └── task_store.py
│       ├── workflows/
│       │   └── pipeline.py
│       └── __init__.py
├── tests/
│   ├── test_api.py
│   └── test_pipeline.py
└── pyproject.toml
```

## Quick Start

```bash
python -m pip install -e .
ibc-plan "Build an electric tricycle" --constraint "Target price below 18000 CNY" --constraint "Designed for short-distance cargo delivery"
```

The CLI currently generates a deterministic planning draft. In the next stage, the deterministic steps can be replaced by live agents and model-backed discussion loops.

### API Mode

```bash
python -m pip install -e .[dev]
ibc-api
```

Example flow:

1. POST /api/projects to create a project.
2. POST /api/planning/generate to generate the first plan version.
3. POST /api/planning/interventions to insert user feedback and regenerate.
4. GET /api/projects/<project_id> to inspect the stored state.
5. POST /api/projects/<project_id>/chat to talk to research, board, or a department.
6. POST /api/projects/<project_id>/chat/promote to turn a chat turn into a formal intervention and trigger regeneration.

Open the control surface at http://127.0.0.1:8000 to create projects, view plans, inspect timeline and progress, and submit interventions.

The console also exposes a conversation panel where you can directly talk to research, board, hardware, software, design, marketing, or finance.

If you want live LLM-backed research, board, and department reviews, set these environment variables before starting the API:

```bash
IBC_LLM_API_KEY=your_key
IBC_LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
IBC_LLM_MODEL=your-model-name
```

## Architecture Direction

The architecture is split into four layers:

1. Domain layer: stable business objects and workflow states.
2. Workflow layer: company operating process and handoffs.
3. Service layer: orchestration entry points and future provider adapters.
4. Interface layer: CLI plus HTTP API first, web and chat surfaces later.

That split matters because the long-term moat is not individual prompts. It is the operating model of the AI company: state, review rules, escalation logic, and human-in-the-loop control.

## Recommended Next Milestones

1. Replace deterministic department outputs with live agent adapters.
2. Add persistence for sessions, interventions, and plan revisions.
3. Build a node-based workflow engine with resumable checkpoints.
4. Add a web console for department conversations and board review.
5. Add evaluation datasets for plan quality, consistency, and cost realism.

## License Note

This repository now uses Apache-2.0.

That aligns the codebase with a permissive adoption strategy: easier commercial collaboration, fewer contributor onboarding hurdles, and cleaner integration into enterprise stacks. The rationale and historical tradeoff note remain in docs/license-strategy.md.
