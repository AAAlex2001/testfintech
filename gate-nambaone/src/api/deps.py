from fastapi import Request

from gate_nambaone.gate_nambaone import GateNambaOne
from sbank_client.client import SbankClient
from settings import settings


def gate_nambaone(request: Request) -> GateNambaOne:
    """FastAPI-зависимость: гейт с общим HTTP-клиентом приложения для sbank."""
    sbank = SbankClient(
        httpx_client=request.app.state.httpx_client,
        base_url=settings.SBANK_API_BASE_URL,
        radmin_base_url=settings.SBANK_RADMIN_BASE_URL,
        auth_token=settings.SBANK_API_AUTH_TOKEN,
    )
    return GateNambaOne(sbank=sbank, request_timeout=settings.REQUEST_TIMEOUT)
