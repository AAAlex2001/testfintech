from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Создавать SSL-контекст дорого, поэтому он один на все клиенты
SSL_CONTEXT = httpx.create_ssl_context()


async def log_request(request: httpx.Request) -> None:
    """Пишет в лог исходящий запрос."""
    logger.info("http_request", method=request.method, url=str(request.url))


async def log_response(response: httpx.Response) -> None:
    """Пишет в лог полученный ответ."""
    logger.info(
        "http_response",
        method=response.request.method,
        url=str(response.request.url),
        status_code=response.status_code,
    )


class AsyncLoggingClient(httpx.AsyncClient):
    """httpx.AsyncClient, который логирует каждый запрос и ответ."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("verify", SSL_CONTEXT)
        super().__init__(event_hooks={"request": [log_request], "response": [log_response]}, **kwargs)
