"""Модели запросов и ответов API Namba One: https://merchant-api-docs.rps.kg"""

from decimal import Decimal
from typing import Any
from typing import Literal
from typing import Self

from pydantic import Field
from pydantic import ValidationError

from gate_nambaone.exceptions import ProviderInvalidResponseError
from gate_nambaone.schemas.base import CamelModel


class WebOptions(CamelModel):
    """Настройки страницы оплаты."""

    redirect_link: str
    auto_redirect: bool = True


class PaymentLinkRequest(CamelModel):
    """Создание одноразовой платёжной ссылки."""

    external_id: str
    amount: str  # в тыйынах
    amount_can_be_changed: bool = False
    webhook_url: str | None = None
    comment: str | None = None
    web_options: WebOptions | None = None


class RefundOrderRequest(CamelModel):
    """Создание возврата."""

    parent_type: str
    payment_order_guid: str
    amount: str  # в тыйынах
    webhook_url: str | None = None
    comment: str | None = None


class PaymentLink(CamelModel):
    """Созданная платёжная ссылка."""

    guid: str
    token: str = Field(min_length=1)  # сама ссылка, по которой платит клиент


class PaymentOrder(CamelModel):
    """Платёж по платёжной ссылке."""

    guid: str
    status: str
    currency: str
    amount: Decimal  # в тыйынах
    payment_amount: Decimal | None = None  # сколько фактически заплатил клиент, в тыйынах


class RefundOrder(CamelModel):
    """Возврат."""

    guid: str
    status: str
    currency: str
    amount: Decimal  # в тыйынах
    error_code: str | None = None


class ProviderErrorDetails(CamelModel):
    """Описание ошибки в ответе со status = ERROR."""

    error_code: str
    message: str | None = None


class ProviderResponse(CamelModel):
    """Общая обёртка любого ответа Namba One."""

    status: Literal["OK", "ERROR"]
    error: ProviderErrorDetails | None = None

    @classmethod
    def parse(cls, body: Any) -> Self:
        """Разбирает тело ответа. Если формат не совпал с документацией, бросает ProviderInvalidResponseError."""
        try:
            return cls.model_validate(body)
        except ValidationError as error:
            raise ProviderInvalidResponseError("Provider response does not match the documentation") from error


class PaymentLinkResponse(ProviderResponse):
    data: PaymentLink | None = None


class PaymentOrderResponse(ProviderResponse):
    data: PaymentOrder | None = None


class RefundOrderResponse(ProviderResponse):
    data: RefundOrder | None = None
