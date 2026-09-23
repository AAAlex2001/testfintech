import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gate_lib import const

logger = structlog.get_logger()


async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Отвечает 422 на невалидный запрос.

    Входные значения полей в ответ и в лог не попадают,
    чтобы случайно не раскрыть секреты терминала.
    """
    errors = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()
    ]
    logger.warning("request_validation_error", path=request.url.path, errors=errors)
    return JSONResponse(
        status_code=422,
        content={"code": const.VALIDATION_ERROR, "message": "Request is not valid", "errors": errors},
    )
