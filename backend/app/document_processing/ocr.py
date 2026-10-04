"""
OCR fallback for scanned PDF pages. Requires `tesseract-ocr` (the OCR
engine) and `poppler-utils` (pdf2image's PDF-to-image rendering) as system
binaries — installed in the backend Docker image (see Dockerfile); not
assumed to exist in every environment, which is exactly why a missing
binary raises `OcrUnavailableError` rather than crashing the caller.
"""
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError
from PIL import Image
from pytesseract import TesseractNotFoundError, image_to_string

from app.core.exceptions import OcrUnavailableError


def ocr_pdf_page(pdf_bytes: bytes, page_number: int) -> str:
    """`page_number` is 0-indexed, matching the rest of this codebase's
    `pages` lists; pdf2image's own `first_page`/`last_page` are 1-indexed."""
    try:
        images: list[Image.Image] = convert_from_bytes(
            pdf_bytes, first_page=page_number + 1, last_page=page_number + 1
        )
    except PDFInfoNotInstalledError as exc:
        raise OcrUnavailableError("poppler-utils (pdftoppm/pdfinfo) is not installed") from exc

    if not images:
        return ""

    try:
        return image_to_string(images[0]).strip()
    except TesseractNotFoundError as exc:
        raise OcrUnavailableError("tesseract-ocr is not installed") from exc
