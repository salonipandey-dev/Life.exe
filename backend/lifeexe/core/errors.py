"""Application error hierarchy, mapped to HTTP responses by the API layer."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str = "Something went wrong.", *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class InvalidTransition(Conflict):
    code = "invalid_transition"


class AlreadyCompleted(Conflict):
    code = "already_completed"


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "Too many requests.", *, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after
