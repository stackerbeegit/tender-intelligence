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
