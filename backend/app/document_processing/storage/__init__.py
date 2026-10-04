from functools import lru_cache

from app.core.config import get_settings
from app.document_processing.storage.base import StorageBackend
from app.document_processing.storage.local_backend import LocalFilesystemStorageBackend
from app.document_processing.storage.s3_backend import S3StorageBackend

__all__ = ["StorageBackend", "get_storage_backend"]


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.storage_provider == "local":
        return LocalFilesystemStorageBackend(settings.local_storage_path)
    return S3StorageBackend(
        bucket=settings.s3_bucket_name,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    )
