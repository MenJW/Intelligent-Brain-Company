from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_defaults() -> dict[str, str]:
    """Load key-value pairs from a local .env file.

    Values from real process environment still take precedence.
    """
    root = Path.cwd()
    env_path = root / ".env"
    if not env_path.exists():
        return {}

    defaults: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            defaults[key] = value
    return defaults


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
        dotenv_defaults = _load_dotenv_defaults()

        data_dir = Path(os.getenv("IBC_DATA_DIR", dotenv_defaults.get("IBC_DATA_DIR", ".data"))).resolve()
        host = os.getenv("IBC_HOST", dotenv_defaults.get("IBC_HOST", "127.0.0.1"))
        port = int(os.getenv("IBC_PORT", dotenv_defaults.get("IBC_PORT", "8000")))
        llm_api_key = os.getenv("IBC_LLM_API_KEY", dotenv_defaults.get("IBC_LLM_API_KEY", ""))
        llm_base_url = os.getenv("IBC_LLM_BASE_URL", dotenv_defaults.get("IBC_LLM_BASE_URL", ""))
        llm_model = os.getenv("IBC_LLM_MODEL", dotenv_defaults.get("IBC_LLM_MODEL", ""))
        llm_timeout_seconds = int(
            os.getenv("IBC_LLM_TIMEOUT_SECONDS", dotenv_defaults.get("IBC_LLM_TIMEOUT_SECONDS", "45"))
        )
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