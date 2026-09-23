from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import SecretStr
from pydantic import ValidationError

from gate_nambaone.exceptions import InvalidRequestError


class TerminalData(BaseModel):
    """Настройки терминала для подключения к Namba One."""

    model_config = ConfigDict(extra="ignore")

    provider_base_url: HttpUrl
    merchant_account_guid: UUID
    secret_key: SecretStr = Field(min_length=1)
    callback_url: HttpUrl | None = None
    refund_callback_url: HttpUrl | None = None
    proxy_url: str | None = None


def parse_terminal_data(raw: dict[str, Any]) -> TerminalData:
    """
    Проверяет настройки терминала.

    В сообщение об ошибке попадают только имена полей, без значений,
    чтобы секрет не оказался в логах и ответах.
    """
    try:
        return TerminalData.model_validate(raw)
    except ValidationError as error:
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        raise InvalidRequestError(f"Terminal data is not valid: {', '.join(fields)}") from error


TERMINAL_DATA_SCHEMA: dict[str, Any] = {
    "title": "NambaOne settings",
    "groups": [
        {
            "name": "connection",
            "label": "Connection",
            "fields": [
                {"name": "provider_base_url", "label": "Provider Base URL", "type": "text", "required": True},
                {"name": "proxy_url", "label": "Proxy URL", "type": "text", "required": False},
            ],
        },
        {
            "name": "provider",
            "label": "Provider",
            "fields": [
                {"name": "merchant_account_guid", "label": "Merchant Account GUID", "type": "text", "required": True},
                {"name": "secret_key", "label": "Secret Key", "type": "password", "required": True},
            ],
        },
        {
            "name": "urls",
            "label": "URLs",
            "fields": [
                {"name": "callback_url", "label": "Callback URL Invoice", "type": "text", "required": False},
                {"name": "refund_callback_url", "label": "Callback URL Refund", "type": "text", "required": False},
            ],
        },
    ],
}
