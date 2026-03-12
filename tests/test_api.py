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
    assert payload["project"]["latest_plan_markdown"]


def test_intervention_creates_new_plan_version(tmp_path: Path) -> None:
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
    project = revised.get_json()["data"]["project"]
    assert len(project["plans"]) == 2
    assert len(project["interventions"]) == 1


def test_timeline_progress_and_diff_endpoints(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()

    created = client.post("/api/projects", json={"title": "Warehouse Shuttle"}).get_json()["data"]
    project_id = created["project_id"]
    client.post("/api/planning/generate", json={"project_id": project_id})
    second = client.post(
        "/api/planning/interventions",
        json={
            "project_id": project_id,
            "stage": "board",
            "speaker": "founder",
            "message": "Reduce capital intensity.",
            "impact": "favor phased rollout and smaller pilot",
        },
    ).get_json()["data"]["project"]

    progress = client.get(f"/api/projects/{project_id}/progress")
    assert progress.status_code == 200
    assert progress.get_json()["data"]["stages"]

    timeline = client.get(f"/api/projects/{project_id}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.get_json()["data"]) >= 3

    version_ids = [item["version_id"] for item in second["plans"]]
    diff = client.get(f"/api/projects/{project_id}/plans/diff?from={version_ids[0]}&to={version_ids[1]}")
    assert diff.status_code == 200
    assert "diff" in diff.get_json()["data"]


def test_console_page_is_served(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Intelligent Brain Company" in response.data


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
    assert payload["history"][0]["agent"] == "research"

    history = client.get(f"/api/projects/{project_id}/chat?agent=research")
    assert history.status_code == 200
    assert len(history.get_json()["data"]["history"]) == 1


def test_chat_turn_can_be_promoted_to_intervention_and_regenerated(tmp_path: Path) -> None:
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
    project = promoted.get_json()["data"]["project"]
    assert len(project["interventions"]) == 1
    assert len(project["plans"]) == 2


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