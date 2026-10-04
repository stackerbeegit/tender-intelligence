"""
Dispatches to the right extractor by detected content type, returning a
uniform `(pages, needs_ocr)` shape regardless of format — only PDF pages
can ever need OCR, so `needs_ocr` is all-False for every other format.
"""
from app.core.exceptions import UnsupportedFileTypeError
from app.document_processing.extractors.docx_extractor import extract_docx
from app.document_processing.extractors.pdf_extractor import extract_pdf
from app.document_processing.extractors.xlsx_extractor import extract_xlsx
from app.document_processing.extractors.zip_extractor import extract_zip

_WORD_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
_EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


def extract_pages(data: bytes, content_type: str) -> tuple[list[str], list[bool]]:
    if content_type == "application/pdf":
        result = extract_pdf(data)
        return result.pages, result.needs_ocr

    if content_type in _WORD_TYPES:
        pages = extract_docx(data)
        return pages, [False] * len(pages)

    if content_type in _EXCEL_TYPES:
        pages = extract_xlsx(data)
        return pages, [False] * len(pages)

    if content_type == "application/zip":
        pages = extract_zip(data)
        return pages, [False] * len(pages)

    raise UnsupportedFileTypeError(f"No extractor for content type {content_type!r}")
