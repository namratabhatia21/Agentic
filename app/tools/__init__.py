from app.tools.arxiv import arxiv
from app.tools.base import Tool, ToolContext, ToolError
from app.tools.calculator import calculator
from app.tools.exchange import exchange_rates
from app.tools.huggingface import classify_text, generate_image, hub_search
from app.tools.knowledge import kb_add, kb_search
from app.tools.news import tech_news
from app.tools.sql import describe_db, query_db
from app.tools.time_tool import current_time
from app.tools.weather import weather
from app.tools.wikipedia import wikipedia

# Order is part of the prompt-cache prefix: keep it stable.
ALL_TOOLS: list[Tool] = [
    current_time,
    calculator,
    weather,
    wikipedia,
    arxiv,
    tech_news,
    exchange_rates,
    kb_search,
    kb_add,
    describe_db,
    query_db,
    hub_search,
    generate_image,
    classify_text,
]
TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in ALL_TOOLS}

from app.tools.runner import available_tools, execute_tool  # noqa: E402

__all__ = [
    "ALL_TOOLS",
    "TOOLS_BY_NAME",
    "Tool",
    "ToolContext",
    "ToolError",
    "available_tools",
    "execute_tool",
]
