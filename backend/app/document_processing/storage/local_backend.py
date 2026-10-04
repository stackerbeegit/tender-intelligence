"""
Plain filesystem storage — for dev environments without a running MinIO/S3
(this project's native-Postgres local setup has no MinIO service). Not
used in Docker, where `storage_provider=minio` selects S3StorageBackend
instead; see docker-compose.yml.
"""
from pathlib import Path

from app.document_processing.storage.base import StorageBackend


class LocalFilesystemStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self._base_path = Path(base_path).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Keys are built by our own code (tenders/{id}/documents/{id}/...),
        # never taken verbatim from user input — this check is defense in
        # depth against a future caller passing something unexpected, not
        # a trust boundary we expect to actually hit.
        if ".." in Path(key).parts:
            raise ValueError(f"Refusing a storage key containing '..': {key!r}")
        return self._base_path / key

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()
