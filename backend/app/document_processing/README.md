# Document processing

Implemented (Sprint 3): download/validation (`downloader.py`, `validators.py`),
per-format text extraction (`extractors/` — PDF, DOCX, XLSX, ZIP bundles), OCR fallback
for scanned PDF pages (`ocr.py`), object storage (`storage/` — local filesystem or
S3-compatible, picked via `settings.storage_provider`), and a pure chunking utility
(`chunking.py`) ready for Sprint 4/7 to call. `app/services/document_processing_service.py`
orchestrates all of it.

OCR requires `tesseract-ocr` + `poppler-utils` as system binaries, installed in the
backend Docker image but not assumed to exist everywhere — `ocr.py` raises
`OcrUnavailableError` rather than crashing when they're missing, and that path is tested
for real in this project's dev environment (tesseract genuinely isn't installed here).

Not yet wired up: persisting chunks/embeddings (no `tender_embeddings` table until
Sprint 7) and automatic processing on ingestion (deliberately decoupled from
connectors/manual entry per `docs/architecture.md` §3 — a document is processed by an
explicit `POST .../documents/{id}/process` call, not implicitly during crawl/upload).
