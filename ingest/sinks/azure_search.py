"""Azure AI Search: create index, upload docs, point the {prefix}-current alias at it."""

import re

import httpx

from ..config import IngestSettings

_KEY_RE = re.compile(r"[^A-Za-z0-9_\-=]")


class AzureSearchSink:
    def __init__(self, s: IngestSettings):
        self.enabled = bool(s.azure_search_endpoint and s.azure_search_key)
        self.v = s.azure_search_api_version
        self.dims = s.embed_dims
        self.c = httpx.AsyncClient(
            base_url=(s.azure_search_endpoint or "http://disabled").rstrip("/"),
            headers={"api-key": s.azure_search_key or ""},
            timeout=60,
        )

    async def ensure_index(self, name: str, extra_fields: list[str], with_vector: bool) -> None:
        if (await self.c.get(f"/indexes/{name}?api-version={self.v}")).status_code == 200:
            return
        fields = [
            {"name": "key", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "record_id", "type": "Edm.String", "filterable": True},
            {"name": "doc_type", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "ingest_date", "type": "Edm.DateTimeOffset", "filterable": True,
             "sortable": True},
            {"name": "summary", "type": "Edm.String", "searchable": True},
        ] + [{"name": f, "type": "Edm.String", "searchable": True} for f in extra_fields]
        body: dict = {
            "name": name,
            "fields": fields,
            "semantic": {"configurations": [{
                "name": "default",
                "prioritizedFields": {"prioritizedContentFields": [{"fieldName": "summary"}]},
            }]},
        }
        if with_vector:
            fields.append({"name": "embedding", "type": "Collection(Edm.Single)",
                           "searchable": True, "dimensions": self.dims,
                           "vectorSearchProfile": "default"})
            body["vectorSearch"] = {
                "algorithms": [{"name": "hnsw", "kind": "hnsw"}],
                "profiles": [{"name": "default", "algorithm": "hnsw"}],
            }
        r = await self.c.put(f"/indexes/{name}?api-version={self.v}", json=body)
        r.raise_for_status()

    async def upload(self, index: str, docs: list[dict], fields: list[str]) -> int:
        allowed = {"record_id", "doc_type", "ingest_date", "summary", "embedding", *fields}
        errors = 0
        for i in range(0, len(docs), 1000):
            batch = [
                {"@search.action": "mergeOrUpload", "key": _KEY_RE.sub("_", d["record_id"]),
                 **{k: v for k, v in d.items() if k in allowed}}
                for d in docs[i : i + 1000]
            ]
            r = await self.c.post(f"/indexes/{index}/docs/index?api-version={self.v}",
                                  json={"value": batch})
            if r.status_code not in (200, 207):
                r.raise_for_status()
            errors += sum(1 for v in r.json()["value"] if not v["status"])
        return errors

    async def swap_alias(self, alias: str, index: str) -> None:
        # Index aliases are a preview feature; failure here is non-fatal.
        r = await self.c.put(f"/aliases/{alias}?api-version=2024-07-01-preview",
                             json={"name": alias, "indexes": [index]})
        r.raise_for_status()

    async def aclose(self) -> None:
        await self.c.aclose()
