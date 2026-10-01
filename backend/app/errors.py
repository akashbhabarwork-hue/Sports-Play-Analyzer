class AppError(Exception):
    """Base exception for all application errors."""

    status_code = 400


class ExternalServiceError(AppError):
    """A dependency (database, storage, upstream API) failed; details stay in the logs."""

    status_code = 502
