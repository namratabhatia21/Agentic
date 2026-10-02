"""Upload API: `uvicorn ingest.api:app`.

POST /upload    file + doc_type (8d|rexm|cq) -> index names + date
GET  /jobs/{id} job status, index names, counts
GET  /indexes   which physical ES index each {type}-current alias points at
"""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from redis.asyncio import Redis

from . import jobs
from .config import get_settings
from .parsers import parse
from .pipeline import Pipeline, index_names
from .schemas import SPECS, DocType

MAX_BYTES = 200 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.redis = Redis.from_url(s.redis_url, decode_responses=True)
    app.state.pipeline = Pipeline(s, app.state.redis)
    yield
    await app.state.pipeline.aclose()
    await app.state.redis.aclose()


app = FastAPI(title="Document Ingestion", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload", status_code=202)
async def upload(file: Annotated[UploadFile, File()], doc_type: Annotated[DocType, Form()]):
    s, r, p = get_settings(), app.state.redis, app.state.pipeline
    data = await file.read()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(400, "Empty or too large file")
    try:
        n = len(parse(file.filename or "", data))  # fail fast on bad files
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    job_id, now = jobs.new_job_id(), datetime.now(UTC)
    names = index_names(doc_type, now, s.index_mode)
    blob_path = f"raw/{doc_type}/{now:%Y-%m-%d}/{job_id}_{file.filename}"
    stored = await p.blob.put(blob_path, data)

    if s.run_inline or not stored:
        result = await p.run(job_id, doc_type, file.filename or "", data)
        return result

    await jobs.save(r, job_id, status="queued", doc_type=str(doc_type), filename=file.filename,
                    records=n, ingest_date=now.isoformat(), raw_blob=stored, **names)
    await r.rpush(s.queue_name, json.dumps({"job_id": job_id, "doc_type": str(doc_type),
                                            "filename": file.filename, "blob_path": blob_path}))
    return {"job_id": job_id, "status": "queued", "doc_type": doc_type, "records": n,
            "ingest_date": now.isoformat(), **names}


@app.get("/jobs/{job_id}")
async def job(job_id: str):
    j = await jobs.load(app.state.redis, job_id)
    if not j:
        raise HTTPException(404, "Unknown job")
    return j


@app.get("/indexes")
async def indexes():
    es = app.state.pipeline.es
    return {
        str(t): {"alias": f"{spec.prefix}-current",
                 "elasticsearch_index": await es.alias_target(f"{spec.prefix}-current")}
        for t, spec in SPECS.items()
    }
