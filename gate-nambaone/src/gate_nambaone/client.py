from typing import Any
from urllib.parse import quote

import httpx

from gate_nambaone.const import RESPONSE_STATUS_ERROR
from gate_nambaone.exceptions import ProviderError
from gate_nambaone.exceptions import ProviderInvalidResponseError
from gate_nambaone.exceptions import ProviderTimeoutError
from gate_nambaone.exceptions import ProviderUnavailableError
from gate_nambaone.schemas.provider import PaymentLink
from gate_nambaone.schemas.provider import PaymentLinkRequest
from gate_nambaone.schemas.provider import PaymentLinkResponse
from gate_nambaone.schemas.provider import PaymentOrder
from gate_nambaone.schemas.provider import PaymentOrderResponse
from gate_nambaone.schemas.provider import ProviderErrorDetails
from gate_nambaone.schemas.provider import ProviderResponse
from gate_nambaone.schemas.provider import RefundOrder
from gate_nambaone.schemas.provider import RefundOrderRequest
from gate_nambaone.schemas.provider import RefundOrderResponse
from gate_nambaone.schemas.terminal_data import TerminalData
from gate_nambaone.signature import make_signature_headers
from utils.httpx import AsyncLoggingClient


class NambaOneClient:
    """
    HTTP-клиент API Namba One.

    Подписывает запросы, а проблемы сети и формата ответа
    превращает в ошибки гейта из gate_nambaone.exceptions.
    """

    def __init__(self, terminal_data: TerminalData, timeout: float) -> None:
        self.base_url = str(terminal_data.provider_base_url).rstrip("/")
        self.merchant_account_guid = str(terminal_data.merchant_account_guid)
        self.secret_key = terminal_data.secret_key.get_secret_value()
        self.proxy_url = terminal_data.proxy_url
        self.timeout = timeout

    async def create_payment_link(self, payload: PaymentLinkRequest) -> PaymentLink:
        """Создаёт одноразовую платёжную ссылку."""
        path = f"/public/merchant/payment/v2/{self.merchant_account_guid}/one-time"
        body = await self.send("POST", path, payload.to_json())

        payment_link = PaymentLinkResponse.parse(body).data
        if payment_link is None:
            raise ProviderInvalidResponseError("Payment link is missing in provider response")
        return payment_link

    async def get_payment(self, invoice_id: str) -> PaymentOrder | None:
        """Платёж по нашему invoice_id. None — клиент ещё не оплатил ссылку."""
        path = f"/public/merchant/payment/v1/{self.merchant_account_guid}/one-time/{quote(invoice_id, safe='')}"
        body = await self.send("GET", path)
        return PaymentOrderResponse.parse(body).data

    async def create_refund(self, refund_id: str, payload: RefundOrderRequest) -> RefundOrder:
        """Создаёт возврат. refund_id — наш идентификатор, он же ключ идемпотентности."""
        path = f"/public/merchant/payment/v1/{self.merchant_account_guid}/refund/{quote(refund_id, safe='')}"
        body = await self.send("POST", path, payload.to_json())

        refund_order = RefundOrderResponse.parse(body).data
        if refund_order is None:
            raise ProviderInvalidResponseError("Refund order is missing in provider response")
        return refund_order

    async def get_refund(self, refund_id: str) -> RefundOrder:
        """Возврат по нашему refund_id."""
        path = f"/public/merchant/payment/v1/{self.merchant_account_guid}/refund/{quote(refund_id, safe='')}"
        body = await self.send("GET", path)

        refund_order = RefundOrderResponse.parse(body).data
        if refund_order is None:
            raise ProviderInvalidResponseError("Refund order is missing in provider response")
        return refund_order

    async def send(self, method: str, path: str, body: str = "") -> Any:
        """Подписывает и отправляет запрос. Возвращает JSON успешного ответа."""
        # Для запросов без тела подпись считается от пустой строки
        headers = make_signature_headers(self.secret_key, path, body)
        if body:
            headers["Content-Type"] = "application/json"

        try:
            async with AsyncLoggingClient(timeout=self.timeout, proxy=self.proxy_url) as client:
                response = await client.request(method, f"{self.base_url}{path}", content=body or None, headers=headers)
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError("Provider did not respond in time") from error
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(f"Provider is unavailable: {error}") from error

        return read_response_body(response)


def read_response_body(response: httpx.Response) -> Any:
    """
    Проверяет ответ провайдера и возвращает его JSON.

    - 5xx: результат операции неизвестен, бросает ProviderUnavailableError;
    - пустое тело или не JSON: бросает ProviderInvalidResponseError;
    - status = ERROR: бросает ProviderError с кодом ошибки провайдера.
    """
    if response.is_server_error:
        raise ProviderUnavailableError(f"Provider responded with HTTP {response.status_code}")
    if not response.content:
        raise ProviderInvalidResponseError("Provider returned an empty response")

    try:
        body = response.json()
    except ValueError as error:
        raise ProviderInvalidResponseError("Provider response is not a valid JSON") from error

    envelope = ProviderResponse.parse(body)
    if envelope.status == RESPONSE_STATUS_ERROR:
        error = envelope.error or ProviderErrorDetails(error_code="UNKNOWN_ERROR")
        raise ProviderError(error.message or error.error_code, code=error.error_code)
    return body
