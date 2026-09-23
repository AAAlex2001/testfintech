import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import PlainTextResponse

from api import deps
from gate_nambaone.exceptions import GateError
from gate_nambaone.gate_nambaone import GateNambaOne
from gate_nambaone.schemas.notifications import PaymentOrderNotification
from sbank_client.exceptions import SbankClientError

logger = structlog.get_logger()

router = APIRouter(prefix="/callback", tags=["callbacks"])


@router.post("/invoice", response_class=PlainTextResponse)
async def invoice_notification(
    req: PaymentOrderNotification,
    gate: GateNambaOne = Depends(deps.gate_nambaone),
) -> PlainTextResponse:
    """
    Вебхук Namba One об оплате.

    Если итог подтвердить не удалось, отвечаем 503: Namba One повторяет
    вебхук каждые 5 секунд в течение часа, пока не получит 2xx.
    """
    try:
        is_processed = await gate.notification_invoice(req)
    except (GateError, SbankClientError) as error:
        logger.error("invoice_notification_failed", invoice_id=req.data.external_id, error=str(error))
        is_processed = False

    if not is_processed:
        return PlainTextResponse("RETRY", status_code=503)
    return PlainTextResponse("OK")
