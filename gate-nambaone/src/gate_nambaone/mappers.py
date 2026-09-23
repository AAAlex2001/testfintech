"""Преобразование данных между протоколом платформы и API Namba One."""

from decimal import Decimal

from pydantic import HttpUrl

from gate_lib import const as gate_lib_const
from gate_lib.protocol.v2.refund import RefundRequest
from gate_lib.protocol.v2.refund import RefundResponse
from gate_lib.protocol.v2.refund import RefundStatusResponse
from gate_lib.protocol.v2.sale import SaleRequest
from gate_lib.protocol.v2.status import StatusResponse
from gate_nambaone.const import CURRENCY_CODE
from gate_nambaone.const import MINOR_UNITS_IN_MAJOR
from gate_nambaone.const import PAYMENT_STATUS_MAPPING
from gate_nambaone.const import REFUND_ERROR_MESSAGES
from gate_nambaone.const import REFUND_PARENT_TYPE
from gate_nambaone.const import REFUND_STATUS_MAPPING
from gate_nambaone.exceptions import InvalidRequestError
from gate_nambaone.schemas.provider import PaymentLinkRequest
from gate_nambaone.schemas.provider import PaymentOrder
from gate_nambaone.schemas.provider import RefundOrder
from gate_nambaone.schemas.provider import RefundOrderRequest
from gate_nambaone.schemas.provider import WebOptions
from gate_nambaone.schemas.terminal_data import TerminalData


def to_minor_units(amount: Decimal) -> str:
    """Сомы → тыйыны строкой: Decimal("10.50") → "1050"."""
    minor_units = amount * MINOR_UNITS_IN_MAJOR
    if minor_units != minor_units.to_integral_value():
        raise InvalidRequestError("Amount must have at most 2 decimal places")
    return str(int(minor_units))


def from_minor_units(amount: Decimal) -> Decimal:
    """Тыйыны → сомы: Decimal("1050") → Decimal("10.50")."""
    return (amount / MINOR_UNITS_IN_MAJOR).quantize(Decimal("0.01"))


def check_currency(currency_code: str) -> None:
    """Namba One принимает только KGS."""
    if currency_code.upper() != CURRENCY_CODE:
        raise InvalidRequestError(f"Currency {currency_code} is not supported, only {CURRENCY_CODE}")


def url_to_str(url: HttpUrl | None) -> str | None:
    """HttpUrl → str, None остаётся None."""
    return str(url) if url else None


def build_payment_link_request(req: SaleRequest, terminal_data: TerminalData) -> PaymentLinkRequest:
    """Запрос платформы на оплату → запрос на создание одноразовой платёжной ссылки."""
    check_currency(req.currency_code)
    return PaymentLinkRequest(
        external_id=req.invoice_id,
        amount=to_minor_units(req.amount),
        webhook_url=url_to_str(terminal_data.callback_url),
        comment=req.description,
        # После оплаты клиент вернётся на страницу магазина
        web_options=WebOptions(redirect_link=req.finish_url) if req.finish_url else None,
    )


def build_refund_order_request(req: RefundRequest, terminal_data: TerminalData) -> RefundOrderRequest:
    """Запрос платформы на возврат → запрос на создание возврата в Namba One."""
    check_currency(req.currency_code)
    return RefundOrderRequest(
        parent_type=REFUND_PARENT_TYPE,
        payment_order_guid=req.external_id,
        amount=to_minor_units(req.amount),
        webhook_url=url_to_str(terminal_data.refund_callback_url),
        comment=req.comment,
    )


def map_payment_status(provider_status: str) -> str:
    """Статус платежа Namba One → статус платформы. Неизвестный статус считаем промежуточным."""
    return PAYMENT_STATUS_MAPPING.get(provider_status, gate_lib_const.PENDING)


def map_refund_status(provider_status: str) -> str:
    """Статус возврата Namba One → статус платформы. Неизвестный статус считаем промежуточным."""
    return REFUND_STATUS_MAPPING.get(provider_status, gate_lib_const.PENDING)


def describe_payment_failure(provider_status: str) -> str:
    """Текст ошибки для неуспешного платежа."""
    return f"Payment finished with status {provider_status}"


def get_refund_error_message(error_code: str) -> str:
    """Текст ошибки возврата по коду errorCode из документации."""
    return REFUND_ERROR_MESSAGES.get(error_code, f"Refund failed with error code {error_code}")


def get_paid_amount(payment: PaymentOrder) -> Decimal:
    """Сколько клиент фактически заплатил, в сомах."""
    amount = payment.payment_amount if payment.payment_amount is not None else payment.amount
    return from_minor_units(amount)


def build_status_response(payment: PaymentOrder) -> StatusResponse:
    """Платёж Namba One → ответ платформе на запрос статуса."""
    response = StatusResponse(
        status=map_payment_status(payment.status),
        amount=get_paid_amount(payment),
        currency_code=payment.currency,
        external_id=payment.guid,
    )
    if response.status == gate_lib_const.FAILED:
        # В code передаём исходный статус провайдера: CANCELED, FAILED или EXPIRED
        response.code = payment.status
        response.message = describe_payment_failure(payment.status)
    return response


def build_refund_response(refund_order: RefundOrder) -> RefundResponse:
    """Возврат Namba One → ответ платформе на создание возврата."""
    response = RefundResponse(
        status=map_refund_status(refund_order.status),
        amount=from_minor_units(refund_order.amount),
        currency_code=refund_order.currency,
        external_id=refund_order.guid,
    )
    if refund_order.error_code:
        response.code = refund_order.error_code
        response.message = get_refund_error_message(refund_order.error_code)
    return response


def build_refund_status_response(refund_order: RefundOrder) -> RefundStatusResponse:
    """Возврат Namba One → ответ платформе на запрос статуса возврата."""
    return RefundStatusResponse.model_validate(build_refund_response(refund_order).model_dump())
