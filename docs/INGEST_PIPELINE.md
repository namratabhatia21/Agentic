# Ingestion Pipeline: 8D / RexMCards / CQ → Elasticsearch + Azure AI Search

## Context
Three document families (8D, RexMCards, CQ) are already in Elasticsearch and Azure AI Search, with AI summaries generated as CSVs by hand. The goal is one automated pipeline: upload a file through FastAPI, and the API returns the index names and the date the data was written. Stack: Blob Storage, Elasticsearch, Redis, Azure AI Search, GitLab CI/CD. The existing repo (`app/main.py` FastAPI, `Dockerfile`, `docker-compose.yml`) is a separate agent app. The new code goes in a new `ingest/` package and reuses its config and logging patterns (`app/config.py`, `app/logging_setup.py`).

## Architecture
```
Client ─POST /upload (file, doc_type)─► FastAPI
   1. validate type (8d|rexm|cq) + schema
   2. save raw → Blob: raw/{doc_type}/{YYYY-MM-DD}/{job_id}_{name}
   3. job record → Redis (status=queued) + push to queue
   ◄─ 202 {job_id, doc_type, target indexes, ingest_date}
Worker (same image, `python -m ingest.worker`, RQ/arq on Redis)
   4. parse (CSV/XLSX/PDF) → normalize to the doc_type's schema
   5. dedupe: hash per record, cached in Redis (skip unchanged rows)
   6. AI summary per record (batched LLM) → write summaries CSV to Blob: summaries/{doc_type}/{date}/
   7. embed (summary + key fields)
   8. bulk upsert → ES index  {doc_type}-{YYYYMMDD}, then alias {doc_type}-current is swapped
   9. upload → Azure AI Search index {doc_type}-idx-{YYYYMMDD} (vector + semantic config), same alias/swap pattern
  10. Redis job → done {es_index, azure_index, date, counts, errors}
GET /jobs/{job_id} → status + index names + date
GET /indexes → current alias → index map per doc_type
```
The upload stays fast because the LLM summaries run in the worker. If you want a synchronous response, the small-file path can run steps 4–10 inline. Default is async.

## Module layout (`ingest/`)
- `api.py`: FastAPI routes `/upload`, `/jobs/{id}`, `/indexes`, `/health`
- `config.py`: pydantic settings (Blob conn string, ES URL/key, Azure Search endpoint/key, Redis URL, LLM key)
- `schemas/`: one pydantic model per doc type: `eight_d.py`, `rexm_card.py`, `cq.py` (field mapping, ID field, text fields to summarize)
- `parsers.py`, `summarize.py` (prompt per doc type, batching, retry), `embed.py`
- `sinks/blob.py`, `sinks/elastic.py` (index template + bulk + alias swap), `sinks/azure_search.py` (index definition + upload + alias)
- `jobs.py`: Redis job state + queue; `worker.py`
- `tests/`: parsers, schema mapping, sinks against mocks

## Index naming / dates
- Versioned physical index per run: `8d-20261002`, `rexm-20261002`, `cq-20261002`. Readers query the stable alias `*-current`, so a bad load can be rolled back by moving the alias.
- Optional mode: incremental upsert into the current index (no new index), keyed on the record ID. Decide per doc type.

## GitLab CI/CD (`.gitlab-ci.yml`)
Stages: `lint` (ruff, mypy) → `test` (pytest, with ES + Redis service containers) → `build` (Docker image → ACR) → `deploy` (Azure Container Apps or AKS: API + worker as two apps from one image) → optional `reindex` (manual/scheduled job that runs `python -m ingest.reindex --doc-type all` for full rebuilds from Blob). Secrets live in GitLab CI variables or Key Vault.

## Verification
- `docker-compose` with ES, Redis, and Azurite (Blob emulator). Upload a sample file for each type, poll `/jobs/{id}`, and check the ES doc counts and alias. Check the summaries CSV in Azurite.
- Run Azure AI Search against a dev service instance with the same sample files.
- Run the pytest suite in CI.

## Open points to confirm before building
- Input file formats per type (CSV/XLSX/PDF?) and the ID field for each
- Full reindex vs incremental upsert
- Which LLM and embedding model to use for summaries (Azure OpenAI?)
- Sync vs async upload response
