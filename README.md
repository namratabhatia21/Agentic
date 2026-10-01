# Agentic

A production-ready **agentic chatbot** that answers from live data. The model plans,
calls tools in parallel, reads the results and cites its sources. Every step streams
to the browser as it happens.

**Models:** Claude Opus 5.5 (through the Anthropic API, Google Vertex AI or Amazon
Bedrock), or an **open-weight model from Hugging Face** (Qwen, Llama, ...) through
Hugging Face Inference Providers. Switch with one environment variable and pay with
whichever credits you have.

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

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: choose LLM_PROVIDER and fill in its credentials, change the passwords
docker compose up -d --build
open http://localhost:8080
```

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
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `vertex`, `bedrock` or `huggingface` |
| `MODEL` | `claude-opus-5-5` | Claude model (first three providers) |
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
| Open-weight chat model | `LLM_PROVIDER=huggingface` runs the whole agent on `HF_CHAT_MODEL` through Inference Providers (OpenAI-compatible tool calling). | `HF_TOKEN` |
| `generate_image` tool | FLUX.1-schnell text-to-image, stored in Postgres, shown inline in the chat | `HF_TOKEN` |
| `classify_text` tool | `cardiffnlp/twitter-roberta-base-sentiment-latest`, `facebook/bart-large-mnli` zero-shot | `HF_TOKEN` |
| `search_huggingface_hub` tool | Trending, popular or newest models, datasets and Spaces | Nothing |

Load your own documents into the knowledge base:

```bash
curl -X POST http://localhost:8080/api/documents -H 'Content-Type: application/json' \
  -d '[{"title": "Refund policy", "content": "Customers may get their money back within 30 days."}]'
```

Claude is still the default "brain". It is markedly better at multi-step tool use.
The open-model mode is there for cost, data-residency or open-source requirements.
Try it with `LLM_PROVIDER=huggingface` and compare.

## Deploy to Google Cloud

```bash
PROJECT_ID=your-project ./deploy/cloudrun.sh
```

This creates Cloud Run, Cloud SQL, Memorystore, Artifact Registry and Secret Manager
entries, and serves Claude from Vertex AI. Details and costs are in
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
```
