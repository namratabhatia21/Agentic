from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError


class WikipediaInput(BaseModel):
    query: str = Field(description="Search terms.", max_length=300)
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}$", description="Wiki language code.")
    limit: int = Field(default=3, ge=1, le=5)


async def _wikipedia(inp: WikipediaInput, ctx: ToolContext) -> str:
    api = f"https://{inp.language}.wikipedia.org/w/api.php"
    data = await ctx.cached_get_json(
        api,
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": inp.query,
            "gsrlimit": inp.limit,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "exchars": 1200,
            "inprop": "url",
        },
    )
    pages = sorted(
        (data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)
    )
    if not pages:
        raise ToolError(f"No Wikipedia results for: {inp.query}")
    return "\n\n".join(
        f"## {p['title']}\n{p.get('fullurl', '')}\n{p.get('extract', '').strip()}" for p in pages
    )


wikipedia = Tool(
    name="search_wikipedia",
    description="Search Wikipedia and return the intro of the top matching articles with URLs. "
    "Good for background facts on people, places, concepts and events.",
    input_model=WikipediaInput,
    handler=_wikipedia,
)
