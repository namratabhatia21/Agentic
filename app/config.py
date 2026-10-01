"""Application settings, loaded from environment variables (see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider -------------------------------------------------------
    # "anthropic": Claude API (billed to Anthropic Console credits)
    # "vertex":    Claude on Google Cloud Vertex AI (billed to your GCP account)
    # "bedrock":   Claude on Amazon Bedrock (billed to your AWS account)
    llm_provider: Literal["anthropic", "vertex", "bedrock"] = "anthropic"
    model: str = "claude-opus-5-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    max_tokens: int = 64000
    max_agent_steps: int = 12

    anthropic_api_key: str | None = None
    gcp_project_id: str | None = None
    gcp_region: str = "global"
    aws_region: str = "us-east-1"

    # --- Infrastructure -----------------------------------------------------
    database_url: str = "postgresql://agentic:agentic@localhost:5432/agentic"
    readonly_database_url: str = "postgresql://agent_readonly:agent_readonly@localhost:5432/agentic"
    redis_url: str = "redis://localhost:6379/0"

    # --- API ----------------------------------------------------------------
    # Comma-separated list of accepted X-API-Key values. Empty = auth disabled.
    api_keys: str = ""
    rate_limit_per_minute: int = 20
    cors_origins: str = "*"
    log_level: str = "INFO"

    tool_http_timeout: float = Field(default=15.0, description="Seconds per outbound tool call")
    tool_cache_ttl: int = 300

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def model_id(self) -> str:
        # Bedrock model IDs carry an "anthropic." prefix; the others use the bare ID.
        if self.llm_provider == "bedrock" and not self.model.startswith("anthropic."):
            return f"anthropic.{self.model}"
        return self.model


@lru_cache
def get_settings() -> Settings:
    return Settings()
