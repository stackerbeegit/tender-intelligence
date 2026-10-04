"""Fetches a document's bytes from its `source_url`. Isolated here so the
rest of the pipeline (validation, extraction) never deals with network
concerns directly."""
import httpx

from app.core.config import get_settings
from app.core.exceptions import DocumentDownloadError


def download_document(url: str) -> bytes:
    settings = get_settings()
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"User-Agent": settings.crawler_user_agent},
            timeout=settings.document_download_timeout_seconds,
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            chunks = bytearray()
            for chunk in response.iter_bytes():
                chunks.extend(chunk)
                if len(chunks) > settings.max_document_size_bytes:
                    raise DocumentDownloadError(
                        f"{url} exceeds the maximum document size of {settings.max_document_size_bytes} bytes"
                    )
            return bytes(chunks)
    except httpx.HTTPError as exc:
        raise DocumentDownloadError(f"Could not download {url}: {exc}") from exc
