"""
Ошибки гейта.

Код и сообщение ошибки гейт отдаёт платформе в полях code и message.
По типу ошибки гейт решает, какой статус вернуть (см. GateNambaOne).
"""


class GateError(Exception):
    """Базовая ошибка гейта."""

    default_code = "gate_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code


class InvalidRequestError(GateError):
    """Запрос платформы нельзя отправить провайдеру: неверные настройки терминала, сумма, валюта."""

    default_code = "validation_error"


class ProviderError(GateError):
    """Провайдер явно отклонил операцию (status = ERROR)."""

    default_code = "provider_error"


class ProviderUnavailableError(GateError):
    """Провайдер не ответил или ответил 5xx: результат операции неизвестен."""

    default_code = "provider_unavailable"


class ProviderTimeoutError(ProviderUnavailableError):
    """Провайдер не ответил за отведённое время."""

    default_code = "provider_timeout"


class ProviderInvalidResponseError(GateError):
    """Ответ провайдера пустой или не соответствует документации."""

    default_code = "invalid_provider_response"
