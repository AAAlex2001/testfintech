from decimal import Decimal
from typing import Any

from pydantic import BaseModel

INVOICE_STATUS_PENDING = "pending"


class InvoiceInfo(BaseModel):
    """Инвойс на стороне платформы."""

    id: str
    status: str
    amount: Decimal
    currency_code: str
    primary_terminal: str
    external_id: str | None = None

    @property
    def is_pending(self) -> bool:
        """Инвойс ещё ждёт итогового статуса."""
        return self.status == INVOICE_STATUS_PENDING


class TerminalInfo(BaseModel):
    """Терминал платформы с настройками подключения к провайдеру."""

    id: str
    data: dict[str, Any]
