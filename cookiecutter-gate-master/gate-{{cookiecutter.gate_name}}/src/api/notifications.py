from api import deps
from api.schemas.notifications import InvoiceNotification
from api.schemas.notifications import WithdrawalNotification
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from gate_{{cookiecutter.gate_name}}.gate_{{cookiecutter.gate_name}} import Gate{{cookiecutter.gate_name_camel}}


router = APIRouter(prefix="/callback")

@router.post("/invoice")
async def invoice_notification(
        req: InvoiceNotification,
        gate_{{cookiecutter.gate_name}}: Gate{{cookiecutter.gate_name_camel}} = Depends(deps.gate_{{cookiecutter.gate_name}})
):
    await gate_{{cookiecutter.gate_name}}.notification_invoice(req)
    return Response(content='OK')

@router.post("/withdrawal")
async def withdrawal_notification(
        req: WithdrawalNotification,
        gate_{{cookiecutter.gate_name}}: Gate{{cookiecutter.gate_name_camel}} = Depends(deps.gate_{{cookiecutter.gate_name}})
):
    await gate_{{cookiecutter.gate_name}}.notification_withdrawal(req)
    return Response(content="OK")
