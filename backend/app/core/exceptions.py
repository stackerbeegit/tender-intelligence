"""
Domain-level exceptions. Services raise these; the API layer (api/v1/*)
catches them and translates to the appropriate HTTP response. Keeping them
separate from HTTPException means services stay framework-agnostic and are
unit-testable without spinning up FastAPI.
"""


class DomainError(Exception):
    """Base class for all domain-level errors."""


class EmailAlreadyRegisteredError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class InactiveUserError(DomainError):
    pass


class RoleNotFoundError(DomainError):
    pass


class InvalidTokenError(DomainError):
    pass


class DocumentDownloadError(DomainError):
    """The source URL could not be fetched (network error, non-2xx, timeout)."""


class UnsupportedFileTypeError(DomainError):
    """The file's detected content type isn't one we process (see
    settings.allowed_document_mime_types)."""


class FileTooLargeError(DomainError):
    """Exceeds settings.max_document_size_bytes."""


class LLMNotConfiguredError(DomainError):
    """LLM_PROVIDER names an unknown provider, or the selected provider
    has no API key set."""


class LLMResponseError(DomainError):
    """The provider call failed (network/API error, refusal, truncated or
    non-JSON output). Vendor SDK exceptions are translated into this one
    type inside each adapter so callers never import a vendor SDK."""


class OcrUnavailableError(DomainError):
    """The tesseract binary (or poppler, for PDF-to-image rendering)
    isn't installed/reachable. Raised rather than letting pytesseract's
    own exception leak past this module, so every caller has one
    exception type to catch regardless of which underlying tool is
    missing."""
