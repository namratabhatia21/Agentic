"""Agent loop for open-weight models: Hugging Face Inference Providers or self-hosted.

Uses the OpenAI-compatible chat-completions format (messages with `tool_calls`,
`tool` role results) through huggingface_hub's AsyncInferenceClient, which also talks
to any self-hosted OpenAI-compatible server (Ollama, vLLM, TGI). Emits the same UI
events as the Claude agent, so the frontend and API don't care which runs.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app import metrics
from app.config import Settings
from app.llm import model_name
from app.prompts import SYSTEM_PROMPT
from app.tools import ToolContext, available_tools, execute_tool

log = logging.getLogger(__name__)

RESULT_PREVIEW_CHARS = 600
# Open models get the same instructions; there is no hosted web search on this path.
HF_SYSTEM_PROMPT = SYSTEM_PROMPT + (
    "\n\nWeb search and web fetch are not available in this deployment; use the other "
    "live-data tools. Call tools with valid JSON arguments that match their schema."
)


class HFAgent:
    def __init__(self, client: Any, settings: Settings, ctx: ToolContext):
        self.client = client
        self.settings = settings
        self.ctx = ctx
        self.tool_defs = [t.openai_definition() for t in available_tools(settings)]

    async def run(
        self, history: list[dict], user_text: str, new_messages: list[dict]
    ) -> AsyncIterator[dict]:
        new_messages.append({"role": "user", "content": user_text})
        usage_totals = {"input_tokens": 0, "output_tokens": 0}

        for _step in range(self.settings.max_agent_steps):
            messages = [{"role": "system", "content": HF_SYSTEM_PROMPT}, *history, *new_messages]
            text_parts: list[str] = []
            calls: dict[int, dict] = {}
            finish_reason = None

            stream = await self.client.chat_completion(
                messages,
                model=model_name(self.settings),
                tools=self.tool_defs,
                tool_choice="auto",
                max_tokens=self.settings.hf_max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage_totals["input_tokens"] += chunk.usage.prompt_tokens or 0
                    usage_totals["output_tokens"] += chunk.usage.completion_tokens or 0
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if getattr(delta, "reasoning", None):
                    yield {"type": "thinking", "text": delta.reasoning}
                if delta.content:
                    text_parts.append(delta.content)
                    yield {"type": "text", "text": delta.content}
                for tc in delta.tool_calls or []:
                    acc = calls.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function and tc.function.name:
                        acc["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        acc["arguments"] += tc.function.arguments
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            assistant: dict = {"role": "assistant", "content": "".join(text_parts)}
            if not calls:
                new_messages.append(assistant)
                _record(usage_totals)
                yield {"type": "done", "stop_reason": finish_reason, "usage": usage_totals}
                return
            if finish_reason == "length":
                yield {"type": "error", "message": "Response truncated mid tool call."}
                return

            ordered = [calls[i] for i in sorted(calls)]
            for i, call in enumerate(ordered):
                call["id"] = call["id"] or f"call_{len(new_messages)}_{i}"
            assistant["tool_calls"] = [
                {
                    "id": c["id"],
                    "type": "function",
                    "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
                }
                for c in ordered
            ]
            new_messages.append(assistant)

            parsed = []
            for c in ordered:
                try:
                    args = json.loads(c["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = None
                parsed.append(args)
                yield {
                    "type": "tool_call",
                    "id": c["id"],
                    "name": c["name"],
                    "server": False,
                    "input": args if args is not None else c["arguments"],
                }

            results = await asyncio.gather(
                *(
                    _invalid_json() if args is None else execute_tool(c["name"], args, self.ctx)
                    for c, args in zip(ordered, parsed, strict=True)
                )
            )
            for c, (content, is_error) in zip(ordered, results, strict=True):
                yield {
                    "type": "tool_result",
                    "id": c["id"],
                    "name": c["name"],
                    "is_error": is_error,
                    "preview": content[:RESULT_PREVIEW_CHARS],
                }
                new_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": f"ERROR: {content}" if is_error else content,
                    }
                )

        _record(usage_totals)
        yield {"type": "error", "message": "Stopped: too many tool-use steps."}


async def _invalid_json() -> tuple[str, bool]:
    return "Arguments were not valid JSON. Retry with a valid JSON object.", True


def _record(usage: dict) -> None:
    for kind, value in usage.items():
        if value:
            metrics.TOKENS.labels(kind=kind).inc(value)
