"""File validation: detect the real content type from the bytes
themselves (never trust a filename extension or a connector/portal's
claimed type), and enforce a size ceiling — both before anything
downstream touches the file."""
import zipfile
from io import BytesIO

import magic

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_GENERIC_ZIP_MIMES = {"application/octet-stream", "application/zip"}


def detect_content_type(data: bytes) -> str:
    """
    `magic`'s MIME-type lookup is only as good as the installed magic
    database — on this system it recognises Word/Excel OOXML files
    textually ("Microsoft OOXML") but has no MIME mapping for the Word
    variant specifically, falling back to `application/octet-stream`.
    Rather than trust that gap, any zip-shaped file magic can't pin down
    gets its internal structure inspected directly (`word/document.xml`
    vs `xl/workbook.xml` are the actual OOXML-mandated markers) — still
    content-based detection, just one layer deeper than a single library
    call, and robust regardless of which magic database version a given
    deployment happens to have installed.
    """
    detected = magic.from_buffer(data, mime=True)
    if detected not in _GENERIC_ZIP_MIMES:
        return detected

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return detected

    if "word/document.xml" in names:
        return _DOCX_MIME
    if "xl/workbook.xml" in names:
        return _XLSX_MIME
    return "application/zip"


def validate_file(data: bytes, file_name: str) -> str:
    """Returns the detected content type, or raises."""
    settings = get_settings()

    if len(data) > settings.max_document_size_bytes:
        raise FileTooLargeError(
            f"{file_name} is {len(data)} bytes, exceeding the {settings.max_document_size_bytes}-byte limit"
        )

    content_type = detect_content_type(data)
    if content_type not in settings.allowed_document_mime_types:
        raise UnsupportedFileTypeError(f"{file_name} has content type {content_type!r}, which is not supported")

    return content_type
