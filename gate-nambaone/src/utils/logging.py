import logging
from typing import Any

import structlog


class AddServiceInfo:
    """Процессор structlog: добавляет имя и версию сервиса в каждую запись."""

    def __init__(self, service_name: str, service_version: str) -> None:
        self.service_name = service_name
        self.service_version = service_version

    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        event_dict["service"] = self.service_name
        event_dict["version"] = self.service_version
        return event_dict


def configure_structlog(service_name: str, service_version: str, log_level: str) -> None:
    """Настраивает structlog на вывод JSON-логов в stdout."""
    level = logging.getLevelNamesMapping()[log_level.upper()]
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            AddServiceInfo(service_name, service_version),
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )
