from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_MODEL_BY_SYSTEM = "qwen2.5-coder:7b"


class Settings(BaseSettings):
    app_name: str = "Arynox AI"
    app_version: str = "0.1.0"

    database_url: str = f"sqlite:///{BASE_DIR / 'arynox.db'}"

    ai_provider: str = "ollama"
    ai_model: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    github_token: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = DEFAULT_MODEL_BY_SYSTEM
    ollama_auto_pull: bool = True
    ollama_default_model: str = ""

    default_permission_mode: str = "ask"

    projects_root: str = "../projects"

    mcp_servers: str = "{}"

    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def projects_root_path(self) -> Path:
        p = Path(self.projects_root)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p.resolve()

    @property
    def effective_default_model(self) -> str:
        if self.ai_model:
            return self.ai_model
        if self.ai_provider == "ollama":
            return self.ollama_model or self.ollama_default_model or DEFAULT_MODEL_BY_SYSTEM
        if self.ai_provider == "openai":
            return self.openai_model
        if self.ai_provider == "openrouter":
            return self.openrouter_model
        return DEFAULT_MODEL_BY_SYSTEM

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
