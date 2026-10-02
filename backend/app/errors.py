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


class NotFoundError(AppError):
    """Missing OR owned by someone else: the two are deliberately indistinguishable (A3)."""

    status_code = 404
    code = "NOT_FOUND"


class JobNotReadyError(AppError):
    """Results were asked for before the job succeeded."""

    status_code = 409
    code = "JOB_NOT_READY"


class RangeNotSatisfiableError(AppError):
    status_code = 416
    code = "RANGE_NOT_SATISFIABLE"


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


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"


class UnsupportedFormatError(AppError):
    status_code = 415
    code = "UNSUPPORTED_FORMAT"


class CorruptFileError(AppError):
    status_code = 422
    code = "CORRUPT_FILE"


class DurationExceededError(AppError):
    status_code = 422
    code = "DURATION_EXCEEDED"


class DecodeError(AppError):
    """ffmpeg could not decode frames from a file that passed validation."""

    status_code = 422
    code = "DECODE_ERROR"


class ModelError(AppError):
    """The detector model is missing, the wrong export, or failed at inference."""

    status_code = 500
    code = "MODEL_ERROR"


class LeaseLostError(AppError):
    """The queue no longer lists this worker as the job's owner; stop without writing."""

    status_code = 409
    code = "LEASE_LOST"


class UrlNotAllowedError(AppError):
    status_code = 422
    code = "URL_NOT_ALLOWED"


class YouTubeBlockedError(AppError):
    """YouTube refused our server (bot check, 403/429, sign-in required)."""

    status_code = 422
    code = "YOUTUBE_BLOCKED"


class DownloadFailedError(AppError):
    status_code = 422
    code = "DOWNLOAD_FAILED"
