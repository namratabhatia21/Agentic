"""Model client factory.

Claude can be reached through three backends, so you can pay with whichever credits
you have: Anthropic Console (Claude API), Google Cloud (Vertex AI) or AWS (Bedrock).
LLM_PROVIDER=huggingface instead runs an open-weight model through Hugging Face
Inference Providers.
"""

from typing import Any

import anthropic
from huggingface_hub import AsyncInferenceClient

from app.config import Settings


def build_client(settings: Settings) -> Any:
    if settings.llm_provider == "huggingface":
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN is required when LLM_PROVIDER=huggingface")
        return build_hf_client(settings)
    if settings.llm_provider == "vertex":
        if not settings.gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID is required when LLM_PROVIDER=vertex")
        # Auth: Application Default Credentials (gcloud auth / attached service account)
        return anthropic.AsyncAnthropicVertex(
            project_id=settings.gcp_project_id, region=settings.gcp_region
        )
    if settings.llm_provider == "bedrock":
        # Auth: standard AWS credential chain (env vars, profile, IAM role)
        return anthropic.AsyncAnthropicBedrockMantle(aws_region=settings.aws_region)
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def server_tools(settings: Settings) -> list[dict]:
    """Anthropic-hosted tools: Claude runs these itself, no code on our side."""
    if settings.llm_provider == "anthropic":
        return [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
        ]
    if settings.llm_provider == "vertex":
        # Vertex offers only the basic web search variant and no web fetch.
        return [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
    # Bedrock and open models have no server-side web tools; client tools cover live data.
    return []


def request_extras(settings: Settings) -> dict:
    """Provider-specific request options."""
    if settings.llm_provider == "anthropic":
        # On a safety-classifier refusal, re-run the request on Anthropic's recommended
        # fallback model instead of returning the refusal. Claude API only.
        return {
            "betas": ["server-side-fallback-2026-07-01"],
            "extra_body": {"fallbacks": "default"},
        }
    return {}


def build_hf_client(settings: Settings) -> AsyncInferenceClient | None:
    """Client for Hugging Face Inference Providers (chat, images, classification)."""
    if not settings.hf_token:
        return None
    return AsyncInferenceClient(
        provider=settings.hf_provider, api_key=settings.hf_token, timeout=120
    )


def conversation_format(settings: Settings) -> str:
    return "openai" if settings.llm_provider == "huggingface" else "anthropic"


def model_name(settings: Settings) -> str:
    if settings.llm_provider == "huggingface":
        return settings.hf_chat_model
    return settings.model_id
