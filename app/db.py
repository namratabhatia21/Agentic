"""Conversation storage in PostgreSQL."""

import json
import uuid

import asyncpg

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
    role             text NOT NULL CHECK (role IN ('user', 'assistant')),
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
"""


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(dsn: str, **kw) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, init=_init_conn, **kw)


async def migrate(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        # Serialise concurrent replicas running the migration at startup.
        await conn.execute("SELECT pg_advisory_lock(727274)")
        try:
            await conn.execute(SCHEMA)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(727274)")


async def ensure_conversation(pool: asyncpg.Pool, conversation_id: uuid.UUID | None, title: str):
    if conversation_id is None:
        conversation_id = uuid.uuid4()
        await pool.execute(
            "INSERT INTO conversations (id, title) VALUES ($1, $2)", conversation_id, title[:120]
        )
        return conversation_id, True
    exists = await pool.fetchval("SELECT 1 FROM conversations WHERE id = $1", conversation_id)
    if not exists:
        return None, False
    return conversation_id, False


async def load_history(pool: asyncpg.Pool, conversation_id: uuid.UUID) -> list[dict]:
    rows = await pool.fetch(
        "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY id",
        conversation_id,
    )
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def append_messages(
    pool: asyncpg.Pool, conversation_id: uuid.UUID, messages: list[dict]
) -> None:
    async with pool.acquire() as conn, conn.transaction():
        await conn.executemany(
            "INSERT INTO messages (conversation_id, role, content) VALUES ($1, $2, $3)",
            [(conversation_id, m["role"], m["content"]) for m in messages],
        )
        await conn.execute(
            "UPDATE conversations SET updated_at = now() WHERE id = $1", conversation_id
        )
