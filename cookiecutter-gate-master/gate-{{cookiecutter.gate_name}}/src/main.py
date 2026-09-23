from contextlib import asynccontextmanager

import aiojobs
import sentry_sdk
import tomllib
import uvicorn
from elasticapm.base import get_client
from elasticapm.contrib.starlette import ElasticAPM
from elasticapm.contrib.starlette import make_apm_client
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from gate_lib.handlers import request_validation_error_handler
from utils.fastapi.middleware import LoggingMiddleware
from utils.fastapi.middleware import TraceIDMiddleware
from utils.fastapi.middleware.logging import IgnoredRoute
from utils.fastapi.middleware.logging import MaskedField
from utils.httpx import AsyncLoggingClient
from utils.logging import configure_structlog
from utils.masking import mask_cvc
from utils.masking import mask_pan

from api.notifications import router as notifications_router
from api.v2.v2 import router
from settings import settings


def _get_service_version() -> str:
    with open("pyproject.toml", "rb") as f:
        project_data = tomllib.load(f)
    version: str = project_data["tool"]["poetry"]["version"]
    return version


configure_structlog(
    service_name=settings.ELASTIC_APM_SERVICE_NAME,
    service_version=_get_service_version(),
    log_level=settings.LOG_LEVEL,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.httpx_client = AsyncLoggingClient(timeout=settings.REQUEST_TIMEOUT)
    app.state.aiojobs_scheduler = aiojobs.Scheduler()
    yield
    await app.state.httpx_client.aclose()
    await app.state.aiojobs_scheduler.close()


app = FastAPI(
    title="Gate{{cookiecutter.gate_name_camel}}",
    docs_url="/api/openapi",
    openapi_url="/api/openapi.json",
    version=_get_service_version(),
    lifespan=lifespan,
)

app.add_middleware(
    LoggingMiddleware,
    ignored_routes=[
        IgnoredRoute(path="/api/openapi"),
        IgnoredRoute(path="/api/openapi.json"),
        IgnoredRoute(path="/v2/ping"),
    ],
    masked_fields=[
        MaskedField(name="pan", method=mask_pan),
        MaskedField(name="cvc", method=mask_cvc),
    ],
    log_invoice_id=True,
)
app.add_middleware(TraceIDMiddleware)

if settings.ELASTIC_APM_ENABLED:
    apm = get_client()
    if apm is None:
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
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production,
        traces_sample_rate=settings.SENTRY_SAMPLE_RATE,
    )

app.include_router(router, prefix="/v2")
app.include_router(notifications_router, prefix=settings.NOTIFICATIONS_PREFIX)
app.exception_handler(RequestValidationError)(request_validation_error_handler)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.WEB_SERVICE_HOST,
        port=settings.WEB_SERVICE_PORT,
        log_level=settings.LOG_LEVEL,
        reload=settings.DEBUG,
        access_log=False,
    )
