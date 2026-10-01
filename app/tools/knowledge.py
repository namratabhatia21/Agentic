"""Knowledge base: hybrid semantic (Hugging Face embeddings + pgvector) and keyword search."""

import logging

from pydantic import BaseModel, Field

from app.embeddings import to_pgvector
from app.tools.base import Tool, ToolContext, ToolError

log = logging.getLogger(__name__)

# Match ANY (stemmed) query term; ranking decides relevance.
TSQUERY = (
    "to_tsquery('english', array_to_string(tsvector_to_array(to_tsvector('english', $1)), ' | '))"
)

KEYWORD_SQL = f"""
SELECT d.id, d.title, d.source, d.created_at,
       ts_headline('english', d.content, q, 'MaxWords=60, MinWords=20') AS snippet
FROM documents d, {TSQUERY} q
WHERE d.search @@ q
ORDER BY ts_rank(d.search, q) DESC
LIMIT $2
"""

# Reciprocal-rank fusion of keyword and vector rankings: robust without score tuning.
HYBRID_SQL = f"""
WITH q AS (SELECT {TSQUERY} AS tsq),
keyword AS (
    SELECT d.id, row_number() OVER (ORDER BY ts_rank(d.search, q.tsq) DESC) AS rnk
    FROM documents d, q WHERE d.search @@ q.tsq
    ORDER BY ts_rank(d.search, q.tsq) DESC LIMIT 20
),
semantic AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> $3::vector) AS rnk
    FROM documents WHERE embedding IS NOT NULL
    ORDER BY embedding <=> $3::vector LIMIT 20
),
fused AS (
    SELECT id, sum(1.0 / (60 + rnk)) AS score
    FROM (SELECT * FROM keyword UNION ALL SELECT * FROM semantic) ranked
    GROUP BY id
)
SELECT d.id, d.title, d.source, d.created_at,
       ts_headline('english', d.content, q.tsq, 'MaxWords=60, MinWords=20') AS snippet
FROM fused f JOIN documents d USING (id), q
ORDER BY f.score DESC
LIMIT $2
"""


class KBSearchInput(BaseModel):
    query: str = Field(description="Natural-language question or search terms.", max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class KBAddInput(BaseModel):
    title: str = Field(max_length=300)
    content: str = Field(description="Text to store.", max_length=20000)
    source: str = Field(default="", description="Optional URL or citation for the content.")


def _need_db(ctx: ToolContext):
    if ctx.db is None:
        raise ToolError("Knowledge base is unavailable (no database configured)")
    return ctx.db


async def search_documents(ctx: ToolContext, query: str, limit: int) -> list:
    db = _need_db(ctx)
    if ctx.embedder is not None:
        try:
            vec = await ctx.embedder.embed(query, query=True)
            return await db.fetch(HYBRID_SQL, query, limit, to_pgvector(vec))
        except Exception as e:  # embedding service down: keyword search still works
            log.warning("semantic search unavailable, falling back to keywords: %s", e)
    return await db.fetch(KEYWORD_SQL, query, limit)


async def add_document(ctx: ToolContext, title: str, content: str, source: str = "") -> int:
    db = _need_db(ctx)
    vec = None
    if ctx.embedder is not None:
        try:
            vec = to_pgvector(await ctx.embedder.embed(f"{title}\n{content}"))
        except Exception as e:  # stored without a vector; backfilled at next startup
            log.warning("could not embed document: %s", e)
    if vec is None:
        return await db.fetchval(
            "INSERT INTO documents (title, content, source) VALUES ($1, $2, $3) RETURNING id",
            title,
            content,
            source,
        )
    return await db.fetchval(
        "INSERT INTO documents (title, content, source, embedding) "
        "VALUES ($1, $2, $3, $4::vector) RETURNING id",
        title,
        content,
        source,
        vec,
    )


async def _search(inp: KBSearchInput, ctx: ToolContext) -> str:
    rows = await search_documents(ctx, inp.query, inp.limit)
    if not rows:
        return f"No knowledge-base documents match: {inp.query}"
    return "\n\n".join(
        f"[doc {r['id']}] {r['title']} ({r['created_at']:%Y-%m-%d})"
        f"{' - ' + r['source'] if r['source'] else ''}\n{r['snippet']}"
        for r in rows
    )


async def _add(inp: KBAddInput, ctx: ToolContext) -> str:
    doc_id = await add_document(ctx, inp.title, inp.content, inp.source)
    return f"Stored as doc {doc_id}."


kb_search = Tool(
    name="search_knowledge_base",
    description="Search the organisation's private knowledge base (documents users have saved) "
    "by meaning and keywords. Check it first for questions about internal or previously saved "
    "information.",
    input_model=KBSearchInput,
    handler=_search,
)

kb_add = Tool(
    name="save_to_knowledge_base",
    description="Save a document or note to the knowledge base so it can be found later. Only "
    "use when the user asks to remember/save something.",
    input_model=KBAddInput,
    handler=_add,
)
