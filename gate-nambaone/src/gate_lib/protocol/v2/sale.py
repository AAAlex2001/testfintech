from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from gate_lib.protocol.v2.base import GateResponse


class SaleRequest(BaseModel):
    """Запрос платформы на создание платежа."""

    invoice_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    terminal_data: dict[str, Any]
    finish_url: str | None = None
    description: str | None = None


class Redirect(BaseModel):
    """Куда отправить плательщика, чтобы он завершил оплату."""

    url: str
    method: str = "GET"


class SaleResponse(GateResponse):
    """Результат создания платежа."""

    redirect: Redirect | None = None
