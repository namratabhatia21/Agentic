"""Raw uploads and generated summary CSVs go to Azure Blob Storage."""

from azure.storage.blob.aio import BlobServiceClient

from ..config import IngestSettings


class BlobSink:
    def __init__(self, s: IngestSettings):
        self.enabled = bool(s.blob_connection_string)
        self.container = s.blob_container
        self.svc = (
            BlobServiceClient.from_connection_string(s.blob_connection_string)
            if self.enabled
            else None
        )

    async def put(self, path: str, data: bytes) -> str | None:
        if not self.svc:
            return None
        cc = self.svc.get_container_client(self.container)
        if not await cc.exists():
            await cc.create_container()
        await cc.upload_blob(path, data, overwrite=True)
        return f"{self.container}/{path}"

    async def get(self, path: str) -> bytes:
        cc = self.svc.get_container_client(self.container)
        return await (await cc.download_blob(path)).readall()

    async def aclose(self) -> None:
        if self.svc:
            await self.svc.close()
