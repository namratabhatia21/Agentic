from typing import Any

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("agentic_chat_requests_total", "Chat requests", ["outcome"])
LLM_LATENCY = Histogram(
    "agentic_llm_step_seconds",
    "Latency of one model step",
    buckets=(0.5, 1, 2, 5, 10, 20, 40, 80, 160),
)
TOOL_CALLS = Counter("agentic_tool_calls_total", "Client tool calls", ["tool", "status"])
TOOL_LATENCY = Histogram("agentic_tool_seconds", "Client tool latency", ["tool"])
TOKENS = Counter("agentic_tokens_total", "Tokens used", ["kind"])


def record_usage(usage: Any) -> None:
    for kind in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        value = getattr(usage, kind, None)
        if value:
            TOKENS.labels(kind=kind).inc(value)
