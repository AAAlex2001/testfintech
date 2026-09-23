"""
Фабрики роутов протокола v2.

Каждая функция регистрирует один метод в роутере сервиса.
Сам гейт приходит через FastAPI-зависимость get_gate.
"""

from typing import Any
from typing import Callable

from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import PlainTextResponse

from gate_lib.protocol.v2.gate import PaymentGate
from gate_lib.protocol.v2.refund import RefundRequest
from gate_lib.protocol.v2.refund import RefundResponse
from gate_lib.protocol.v2.refund import RefundStatusRequest
from gate_lib.protocol.v2.refund import RefundStatusResponse
from gate_lib.protocol.v2.sale import SaleRequest
from gate_lib.protocol.v2.sale import SaleResponse
from gate_lib.protocol.v2.status import StatusRequest
from gate_lib.protocol.v2.status import StatusResponse

GateDependency = Callable[..., PaymentGate]


def build_ping_method(router: APIRouter) -> None:
    """GET /ping — проверка, что сервис жив."""

    @router.get("/ping", response_class=PlainTextResponse)
    async def ping() -> str:
        return "pong"


def build_terminal_data_schema_method(router: APIRouter, get_gate: GateDependency) -> None:
    """GET /terminal_data_schema — описание настроек терминала."""

    @router.get("/terminal_data_schema")
    async def terminal_data_schema(gate: PaymentGate = Depends(get_gate)) -> dict[str, Any]:
        return await gate.terminal_data_schema()


def build_sale_without_card_method(router: APIRouter, get_gate: GateDependency) -> None:
    """POST /sale — создание платежа с редиректом на страницу провайдера."""

    @router.post("/sale")
    async def sale(req: SaleRequest, gate: PaymentGate = Depends(get_gate)) -> SaleResponse:
        return await gate.sale_without_card(req)


def build_status_method(router: APIRouter, get_gate: GateDependency) -> None:
    """POST /status — статус платежа."""

    @router.post("/status")
    async def status(req: StatusRequest, gate: PaymentGate = Depends(get_gate)) -> StatusResponse:
        return await gate.status(req)


def build_refund_method(router: APIRouter, get_gate: GateDependency) -> None:
    """POST /refund — создание возврата."""

    @router.post("/refund")
    async def refund(req: RefundRequest, gate: PaymentGate = Depends(get_gate)) -> RefundResponse:
        return await gate.refund(req)


def build_refund_status_method(router: APIRouter, get_gate: GateDependency) -> None:
    """POST /refund_status — статус возврата."""

    @router.post("/refund_status")
    async def refund_status(req: RefundStatusRequest, gate: PaymentGate = Depends(get_gate)) -> RefundStatusResponse:
        return await gate.refund_status(req)
