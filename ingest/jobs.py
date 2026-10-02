"""Job state and queue in Redis."""

import json
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis

TTL = 7 * 24 * 3600


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


async def save(r: Redis, job_id: str, **fields) -> dict:
    key = f"ingest:job:{job_id}"
    cur = json.loads(await r.get(key) or "{}")
    cur.update(fields, job_id=job_id, updated_at=datetime.now(UTC).isoformat())
    await r.set(key, json.dumps(cur), ex=TTL)
    return cur


async def load(r: Redis, job_id: str) -> dict | None:
    raw = await r.get(f"ingest:job:{job_id}")
    return json.loads(raw) if raw else None
