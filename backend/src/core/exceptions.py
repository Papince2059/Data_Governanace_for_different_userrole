"""
Domain exceptions for the Enterprise Data Governance System.

All exceptions carry a human-readable message, a machine-readable error_code,
and an HTTP status_code so that API exception handlers can convert them into
consistent JSON error responses without further logic.
"""
from __future__ import annotations


class GovernanceBaseError(Exception):
    """Root exception for every domain error in this system."""

    def __init__(
        self,
        message: str,
        error_code: str = "GOVERNANCE_ERROR",
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"status_code={self.status_code})"
        )


class AuthenticationError(GovernanceBaseError):
    """Raised when a request cannot be authenticated (invalid/missing credentials)."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=401)


class AuthorizationError(GovernanceBaseError):
    """Raised when an authenticated user lacks permission for a resource/action."""

    def __init__(
        self,
        message: str = "Access denied",
        error_code: str = "AUTHORIZATION_ERROR",
        resource: str = "",
        action: str = "",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=403)
        self.resource = resource
        self.action = action


class NotFoundError(GovernanceBaseError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        error_code: str = "NOT_FOUND",
    ) -> None:
        message = f"{resource_type} with id '{resource_id}' was not found"
        super().__init__(message=message, error_code=error_code, status_code=404)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(GovernanceBaseError):
    """Raised when input data fails business-rule or schema validation."""

    def __init__(
        self,
        message: str = "Validation failed",
        error_code: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=422)


class ConflictError(GovernanceBaseError):
    """Raised when an operation conflicts with existing data (e.g., duplicate key)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        error_code: str = "CONFLICT_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=409)


class AuthorizationServiceUnavailableError(GovernanceBaseError):
    """
    Raised when the OpenFGA (or other authz) service is unreachable.
    Defaults to *deny* (503) so the system fails closed.
    """

    def __init__(
        self,
        message: str = "Authorization service unavailable — access denied",
        error_code: str = "AUTHZ_SERVICE_UNAVAILABLE",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=503)


class DocumentIngestionError(GovernanceBaseError):
    """Raised when document parsing or chunking fails during ingestion."""

    def __init__(
        self,
        message: str = "Document ingestion failed",
        error_code: str = "DOCUMENT_INGESTION_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=422)


class EmbeddingError(GovernanceBaseError):
    """Raised when the embedding model fails to produce a vector representation."""

    def __init__(
        self,
        message: str = "Embedding generation failed",
        error_code: str = "EMBEDDING_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=500)


class RateLimitError(GovernanceBaseError):
    """Raised when a client exceeds its configured request rate limit."""

    def __init__(
        self,
        message: str = "Rate limit exceeded — please slow down",
        error_code: str = "RATE_LIMIT_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=429)


class TenantIsolationError(GovernanceBaseError):
    """
    Raised when a cross-tenant data access attempt is detected.
    Always results in a 403 Forbidden regardless of admin status.
    """

    def __init__(
        self,
        message: str = "Cross-tenant access is not permitted",
        error_code: str = "TENANT_ISOLATION_ERROR",
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=403)
