"""
ORBIT Custom Exceptions and Global Exception Handlers
Formats errors into standard API envelope: {success: False, data: None, meta: None, error: str}
"""

from typing import Any
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from schemas.common import api_response


class OrbitException(Exception):
    """Base exception for ORBIT domain errors."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EntityNotFoundException(OrbitException):
    """Raised when an entity is not found."""

    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            f"{entity_name} with identifier '{identifier}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AuthenticationException(OrbitException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class PermissionDeniedException(OrbitException):
    """Raised when a user lacks required permissions."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform envelope exception handlers on FastAPI instance."""

    @app.exception_handler(OrbitException)
    async def orbit_exception_handler(request: Request, exc: OrbitException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=api_response(data=None, error=exc.message, success=False),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=api_response(data=None, error=str(exc.detail), success=False),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()]
        error_msg = "; ".join(errors)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=api_response(data=None, error=f"Validation error: {error_msg}", success=False),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=api_response(
                data=None,
                error="An unexpected internal server error occurred.",
                success=False,
            ),
        )
