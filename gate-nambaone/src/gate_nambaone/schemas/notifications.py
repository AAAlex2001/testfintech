from typing import Literal

from pydantic import Field

from gate_nambaone.schemas.base import CamelModel


class PaymentOrderNotificationData(CamelModel):
    """Данные платежа из вебхука."""

    guid: str
    external_id: str = Field(min_length=1)  # наш invoice_id
    status: str


class PaymentOrderNotification(CamelModel):
    """Вебхук Payment Order Updated: https://merchant-api-docs.rps.kg/src-pages-webhooks-payment-order-updated-index"""

    type: Literal["PAYMENT_ORDER"]
    data: PaymentOrderNotificationData
