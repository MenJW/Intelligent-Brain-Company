from __future__ import annotations

import json
import sqlite3

from intelligent_brain_company.config import AppConfig
from intelligent_brain_company.domain.project_state import TaskRecord


class TaskStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.config.ensure_directories()
        self._initialize_database()
        self._import_legacy_files()

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return TaskRecord.from_dict(json.loads(row[0]))

    def save_task(self, task: TaskRecord) -> TaskRecord:
        payload = json.dumps(task.to_dict(), ensure_ascii=False, indent=2)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (task_id, project_id, updated_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (task.task_id, task.project_id, task.updated_at, payload),
            )
            connection.commit()
        return task

    def list_tasks_for_project(self, project_id: str) -> list[TaskRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM tasks WHERE project_id = ? ORDER BY updated_at ASC",
                (project_id,),
            ).fetchall()
        return [TaskRecord.from_dict(json.loads(row[0])) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _import_legacy_files(self) -> None:
        with self._connect() as connection:
            has_rows = connection.execute("SELECT 1 FROM tasks LIMIT 1").fetchone()
            if has_rows is not None:
                return

        for path in sorted(self.config.tasks_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.save_task(TaskRecord.from_dict(data))