from typing import Any
from typing import Protocol

from gate_lib.protocol.v2.refund import RefundRequest
from gate_lib.protocol.v2.refund import RefundResponse
from gate_lib.protocol.v2.refund import RefundStatusRequest
from gate_lib.protocol.v2.refund import RefundStatusResponse
from gate_lib.protocol.v2.sale import SaleRequest
from gate_lib.protocol.v2.sale import SaleResponse
from gate_lib.protocol.v2.status import StatusRequest
from gate_lib.protocol.v2.status import StatusResponse


class PaymentGate(Protocol):
    """
    Интерфейс гейта: какие методы должны быть у любой интеграции с провайдером.

    Роуты gate_lib работают с любым объектом, у которого есть эти методы,
    и не знают про конкретный гейт вроде GateNambaOne.
    Наследоваться от этого класса не нужно, достаточно реализовать такие же методы.
    """

    async def terminal_data_schema(self) -> dict[str, Any]:
        """Описание настроек терминала для админки."""
        ...

    async def sale_without_card(self, req: SaleRequest) -> SaleResponse:
        """Создание платежа с редиректом плательщика к провайдеру."""
        ...

    async def status(self, req: StatusRequest) -> StatusResponse:
        """Получение статуса платежа."""
        ...

    async def refund(self, req: RefundRequest) -> RefundResponse:
        """Создание возврата."""
        ...

    async def refund_status(self, req: RefundStatusRequest) -> RefundStatusResponse:
        """Получение статуса возврата."""
        ...
