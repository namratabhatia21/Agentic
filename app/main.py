"""HTTP API: chat over Server-Sent Events, conversation history, health and metrics."""

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
import httpx
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app import db, metrics
from app.agent import Agent
from app.config import Settings, get_settings
from app.llm import build_client
from app.logging_setup import configure_logging
from app.tools import ALL_TOOLS, ToolContext

log = logging.getLogger("agentic")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.llm = build_client(settings)
    app.state.http = httpx.AsyncClient(
        timeout=settings.tool_http_timeout,
        headers={"User-Agent": "agentic-chatbot/0.1 (+https://github.com/namratabhatia21/agentic)"},
        follow_redirects=True,
    )
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    app.state.db = await db.create_pool(settings.database_url, min_size=1, max_size=10)
    await db.migrate(app.state.db)
    try:
        app.state.readonly_db = await db.create_pool(
            settings.readonly_database_url, min_size=1, max_size=5
        )
    except Exception:
        # The analytics role is created by db/init; without it only the SQL tools degrade.
        log.warning("read-only analytics database unavailable; SQL tools disabled")
        app.state.readonly_db = None
    log.info("started provider=%s model=%s", settings.llm_provider, settings.model_id)
    try:
        yield
    finally:
        if app.state.readonly_db is not None:
            await app.state.readonly_db.close()
        await app.state.db.close()
        await app.state.redis.aclose()
        await app.state.http.aclose()


app = FastAPI(title="Agentic", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- dependencies -------------------------------------------------------------


async def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    settings: Settings = request.app.state.settings
    if settings.api_key_set:
        if x_api_key not in settings.api_key_set:
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
        return x_api_key
    return request.client.host if request.client else "anonymous"


async def rate_limit(request: Request, principal: str = Depends(require_api_key)) -> str:
    settings: Settings = request.app.state.settings
    key = f"ratelimit:{principal}"
    try:
        count = await request.app.state.redis.incr(key)
        if count == 1:
            await request.app.state.redis.expire(key, 60)
    except Exception:  # fail open if Redis is down; the request still works
        log.warning("rate limiter unavailable")
        return principal
    if count > settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, retry in a minute")
    return principal


# --- routes -------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: uuid.UUID | None = None


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request, _: str = Depends(rate_limit)):
    state = request.app.state
    conversation_id, _created = await db.ensure_conversation(
        state.db, body.conversation_id, body.message
    )
    if conversation_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    lock_key = f"lock:conversation:{conversation_id}"
    if not await state.redis.set(lock_key, "1", nx=True, ex=600):
        raise HTTPException(status_code=409, detail="A reply is already in progress")

    history = await db.load_history(state.db, conversation_id)
    ctx = ToolContext(
        settings=state.settings,
        http=state.http,
        redis=state.redis,
        db=state.db,
        readonly_db=state.readonly_db,
    )
    agent = Agent(state.llm, state.settings, ctx)

    async def event_stream():
        new_messages: list[dict] = []
        outcome = "error"
        try:
            yield sse({"type": "conversation", "id": str(conversation_id)})
            async for event in agent.run(history, body.message, new_messages):
                if event["type"] == "done":
                    await db.append_messages(state.db, conversation_id, new_messages)
                    outcome = "ok"
                elif event["type"] == "refusal":
                    outcome = "refusal"
                yield sse(event)
        except anthropic.RateLimitError:
            yield sse({"type": "error", "message": "Model rate limit hit, try again shortly."})
        except anthropic.APIStatusError as e:
            log.error("anthropic api error status=%s body=%s", e.status_code, e.message)
            yield sse({"type": "error", "message": f"Model API error ({e.status_code})."})
        except anthropic.APIConnectionError:
            yield sse({"type": "error", "message": "Could not reach the model API."})
        except Exception:
            log.exception("chat turn failed")
            yield sse({"type": "error", "message": "Internal error."})
        finally:
            metrics.HTTP_REQUESTS.labels(outcome=outcome).inc()
            await state.redis.delete(lock_key)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, request: Request, _: str = Depends(require_api_key)
):
    """Return the conversation as plain user/assistant text for display."""
    history = await db.load_history(request.app.state.db, conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")
    out = []
    for m in history:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "text": m["content"]})
            continue
        text = "".join(b.get("text", "") for b in m["content"] if b.get("type") == "text")
        if text:
            out.append({"role": m["role"], "text": text})
    return {"id": str(conversation_id), "messages": out}


@app.get("/api/tools")
async def list_tools(request: Request):
    from app.llm import server_tools

    return {
        "client_tools": [{"name": t.name, "description": t.description} for t in ALL_TOOLS],
        "server_tools": [t["name"] for t in server_tools(request.app.state.settings)],
        "provider": request.app.state.settings.llm_provider,
        "model": request.app.state.settings.model_id,
    }


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request):
    checks = {}
    try:
        await request.app.state.db.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {type(e).__name__}"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
    ok = all(v == "ok" for v in checks.values())
    return Response(
        content=json.dumps({"status": "ok" if ok else "degraded", "checks": checks}),
        media_type="application/json",
        status_code=200 if ok else 503,
    )


@app.get("/metrics")
async def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
