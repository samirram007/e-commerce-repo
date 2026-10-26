"""Exception hierarchy and centralized exception handlers.

All errors are returned in the documented envelope:
{"error": {"code": "...", "message": "...", "details": [...]}}
"""
import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    loc: str
    msg: str
    type: str = "value_error"


class AppError(Exception):
    """Base class for application errors with the canonical error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: list[ErrorDetail] | dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class AuthError(AppError):
    def __init__(self, code: str, message: str, status_code: int = 401) -> None:
        super().__init__(code, message, status_code=status_code)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__("FORBIDDEN", message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, entity: str = "Resource") -> None:
        super().__init__("NOT_FOUND", f"{entity} not found", status_code=404)


class ConflictError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=status.HTTP_409_CONFLICT)


class BusinessRuleError(AppError):
    """Domain rule violations (e.g. unbalanced journal entry, negative stock)."""


def error_body(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details if details is not None else []}}


def install_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(
                loc=".".join(str(x) for x in err.get("loc", [])),
                msg=err.get("msg", "invalid"),
                type=err.get("type", "value_error"),
            ).model_dump()
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Request validation failed", details),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        status_code = getattr(exc, "status_code", 500)
        if status_code >= 500:
            logging.getLogger("erp").error("unhandled_exception", exc_info=exc)
            message, code = "Internal server error", "INTERNAL_ERROR"
        else:
            message, code = str(exc), getattr(exc, "code", "ERROR")
        return JSONResponse(status_code=status_code, content=error_body(code, message, []))
