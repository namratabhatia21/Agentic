"""Ingestion settings, loaded from environment variables (prefix INGEST_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="INGEST_", extra="ignore")

    redis_url: str = "redis://localhost:6379/1"
    queue_name: str = "ingest:queue"

    blob_connection_string: str | None = None  # Azurite works for local dev
    blob_container: str = "ingest"

    es_url: str = "http://localhost:9200"
    es_api_key: str | None = None

    azure_search_endpoint: str | None = None  # https://<svc>.search.windows.net
    azure_search_key: str | None = None
    azure_search_api_version: str = "2024-07-01"

    # Azure OpenAI for summaries + embeddings; leave unset to skip both
    aoai_endpoint: str | None = None
    aoai_key: str | None = None
    aoai_api_version: str = "2024-10-21"
    aoai_chat_deployment: str = "gpt-4o-mini"
    aoai_embed_deployment: str | None = None
    embed_dims: int = 1536
    summary_batch_size: int = 10

    # "versioned": new {prefix}-{YYYYMMDD} index per run + alias swap; "upsert": into current
    index_mode: str = "versioned"
    run_inline: bool = False  # True: process in the request (no worker needed)


@lru_cache
def get_settings() -> IngestSettings:
    return IngestSettings()
