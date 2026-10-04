"""Tender document bundles are sometimes a single ZIP containing the NIT,
annexures, and BOQ as separate files. Extract each supported member and
concatenate, prefixed with its filename so the source of each page stays
traceable. Nested ZIPs aren't recursed into (no legitimate case observed
yet, and it avoids an unbounded-recursion/zip-bomb-shaped surface)."""
import zipfile
from io import BytesIO

import magic


def extract_zip(data: bytes) -> list[str]:
    from app.document_processing.extractors import extract_pages  # local import avoids a circular import

    pages: list[str] = []
    with zipfile.ZipFile(BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member_bytes = archive.read(info)
            content_type = magic.from_buffer(member_bytes, mime=True)
            if content_type == "application/zip":
                continue  # not recursing into nested archives
            try:
                member_pages, _ = extract_pages(member_bytes, content_type)
            except Exception as exc:  # noqa: BLE001 — one bad member shouldn't fail the whole bundle
                pages.append(f"[File: {info.filename}] (could not extract: {exc})")
                continue
            for page in member_pages:
                pages.append(f"[File: {info.filename}]\n{page}")

    return pages
