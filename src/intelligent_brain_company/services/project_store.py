from __future__ import annotations

import json
import sqlite3

from intelligent_brain_company.config import AppConfig
from intelligent_brain_company.domain.project_state import ProjectRecord


class ProjectStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.config.ensure_directories()
        self._initialize_database()
        self._import_legacy_files()

    def list_projects(self) -> list[ProjectRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [ProjectRecord.from_dict(json.loads(row[0])) for row in rows]

    def get_project(self, project_id: str) -> ProjectRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return ProjectRecord.from_dict(json.loads(row[0]))

    def save_project(self, project: ProjectRecord) -> ProjectRecord:
        payload = json.dumps(project.to_dict(), ensure_ascii=False, indent=2)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (project_id, updated_at, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (project.project_id, project.updated_at, payload),
            )
            connection.commit()
        return project

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _import_legacy_files(self) -> None:
        with self._connect() as connection:
            has_rows = connection.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
            if has_rows is not None:
                return

        for path in sorted(self.config.projects_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.save_project(ProjectRecord.from_dict(data))