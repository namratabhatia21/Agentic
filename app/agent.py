"""The agent loop: stream a Claude turn, run requested tools, repeat until done.

The loop is hand-written (rather than the SDK tool runner) so that it can stream
fine-grained events - text, thinking summaries, tool calls, tool results - to the
browser over SSE as they happen.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from app import metrics
from app.config import Settings
from app.llm import request_extras, server_tools
from app.prompts import SYSTEM_PROMPT
from app.tools import ALL_TOOLS, TOOLS_BY_NAME, ToolContext

log = logging.getLogger(__name__)

MAX_JSON_RETRIES = 2
RESULT_PREVIEW_CHARS = 600


def block_to_param(block: Any) -> dict:
    """Serialise a response content block so it can be stored and sent back verbatim."""
    return block.model_dump(mode="json", exclude_none=True)


class Agent:
    def __init__(self, client: Any, settings: Settings, ctx: ToolContext):
        self.client = client
        self.settings = settings
        self.ctx = ctx
        self.tool_defs = [t.definition() for t in ALL_TOOLS] + server_tools(settings)

    def _request(self, messages: list[dict]) -> dict:
        return {
            "model": self.settings.model_id,
            "max_tokens": self.settings.max_tokens,
            "system": [
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            "tools": self.tool_defs,
            "messages": messages,
            # Cache the growing conversation prefix automatically.
            "cache_control": {"type": "ephemeral"},
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self.settings.effort},
            **request_extras(self.settings),
        }

    async def run(
        self, history: list[dict], user_text: str, new_messages: list[dict]
    ) -> AsyncIterator[dict]:
        """Yield UI events for one user turn.

        Messages created during the turn are appended to `new_messages`. The caller should
        persist them only after a `done` event, so history stays append-only and valid.
        """
        new_messages.append({"role": "user", "content": user_text})
        messages = history + new_messages
        json_retries = 0
        step = 0

        while True:
            step += 1
            if step > self.settings.max_agent_steps:
                yield {"type": "error", "message": "Stopped: too many tool-use steps."}
                return

            started = time.perf_counter()
            try:
                async with self.client.beta.messages.stream(**self._request(messages)) as stream:
                    async for event in stream:
                        ui_event = _translate(event)
                        if ui_event is not None:
                            yield ui_event
                    response = await stream.get_final_message()
                json_retries = 0
            except ValueError:
                # Eager input streaming: the SDK could not parse a tool input at all.
                # No complete tool_use block exists to answer, so re-issue the step.
                json_retries += 1
                if json_retries > MAX_JSON_RETRIES:
                    raise
                log.warning("unparseable tool input; retrying step")
                step -= 1
                continue
            finally:
                metrics.LLM_LATENCY.observe(time.perf_counter() - started)

            metrics.record_usage(response.usage)
            assistant = {
                "role": "assistant",
                "content": [block_to_param(b) for b in response.content],
            }

            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                yield {
                    "type": "refusal",
                    "message": "The model declined this request.",
                    "category": getattr(details, "category", None),
                }
                return

            if response.stop_reason == "pause_turn":
                # A long server-tool turn was paused; send it back to let it continue.
                new_messages.append(assistant)
                messages = history + new_messages
                continue

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                new_messages.append(assistant)
                yield {
                    "type": "done",
                    "stop_reason": response.stop_reason,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "cache_read_input_tokens": getattr(
                            response.usage, "cache_read_input_tokens", 0
                        ),
                    },
                }
                return

            if response.stop_reason == "max_tokens":
                # A truncated tool input can still parse as a valid-looking object.
                yield {"type": "error", "message": "Response truncated mid tool call."}
                return

            new_messages.append(assistant)
            results = await asyncio.gather(*(self._run_tool(b) for b in tool_uses))
            for block, (content, is_error) in zip(tool_uses, results, strict=True):
                yield {
                    "type": "tool_result",
                    "id": block.id,
                    "name": block.name,
                    "is_error": is_error,
                    "preview": content[:RESULT_PREVIEW_CHARS],
                }
            # All results go back together in one user message.
            new_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                            **({"is_error": True} if is_error else {}),
                        }
                        for block, (content, is_error) in zip(tool_uses, results, strict=True)
                    ],
                }
            )
            messages = history + new_messages

    async def _run_tool(self, block: Any) -> tuple[str, bool]:
        tool = TOOLS_BY_NAME.get(block.name)
        if tool is None:
            return f"Unknown tool: {block.name}", True
        started = time.perf_counter()
        try:
            content, is_error = await asyncio.wait_for(
                tool.run(block.input, self.ctx), timeout=self.settings.tool_http_timeout * 2
            )
        except TimeoutError:
            content, is_error = "Tool timed out", True
        except Exception as e:  # never let one tool failure kill the turn
            log.exception("tool %s crashed", block.name)
            content, is_error = f"Tool failed: {type(e).__name__}", True
        metrics.TOOL_CALLS.labels(tool=block.name, status="error" if is_error else "ok").inc()
        metrics.TOOL_LATENCY.labels(tool=block.name).observe(time.perf_counter() - started)
        return content, is_error


def _translate(event: Any) -> dict | None:
    """Map SDK stream events to the small set of events the UI understands."""
    etype = event.type
    if etype == "content_block_delta":
        delta = event.delta
        if delta.type == "text_delta":
            return {"type": "text", "text": delta.text}
        if delta.type == "thinking_delta" and delta.thinking:
            return {"type": "thinking", "text": delta.thinking}
        return None
    if etype == "content_block_stop":
        block = getattr(event, "content_block", None)
        if block is None:
            return None
        if block.type in ("tool_use", "server_tool_use"):
            return {
                "type": "tool_call",
                "id": block.id,
                "name": block.name,
                "server": block.type == "server_tool_use",
                "input": json.loads(json.dumps(block.input, default=str)),
            }
        if block.type.endswith("_tool_result") and hasattr(block, "tool_use_id"):
            return {
                "type": "tool_result",
                "id": block.tool_use_id,
                "name": block.type.removesuffix("_tool_result"),
                "is_error": False,
                "preview": "",
            }
        if block.type == "fallback":
            return {"type": "notice", "message": "Request was rerouted to a fallback model."}
    return None
