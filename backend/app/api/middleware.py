"""Request identity, size guarding, and compact request telemetry."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .schemas import ErrorDetail, ErrorResponse

LOGGER = logging.getLogger(__name__)
MAX_REQUEST_ID_LENGTH = 128


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, max_request_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_request_bytes = max_request_bytes

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started = perf_counter()
        request_id = _trusted_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > self.max_request_bytes
        ):
            body = ErrorResponse(
                error=ErrorDetail(
                    code="request_validation_failed",
                    message="Request body exceeds the configured size limit.",
                    request_id=request_id,
                )
            )
            response: Response = JSONResponse(
                status_code=422, content=body.model_dump(mode="json")
            )
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            "api_request request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.scope.get("route").path
            if request.scope.get("route") is not None
            else request.url.path,
            response.status_code,
            round((perf_counter() - started) * 1000),
        )
        return response


def _trusted_request_id(value: str | None) -> str:
    if (
        value
        and len(value) <= MAX_REQUEST_ID_LENGTH
        and all(32 <= ord(character) < 127 for character in value)
    ):
        return value
    return str(uuid4())
