"""Hugging Face features: open-model agent loop, embeddings, HF tools (all offline)."""

import json
from types import SimpleNamespace as NS

import httpx
import numpy as np
import pytest

from app.config import Settings
from app.embeddings import Embedder, to_pgvector
from app.hf_agent import HFAgent
from app.main import _chunk
from app.tools import ToolContext, available_tools, execute_tool


def chunk(content=None, tool_calls=None, finish=None, usage=None, reasoning=None):
    delta = NS(content=content, tool_calls=tool_calls, reasoning=reasoning)
    return NS(choices=[NS(delta=delta, finish_reason=finish)], usage=usage)


def tc(index, id=None, name=None, args=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=args))


class FakeHF:
    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = []

    async def chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": list(messages), **kwargs})
        chunks = self.turns.pop(0)

        async def gen():
            for c in chunks:
                yield c

        return gen()


@pytest.fixture
async def ctx():
    async with httpx.AsyncClient() as http:
        yield ToolContext(settings=Settings(llm_provider="huggingface", hf_token="x"), http=http)


async def run(agent, text="hi", history=None):
    new = []
    events = [e async for e in agent.run(history or [], text, new)]
    return events, new


async def test_hf_agent_streams_tool_call_arguments_and_finishes(ctx):
    client = FakeHF(
        [
            [
                chunk(reasoning="need math"),
                chunk(tool_calls=[tc(0, id="c1", name="calculator", args='{"expre')]),
                chunk(tool_calls=[tc(0, args='ssion": "6*7"}')]),
                chunk(tool_calls=[tc(1, id="c2", name="calculator", args='{"expression": "2+2"}')]),
                chunk(finish="tool_calls"),
                NS(choices=[], usage=NS(prompt_tokens=100, completion_tokens=20)),
            ],
            [chunk(content="42 and 4."), chunk(finish="stop")],
        ]
    )
    agent = HFAgent(client, ctx.settings, ctx)
    events, new = await run(agent)

    assert [e["type"] for e in events if e["type"] != "thinking"] == [
        "tool_call",
        "tool_call",
        "tool_result",
        "tool_result",
        "text",
        "done",
    ]
    assert [m["role"] for m in new] == ["user", "assistant", "tool", "tool", "assistant"]
    assert new[1]["tool_calls"][0]["function"]["arguments"] == '{"expression": "6*7"}'
    assert [m["content"] for m in new[2:4]] == ["42", "4"]
    assert [m["tool_call_id"] for m in new[2:4]] == ["c1", "c2"]
    # system prompt prepended, tools in chat-completions format
    req = client.calls[0]
    assert req["messages"][0]["role"] == "system"
    assert req["tools"][0]["type"] == "function"
    assert req["model"] == ctx.settings.hf_chat_model
    # the second request contains the whole turn so far
    assert len(client.calls[1]["messages"]) == 1 + 4


async def test_hf_agent_invalid_json_arguments_become_error_results(ctx):
    client = FakeHF(
        [
            [chunk(tool_calls=[tc(0, id="c1", name="calculator", args="{not json")])],
            [chunk(content="Sorry."), chunk(finish="stop")],
        ]
    )
    events, new = await run(HFAgent(client, ctx.settings, ctx))
    assert new[2]["role"] == "tool" and new[2]["content"].startswith("ERROR:")
    assert events[-1]["type"] == "done"


async def test_hf_agent_continues_stored_history(ctx):
    history = [
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "reply"},
    ]
    client = FakeHF([[chunk(content="ok"), chunk(finish="stop")]])
    await run(HFAgent(client, ctx.settings, ctx), history=history)
    assert [m["content"] for m in client.calls[0]["messages"][1:]] == ["earlier", "reply", "hi"]


def test_hf_tools_need_a_token():
    without = {t.name for t in available_tools(Settings())}
    with_token = {t.name for t in available_tools(Settings(hf_token="x"))}
    assert "search_huggingface_hub" in without
    assert {"generate_image", "classify_text"} - without == {"generate_image", "classify_text"}
    assert {"generate_image", "classify_text"} <= with_token


async def test_classify_text_sentiment_and_zero_shot(ctx):
    class HF:
        async def text_classification(self, text, model):
            return [NS(label="positive", score=0.91), NS(label="negative", score=0.02)]

        async def zero_shot_classification(self, text, labels, model, multi_label):
            return [NS(label=lbl, score=s) for lbl, s in zip(labels, (0.8, 0.2), strict=False)]

    ctx.hf = HF()
    content, err = await execute_tool("classify_text", {"texts": ["love it"]}, ctx)
    assert not err and "positive: 0.91" in content
    content, err = await execute_tool(
        "classify_text",
        {"texts": ["refund please"], "mode": "zero_shot", "labels": ["billing", "bug"]},
        ctx,
    )
    assert not err and "billing: 0.80" in content
    content, err = await execute_tool(
        "classify_text", {"texts": ["x"], "mode": "zero_shot", "labels": ["one"]}, ctx
    )
    assert err and "two labels" in content


async def test_hub_search_formats_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/models"
        assert request.url.params["sort"] == "createdAt"
        assert request.url.params["pipeline_tag"] == "text-generation"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "org/new-llm",
                    "likes": 12,
                    "downloads": 345,
                    "pipeline_tag": "text-generation",
                    "createdAt": "2026-09-30T10:00:00Z",
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        ctx = ToolContext(settings=Settings(), http=http)
        content, err = await execute_tool(
            "search_huggingface_hub",
            {"query": "llm", "task": "text-generation", "sort": "createdAt"},
            ctx,
        )
    assert not err
    assert "org/new-llm" in content and "https://huggingface.co/org/new-llm" in content


async def test_embedder_uses_tei_and_normalises(monkeypatch):
    settings = Settings(embeddings_url="http://embeddings:80", embedding_dim=3)
    emb = Embedder(settings)
    seen = {}

    async def fake_fe(text, model):
        seen.update(text=text, model=model)
        return np.array([[3.0, 0.0, 4.0]])

    monkeypatch.setattr(emb.client, "feature_extraction", fake_fe)
    vec = await emb.embed("what is RAG", query=True)
    assert vec == pytest.approx([0.6, 0.0, 0.8])
    assert seen["model"] == "http://embeddings:80/embed"
    assert seen["text"].startswith(settings.embedding_query_prefix)
    assert to_pgvector(vec) == "[0.600000,0.000000,0.800000]"


async def test_embedder_rejects_wrong_dimension(monkeypatch):
    emb = Embedder(Settings(embeddings_url="http://e", embedding_dim=384))

    async def fake_fe(text, model):
        return np.zeros(768)

    monkeypatch.setattr(emb.client, "feature_extraction", fake_fe)
    with pytest.raises(RuntimeError, match="EMBEDDING_DIM"):
        await emb.embed("x")


def test_embedder_disabled_without_backend():
    assert not Embedder(Settings()).enabled
    assert Embedder(Settings(hf_token="x")).enabled


def test_chunking_keeps_text_and_bounds_size():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 100 for i in range(10)) + "\n\n" + "x" * 4000
    chunks = _chunk(text)
    assert all(len(c) <= 1500 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")
    assert _chunk("short") == ["short"]


def test_openai_tool_definition_shape():
    from app.tools import TOOLS_BY_NAME

    d = TOOLS_BY_NAME["calculator"].openai_definition()
    assert d["type"] == "function"
    assert d["function"]["parameters"]["required"] == ["expression"]
    json.dumps(d)


def test_open_source_is_the_default():
    from app.llm import conversation_format, model_name

    s = Settings()
    assert s.llm_provider == "huggingface" and s.uses_open_model
    assert conversation_format(s) == "openai"
    assert model_name(s) == s.hf_chat_model


def test_local_provider_uses_self_hosted_server():
    from huggingface_hub import AsyncInferenceClient

    from app.llm import build_client, model_name, server_tools

    s = Settings(
        llm_provider="local", local_llm_url="http://ollama:11434/v1", local_model="qwen3:8b"
    )
    client = build_client(s)
    assert isinstance(client, AsyncInferenceClient)
    assert model_name(s) == "qwen3:8b"
    assert server_tools(s) == []


async def test_hf_agent_sends_local_model_name(ctx):
    settings = Settings(llm_provider="local", local_model="llama3.3:70b")
    client = FakeHF([[chunk(content="ok"), chunk(finish="stop")]])
    await run(HFAgent(client, settings, ctx))
    assert client.calls[0]["model"] == "llama3.3:70b"


def test_missing_hf_token_is_reported_not_fatal():
    from app.llm import ProviderNotConfigured, build_client

    with pytest.raises(ProviderNotConfigured, match="HF_TOKEN"):
        build_client(Settings(llm_provider="huggingface"))
