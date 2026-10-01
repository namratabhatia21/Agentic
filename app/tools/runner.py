"""Provider-independent tool execution with timeouts and metrics."""

import asyncio
import logging
import time
from typing import Any

from app import metrics
from app.config import Settings
from app.tools.base import Tool, ToolContext

log = logging.getLogger(__name__)


def available_tools(settings: Settings) -> list[Tool]:
    from app.tools import ALL_TOOLS

    return [t for t in ALL_TOOLS if settings.hf_token or not t.requires_hf_token]


async def execute_tool(name: str, raw_input: Any, ctx: ToolContext) -> tuple[str, bool]:
    """Run one tool call. Never raises: failures come back as (message, True)."""
    tool = {t.name: t for t in available_tools(ctx.settings)}.get(name)
    if tool is None:
        return f"Unknown tool: {name}", True
    started = time.perf_counter()
    try:
        content, is_error = await asyncio.wait_for(
            tool.run(raw_input, ctx), timeout=ctx.settings.tool_http_timeout * 4
        )
    except TimeoutError:
        content, is_error = "Tool timed out", True
    except Exception as e:  # one tool failure must not kill the turn
        log.exception("tool %s crashed", name)
        content, is_error = f"Tool failed: {type(e).__name__}", True
    metrics.TOOL_CALLS.labels(tool=name, status="error" if is_error else "ok").inc()
    metrics.TOOL_LATENCY.labels(tool=name).observe(time.perf_counter() - started)
    return content, is_error
