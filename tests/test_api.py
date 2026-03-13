from __future__ import annotations

import sqlite3
from pathlib import Path

from intelligent_brain_company.app import create_app
from intelligent_brain_company.config import AppConfig


def make_test_app(tmp_path: Path):
    config = AppConfig(data_dir=tmp_path / "runtime", host="127.0.0.1", port=8000)
    app = create_app(config)
    app.config.update(TESTING=True)
    return app


def test_create_project_and_generate_plan(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    response = client.post(
        "/api/projects",
        json={
            "title": "Electric Tricycle",
            "summary": "Cargo mobility for short-distance distribution.",
            "constraints": ["Keep acquisition cost low"],
        },
    )
    assert response.status_code == 201
    project_id = response.get_json()["data"]["project_id"]

    generation = client.post("/api/planning/generate", json={"project_id": project_id})
    assert generation.status_code == 200
    payload = generation.get_json()["data"]
    assert payload["task"]["status"] == "completed"
    assert payload["executed_stage"] == "research"
    assert payload["project"]["current_stage"] == "research"
    assert payload["project"]["latest_plan_markdown"]
    assert payload["project"]["latest_plan"]["scorecard"] is None
    assert payload["project"]["latest_plan"]["roundtable_reviews"] == []


def test_scorecard_is_generated_only_at_board_stage(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Stage Gate Validation"}).get_json()["data"]
    project_id = created["project_id"]

    research = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    assert research["executed_stage"] == "research"
    assert research["project"]["latest_plan"]["scorecard"] is None

    department = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    assert department["executed_stage"] == "department_design"
    assert department["project"]["latest_plan"]["scorecard"] is None

    roundtable = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    assert roundtable["executed_stage"] == "roundtable"
    assert roundtable["project"]["latest_plan"]["scorecard"] is None
    assert roundtable["project"]["latest_plan"]["roundtable_reviews"]

    synthesis = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    assert synthesis["executed_stage"] == "synthesis"
    assert synthesis["project"]["latest_plan"]["scorecard"] is None

    board = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    assert board["executed_stage"] == "board"
    assert board["project"]["latest_plan"]["scorecard"]["recommendation"] in {"Go", "Maybe", "No-Go"}


def test_intervention_is_recorded_without_auto_regeneration(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Neighborhood Delivery Robot"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})

    revised = client.post(
        "/api/planning/interventions",
        json={
            "project_id": project_id,
            "stage": "roundtable",
            "speaker": "founder",
            "message": "Battery maintenance must be simplified.",
            "impact": "prioritize maintainability over feature density",
        },
    )
    assert revised.status_code == 200
    payload = revised.get_json()["data"]
    project = payload["project"]
    assert payload["auto_regenerated"] is False
    assert len(project["plans"]) == 1
    assert len(project["interventions"]) == 1


def test_timeline_progress_and_diff_endpoints(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Warehouse Shuttle"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})
    client.post(
        "/api/planning/interventions",
        json={
            "project_id": project_id,
            "stage": "research",
            "speaker": "founder",
            "message": "Reduce capital intensity.",
            "impact": "favor phased rollout and smaller pilot",
        },
    )
    client.post("/api/planning/generate", json={"project_id": project_id})
    client.post("/api/planning/generate", json={"project_id": project_id})

    progress = client.get(f"/api/projects/{project_id}/progress")
    assert progress.status_code == 200
    assert progress.get_json()["data"]["stages"]

    timeline = client.get(f"/api/projects/{project_id}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.get_json()["data"]) >= 3

    project = client.get(f"/api/projects/{project_id}").get_json()["data"]
    version_ids = [item["version_id"] for item in project["plans"]]
    assert len(version_ids) >= 2
    diff = client.get(f"/api/projects/{project_id}/plans/diff?from={version_ids[0]}&to={version_ids[-1]}")
    assert diff.status_code == 200
    assert "diff" in diff.get_json()["data"]


def test_console_page_is_served(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"TOBECEO" in response.data
    assert "一键体验 Demo".encode("utf-8") in response.data


def test_chat_endpoint_persists_history(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Portable Cold Chain Box"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})

    chat = client.post(
        f"/api/projects/{project_id}/chat",
        json={"agent": "research", "message": "目标客户更像 B 端还是 C 端？"},
    )
    assert chat.status_code == 200
    payload = chat.get_json()["data"]
    assert payload["history"]
    chat_items = [item for item in payload["history"] if item.get("source") == "chat"]
    assert chat_items
    assert chat_items[0]["agent"] == "research"

    history = client.get(f"/api/projects/{project_id}/chat?agent=research")
    assert history.status_code == 200
    history_items = history.get_json()["data"]["history"]
    assert any(item.get("source") == "chat" for item in history_items)
    assert any(item.get("source") == "stage_review" for item in history_items)


def test_chat_history_includes_stage_and_employee_replay(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Autonomous Store Cart"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})
    client.post("/api/planning/generate", json={"project_id": project_id})
    client.post("/api/planning/generate", json={"project_id": project_id})

    history = client.get(f"/api/projects/{project_id}/chat?agent=hardware")
    assert history.status_code == 200
    history_items = history.get_json()["data"]["history"]
    assert not any(item.get("source") == "stage_review" for item in history_items)
    assert any(item.get("source") == "employee_statement" for item in history_items)


def test_department_chat_employee_roster_endpoint(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Employee Picker"}).get_json()["data"]
    project_id = created["project_id"]

    roster = client.get(f"/api/projects/{project_id}/chat/employees?agent=hardware")
    assert roster.status_code == 200
    payload = roster.get_json()["data"]
    assert payload["agent"] == "hardware"
    assert payload["employees"]
    assert all("mention_key" in item for item in payload["employees"])

    empty_roster = client.get(f"/api/projects/{project_id}/chat/employees?agent=research")
    assert empty_roster.status_code == 200
    assert empty_roster.get_json()["data"]["employees"] == []


def test_chat_turn_can_be_promoted_to_intervention_without_auto_regeneration(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Compact Cargo EV"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})

    chat = client.post(
        f"/api/projects/{project_id}/chat",
        json={"agent": "hardware", "message": "请优先降低电池包维护复杂度"},
    ).get_json()["data"]
    turn_id = chat["turn"]["turn_id"]

    promoted = client.post(
        f"/api/projects/{project_id}/chat/promote",
        json={"turn_id": turn_id},
    )
    assert promoted.status_code == 200
    payload = promoted.get_json()["data"]
    project = payload["project"]
    assert payload["auto_regenerated"] is False
    assert len(project["interventions"]) == 1
    assert len(project["plans"]) == 1


def test_chat_supports_at_employee_reply_and_promotion_independence(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Employee Mention Flow"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})
    client.post("/api/planning/generate", json={"project_id": project_id})

    chat = client.post(
        f"/api/projects/{project_id}/chat",
        json={"agent": "hardware", "message": "@Noah 请给一个传感器集成风险控制建议"},
    )
    assert chat.status_code == 200
    payload = chat.get_json()["data"]
    assert payload["turn"]["speaker"] == "Noah Bennett"
    assert "周彦霖" in payload["turn"]["assistant_message"]

    turn_id = payload["turn"]["turn_id"]
    promoted = client.post(
        f"/api/projects/{project_id}/chat/promote",
        json={"turn_id": turn_id},
    )
    assert promoted.status_code == 200
    project = promoted.get_json()["data"]["project"]
    assert project["interventions"]
    assert project["interventions"][-1]["speaker"] == "Noah Bennett"


def test_language_switch_affects_new_chat_turn_only(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Language Switch Flow"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})

    zh_chat = client.post(
        f"/api/projects/{project_id}/chat",
        json={"agent": "research", "message": "请先给我中文建议"},
    )
    assert zh_chat.status_code == 200
    zh_turn = zh_chat.get_json()["data"]["turn"]
    assert zh_turn["language"] == "zh-CN"
    assert "研究组当前判断是" in zh_turn["assistant_message"]
    assert "Proceed to departmental planning" not in zh_turn["assistant_message"]

    switched = client.post(
        f"/api/projects/{project_id}/language",
        json={"language": "en-US"},
    )
    assert switched.status_code == 200
    assert switched.get_json()["data"]["language"] == "en-US"

    en_chat = client.post(
        f"/api/projects/{project_id}/chat",
        json={"agent": "research", "message": "Please answer in English"},
    )
    assert en_chat.status_code == 200
    en_turn = en_chat.get_json()["data"]["turn"]
    assert en_turn["language"] == "en-US"
    assert "Research team's current assessment" in en_turn["assistant_message"]

    history = client.get(f"/api/projects/{project_id}/chat?agent=research")
    assert history.status_code == 200
    turns = [item for item in history.get_json()["data"]["history"] if item.get("source") == "chat"]
    assert any(item.get("language") == "zh-CN" for item in turns)
    assert any(item.get("language") == "en-US" for item in turns)


def test_stage_outputs_are_fully_localized_in_zh_mode(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "阶段全链路中文"}).get_json()["data"]
    project_id = created["project_id"]

    research = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    research_md = research["project"]["latest_plan_markdown"]
    assert "# 阶段输出: research" in research_md
    assert "## 研究评估" in research_md
    assert "# Stage Output" not in research_md

    department = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    department_md = department["project"]["latest_plan_markdown"]
    assert "# 阶段输出: department_design" in department_md
    assert "## 部门讨论" in department_md
    assert "## Department Discussions" not in department_md
    assert "(score " not in department_md
    assert "周彦霖（嵌入式系统工程师）" in department_md
    assert "Noah Bennett (Embedded Systems Engineer)" not in department_md

    roundtable = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    roundtable_md = roundtable["project"]["latest_plan_markdown"]
    assert "# 阶段输出: roundtable" in roundtable_md
    assert "## 跨部门圆桌评审" in roundtable_md
    assert "## Cross-Department Roundtable" not in roundtable_md
    assert " said: " not in roundtable_md

    synthesis = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    synthesis_md = synthesis["project"]["latest_plan_markdown"]
    assert "# 阶段输出: synthesis" in synthesis_md
    assert "## 入选方案综合" in synthesis_md
    assert "## Selected Solution Synthesis" not in synthesis_md

    board = client.post("/api/planning/generate", json={"project_id": project_id}).get_json()["data"]
    board_md = board["project"]["latest_plan_markdown"]
    assert "# 阶段输出: board" in board_md
    assert "## 董事会决策" in board_md
    assert "## 评分卡" in board_md
    assert "## Board Decision" not in board_md
    assert "## Scorecard" not in board_md


def test_intervention_does_not_auto_replace_latest_markdown(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "完整计划中文化"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})

    before = client.get(f"/api/projects/{project_id}").get_json()["data"]["latest_plan_markdown"]

    recorded = client.post(
        "/api/planning/interventions",
        json={
            "project_id": project_id,
            "stage": "roundtable",
            "speaker": "founder",
            "message": "优先保证供应链稳定",
            "impact": "强化供应稳定与交付节奏",
        },
    )
    assert recorded.status_code == 200
    payload = recorded.get_json()["data"]
    assert payload["auto_regenerated"] is False
    assert payload["project"]["latest_plan_markdown"] == before

    regenerated = client.post("/api/planning/generate", json={"project_id": project_id})
    assert regenerated.status_code == 200
    stage_md = regenerated.get_json()["data"]["project"]["latest_plan_markdown"]
    assert "# 阶段输出:" in stage_md


def test_sqlite_database_is_used_for_persistence(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()
    config = app.config["IBC_CONFIG"]

    created = client.post("/api/projects", json={"title": "Fleet Battery Swap"})
    assert created.status_code == 201
    assert config.database_path.exists()

    with sqlite3.connect(config.database_path) as connection:
        project_count = connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        assert project_count >= 1


def test_delete_project_endpoint_removes_project(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Delete Me"}).get_json()["data"]
    project_id = created["project_id"]

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["data"]["project_id"] == project_id

    missing = client.get(f"/api/projects/{project_id}")
    assert missing.status_code == 404