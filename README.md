# Agentic

A production-ready **agentic chatbot** that answers from live data. Claude (Opus 5.5)
plans, calls tools in parallel, reads the results and cites its sources. Every step
streams to the browser as it happens.

**Tools:** web search & fetch · arXiv (latest papers) · Hacker News (tech news) ·
Wikipedia · weather · ECB exchange rates · private knowledge base (Postgres full-text)
· read-only analytics SQL · calculator · clock.

**Stack:** FastAPI · PostgreSQL · Redis · Nginx · Docker Compose · Prometheus/Grafana
· GitHub Actions CI · Cloud Run deploy script. Claude can run through the **Anthropic
API, Google Vertex AI or Amazon Bedrock**, so you can pay with whichever cloud
credits you have.

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
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `vertex` or `bedrock` |
| `MODEL` | `claude-opus-5-5` | |
| `EFFORT` | `medium` | `low` … `max`. Trades quality against cost and latency. |
| `API_KEYS` | *(empty)* | Comma-separated. **Set in production.** |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per API key (or per IP when auth is off) |
| `MAX_AGENT_STEPS` | `12` | Upper bound on model↔tool round-trips per message |

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
db/init/           read-only role + analytics demo data (first Postgres start)
nginx/             reverse proxy config
monitoring/        Prometheus + Grafana provisioning
deploy/            Cloud Run deployment script
tests/             unit tests incl. agent loop against a fake model
```
