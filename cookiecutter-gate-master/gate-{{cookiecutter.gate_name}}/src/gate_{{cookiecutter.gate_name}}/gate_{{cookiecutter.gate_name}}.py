import asyncio
import json
import secrets
import time
from typing import Any

import aiojobs
import httpx
import structlog
from api.schemas.notifications import InvoiceNotification
from api.schemas.notifications import WithdrawalNotification
from api.schemas.terminal_data import TerminalData
from cds_client.services.cds import CardData
from const import ORDER_STATUS_MAPPING
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac
from gate_lib import const as gate_lib_const
from gate_lib.protocol.v2.balance import BalanceRequest
from gate_lib.protocol.v2.balance import BalanceResponse
from gate_lib.protocol.v2.p2p_selector import P2pSelectorSaleRequest
from gate_lib.protocol.v2.p2p_selector import P2pSelectorSaleResponse
from gate_lib.protocol.v2.refund import RefundRequest
from gate_lib.protocol.v2.refund import RefundResponse
from gate_lib.protocol.v2.refund import RefundStatusResponse
from gate_lib.protocol.v2.refund import RefundStatusRequest
from gate_lib.protocol.v2.sale import Redirect
from gate_lib.protocol.v2.sale import SaleConfirmRequest
from gate_lib.protocol.v2.sale import SaleConfirmResponse
from gate_lib.protocol.v2.sale import SaleRequest
from gate_lib.protocol.v2.sale import SaleResponse
from gate_lib.protocol.v2.status import StatusRequest
from gate_lib.protocol.v2.status import StatusResponse
from gate_lib.protocol.v2.withdrawal import WithdrawalRequest
from gate_lib.protocol.v2.withdrawal import WithdrawalResponse
from pydantic import ValidationError
from sbank_client.client import SbankClient
from settings import settings
from utils.httpx import AsyncLoggingClient
from yarl import URL


logger = structlog.get_logger()


class Gate{{cookiecutter.gate_name_camel}}:
    def __init__(
            self,
            httpx_client: httpx.AsyncClient,
            aiojobs_scheduler: aiojobs.Scheduler,
    ):
        self.httpx_client = httpx_client
        self.aiojobs_scheduler = aiojobs_scheduler
        self.sbank = SbankClient(
            httpx_client=self.httpx_client,
            base_url=settings.SBANK_API_BASE_URL,
            radmin_base_url=settings.SBANK_RADMIN_BASE_URL,
            auth_token=settings.SBANK_API_AUTH_TOKEN,
        )

    async def terminal_data_schema(self) -> dict[str, Any]:
        return {
            "title": "{{cookiecutter.gate_name_camel}} settings",
            "groups": [
                {
                    "name": "connection",
                    "label": "Connection",
                    "fields": [
                        {
                            "name": "provider_base_url",
                            "label": "Provider Base URL",
                            "type": "text",
                            "required": True,
                        },
                        {
                            "name": "gate_connection.url",
                            "label": "Gate Connection URL",
                            "type": "text",
                            "required": True,
                        },
                        {
                            "name": "proxy_url",
                            "label": "Proxy URL",
                            "type": "text",
                            "required": True,
                        },
                    ],
                },
                {
                    "name": "provider",
                    "label": "Provider",
                    "fields": [
                        {
                            "name": "provider_api_key",
                            "label": "Provider API Key",
                            "type": "text",
                            "required": True,
                        },
                        {
                            "name": "provider_payment_method",
                            "label": "Provider Payment Method",
                            "type": "text",
                            "required": True,
                        },
                    ],
                },
                {
                    "name": "urls",
                    "label": "URLs",
                    "fields": [
                        {
                            "name": "provider_callback_url_invoice",
                            "label": "Callback URL Invoice",
                            "type": "text",
                            "required": False,
                        },
                        {
                            "name": "provider_callback_url_withdrawal",
                            "label": "Callback URL Withdrawal",
                            "type": "text",
                            "required": False,
                        },
                    ],
                },
            ],
        }

    async def _process_callback_task(self, notification: WithdrawalNotification):
        withdrawal_info = await self.sbank.get_withdrawal_info(notification.id)
        terminal_info = await self.sbank.get_terminal_info(
            withdrawal_info.primary_terminal
        )

        status_req = StatusRequest(
            withdrawal_id=withdrawal_info.id,
            terminal_data=terminal_info.data,
            currency_code=withdrawal_info.currency_code,
            external_id=withdrawal_info.external_id,
        )

        status_result = await self.withdrawal_status(status_req)

        if status_result.status == gate_lib_const.PENDING:
            for attempt in range(int(settings.MAX_RETRY_ATTEMPTS)):
                await asyncio.sleep(settings.RETRY_DELAY + attempt * 2)
                status_result = await self.withdrawal_status(status_req)
                if status_result.status != gate_lib_const.PENDING:
                    break

        data = {
            "amount": status_result.amount if status_result.amount else "0",
            "status": status_result.status,
            "withdrawal_id": withdrawal_info.id,
            "source": status_result.source,
        }
        if status_result.status == gate_lib_const.FAILED:
            data["error_code"] = status_result.code
            data["error_message"] = status_result.message
        try:
            await self.sbank.update_withdrawal_request(**data)
        except Exception as e:
            m = f"{withdrawal_info.id}: {str(e)}"
            logger.info(f"Exception during update withdrawal request {m}")

    def _make_secure_redirect_url(self, invoice_id: str, terminal_data: TerminalData) -> str:
        secure_redirect_params = {
            "invoice_id": invoice_id,
            "nonce": secrets.token_urlsafe(16),
            "timestamp": str(int(time.time())),
        }

        sign_msg = "".join(secure_redirect_params.values())
        h = hmac.HMAC(settings.SECURE_REDIRECT_KEY.encode(), hashes.SHA256())
        h.update(sign_msg.encode())
        signature = h.finalize()

        secure_redirect_params["signature"] = signature.hex()
        secure_redirect_url = URL(terminal_data.secure_redirect_url).with_query(
            secure_redirect_params,
        )
        return str(secure_redirect_url)

    async def sale(self, req: SaleRequest, card_data: CardData):
        """
        Sale - оплата картой

        Оплата, когда переданы карточные данные.
        """

        # TODO код похода в гейт
        try:
            terminal_data = TerminalData(**req.terminal_data)
        except ValidationError:
            return SaleResponse(
                status=gate_lib_const.FAILED,
                amount=req.amount,
                currency_code=req.currency_code,
                code="validation_error",
                message=f"Terminal data is not valid",
            )
        secure_redirect_url = self._make_secure_redirect_url(req.invoice_id)
        redirect = Redirect(
                url=secure_redirect_url
            )
        secure_redirect_data = {
            "url": req.finish_url,
            "method": "GET",
            "payload": [],
        }
        await self.sbank.update_invoice(
            invoice_id=req.invoice_id,
            secure_redirect_data=json.dumps(secure_redirect_data),
        )
        return SaleResponse(
            # Статус платежа
            status=gate_lib_const.PENDING,
            # Реальная сумма платежа
            amount=req.amount,
            # Валюта платежа
            currency_code=req.currency_code,
            # ID в системе платежного шлюза
            external_id=None,
            # Редирект, как правило на 3ds страницу
            redirect=redirect
        )

    async def sale_without_card(self, req: SaleRequest):
        """
        Sale - оплата картой с редиректом

        Оплата, в которой карточные данные не переданы и пользователю
        необходимо перейти на другую страницу, где уже обновить данные.
        """
        try:
            terminal_data = TerminalData(**req.terminal_data)
        except ValidationError:
            return SaleResponse(
                status=gate_lib_const.FAILED,
                amount=req.amount,
                currency_code=req.currency_code,
                code="validation_error",
                message=f"Terminal data is not valid",
            )
        secure_redirect_url = self._make_secure_redirect_url(req.invoice_id)
        redirect = Redirect(
            url=secure_redirect_url
        )
        secure_redirect_data = {
            "url": req.finish_url,
            "method": "GET",
            "payload": [],
        }
        await self.sbank.update_invoice(
            invoice_id=req.invoice_id,
            secure_redirect_data=json.dumps(secure_redirect_data),
        )
        return SaleResponse(
            # Статус платежа
            status=gate_lib_const.PENDING,
            # Реальная сумма платежа
            amount=req.amount,
            # Валюта платежа
            currency_code=req.currency_code,
            # ID в системе платежного шлюза
            external_id=None,
            # Редирект, как правило на 3ds страницу
            redirect=redirect
        )

    async def sale_confirm(self, req: SaleConfirmRequest):
        """
        SaleConfirm - подтверждение платежа
        """

        return SaleConfirmResponse(
            # Статус платежа
            status=gate_lib_const.COMPLETE
        )

    async def p2p_selector_sale(self, req: P2pSelectorSaleRequest):
        """
        P2P - оплата по реквизитам

        Оплата, когда получены реквизиты - карта или телефон (СБП)
        """
        try:
            terminal_data = TerminalData(**req.terminal_data)
        except ValidationError:
            return P2pSelectorSaleResponse(
                status=gate_lib_const.FAILED,
                amount=req.amount,
                currency_code=req.currency_code,
                code="validation_error",
                message=f"Terminal data is not valid",
            )

        return P2pSelectorSaleResponse(
            status=status,
            amount=req.amount,
            currency_code=req.currency_code,
            external_id=external_id,
            beneficiary=beneficiary,
            code=code,
            message=message,
        )

    async def status(self, req: StatusRequest):
        """
        Status - получение статуса платежа
        """
        try:
            terminal_data = TerminalData(**req.terminal_data)
        except ValidationError:
            return StatusResponse(
                status=gate_lib_const.PENDING,
                amount=None,
                currency_code=req.currency_code,
                code="validation_error",
                message=f"Terminal data is not valid",
            )

        if not req.external_id:
            return StatusResponse(
                status=gate_lib_const.PENDING,
                amount=None,
                currency_code=req.currency_code,
                code="validation_error",
                message="External ID is not provided",
            )

        return StatusResponse(
            status=status,
            amount="100",
            currency_code="RUB",
            rrn=f"RRN-{req.invoice_id}",
            external_id=req.external_id,
        )

    async def refund(self, req: RefundRequest):
        """
        Refund - проведение возврата
        """
        terminal_data = TerminalData(**req.terminal_data)
        return RefundResponse(
            status=gate_lib_const.PENDING,
            amount=req.amount,
            currency_code=req.currency_code,
            external_id=req.external_id,
        )

    async def refund_status(self, req: RefundStatusRequest):
        terminal_data = TerminalData(**req.terminal_data)
        return RefundStatusResponse(
            status=gate_lib_const.PENDING,
            code="validation_error",
            message="Refund status is not implemented",
        )

    async def notification_invoice(self, notification: InvoiceNotification):
        invoice_info = await self.sbank.get_invoice_info(notification.Param)
        terminal_info = await self.sbank.get_terminal_info(
            invoice_info.primary_terminal
        )

        status_req = StatusRequest(
            invoice_id=invoice_info.id,
            terminal_data=terminal_info.data,
            currency_code=invoice_info.currency_code,
            external_id=invoice_info.external_id,
        )

        status_result = await self.status(status_req)

        if status_result.status == gate_lib_const.COMPLETE:
            try:
                await self.sbank.invoice_income(
                    invoice_id=invoice_info.id,
                    amount_paid=status_result.amount,
                    external_transaction_id=str(status_result.external_id),
                )
            except Exception as e:
                logger.error(f"Mark invoice success exception: {str(e)}")

        elif status_result.status == gate_lib_const.FAILED:
            try:
                await self.sbank.mark_invoice_fail(
                    invoice_id=invoice_info.id,
                    data={
                        "error_code": status_result.code,
                        "error_message": status_result.message,
                        "external_id": str(status_result.external_id),
                        "payment_gate_iname": settings.ELASTIC_APM_SERVICE_NAME,
                    },
                )
            except Exception as e:
                logger.error(f"Mark invoice fail exception: {str(e)}")

    async def balance(self, req: BalanceRequest):
        """
        Balance - получение баланса
        """
        try:
            terminal_data = TerminalData(**req.terminal_data)
        except ValidationError as e:
            return BalanceResponse(
                status=gate_lib_const.FAILED,
                amount=Decimal("0"),
                currency_code=req.currency_code,
                code="validation_error",
                message=f"Terminal data is not valid: {e.errors()}",
            )
        return BalanceResponse(
            balance=balance,
            currency=req.currency,
        )

    async def withdrawal(self, req: WithdrawalRequest, card_data: CardData):
        """
        Wihdrawal - проведение выплаты
        """
        try:
            terminal_data = TerminalData(**req.terminal_data)
        except ValidationError as e:
            return WithdrawalResponse(
                status=gate_lib_const.FAILED,
                amount=req.amount,
                currency_code=req.currency_code,
                external_id=None,
                code="validation_error",
                message=f"Terminal data is not valid: {e.errors()}"
            )
        return WithdrawalResponse(
            status=status,
            amount=req.amount,
            external_id=None,
        )

    async def withdrawal_status(self, req: StatusRequest):
        """
        WihdrawalStatus - получение статуса выплаты
        """
        terminal_data = TerminalData(**req.terminal_data)
        return StatusResponse(
            status=gate_lib_const.PENDING,
            amount="100",
            currency_code="RUB",
            external_id=req.external_id,
            source=settings.ELASTIC_APM_SERVICE_NAME,
        )

    async def notification_withdrawal(self, notification: WithdrawalNotification):
        callback_status = ORDER_STATUS_MAPPING.get(
            notification.status, gate_lib_const.PENDING
        )
        if callback_status in (gate_lib_const.COMPLETE, gate_lib_const.FAILED):
            await self.aiojobs_scheduler.spawn(
                self._process_callback_task(notification)
            )

    async def _request(
        self,
        url: str,
        method: str,
        proxy_url: str,
        data: dict | None = None,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict[str, Any] | None = None,
    ) -> Any:
        proxies = {"http://": proxy_url, "https://": proxy_url}
        async with AsyncLoggingClient(timeout=settings.REQUEST_TIMEOUT, proxies=proxies) as client:
            resp = None
            try:
                resp = await client.request(
                    method=method,
                    url=url,
                    data=data,
                    json=json,
                    params=params,
                    headers=headers,
                )
                status_code = resp.status_code

                try:
                    result = resp.json()
                except Exception:
                    text = (resp.text or "").strip()
                    if text:
                        result = {"text": text}
                    else:
                        result = {"error": "empty_response"}

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout):
                try:
                    result = resp.json()
                except Exception:
                    result = {"error": "invalid_json"}
                status_code = 504

            except httpx.RequestError as e:
                result = {"error": f"request_failed: {str(e)}"}
                status_code = 502

            except Exception as e:
                result = {"error": f"unhandled_exception: {str(e)}"}
                status_code = 500

        return result, status_code


def get_gate_{{cookiecutter.gate_name}}(**kwargs):
    return Gate{{cookiecutter.gate_name_camel}}(**kwargs)
