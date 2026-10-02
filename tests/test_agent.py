"""Agent loop tests against a scripted fake Claude client (no network)."""

from types import SimpleNamespace

import httpx
import pytest
from anthropic.types.beta import BetaMessage

from app.agent import Agent
from app.config import Settings
from app.tools import ToolContext

USAGE = {"input_tokens": 10, "output_tokens": 5}


def message(content, stop_reason):
    return BetaMessage.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": USAGE,
        }
    )


class FakeStream:
    def __init__(self, final):
        self.final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for block in self.final.content:
                if block.type == "text":
                    yield SimpleNamespace(
                        type="content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text=block.text),
                    )
                yield SimpleNamespace(type="content_block_stop", content_block=block)

        return gen()

    async def get_final_message(self):
        return self.final


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        # Snapshot messages: the agent rebuilds the list each step.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.script.pop(0))


@pytest.fixture
async def ctx():
    async with httpx.AsyncClient() as http:
        yield ToolContext(settings=Settings(llm_provider="anthropic"), http=http)


async def collect(agent, history, text):
    new_messages = []
    events = [e async for e in agent.run(history, text, new_messages)]
    return events, new_messages


async def test_tool_loop_runs_tools_in_parallel_and_finishes(ctx):
    client = FakeClient(
        [
            message(
                [
                    {"type": "text", "text": "Let me compute."},
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "calculator",
                        "input": {"expression": "6*7"},
                    },
                    {
                        "type": "tool_use",
                        "id": "t2",
                        "name": "calculator",
                        "input": {"expression": "2**10"},
                    },
                ],
                "tool_use",
            ),
            message([{"type": "text", "text": "42 and 1024."}], "end_turn"),
        ]
    )
    agent = Agent(client, Settings(llm_provider="anthropic"), ctx)
    events, new_messages = await collect(agent, [], "compute")

    types = [e["type"] for e in events]
    assert types.count("tool_call") == 2
    assert types.count("tool_result") == 2
    assert types[-1] == "done"

    # user, assistant(tool_use), user(tool_results), assistant(final)
    assert [m["role"] for m in new_messages] == ["user", "assistant", "user", "assistant"]
    results = new_messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert [r["content"] for r in results] == ["42", "1024"]

    # second request carries the full transcript, in order
    assert len(client.requests[1]["messages"]) == 3
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["thinking"]["type"] == "adaptive"
    assert req["extra_body"] == {"fallbacks": "default"}


async def test_unknown_tool_and_bad_input_return_errors(ctx):
    client = FakeClient(
        [
            message(
                [
                    {"type": "tool_use", "id": "t1", "name": "nope", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "calculator", "input": {"x": 1}},
                ],
                "tool_use",
            ),
            message([{"type": "text", "text": "Sorry."}], "end_turn"),
        ]
    )
    events, new_messages = await collect(
        Agent(client, Settings(llm_provider="anthropic"), ctx), [], "hi"
    )
    results = new_messages[2]["content"]
    assert all(r.get("is_error") for r in results)
    assert events[-1]["type"] == "done"


async def test_refusal_is_not_persisted(ctx):
    client = FakeClient([message([], "refusal")])
    events, _ = await collect(Agent(client, Settings(llm_provider="anthropic"), ctx), [], "bad")
    assert events[-1]["type"] == "refusal"
    assert not any(e["type"] == "done" for e in events)


async def test_step_limit(ctx):
    loop_msg = message(
        [{"type": "tool_use", "id": "t", "name": "calculator", "input": {"expression": "1"}}],
        "tool_use",
    )
    settings = Settings(llm_provider="anthropic", max_agent_steps=3)
    client = FakeClient([loop_msg] * 5)
    events, _ = await collect(Agent(client, settings, ctx), [], "loop")
    assert events[-1]["type"] == "error"
    assert len(client.requests) == 3


def test_provider_specific_tools():
    from app.llm import request_extras, server_tools

    assert {t["name"] for t in server_tools(Settings(llm_provider="anthropic"))} == {
        "web_search",
        "web_fetch",
    }
    vertex = Settings(llm_provider="vertex")
    assert [t["type"] for t in server_tools(vertex)] == ["web_search_20250305"]
    assert request_extras(vertex) == {}
    bedrock = Settings(llm_provider="bedrock")
    assert server_tools(bedrock) == []
    assert bedrock.model_id == "anthropic.claude-opus-5-5"
