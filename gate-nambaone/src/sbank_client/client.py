from decimal import Decimal
from typing import Any

import httpx
from pydantic import ValidationError

from sbank_client.exceptions import SbankClientError
from sbank_client.schemas import InvoiceInfo
from sbank_client.schemas import TerminalInfo


class SbankClient:
    """Клиент внутреннего API платформы: инвойсы и терминалы."""

    def __init__(self, httpx_client: httpx.AsyncClient, base_url: str, radmin_base_url: str, auth_token: str) -> None:
        self.httpx_client = httpx_client
        self.base_url = base_url.rstrip("/")
        self.radmin_base_url = radmin_base_url.rstrip("/")
        self.auth_token = auth_token

    async def get_invoice_info(self, invoice_id: str) -> InvoiceInfo:
        """Возвращает инвойс по его идентификатору."""
        body = await self.send("GET", f"{self.base_url}/invoices/{invoice_id}")
        try:
            return InvoiceInfo.model_validate(body)
        except ValidationError as error:
            raise SbankClientError(f"Invalid invoice info: {error}") from error

    async def get_terminal_info(self, terminal_id: str) -> TerminalInfo:
        """Возвращает терминал с его настройками (terminal_data)."""
        body = await self.send("GET", f"{self.radmin_base_url}/terminals/{terminal_id}")
        try:
            return TerminalInfo.model_validate(body)
        except ValidationError as error:
            raise SbankClientError(f"Invalid terminal info: {error}") from error

    async def invoice_income(self, invoice_id: str, amount_paid: Decimal, external_transaction_id: str) -> None:
        """Помечает инвойс оплаченным."""
        payload = {"amount_paid": str(amount_paid), "external_transaction_id": external_transaction_id}
        await self.send("POST", f"{self.base_url}/invoices/{invoice_id}/income", payload)

    async def mark_invoice_fail(self, invoice_id: str, error_code: str, error_message: str) -> None:
        """Помечает инвойс неуспешным."""
        payload = {"error_code": error_code, "error_message": error_message}
        await self.send("POST", f"{self.base_url}/invoices/{invoice_id}/fail", payload)

    async def send(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        """Отправляет запрос в sbank и возвращает JSON ответа."""
        try:
            response = await self.httpx_client.request(
                method,
                url,
                json=payload,
                headers={"Authorization": f"Token {self.auth_token}"},
            )
            response.raise_for_status()
            return response.json() if response.content else None
        except (httpx.HTTPError, ValueError) as error:
            raise SbankClientError(f"Sbank request failed: {method} {url}: {error}") from error
