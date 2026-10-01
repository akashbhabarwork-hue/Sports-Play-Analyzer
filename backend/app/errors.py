class AppError(Exception):
    """Base exception for all application errors."""

    status_code = 400


class ExternalServiceError(AppError):
    """A dependency (database, storage, upstream API) failed; details stay in the logs."""

    status_code = 502


class ServiceUnavailableError(AppError):
    """A feature is not configured on this deployment (e.g. Google login in local dev)."""

    status_code = 503


class OAuthLoginError(AppError):
    """The OAuth provider rejected or could not complete the login. Never shown verbatim."""

    status_code = 400
