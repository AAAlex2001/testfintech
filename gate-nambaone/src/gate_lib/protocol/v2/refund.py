from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from gate_lib.protocol.v2.base import GateResponse


class RefundRequest(BaseModel):
    """Запрос платформы на возврат платежа."""

    refund_id: str = Field(min_length=1)
    # Идентификатор исходного платежа в системе провайдера
    external_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    terminal_data: dict[str, Any]
    comment: str | None = None


class RefundResponse(GateResponse):
    """Результат создания возврата."""


class RefundStatusRequest(BaseModel):
    """Запрос платформы на получение статуса возврата."""

    refund_id: str = Field(min_length=1)
    external_id: str | None = None
    currency_code: str = Field(min_length=3, max_length=3)
    terminal_data: dict[str, Any]


class RefundStatusResponse(GateResponse):
    """Текущий статус возврата."""
