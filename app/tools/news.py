from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError

HN_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_SEARCH_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"


class NewsInput(BaseModel):
    query: str = Field(default="", description="Topic to search for. Empty = front page.")
    mode: Literal["front_page", "latest", "popular"] = Field(
        default="front_page",
        description="'front_page' = current HN front page, 'latest' = newest stories matching "
        "query, 'popular' = most upvoted stories matching query.",
    )
    limit: int = Field(default=8, ge=1, le=20)


async def _news(inp: NewsInput, ctx: ToolContext) -> str:
    params: dict = {"hitsPerPage": inp.limit, "tags": "story"}
    if inp.mode == "front_page":
        params["tags"] = "front_page"
        url = HN_SEARCH
    else:
        url = HN_SEARCH_BY_DATE if inp.mode == "latest" else HN_SEARCH
    if inp.query:
        params["query"] = inp.query
    data = await ctx.cached_get_json(url, params)
    hits = data.get("hits", [])
    if not hits:
        raise ToolError("No stories found")
    lines = []
    for h in hits:
        ts = datetime.fromtimestamp(h.get("created_at_i", 0), UTC).strftime("%Y-%m-%d %H:%M")
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        lines.append(
            f"- {h.get('title')} ({h.get('points', 0)} points, {h.get('num_comments', 0)} "
            f"comments, {ts} UTC)\n  {link}"
        )
    return "\n".join(lines)


tech_news = Tool(
    name="get_tech_news",
    description="Live technology news from Hacker News: the current front page, or the latest "
    "/ most popular stories on a topic.",
    input_model=NewsInput,
    handler=_news,
)
