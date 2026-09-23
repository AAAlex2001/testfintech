import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Логирует каждый входящий запрос: метод, путь, код ответа и время обработки."""

    def __init__(self, app: ASGIApp, ignored_paths: list[str] | None = None) -> None:
        super().__init__(app)
        self.ignored_paths = set(ignored_paths or [])

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.ignored_paths:
            return await call_next(request)

        started_at = time.perf_counter()
        response = await call_next(request)
        logger.info(
            "request_handled",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started_at) * 1000),
        )
        return response
