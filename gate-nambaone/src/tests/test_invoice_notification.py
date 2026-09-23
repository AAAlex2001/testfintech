import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from tests.data import INVALID_PROVIDER_RESPONSES
from tests.data import PAYMENT_ORDER_GUID
from tests.data import PAYMENT_ORDER_URL
from tests.data import PROVIDER_UNAVAILABLE_RESPONSES
from tests.data import SBANK_INVOICE_FAIL_URL
from tests.data import SBANK_INVOICE_INCOME_URL
from tests.data import SBANK_INVOICE_URL
from tests.data import SBANK_TERMINAL_URL
from tests.data import make_error_response
from tests.data import make_invoice_info
from tests.data import make_ok_response
from tests.data import make_payment_order
from tests.data import make_payment_webhook
from tests.data import make_terminal_info

NOTIFICATION_URL = "/nambaone/callback/invoice"


def mock_sbank_invoice(httpx_mock: HTTPXMock) -> None:
    """sbank отдаёт неоплаченный инвойс и терминал с настройками Namba One."""
    httpx_mock.add_response(method="GET", url=SBANK_INVOICE_URL, json=make_invoice_info())
    httpx_mock.add_response(method="GET", url=SBANK_TERMINAL_URL, json=make_terminal_info())


def test_invoice_notification_success(client: TestClient, httpx_mock: HTTPXMock) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(make_payment_order()))
    httpx_mock.add_response(method="POST", url=SBANK_INVOICE_INCOME_URL)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 200
    assert resp.text == "OK"
    income_request = httpx_mock.get_request(url=SBANK_INVOICE_INCOME_URL)
    assert json.loads(income_request.content) == {
        "amount_paid": "100.50",
        "external_transaction_id": PAYMENT_ORDER_GUID,
    }


def test_invoice_notification_payment_failed(client: TestClient, httpx_mock: HTTPXMock) -> None:
    mock_sbank_invoice(httpx_mock)
    payment_order = make_payment_order(status="EXPIRED")
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(payment_order))
    httpx_mock.add_response(method="POST", url=SBANK_INVOICE_FAIL_URL)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook(status="EXPIRED"))

    assert resp.status_code == 200
    fail_request = httpx_mock.get_request(url=SBANK_INVOICE_FAIL_URL)
    assert json.loads(fail_request.content) == {
        "error_code": "EXPIRED",
        "error_message": "Payment finished with status EXPIRED",
    }


def test_invoice_notification_does_not_trust_webhook_status(client: TestClient, httpx_mock: HTTPXMock) -> None:
    # Вебхук говорит COMPLETED, но провайдер подтверждает, что платежа нет
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response())

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook(status="COMPLETED"))

    assert resp.status_code == 503
    assert httpx_mock.get_request(url=SBANK_INVOICE_INCOME_URL) is None


def test_invoice_notification_already_processed(client: TestClient, httpx_mock: HTTPXMock) -> None:
    # Namba One повторяет вебхук, а инвойс уже оплачен: провайдера не спрашиваем
    httpx_mock.add_response(method="GET", url=SBANK_INVOICE_URL, json=make_invoice_info(status="complete"))

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 200
    assert resp.text == "OK"


def test_invoice_notification_provider_error(client: TestClient, httpx_mock: HTTPXMock) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(
        method="GET",
        url=PAYMENT_ORDER_URL,
        status_code=401,
        json=make_error_response("MERCHANT_API_WRONG_SIGNATURE", "Signature is wrong"),
    )

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(make_payment_webhook() | {"type": "REFUND_ORDER"}, id="wrong_type"),
        pytest.param({"type": "PAYMENT_ORDER", "data": {"guid": PAYMENT_ORDER_GUID}}, id="missing_external_id"),
        pytest.param({}, id="empty_body"),
    ],
)
def test_invoice_notification_invalid_request(
    client: TestClient,
    httpx_mock: HTTPXMock,
    request_body: dict[str, Any],
) -> None:
    resp = client.post(NOTIFICATION_URL, json=request_body)

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_invoice_notification_invalid_terminal_data(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=SBANK_INVOICE_URL, json=make_invoice_info())
    httpx_mock.add_response(method="GET", url=SBANK_TERMINAL_URL, json={"id": "terminal-1", "data": {}})

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


@pytest.mark.parametrize("provider_response", INVALID_PROVIDER_RESPONSES)
def test_invoice_notification_invalid_provider_response(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, **provider_response)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


def test_invoice_notification_empty_provider_response(client: TestClient, httpx_mock: HTTPXMock) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, content=b"")

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


def test_invoice_notification_provider_timeout(client: TestClient, httpx_mock: HTTPXMock) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"), method="GET", url=PAYMENT_ORDER_URL)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


@pytest.mark.parametrize("provider_response", PROVIDER_UNAVAILABLE_RESPONSES)
def test_invoice_notification_provider_unavailable(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, **provider_response)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


def test_invoice_notification_sbank_unavailable(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), method="GET", url=SBANK_INVOICE_URL)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503


def test_invoice_notification_sbank_income_failed(client: TestClient, httpx_mock: HTTPXMock) -> None:
    mock_sbank_invoice(httpx_mock)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(make_payment_order()))
    httpx_mock.add_response(method="POST", url=SBANK_INVOICE_INCOME_URL, status_code=500)

    resp = client.post(NOTIFICATION_URL, json=make_payment_webhook())

    assert resp.status_code == 503
