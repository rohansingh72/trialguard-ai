from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ollama_model: str
    ollama_base_url: str
    log_level: str
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.getenv("TRIALGUARD_DATA_DIR", ".trialguard")),
            ollama_model=os.getenv("TRIALGUARD_OLLAMA_MODEL", "llama3.2:3b"),
            ollama_base_url=os.getenv(
                "TRIALGUARD_OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ),
            log_level=os.getenv("TRIALGUARD_LOG_LEVEL", "INFO").upper(),
            api_host=os.getenv("TRIALGUARD_API_HOST", "0.0.0.0"),
            api_port=_env_int("TRIALGUARD_API_PORT", 8000),
        )
