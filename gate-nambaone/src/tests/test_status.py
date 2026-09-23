from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gate_lib import const as gate_lib_const
from tests.data import INVALID_PROVIDER_RESPONSES
from tests.data import PAYMENT_LINK_GUID
from tests.data import PAYMENT_ORDER_GUID
from tests.data import PAYMENT_ORDER_URL
from tests.data import PROVIDER_UNAVAILABLE_RESPONSES
from tests.data import make_error_response
from tests.data import make_ok_response
from tests.data import make_payment_order
from tests.data import make_status_request
from tests.data import make_terminal_data


def test_status_success(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(make_payment_order()))

    resp = client.post("/v2/status", json=make_status_request())

    assert resp.status_code == 200
    assert resp.json() == {
        "status": gate_lib_const.COMPLETE,
        "amount": "100.50",
        "currency_code": "KGS",
        "external_id": PAYMENT_ORDER_GUID,
        "code": None,
        "message": None,
    }


def test_status_returns_actually_paid_amount(client: TestClient, httpx_mock: HTTPXMock) -> None:
    payment_order = make_payment_order(payment_amount="5000")
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(payment_order))

    resp = client.post("/v2/status", json=make_status_request())

    assert resp.json()["amount"] == "50.00"


@pytest.mark.parametrize(
    ("provider_status", "expected_status"),
    [
        ("CREATED", gate_lib_const.PENDING),
        ("PROCESSING", gate_lib_const.PENDING),
        ("CANCELLATION_FAILED", gate_lib_const.PENDING),
        ("REFUNDED", gate_lib_const.COMPLETE),
        ("SOMETHING_NEW", gate_lib_const.PENDING),
    ],
)
def test_status_mapping(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_status: str,
    expected_status: str,
) -> None:
    payment_order = make_payment_order(status=provider_status)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(payment_order))

    resp = client.post("/v2/status", json=make_status_request())

    assert resp.json()["status"] == expected_status


@pytest.mark.parametrize("provider_status", ["CANCELED", "FAILED", "EXPIRED"])
def test_status_payment_failed(client: TestClient, httpx_mock: HTTPXMock, provider_status: str) -> None:
    payment_order = make_payment_order(status=provider_status)
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response(payment_order))

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == provider_status
    assert data["message"] == f"Payment finished with status {provider_status}"


def test_status_not_paid_yet(client: TestClient, httpx_mock: HTTPXMock) -> None:
    # Пока клиент не оплатил ссылку, провайдер отвечает без data
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, json=make_ok_response())

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["external_id"] == PAYMENT_LINK_GUID
    assert data["code"] is None


def test_status_provider_error(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=PAYMENT_ORDER_URL,
        status_code=401,
        json=make_error_response("MERCHANT_API_WRONG_SIGNATURE", "Signature is wrong"),
    )

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "MERCHANT_API_WRONG_SIGNATURE"
    assert data["message"] == "Signature is wrong"


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(make_status_request(invoice_id=""), id="empty_invoice_id"),
        pytest.param(make_status_request(currency_code="KGSS"), id="invalid_currency"),
        pytest.param(make_status_request(terminal_data="not-an-object"), id="terminal_data_not_object"),
    ],
)
def test_status_invalid_request(client: TestClient, httpx_mock: HTTPXMock, request_body: dict[str, Any]) -> None:
    resp = client.post("/v2/status", json=request_body)

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_status_invalid_terminal_data(client: TestClient, httpx_mock: HTTPXMock) -> None:
    terminal_data = make_terminal_data()
    terminal_data.pop("secret_key")

    resp = client.post("/v2/status", json=make_status_request(terminal_data=terminal_data))

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "validation_error"
    assert data["message"] == "Terminal data is not valid: secret_key"


@pytest.mark.parametrize(
    "provider_response",
    [
        *INVALID_PROVIDER_RESPONSES,
        pytest.param({"json": make_ok_response({"guid": PAYMENT_ORDER_GUID})}, id="data_without_status"),
        pytest.param({"json": make_ok_response(make_payment_order() | {"amount": "abc"})}, id="amount_not_a_number"),
    ],
)
def test_status_invalid_provider_response(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, **provider_response)

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "invalid_provider_response"


def test_status_empty_provider_response(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, content=b"")

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "invalid_provider_response"


def test_status_provider_timeout(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"), method="GET", url=PAYMENT_ORDER_URL)

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "provider_timeout"


@pytest.mark.parametrize("provider_response", PROVIDER_UNAVAILABLE_RESPONSES)
def test_status_provider_unavailable(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="GET", url=PAYMENT_ORDER_URL, **provider_response)

    resp = client.post("/v2/status", json=make_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "provider_unavailable"
