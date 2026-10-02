# Agentic

A production-ready **agentic chatbot** that answers from live data. The model plans,
calls tools in parallel, reads the results and cites its sources. Every step streams
to the browser as it happens.

**Models:** open-source by default. Choose with `LLM_PROVIDER`:

| `LLM_PROVIDER` | Model | Runs where | Needs |
|---|---|---|---|
| `huggingface` *(default)* | Qwen3-235B (any HF chat model with tool calling) | Hugging Face Inference Providers | free `HF_TOKEN` |
| `local` | `qwen3:8b` via Ollama (or any vLLM/TGI server) | your own machine/GPU, fully private | nothing |
| `anthropic` / `vertex` / `bedrock` | Claude Opus 5.5 (optional) | Anthropic, Google Cloud or AWS | API key or cloud credits |

**Tools:** web search & fetch · arXiv (latest papers) · Hacker News · Wikipedia ·
**Hugging Face Hub search** · weather · ECB exchange rates · **semantic knowledge base**
(Hugging Face embeddings + pgvector, hybrid with keyword search) · read-only analytics
SQL · **image generation (FLUX)** · **sentiment / zero-shot classification** ·
calculator · clock.

**Stack:** FastAPI · PostgreSQL + pgvector · Redis · Hugging Face Text Embeddings
Inference · Nginx · Docker Compose · Prometheus/Grafana · GitHub Actions CI · Cloud Run
deploy script.

- Architecture & design decisions → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Paying with GCP / AWS / Anthropic credits → [docs/CLOUD_CREDITS.md](docs/CLOUD_CREDITS.md)
- Building, packaging and marketing a Claude Code skill → [docs/CLAUDE_SKILLS_GUIDE.md](docs/CLAUDE_SKILLS_GUIDE.md)

This repo is also a Claude Code plugin marketplace. Its
[`launchpad`](plugins/launchpad) plugin checks a skill and writes its launch kit
(README, demo video script, posts):

```bash
claude plugin marketplace add namratabhatia21/Agentic
claude plugin install launchpad@namrata-skills
```

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: paste your HF_TOKEN (huggingface.co/settings/tokens), change the passwords
docker compose up -d --build
open http://localhost:8080
```

Fully self-hosted, no API keys at all (Ollama downloads `qwen3:8b`, ~5 GB, on first start):

```bash
# in .env: LLM_PROVIDER=local
docker compose --profile local-llm up -d --build
```

On CPU an 8B model answers in tens of seconds. With an NVIDIA GPU, add `gpus: all` to the
`ollama` service and try a larger model (`LOCAL_MODEL=qwen3:32b`).

With monitoring (Prometheus on :9090, Grafana on :3000):

```bash
docker compose --profile monitoring up -d --build
```

Behind a TLS-intercepting corporate proxy, pass its CA when building:
`docker build --secret id=pip_ca,src=/path/to/ca.crt -t agentic-api:latest .`

## Local development

```bash
python -m venv .venv && . .venv/bin/activate
make install          # app + dev dependencies
make dev              # postgres+redis in docker, API with autoreload on :8000
make test lint        # pytest + ruff
```

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents` | Bulk-load the knowledge base: `[{"title", "content", "source"}]` (auto-chunked and embedded) |
| `GET` | `/api/images/{id}.png` | Images created by `generate_image` |
| `POST` | `/api/chat` | `{"message": "...", "conversation_id": "<uuid, optional>"}` → `text/event-stream` |
| `GET` | `/api/conversations/{id}` | Conversation transcript (text) |
| `GET` | `/api/tools` | Enabled tools, provider and model |
| `GET` | `/healthz` / `/readyz` | Liveness / readiness (checks Postgres and Redis) |
| `GET` | `/metrics` | Prometheus metrics (blocked at Nginx, internal only) |

When `API_KEYS` is set, send `X-API-Key: <key>`. The UI has an "API key" button.

SSE event types: `conversation`, `thinking`, `text`, `tool_call`, `tool_result`,
`notice`, `refusal`, `error`, `done`.

```bash
curl -N http://localhost:8080/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"Newest arXiv papers on agent memory? Top 3 with links."}'
```

## Configuration

All settings come from environment variables. See [.env.example](.env.example).
The most important ones:

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `huggingface` | `huggingface`, `local`, `anthropic`, `vertex` or `bedrock` |
| `LOCAL_MODEL` | `qwen3:8b` | Model served by Ollama/vLLM/TGI for `local` |
| `LOCAL_LLM_URL` | `http://ollama:11434/v1` | OpenAI-compatible endpoint for `local` |
| `MODEL` | `claude-opus-5-5` | Claude model (Claude providers only) |
| `HF_TOKEN` | *(empty)* | Enables the open-model provider, image generation and classification |
| `HF_CHAT_MODEL` | `Qwen/Qwen3-235B-A22B-Instruct-2507` | Any HF chat model with tool calling |
| `EMBEDDINGS_URL` | `http://embeddings:80` | Text Embeddings Inference server (compose service) |
| `EFFORT` | `medium` | `low` … `max`. Trades quality against cost and latency. |
| `API_KEYS` | *(empty)* | Comma-separated. **Set in production.** |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per API key (or per IP when auth is off) |
| `MAX_AGENT_STEPS` | `12` | Upper bound on model↔tool round-trips per message |

## Hugging Face integration

| Feature | How | Needs |
|---|---|---|
| Semantic search | `embeddings` compose service runs [Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference) with `BAAI/bge-small-en-v1.5` on CPU. Vectors go in pgvector, and results are fused with keyword search (reciprocal rank fusion). | Nothing. Free and local. |
| Open-weight chat model (default) | `LLM_PROVIDER=huggingface` runs the whole agent on `HF_CHAT_MODEL` through Inference Providers (OpenAI-compatible tool calling). | `HF_TOKEN` |
| `generate_image` tool | FLUX.1-schnell text-to-image, stored in Postgres, shown inline in the chat | `HF_TOKEN` |
| `classify_text` tool | `cardiffnlp/twitter-roberta-base-sentiment-latest`, `facebook/bart-large-mnli` zero-shot | `HF_TOKEN` |
| `search_huggingface_hub` tool | Trending, popular or newest models, datasets and Spaces | Nothing |

Load your own documents into the knowledge base:

```bash
curl -X POST http://localhost:8080/api/documents -H 'Content-Type: application/json' \
  -d '[{"title": "Refund policy", "content": "Customers may get their money back within 30 days."}]'
```

Which model to pick: large open models (Qwen3-235B on Hugging Face) handle the tools
well. Small local models (8B) are private and free but call tools less reliably on
long multi-step questions. Claude is optional if you want the strongest tool use; the
app and UI work the same with every provider.

## Deploy to Google Cloud

```bash
PROJECT_ID=your-project ./deploy/cloudrun.sh
```

This creates Cloud Run, Cloud SQL, Memorystore, Artifact Registry and Secret Manager
entries. Pass `HF_TOKEN=hf_...` to use the open-source model (default), or
`LLM_PROVIDER=vertex` to serve Claude from Vertex AI with GCP credits. Details and costs are in
[docs/CLOUD_CREDITS.md](docs/CLOUD_CREDITS.md).

## Project layout

```
app/
  main.py          HTTP API, SSE, auth, rate limiting, health, metrics
  agent.py         agent loop (stream → tools in parallel → repeat)
  llm.py           Anthropic / Vertex / Bedrock client factory
  tools/           one file per tool + registry
  static/          chat UI
  hf_agent.py      agent loop for open-weight Hugging Face models
  embeddings.py    Hugging Face embeddings (TEI or hosted)
db/init/           read-only role + analytics demo data (first Postgres start)
nginx/             reverse proxy config
monitoring/        Prometheus + Grafana provisioning
deploy/            Cloud Run deployment script
tests/             unit tests incl. agent loop against a fake model
plugins/launchpad/ Claude Code plugin: preflight + launch kit for skills
.claude-plugin/    marketplace manifest that lists the plugin
```
