from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import sentry_sdk
import tomllib
import uvicorn
from elasticapm.contrib.starlette import ElasticAPM
from elasticapm.contrib.starlette import make_apm_client
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from api.notifications import router as notifications_router
from api.v2.v2 import router
from gate_lib.handlers import request_validation_error_handler
from settings import settings
from utils.fastapi.middleware import LoggingMiddleware
from utils.fastapi.middleware import TraceIDMiddleware
from utils.httpx import AsyncLoggingClient
from utils.logging import configure_structlog

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def get_service_version() -> str:
    """Версия сервиса из pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as file:
        return tomllib.load(file)["tool"]["poetry"]["version"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Один HTTP-клиент на всё приложение, закрывается при остановке."""
    app.state.httpx_client = AsyncLoggingClient(timeout=settings.REQUEST_TIMEOUT)
    yield
    await app.state.httpx_client.aclose()


configure_structlog(
    service_name=settings.ELASTIC_APM_SERVICE_NAME,
    service_version=get_service_version(),
    log_level=settings.LOG_LEVEL,
)

app = FastAPI(
    title="GateNambaOne",
    docs_url="/api/openapi",
    openapi_url="/api/openapi.json",
    version=get_service_version(),
    lifespan=lifespan,
)

app.add_middleware(
    LoggingMiddleware,
    ignored_paths=["/api/openapi", "/api/openapi.json", "/v2/ping"],
)
app.add_middleware(TraceIDMiddleware)

if settings.ELASTIC_APM_ENABLED:
    apm = make_apm_client(
        {
            "SERVICE_NAME": settings.ELASTIC_APM_SERVICE_NAME,
            "SERVER_URL": settings.ELASTIC_APM_SERVER_URL,
            "SECRET_TOKEN": settings.ELASTIC_APM_SECRET_TOKEN,
            "ENVIRONMENT": settings.ELASTIC_APM_ENVIRONMENT,
        }
    )
    app.add_middleware(ElasticAPM, client=apm)

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=settings.SENTRY_SAMPLE_RATE)

app.include_router(router, prefix="/v2")
app.include_router(notifications_router, prefix=settings.NOTIFICATIONS_PREFIX)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.WEB_SERVICE_HOST,
        port=settings.WEB_SERVICE_PORT,
        log_level=settings.LOG_LEVEL,
        reload=settings.DEBUG,
        access_log=False,
    )
