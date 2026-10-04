"""Native (non-scanned) PDF text extraction. A page with little or no
extractable text is almost certainly a scanned image — `needs_ocr` on
that index tells the caller to run OCR for it rather than guessing."""
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

from app.core.config import get_settings


@dataclass
class PdfExtractionResult:
    pages: list[str]
    needs_ocr: list[bool]


def extract_pdf(data: bytes) -> PdfExtractionResult:
    settings = get_settings()
    reader = PdfReader(BytesIO(data))

    pages: list[str] = []
    needs_ocr: list[bool] = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        pages.append(text)
        needs_ocr.append(len(text) < settings.ocr_min_chars_per_page)

    return PdfExtractionResult(pages=pages, needs_ocr=needs_ocr)
