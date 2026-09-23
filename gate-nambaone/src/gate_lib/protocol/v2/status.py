from typing import Any

from pydantic import BaseModel
from pydantic import Field

from gate_lib.protocol.v2.base import GateResponse


class StatusRequest(BaseModel):
    """Запрос платформы на получение статуса платежа."""

    invoice_id: str = Field(min_length=1)
    external_id: str | None = None
    currency_code: str = Field(min_length=3, max_length=3)
    terminal_data: dict[str, Any]


class StatusResponse(GateResponse):
    """Текущий статус платежа."""
