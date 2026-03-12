from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8000
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 45

    @classmethod
    def from_env(cls) -> "AppConfig":
        data_dir = Path(os.getenv("IBC_DATA_DIR", ".data")).resolve()
        host = os.getenv("IBC_HOST", "127.0.0.1")
        port = int(os.getenv("IBC_PORT", "8000"))
        llm_api_key = os.getenv("IBC_LLM_API_KEY", "")
        llm_base_url = os.getenv("IBC_LLM_BASE_URL", "")
        llm_model = os.getenv("IBC_LLM_MODEL", "")
        llm_timeout_seconds = int(os.getenv("IBC_LLM_TIMEOUT_SECONDS", "45"))
        return cls(
            data_dir=data_dir,
            host=host,
            port=port,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_timeout_seconds=llm_timeout_seconds,
        )

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def tasks_dir(self) -> Path:
        return self.data_dir / "tasks"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "ibc.sqlite3"

    def ensure_directories(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)