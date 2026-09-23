from typing import Any

import structlog

from gate_lib import const as gate_lib_const
from gate_lib.protocol.v2.refund import RefundRequest
from gate_lib.protocol.v2.refund import RefundResponse
from gate_lib.protocol.v2.refund import RefundStatusRequest
from gate_lib.protocol.v2.refund import RefundStatusResponse
from gate_lib.protocol.v2.sale import Redirect
from gate_lib.protocol.v2.sale import SaleRequest
from gate_lib.protocol.v2.sale import SaleResponse
from gate_lib.protocol.v2.status import StatusRequest
from gate_lib.protocol.v2.status import StatusResponse
from gate_nambaone.client import NambaOneClient
from gate_nambaone.exceptions import GateError
from gate_nambaone.exceptions import ProviderInvalidResponseError
from gate_nambaone.exceptions import ProviderUnavailableError
from gate_nambaone.mappers import build_payment_link_request
from gate_nambaone.mappers import build_refund_order_request
from gate_nambaone.mappers import build_refund_response
from gate_nambaone.mappers import build_refund_status_response
from gate_nambaone.mappers import build_status_response
from gate_nambaone.mappers import describe_payment_failure
from gate_nambaone.mappers import get_paid_amount
from gate_nambaone.mappers import map_payment_status
from gate_nambaone.schemas.notifications import PaymentOrderNotification
from gate_nambaone.schemas.terminal_data import TERMINAL_DATA_SCHEMA
from gate_nambaone.schemas.terminal_data import parse_terminal_data
from sbank_client.client import SbankClient

logger = structlog.get_logger()


class GateNambaOne:
    """
    Гейт Namba One: оплата по платёжной ссылке, статусы, возвраты и вебхук оплаты.

    Какой статус вернуть, если что-то пошло не так:
    - создание платежа: любая ошибка → failed, деньги ещё не списаны;
    - запрос статуса: любая ошибка → pending, итог неизвестен и платформа спросит ещё раз;
    - создание возврата: явный отказ провайдера → failed,
      а таймаут, 5xx или непонятный ответ → pending, потому что возврат мог создаться.
    """

    def __init__(self, sbank: SbankClient, request_timeout: float) -> None:
        self.sbank = sbank
        self.request_timeout = request_timeout

    async def terminal_data_schema(self) -> dict[str, Any]:
        """Описание настроек терминала для админки."""
        return TERMINAL_DATA_SCHEMA

    async def sale_without_card(self, req: SaleRequest) -> SaleResponse:
        """Создаёт одноразовую платёжную ссылку и отправляет на неё клиента."""
        try:
            terminal_data = parse_terminal_data(req.terminal_data)
            payload = build_payment_link_request(req, terminal_data)
            payment_link = await NambaOneClient(terminal_data, self.request_timeout).create_payment_link(payload)
        except GateError as error:
            logger.warning("sale_failed", invoice_id=req.invoice_id, code=error.code, message=error.message)
            # Платформа ждёт от sale один код ошибки, причина передаётся в message, исходный код пишется в лог
            return SaleResponse(
                status=gate_lib_const.FAILED,
                amount=req.amount,
                currency_code=req.currency_code,
                code=gate_lib_const.VALIDATION_ERROR,
                message=error.message,
            )

        return SaleResponse(
            status=gate_lib_const.PENDING,
            amount=req.amount,
            currency_code=req.currency_code,
            external_id=payment_link.guid,
            redirect=Redirect(url=payment_link.token),
        )

    async def status(self, req: StatusRequest) -> StatusResponse:
        """Статус платежа по invoice_id."""
        try:
            terminal_data = parse_terminal_data(req.terminal_data)
            payment = await NambaOneClient(terminal_data, self.request_timeout).get_payment(req.invoice_id)
        except GateError as error:
            logger.warning("status_failed", invoice_id=req.invoice_id, code=error.code, message=error.message)
            return StatusResponse(
                status=gate_lib_const.PENDING,
                currency_code=req.currency_code,
                external_id=req.external_id,
                code=error.code,
                message=error.message,
            )

        if payment is None:
            # Провайдер отвечает без data, пока клиент не оплатил ссылку
            return StatusResponse(
                status=gate_lib_const.PENDING,
                currency_code=req.currency_code,
                external_id=req.external_id,
            )
        return build_status_response(payment)

    async def refund(self, req: RefundRequest) -> RefundResponse:
        """Создаёт возврат по платежу."""
        try:
            terminal_data = parse_terminal_data(req.terminal_data)
            payload = build_refund_order_request(req, terminal_data)
            refund_order = await NambaOneClient(terminal_data, self.request_timeout).create_refund(
                req.refund_id, payload
            )
        except (ProviderUnavailableError, ProviderInvalidResponseError) as error:
            # Возврат мог создаться у провайдера, поэтому не отклоняем его: итог покажет refund_status
            logger.warning("refund_unknown_result", refund_id=req.refund_id, code=error.code, message=error.message)
            return RefundResponse(
                status=gate_lib_const.PENDING,
                amount=req.amount,
                currency_code=req.currency_code,
                code=error.code,
                message=error.message,
            )
        except GateError as error:
            logger.warning("refund_failed", refund_id=req.refund_id, code=error.code, message=error.message)
            return RefundResponse(
                status=gate_lib_const.FAILED,
                amount=req.amount,
                currency_code=req.currency_code,
                code=error.code,
                message=error.message,
            )

        return build_refund_response(refund_order)

    async def refund_status(self, req: RefundStatusRequest) -> RefundStatusResponse:
        """Статус возврата по refund_id."""
        try:
            terminal_data = parse_terminal_data(req.terminal_data)
            refund_order = await NambaOneClient(terminal_data, self.request_timeout).get_refund(req.refund_id)
        except GateError as error:
            logger.warning("refund_status_failed", refund_id=req.refund_id, code=error.code, message=error.message)
            return RefundStatusResponse(
                status=gate_lib_const.PENDING,
                currency_code=req.currency_code,
                external_id=req.external_id,
                code=error.code,
                message=error.message,
            )

        return build_refund_status_response(refund_order)

    async def notification_invoice(self, notification: PaymentOrderNotification) -> bool:
        """
        Обрабатывает вебхук об изменении статуса платежа.

        Статусу из вебхука не доверяем и перезапрашиваем его у провайдера
        с настройками терминала из sbank, поэтому поддельный вебхук не проведёт платёж.

        Возвращает True, если у инвойса итоговый статус.
        False — подтвердить итог не удалось, провайдер должен повторить вебхук.
        Ошибки sbank и провайдера пробрасываются наверх.
        """
        invoice = await self.sbank.get_invoice_info(notification.data.external_id)
        if not invoice.is_pending:
            # Повторный вебхук: инвойс уже обработан
            return True

        terminal = await self.sbank.get_terminal_info(invoice.primary_terminal)
        terminal_data = parse_terminal_data(terminal.data)
        payment = await NambaOneClient(terminal_data, self.request_timeout).get_payment(invoice.id)
        if payment is None:
            return False

        status = map_payment_status(payment.status)
        if status == gate_lib_const.COMPLETE:
            await self.sbank.invoice_income(
                invoice.id,
                amount_paid=get_paid_amount(payment),
                external_transaction_id=payment.guid,
            )
            return True
        if status == gate_lib_const.FAILED:
            await self.sbank.mark_invoice_fail(
                invoice.id,
                error_code=payment.status,
                error_message=describe_payment_failure(payment.status),
            )
            return True
        return False
