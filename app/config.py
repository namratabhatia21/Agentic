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
    # "huggingface": an open-weight model (Qwen, Llama, ...) via Hugging Face Inference Providers
    llm_provider: Literal["anthropic", "vertex", "bedrock", "huggingface"] = "anthropic"
    model: str = "claude-opus-5-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    max_tokens: int = 64000
    max_agent_steps: int = 12

    anthropic_api_key: str | None = None
    gcp_project_id: str | None = None
    gcp_region: str = "global"
    aws_region: str = "us-east-1"

    # --- Hugging Face ----------------------------------------------------------
    # One token (hf.co/settings/tokens, "Make calls to Inference Providers") enables the
    # open-weight chat model, hosted embeddings and the HF tools (image generation,
    # classification). Hub search works without it.
    hf_token: str | None = None
    hf_provider: str = "auto"  # or pin one: "together", "groq", "fireworks-ai", ...
    hf_chat_model: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"
    hf_max_tokens: int = 4096
    hf_image_model: str = "black-forest-labs/FLUX.1-schnell"
    hf_sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    hf_zero_shot_model: str = "facebook/bart-large-mnli"

    # Embeddings for semantic knowledge-base search. EMBEDDINGS_URL points at a
    # Text Embeddings Inference server (the `embeddings` compose service). If it is
    # unset but HF_TOKEN is set, EMBEDDING_MODEL is called on Hugging Face instead.
    embeddings_url: str | None = None
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    # bge models expect this instruction in front of search queries (not documents).
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "

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
