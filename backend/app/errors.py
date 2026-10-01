"""Expected failures. The API turns them into {"error": {"code": CODE, "message": text}}."""


class AppError(Exception):
    """Base exception for all application errors."""

    status_code = 400
    code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    """No valid session (missing, unknown or expired cookie)."""

    status_code = 401
    code = "UNAUTHORIZED"


class CsrfRejectedError(AppError):
    """An unsafe request that did not prove it came from our own pages."""

    status_code = 403
    code = "CSRF_REJECTED"


class ExternalServiceError(AppError):
    """A dependency (database, storage, upstream API) failed; details stay in the logs."""

    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"


class ServiceUnavailableError(AppError):
    """A feature is not configured on this deployment (e.g. Google login in local dev)."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"


class OAuthLoginError(AppError):
    """The OAuth provider rejected or could not complete the login. Never shown verbatim."""

    status_code = 400
    code = "OAUTH_FAILED"


class InvalidBlobKeyError(AppError):
    """A storage key failed validation (traversal, bad characters, too long)."""

    status_code = 400
    code = "INVALID_STORAGE_KEY"


class BlobNotFoundError(AppError):
    """No object is stored under the key."""

    status_code = 404
    code = "NOT_FOUND"
