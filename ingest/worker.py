"""Queue worker: `python -m ingest.worker`. Pulls jobs from Redis, raw files from Blob."""

import asyncio
import json
import logging

from redis.asyncio import Redis

from . import jobs
from .config import get_settings
from .pipeline import Pipeline
from .schemas import DocType

log = logging.getLogger("ingest.worker")


async def main() -> None:
    s = get_settings()
    r = Redis.from_url(s.redis_url, decode_responses=True)
    p = Pipeline(s, r)
    log.info("worker listening on %s", s.queue_name)
    try:
        while True:
            item = await r.blpop(s.queue_name, timeout=5)
            if not item:
                continue
            msg = json.loads(item[1])
            try:
                data = await p.blob.get(msg["blob_path"])
                await p.run(msg["job_id"], DocType(msg["doc_type"]), msg["filename"], data)
            except Exception as e:
                log.exception("job %s failed", msg["job_id"])
                await jobs.save(r, msg["job_id"], status="failed", error=str(e))
    finally:
        await p.aclose()
        await r.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
