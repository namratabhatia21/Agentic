"""Core pipeline: parse -> dedupe -> summarize -> embed -> ES + Azure AI Search."""

import asyncio
import csv
import hashlib
import io
import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from . import jobs
from .ai import AzureOpenAI
from .config import IngestSettings
from .parsers import parse
from .schemas import SPECS, DocType, record_text
from .sinks.azure_search import AzureSearchSink
from .sinks.blob import BlobSink
from .sinks.elastic import ElasticSink

log = logging.getLogger(__name__)


def index_names(doc_type: DocType, date: datetime, mode: str) -> dict:
    p = SPECS[doc_type].prefix
    suffix = date.strftime("%Y%m%d") if mode == "versioned" else "current-data"
    return {
        "elasticsearch_index": f"{p}-{suffix}",
        "elasticsearch_alias": f"{p}-current",
        "azure_search_index": f"{p}-idx-{suffix}",
        "azure_search_alias": f"{p}-current",
    }


class Pipeline:
    def __init__(self, s: IngestSettings, redis: Redis):
        self.s, self.r = s, redis
        self.blob, self.ai = BlobSink(s), AzureOpenAI(s)
        self.es, self.az = ElasticSink(s), AzureSearchSink(s)

    async def aclose(self) -> None:
        for c in (self.blob, self.ai, self.es, self.az):
            await c.aclose()

    async def run(self, job_id: str, doc_type: DocType, filename: str, data: bytes) -> dict:
        spec = SPECS[doc_type]
        now = datetime.now(UTC)
        names = index_names(doc_type, now, self.s.index_mode)
        await jobs.save(self.r, job_id, status="running", **names)

        records = parse(filename, data)
        for i, rec in enumerate(records):
            if not rec.get(spec.id_field):
                rec[spec.id_field] = f"{job_id}-{i}"

        # Dedupe on content hash: unchanged records keep their cached summary.
        hkey = f"ingest:hash:{doc_type}"
        todo, cached = [], 0
        for rec in records:
            h = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
            prev = await self.r.hget(hkey, rec[spec.id_field])
            prev = json.loads(prev) if prev else None
            if prev and prev["h"] == h and prev.get("summary"):
                rec["summary"] = prev["summary"]
                cached += 1
            else:
                todo.append(rec)
            rec["_hash"] = h

        sem = asyncio.Semaphore(self.s.summary_batch_size)

        async def summarize(rec: dict) -> None:
            async with sem:
                rec["summary"] = rec.get("summary") or await self.ai.summarize(
                    spec.summary_prompt, record_text(spec, rec)
                )

        await asyncio.gather(*(summarize(r) for r in todo))

        embeddings = None
        if self.ai.enabled and self.s.aoai_embed_deployment:
            embeddings = []
            for i in range(0, len(records), 64):
                chunk = records[i : i + 64]
                embeddings += await self.ai.embed(
                    [r["summary"] or record_text(spec, r) for r in chunk]
                ) or []

        iso = now.isoformat()
        docs = []
        for i, rec in enumerate(records):
            h = rec.pop("_hash")
            cache = json.dumps({"h": h, "summary": rec["summary"]})
            await self.r.hset(hkey, rec[spec.id_field], cache)
            d = {**rec, "record_id": str(rec[spec.id_field]), "doc_type": str(doc_type),
                 "ingest_date": iso}
            if embeddings:
                d["embedding"] = embeddings[i]
            docs.append(d)

        date_path = now.strftime("%Y-%m-%d")
        summary_blob = await self.blob.put(
            f"summaries/{doc_type}/{date_path}/{job_id}_summaries.csv", _to_csv(docs)
        )

        es_idx = names["elasticsearch_index"]
        await self.es.ensure_index(es_idx, bool(embeddings))
        es_errors = await self.es.bulk(es_idx, docs)
        await self.es.swap_alias(names["elasticsearch_alias"], es_idx)

        az_errors = None
        if self.az.enabled:
            fields = sorted({k for d in docs for k in d} - {"record_id", "doc_type",
                            "ingest_date", "summary", "embedding", "key"})
            az_idx = names["azure_search_index"]
            await self.az.ensure_index(az_idx, fields, bool(embeddings))
            az_errors = await self.az.upload(az_idx, docs, fields)
            try:
                await self.az.swap_alias(names["azure_search_alias"], az_idx)
            except Exception as e:  # aliases are preview; don't fail the job
                log.warning("Azure Search alias swap failed: %s", e)
        else:
            names["azure_search_index"] = names["azure_search_alias"] = None

        return await jobs.save(
            self.r, job_id, status="done", ingest_date=iso, **names,
            records=len(docs), summarized=len(todo), cached=cached,
            es_errors=es_errors, azure_errors=az_errors, summaries_blob=summary_blob,
        )


def _to_csv(docs: list[dict]) -> bytes:
    cols = sorted({k for d in docs for k in d if k != "embedding"})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(docs)
    return buf.getvalue().encode()
