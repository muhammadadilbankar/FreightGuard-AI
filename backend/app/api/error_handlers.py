"""Safe, consistent HTTP error translation."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..state.errors import ApplicationError
from .schemas import ErrorDetail, ErrorResponse

LOGGER = logging.getLogger(__name__)

STATUS_BY_CODE = {
    "request_validation_failed": 422,
    "analysis_not_ready": 503,
    "analysis_run_in_progress": 409,
    "unsupported_explanation_mode": 422,
    "anomaly_not_found": 404,
    "root_cause_not_applicable": 409,
    "root_cause_unavailable": 422,
    "root_cause_invariant_failed": 500,
    "unsupported_assistant_mode": 422,
    "assistant_planner_unavailable": 503,
    "assistant_execution_failed": 500,
    "assistant_grounding_failed": 500,
    "route_not_found": 404,
    "evaluation_not_available": 503,
    "export_not_available": 503,
    "model_provider_unavailable": 503,
    "analysis_run_failed": 500,
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=STATUS_BY_CODE.get(exc.code, 500),
            code=exc.code,
            message=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = {
            "errors": [
                {
                    "location": [str(part) for part in item.get("loc", ())],
                    "message": item.get("msg", "Invalid value."),
                    "type": item.get("type", "validation_error"),
                }
                for item in exc.errors()
            ]
        }
        return _error_response(
            request,
            status_code=422,
            code="request_validation_failed",
            message="The request did not satisfy the API contract.",
            details=details,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        LOGGER.exception("Unhandled API error request_id=%s", request_id, exc_info=exc)
        return _error_response(
            request,
            status_code=500,
            code="internal_server_error",
            message="An unexpected server error occurred.",
        )


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Request-ID": request_id},
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))
