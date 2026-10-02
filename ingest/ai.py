"""Summaries and embeddings via Azure OpenAI (REST). Both are optional."""

import asyncio

import httpx

from .config import IngestSettings


class AzureOpenAI:
    def __init__(self, s: IngestSettings):
        self.s = s
        self.enabled = bool(s.aoai_endpoint and s.aoai_key)
        self.client = httpx.AsyncClient(timeout=60, headers={"api-key": s.aoai_key or ""})

    def _url(self, deployment: str, op: str) -> str:
        base = (self.s.aoai_endpoint or "").rstrip("/")
        return f"{base}/openai/deployments/{deployment}/{op}?api-version={self.s.aoai_api_version}"

    async def _post(self, url: str, body: dict) -> dict:
        for attempt in range(5):
            r = await self.client.post(url, json=body)
            if r.status_code in (429, 500, 502, 503):
                await asyncio.sleep(2**attempt)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return r.json()

    async def summarize(self, prompt: str, text: str) -> str:
        if not self.enabled:
            return ""
        data = await self._post(
            self._url(self.s.aoai_chat_deployment, "chat/completions"),
            {
                "messages": [
                    {"role": "system", "content": prompt + " Answer in 3-5 sentences."},
                    {"role": "user", "content": text[:12000]},
                ],
                "temperature": 0.1,
            },
        )
        return data["choices"][0]["message"]["content"].strip()

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not (self.enabled and self.s.aoai_embed_deployment):
            return None
        data = await self._post(
            self._url(self.s.aoai_embed_deployment, "embeddings"),
            {"input": [t[:8000] for t in texts]},
        )
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]

    async def aclose(self) -> None:
        await self.client.aclose()
