"""Elasticsearch: create index, bulk upsert, swap the {prefix}-current alias."""

import json

import httpx

from ..config import IngestSettings


class ElasticSink:
    def __init__(self, s: IngestSettings):
        headers = {"Content-Type": "application/json"}
        if s.es_api_key:
            headers["Authorization"] = f"ApiKey {s.es_api_key}"
        self.c = httpx.AsyncClient(base_url=s.es_url.rstrip("/"), headers=headers, timeout=60)
        self.dims = s.embed_dims

    async def ensure_index(self, name: str, with_vector: bool) -> None:
        if (await self.c.head(f"/{name}")).status_code == 200:
            return
        props = {"summary": {"type": "text"}, "doc_type": {"type": "keyword"},
                 "ingest_date": {"type": "date"}, "record_id": {"type": "keyword"}}
        if with_vector:
            props["embedding"] = {"type": "dense_vector", "dims": self.dims,
                                  "index": True, "similarity": "cosine"}
        r = await self.c.put(f"/{name}", json={"mappings": {"properties": props}})
        r.raise_for_status()

    async def bulk(self, index: str, docs: list[dict]) -> int:
        errors = 0
        for i in range(0, len(docs), 500):
            lines = []
            for d in docs[i : i + 500]:
                lines.append(json.dumps({"index": {"_index": index, "_id": d["record_id"]}}))
                lines.append(json.dumps(d))
            r = await self.c.post("/_bulk?refresh=wait_for", content="\n".join(lines) + "\n",
                                  headers={"Content-Type": "application/x-ndjson"})
            r.raise_for_status()
            body = r.json()
            if body.get("errors"):
                errors += sum(1 for it in body["items"] if "error" in it["index"])
        return errors

    async def swap_alias(self, alias: str, index: str) -> None:
        actions = [{"add": {"index": index, "alias": alias}}]
        r = await self.c.get(f"/_alias/{alias}")
        if r.status_code == 200:
            actions = [{"remove": {"index": old, "alias": alias}}
                       for old in r.json() if old != index] + actions
        (await self.c.post("/_aliases", json={"actions": actions})).raise_for_status()

    async def alias_target(self, alias: str) -> str | None:
        r = await self.c.get(f"/_alias/{alias}")
        return next(iter(r.json()), None) if r.status_code == 200 else None

    async def aclose(self) -> None:
        await self.c.aclose()
