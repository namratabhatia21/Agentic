"""Read-only SQL over the `analytics` schema.

Defence in depth: the pool connects as a role that only has SELECT on `analytics`,
every query runs in a READ ONLY transaction with a statement timeout, and results
are truncated before they reach the model.
"""

import json

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError

MAX_ROWS = 100


class SQLInput(BaseModel):
    sql: str = Field(
        description="A single PostgreSQL SELECT statement over the analytics schema.",
        max_length=5000,
    )


class DescribeInput(BaseModel):
    pass


def _need_db(ctx: ToolContext):
    if ctx.readonly_db is None:
        raise ToolError("Analytics database is unavailable")
    return ctx.readonly_db


async def _describe(inp: DescribeInput, ctx: ToolContext) -> str:
    rows = await _need_db(ctx).fetch(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'analytics'
        ORDER BY table_name, ordinal_position
        """
    )
    if not rows:
        return "The analytics schema has no tables."
    tables: dict[str, list[str]] = {}
    for r in rows:
        tables.setdefault(r["table_name"], []).append(f"{r['column_name']} {r['data_type']}")
    return "\n".join(f"analytics.{t}({', '.join(cols)})" for t, cols in tables.items())


async def _query(inp: SQLInput, ctx: ToolContext) -> str:
    sql = inp.sql.strip().rstrip(";")
    if ";" in sql:
        raise ToolError("Only a single statement is allowed")
    async with _need_db(ctx).acquire() as conn:
        async with conn.transaction(readonly=True):
            await conn.execute("SET LOCAL statement_timeout = '5s'")
            try:
                rows = await conn.fetch(sql)
            except Exception as e:  # asyncpg raises many subclasses; show the DB message
                raise ToolError(f"SQL error: {e}") from e
    if not rows:
        return "Query returned 0 rows."
    records = [dict(r) for r in rows[:MAX_ROWS]]
    note = f"\n(truncated to {MAX_ROWS} of {len(rows)} rows)" if len(rows) > MAX_ROWS else ""
    return json.dumps(records, default=str, indent=1) + note


describe_db = Tool(
    name="describe_database",
    description="List the tables and columns of the analytics database. Call before writing SQL.",
    input_model=DescribeInput,
    handler=_describe,
)

query_db = Tool(
    name="query_database",
    description="Run a read-only SQL SELECT against the analytics database and return rows as "
    f"JSON (max {MAX_ROWS}). Aggregate in SQL rather than fetching raw rows.",
    input_model=SQLInput,
    handler=_query,
)
