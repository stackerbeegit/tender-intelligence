"""
Storage backend interface. Every document (tender attachment) is written
and read through this, never via a direct filesystem/boto3 call elsewhere
— that's what keeps "swap MinIO for S3 in production" a one-line config
change rather than a code change.
"""
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Write `data` under `key`, creating any intermediate structure."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Raise FileNotFoundError if `key` doesn't exist."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...
