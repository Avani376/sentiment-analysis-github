"""Application error model and the consistent HTTP error envelope.

Every error response has the shape::

    {"error": {"code": "<machine_code>", "message": "<human message>",
               "details": {...} | null}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, well-mapped application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status.HTTP_404_NOT_FOUND, details)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status.HTTP_409_CONFLICT, details)


class PayloadTooLargeError(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status.HTTP_413_CONTENT_TOO_LARGE, details)


class UnprocessableError(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status.HTTP_422_UNPROCESSABLE_CONTENT, details)


class ServiceUnavailableError(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status.HTTP_503_SERVICE_UNAVAILABLE, details)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def register_exception_handlers(app) -> None:  # noqa: ANN001 - FastAPI app type
    """Attach the consistent error envelope to every failure path."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorEnvelope(
                error=ErrorBody(code=exc.code, message=exc.message, details=exc.details or None)
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="validation_error",
                    message="Request validation failed.",
                    details={"errors": exc.errors()},
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to logs; the client gets an opaque message. Review
        # text is never included in either, only request metadata.
        logger.exception("Unhandled exception: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="internal_error",
                    message="An unexpected error occurred.",
                )
            ).model_dump(),
        )
