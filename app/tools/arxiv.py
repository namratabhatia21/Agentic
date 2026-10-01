import xml.etree.ElementTree as ET
from typing import Literal

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError

ARXIV_URL = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


class ArxivInput(BaseModel):
    query: str = Field(description="Search terms, e.g. 'retrieval augmented generation'.")
    sort_by: Literal["submittedDate", "relevance"] = Field(
        default="submittedDate", description="'submittedDate' returns the newest papers first."
    )
    max_results: int = Field(default=5, ge=1, le=10)


async def _arxiv(inp: ArxivInput, ctx: ToolContext) -> str:
    text = await ctx.cached_get_text(
        ARXIV_URL,
        {
            "search_query": f"all:{inp.query}",
            "sortBy": inp.sort_by,
            "sortOrder": "descending",
            "max_results": inp.max_results,
        },
    )
    root = ET.fromstring(text)
    entries = root.findall("a:entry", NS)
    if not entries:
        raise ToolError(f"No arXiv papers for: {inp.query}")
    out = []
    for e in entries:
        title = " ".join((e.findtext("a:title", "", NS)).split())
        summary = " ".join((e.findtext("a:summary", "", NS)).split())
        authors = ", ".join(a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)[:5])
        out.append(
            f"## {title}\nPublished: {e.findtext('a:published', '', NS)[:10]} | "
            f"Authors: {authors}\n{e.findtext('a:id', '', NS)}\n{summary[:700]}"
        )
    return "\n\n".join(out)


arxiv = Tool(
    name="search_arxiv",
    description="Search arXiv for research papers (live). Defaults to newest first - use it for "
    "'latest research on X' questions.",
    input_model=ArxivInput,
    handler=_arxiv,
)
