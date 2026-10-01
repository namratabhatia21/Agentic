"""Tool framework: each tool is a typed input model plus an async handler."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings


@dataclass
class ToolContext:
    settings: Settings
    http: httpx.AsyncClient
    redis: Any | None = None  # redis.asyncio.Redis
    db: Any | None = None  # asyncpg.Pool (read/write, app role)
    readonly_db: Any | None = None  # asyncpg.Pool (SELECT-only role)

    async def cached_get_json(self, url: str, params: dict | None = None) -> Any:
        """GET a JSON URL, caching the body in Redis for tool_cache_ttl seconds."""
        text = await self.cached_get_text(url, params)
        return json.loads(text)

    async def cached_get_text(self, url: str, params: dict | None = None) -> str:
        key = (
            "toolcache:"
            + hashlib.sha256((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        )
        if self.redis is not None:
            try:
                hit = await self.redis.get(key)
                if hit is not None:
                    return hit
            except Exception:  # cache is best-effort
                pass
        resp = await self.http.get(url, params=params)
        resp.raise_for_status()
        if self.redis is not None:
            try:
                await self.redis.set(key, resp.text, ex=self.settings.tool_cache_ttl)
            except Exception:
                pass
        return resp.text


class ToolError(Exception):
    """An expected failure whose message is safe to show the model."""


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], Awaitable[str]]

    def definition(self) -> dict:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        schema["additionalProperties"] = False
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
            # Stream tool inputs as they are generated. The API no longer validates
            # them, so run() validates against the pydantic model before executing.
            "eager_input_streaming": True,
        }

    async def run(self, raw_input: Any, ctx: ToolContext) -> tuple[str, bool]:
        """Returns (content, is_error)."""
        if not isinstance(raw_input, dict):
            return f"Invalid input: expected an object, got {type(raw_input).__name__}", True
        try:
            parsed = self.input_model.model_validate(raw_input)
        except ValidationError as e:
            return f"Invalid input: {e.errors(include_url=False)}", True
        try:
            return await self.handler(parsed, ctx), False
        except ToolError as e:
            return str(e), True
        except httpx.HTTPError as e:
            return f"Upstream request failed: {type(e).__name__}: {e}", True
