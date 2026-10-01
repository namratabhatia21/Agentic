"""Sentence embeddings from a Hugging Face model, for semantic knowledge-base search.

Backends, in order of preference:
1. EMBEDDINGS_URL - a self-hosted Text Embeddings Inference (TEI) server. Free, private,
   runs on CPU; docker-compose starts one with BAAI/bge-small-en-v1.5.
2. HF_TOKEN       - the same model served by Hugging Face Inference Providers.
"""

import logging

import numpy as np
from huggingface_hub import AsyncInferenceClient

from app.config import Settings

log = logging.getLogger(__name__)

MAX_CHARS = 2000  # ~512 tokens, the context of small bge/e5 models


class Embedder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: AsyncInferenceClient | None = None
        self.model: str | None = None
        if settings.embeddings_url:
            self.client = AsyncInferenceClient(timeout=30)
            self.model = settings.embeddings_url.rstrip("/") + "/embed"
        elif settings.hf_token:
            self.client = AsyncInferenceClient(provider="hf-inference", api_key=settings.hf_token)
            self.model = settings.embedding_model

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def embed(self, text: str, *, query: bool = False) -> list[float]:
        if self.client is None:
            raise RuntimeError("embeddings are not configured")
        if query:
            text = self.settings.embedding_query_prefix + text
        vector = np.asarray(
            await self.client.feature_extraction(text[:MAX_CHARS], model=self.model),
            dtype=np.float32,
        )
        if vector.ndim > 1:  # [[...]] for a single input, or per-token vectors
            vector = vector.reshape(-1, vector.shape[-1]).mean(axis=0)
        if vector.shape[-1] != self.settings.embedding_dim:
            raise RuntimeError(
                f"embedding has {vector.shape[-1]} dims, EMBEDDING_DIM is "
                f"{self.settings.embedding_dim}"
            )
        norm = float(np.linalg.norm(vector)) or 1.0
        return (vector / norm).tolist()


def to_pgvector(vector: list[float]) -> str:
    """pgvector text literal, passed as a parameter and cast with ::vector."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
