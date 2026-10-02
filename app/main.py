"""HTTP API: chat over Server-Sent Events, conversation history, health and metrics."""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
import httpx
import httpx2
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from huggingface_hub.errors import HfHubHTTPError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app import db, metrics
from app.agent import Agent
from app.config import Settings, get_settings
from app.embeddings import Embedder
from app.hf_agent import HFAgent
from app.llm import (
    ProviderNotConfigured,
    build_client,
    build_hf_client,
    conversation_format,
    model_name,
    server_tools,
)
from app.logging_setup import configure_logging
from app.tools import ToolContext, available_tools
from app.tools.knowledge import add_document

log = logging.getLogger("agentic")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    try:
        app.state.llm = build_client(settings)
        app.state.llm_error = None
    except ProviderNotConfigured as e:
        # Start anyway so health checks, the UI and the knowledge base work;
        # chat requests explain what to configure.
        log.error("%s", e)
        app.state.llm, app.state.llm_error = None, str(e)
    app.state.http = httpx.AsyncClient(
        timeout=settings.tool_http_timeout,
        headers={"User-Agent": "agentic-chatbot/0.1 (+https://github.com/namratabhatia21/agentic)"},
        follow_redirects=True,
    )
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    app.state.hf = build_hf_client(settings)
    app.state.db = await db.create_pool(settings.database_url, min_size=1, max_size=10)
    vector_ok = await db.migrate(app.state.db, settings.embedding_dim)
    embedder = Embedder(settings)
    app.state.embedder = embedder if (vector_ok and embedder.enabled) else None
    if app.state.embedder is not None:
        app.state.backfill = asyncio.create_task(_backfill(app.state.db, app.state.embedder))
    try:
        app.state.readonly_db = await db.create_pool(
            settings.readonly_database_url, min_size=1, max_size=5
        )
    except Exception:
        # The analytics role is created by db/init; without it only the SQL tools degrade.
        log.warning("read-only analytics database unavailable; SQL tools disabled")
        app.state.readonly_db = None
    log.info(
        "started provider=%s model=%s semantic_search=%s",
        settings.llm_provider,
        model_name(settings),
        app.state.embedder is not None,
    )
    try:
        yield
    finally:
        if app.state.readonly_db is not None:
            await app.state.readonly_db.close()
        await app.state.db.close()
        await app.state.redis.aclose()
        await app.state.http.aclose()


async def _backfill(pool, embedder) -> None:
    # Give the embeddings server time to load its model on a cold start.
    for delay in (0, 15, 30, 60, 120):
        await asyncio.sleep(delay)
        try:
            done = await db.backfill_embeddings(pool, embedder)
            log.info("embedding backfill: %d documents", done)
            return
        except Exception as e:
            log.warning("embedding backfill failed: %s", e)


def tool_context(state) -> ToolContext:
    return ToolContext(
        settings=state.settings,
        http=state.http,
        redis=state.redis,
        db=state.db,
        readonly_db=state.readonly_db,
        hf=state.hf,
        embedder=state.embedder,
    )


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
    if state.llm is None:
        raise HTTPException(status_code=503, detail=state.llm_error)
    fmt = conversation_format(state.settings)
    try:
        conversation_id = await db.ensure_conversation(
            state.db, body.conversation_id, body.message, fmt
        )
    except db.ConversationFormatError as e:
        raise HTTPException(
            status_code=409,
            detail=f"This conversation was created with a different model provider ({e}); "
            "start a new chat.",
        ) from e
    if conversation_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    lock_key = f"lock:conversation:{conversation_id}"
    if not await state.redis.set(lock_key, "1", nx=True, ex=600):
        raise HTTPException(status_code=409, detail="A reply is already in progress")

    history = await db.load_history(state.db, conversation_id)
    agent_cls = HFAgent if fmt == "openai" else Agent
    agent = agent_cls(state.llm, state.settings, tool_context(state))

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
        except HfHubHTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            log.error("hugging face error status=%s: %s", status, e)
            yield sse({"type": "error", "message": f"Hugging Face API error ({status})."})
        except httpx2.TransportError:
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
        if m["role"] not in ("user", "assistant"):
            continue
        content = m.get("content")
        if isinstance(content, str):
            text = content
        else:
            text = "".join(b.get("text", "") for b in content or [] if b.get("type") == "text")
        if text:
            out.append({"role": m["role"], "text": text})
    return {"id": str(conversation_id), "messages": out}


class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200_000)
    source: str = ""


@app.post("/api/documents", status_code=201)
async def add_documents(
    docs: list[DocumentIn], request: Request, _: str = Depends(require_api_key)
):
    """Bulk-load the knowledge base. Long texts are split into ~1500-character chunks."""
    if len(docs) > 200:
        raise HTTPException(status_code=413, detail="At most 200 documents per request")
    ctx = tool_context(request.app.state)
    ids = []
    for doc in docs:
        chunks = _chunk(doc.content)
        for i, chunk in enumerate(chunks, 1):
            title = doc.title if len(chunks) == 1 else f"{doc.title} (part {i}/{len(chunks)})"
            ids.append(await add_document(ctx, title, chunk, doc.source))
    return {"ids": ids, "semantic": request.app.state.embedder is not None}


def _chunk(text: str, size: int = 1500) -> list[str]:
    paragraphs, chunks, current = text.split("\n\n"), [], ""
    for p in paragraphs:
        while len(p) > size:  # hard-split very long paragraphs
            if current:
                chunks.append(current)
                current = ""
            chunks.append(p[:size])
            p = p[size:]
        if current and len(current) + len(p) + 2 > size:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current.strip():
        chunks.append(current)
    return chunks or [text]


@app.get("/api/images/{image_id}.png")
async def get_image(image_id: uuid.UUID, request: Request):
    # Image ids are random UUIDs, so links are unguessable (the browser <img> tag
    # can't send X-API-Key).
    png = await request.app.state.db.fetchval("SELECT png FROM images WHERE id = $1", image_id)
    if png is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        png, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"}
    )


@app.get("/api/tools")
async def list_tools(request: Request):
    state = request.app.state
    settings = state.settings
    return {
        "client_tools": [
            {"name": t.name, "description": t.description} for t in available_tools(settings)
        ],
        "server_tools": [t["name"] for t in server_tools(settings)],
        "provider": settings.llm_provider,
        "model": model_name(settings),
        "open_source": settings.uses_open_model,
        "configured": state.llm is not None,
        "semantic_search": state.embedder is not None,
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
