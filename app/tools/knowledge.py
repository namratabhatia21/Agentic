"""Knowledge base backed by PostgreSQL full-text search."""

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError


class KBSearchInput(BaseModel):
    query: str = Field(description="Natural-language search terms.", max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class KBAddInput(BaseModel):
    title: str = Field(max_length=300)
    content: str = Field(description="Text to store.", max_length=20000)
    source: str = Field(default="", description="Optional URL or citation for the content.")


def _need_db(ctx: ToolContext):
    if ctx.db is None:
        raise ToolError("Knowledge base is unavailable (no database configured)")
    return ctx.db


async def _search(inp: KBSearchInput, ctx: ToolContext) -> str:
    rows = await _need_db(ctx).fetch(
        """
        SELECT id, title, source, created_at,
               ts_headline('english', content, q, 'MaxWords=60, MinWords=20') AS snippet,
               ts_rank(search, q) AS rank
        FROM documents,
             -- match ANY query term (stemmed); ts_rank orders by how many/how well
             to_tsquery('english', array_to_string(
                 tsvector_to_array(to_tsvector('english', $1)), ' | ')) q
        WHERE search @@ q
        ORDER BY rank DESC
        LIMIT $2
        """,
        inp.query,
        inp.limit,
    )
    if not rows:
        return f"No knowledge-base documents match: {inp.query}"
    return "\n\n".join(
        f"[doc {r['id']}] {r['title']} ({r['created_at']:%Y-%m-%d})"
        f"{' - ' + r['source'] if r['source'] else ''}\n{r['snippet']}"
        for r in rows
    )


async def _add(inp: KBAddInput, ctx: ToolContext) -> str:
    doc_id = await _need_db(ctx).fetchval(
        "INSERT INTO documents (title, content, source) VALUES ($1, $2, $3) RETURNING id",
        inp.title,
        inp.content,
        inp.source,
    )
    return f"Stored as doc {doc_id}."


kb_search = Tool(
    name="search_knowledge_base",
    description="Search the organisation's private knowledge base (documents users have saved). "
    "Check it first for questions about internal or previously saved information.",
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
