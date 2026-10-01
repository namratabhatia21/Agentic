"""Conversation storage in PostgreSQL."""

import json
import logging
import uuid

import asyncpg

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          uuid PRIMARY KEY,
    title       text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id               bigserial PRIMARY KEY,
    conversation_id  uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             text NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content          jsonb NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages (conversation_id, id);

CREATE TABLE IF NOT EXISTS documents (
    id          bigserial PRIMARY KEY,
    title       text NOT NULL,
    content     text NOT NULL,
    source      text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    search      tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', content), 'B')
    ) STORED
);
CREATE INDEX IF NOT EXISTS documents_search_idx ON documents USING gin (search);

-- "anthropic" = Claude content blocks, "openai" = chat-completions messages (HF models).
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS format text NOT NULL DEFAULT 'anthropic';
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_role_check;
ALTER TABLE messages ADD CONSTRAINT messages_role_check
    CHECK (role IN ('user', 'assistant', 'tool'));

CREATE TABLE IF NOT EXISTS images (
    id          uuid PRIMARY KEY,
    prompt      text NOT NULL,
    model       text NOT NULL,
    png         bytea NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
"""

# Semantic search needs the pgvector extension (pgvector/pgvector image, Cloud SQL,
# RDS and most managed Postgres offer it).
VECTOR_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding vector({dim});
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops);
"""


class ConversationFormatError(Exception):
    """The conversation was created by a provider with a different message format."""


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(dsn: str, **kw) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, init=_init_conn, **kw)


async def migrate(pool: asyncpg.Pool, embedding_dim: int) -> bool:
    """Create/upgrade tables. Returns True if vector search is available."""
    async with pool.acquire() as conn:
        # Serialise concurrent replicas running the migration at startup.
        await conn.execute("SELECT pg_advisory_lock(727274)")
        try:
            await conn.execute(SCHEMA)
            try:
                async with conn.transaction():
                    await conn.execute(VECTOR_SCHEMA.format(dim=int(embedding_dim)))
                return True
            except asyncpg.PostgresError as e:
                log.warning("pgvector unavailable, keyword search only: %s", e)
                return False
        finally:
            await conn.execute("SELECT pg_advisory_unlock(727274)")


async def ensure_conversation(
    pool: asyncpg.Pool, conversation_id: uuid.UUID | None, title: str, fmt: str
):
    """Returns the conversation id (creating one if needed) or None if it does not exist."""
    if conversation_id is None:
        conversation_id = uuid.uuid4()
        await pool.execute(
            "INSERT INTO conversations (id, title, format) VALUES ($1, $2, $3)",
            conversation_id,
            title[:120],
            fmt,
        )
        return conversation_id
    existing = await pool.fetchval(
        "SELECT format FROM conversations WHERE id = $1", conversation_id
    )
    if existing is None:
        return None
    if existing != fmt:
        raise ConversationFormatError(existing)
    return conversation_id


async def load_history(pool: asyncpg.Pool, conversation_id: uuid.UUID) -> list[dict]:
    """Messages in the stored format.

    Claude conversations store each message's content blocks; HF (chat-completions)
    conversations store the whole message dict, since it carries tool_calls etc.
    """
    rows = await pool.fetch(
        "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY id",
        conversation_id,
    )
    out = []
    for r in rows:
        c = r["content"]
        if isinstance(c, dict) and "role" in c:
            out.append(c)
        else:
            out.append({"role": r["role"], "content": c})
    return out


async def append_messages(
    pool: asyncpg.Pool, conversation_id: uuid.UUID, messages: list[dict]
) -> None:
    async with pool.acquire() as conn, conn.transaction():
        await conn.executemany(
            "INSERT INTO messages (conversation_id, role, content) VALUES ($1, $2, $3)",
            [(conversation_id, m["role"], _stored(m)) for m in messages],
        )
        await conn.execute(
            "UPDATE conversations SET updated_at = now() WHERE id = $1", conversation_id
        )


def _stored(message: dict):
    # Anthropic-format messages are exactly {role, content}; anything richer
    # (chat-completions tool_calls / tool_call_id) is stored whole.
    if set(message) == {"role", "content"}:
        return message["content"]
    return message


async def save_image(pool: asyncpg.Pool, prompt: str, model: str, png: bytes) -> uuid.UUID:
    image_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO images (id, prompt, model, png) VALUES ($1, $2, $3, $4)",
        image_id,
        prompt,
        model,
        png,
    )
    return image_id


async def backfill_embeddings(pool: asyncpg.Pool, embedder, limit: int = 1000) -> int:
    """Embed documents saved while the embedding service was unavailable."""
    from app.embeddings import to_pgvector

    rows = await pool.fetch(
        "SELECT id, title, content FROM documents WHERE embedding IS NULL ORDER BY id LIMIT $1",
        limit,
    )
    done = 0
    for r in rows:
        try:
            vec = await embedder.embed(f"{r['title']}\n{r['content']}")
        except Exception as e:
            log.warning("embedding backfill stopped: %s", e)
            break
        await pool.execute(
            "UPDATE documents SET embedding = $1::vector WHERE id = $2", to_pgvector(vec), r["id"]
        )
        done += 1
    return done
