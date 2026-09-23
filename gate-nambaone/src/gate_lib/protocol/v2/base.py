from decimal import Decimal

from pydantic import BaseModel


class GateResponse(BaseModel):
    """Общие поля ответа гейта на любую операцию."""

    status: str
    amount: Decimal | None = None
    currency_code: str | None = None
    external_id: str | None = None
    code: str | None = None
    message: str | None = None
