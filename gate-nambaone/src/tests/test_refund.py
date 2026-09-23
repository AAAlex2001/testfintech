import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gate_lib import const as gate_lib_const
from tests.data import INVALID_PROVIDER_RESPONSES
from tests.data import PAYMENT_ORDER_GUID
from tests.data import PROVIDER_UNAVAILABLE_RESPONSES
from tests.data import REFUND_GUID
from tests.data import REFUND_URL
from tests.data import make_error_response
from tests.data import make_ok_response
from tests.data import make_refund_order
from tests.data import make_refund_request
from tests.data import make_terminal_data


def test_refund_success(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=REFUND_URL, json=make_ok_response(make_refund_order()))

    resp = client.post("/v2/refund", json=make_refund_request())

    assert resp.status_code == 200
    assert resp.json() == {
        "status": gate_lib_const.PENDING,
        "amount": "10.00",
        "currency_code": "KGS",
        "external_id": REFUND_GUID,
        "code": None,
        "message": None,
    }


def test_refund_sends_request_in_minor_units(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=REFUND_URL, json=make_ok_response(make_refund_order()))

    client.post("/v2/refund", json=make_refund_request())

    assert json.loads(httpx_mock.get_request().content) == {
        "parentType": "PAYMENT_QR",
        "paymentOrderGuid": PAYMENT_ORDER_GUID,
        "amount": "1000",
        "comment": "Клиент вернул товар",
    }


def test_refund_completed_immediately(client: TestClient, httpx_mock: HTTPXMock) -> None:
    refund_order = make_refund_order(status="COMPLETED")
    httpx_mock.add_response(method="POST", url=REFUND_URL, json=make_ok_response(refund_order))

    resp = client.post("/v2/refund", json=make_refund_request())

    assert resp.json()["status"] == gate_lib_const.COMPLETE


@pytest.mark.parametrize(
    ("error_code", "message"),
    [
        ("PAYMENT_ORDER_NOT_FOUND_EXCEPTION", "Payment order not found"),
        ("REFUND_ORDERS_AMOUNT_IS_MORE_THAN_PARENT", "Refund orders amount is more than parent (partial)"),
        ("REFUND_PARENT_ORDER_WRONG_STATUS", "Parent payment order wrong status"),
        ("MERCHANT_ACCOUNT_LIMIT_BALANCE_EXCEEDED_EXCEPTION", "MerchantAccount limit balance exceeded"),
    ],
)
def test_refund_provider_error(client: TestClient, httpx_mock: HTTPXMock, error_code: str, message: str) -> None:
    httpx_mock.add_response(
        method="POST",
        url=REFUND_URL,
        status_code=400,
        json=make_error_response(error_code, message),
    )

    resp = client.post("/v2/refund", json=make_refund_request())

    data = resp.json()
    assert resp.status_code == 200
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == error_code
    assert data["message"] == message


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(make_refund_request(refund_id=""), id="empty_refund_id"),
        pytest.param(make_refund_request(external_id=""), id="empty_external_id"),
        pytest.param(make_refund_request(amount="0"), id="zero_amount"),
        pytest.param({"refund_id": "1"}, id="missing_fields"),
    ],
)
def test_refund_invalid_request(client: TestClient, httpx_mock: HTTPXMock, request_body: dict[str, Any]) -> None:
    resp = client.post("/v2/refund", json=request_body)

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(
            make_refund_request(terminal_data=make_terminal_data(secret_key="")),
            id="invalid_terminal_data",
        ),
        pytest.param(make_refund_request(currency_code="EUR"), id="unsupported_currency"),
    ],
)
def test_refund_request_not_supported_by_provider(
    client: TestClient,
    httpx_mock: HTTPXMock,
    request_body: dict[str, Any],
) -> None:
    resp = client.post("/v2/refund", json=request_body)

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "validation_error"


# Если ответ провайдера непонятен или не получен, возврат мог создаться:
# отклонять его нельзя, итог покажет refund_status
@pytest.mark.parametrize(
    "provider_response",
    [
        *INVALID_PROVIDER_RESPONSES,
        pytest.param({"json": make_ok_response()}, id="ok_without_data"),
    ],
)
def test_refund_invalid_provider_response(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="POST", url=REFUND_URL, **provider_response)

    resp = client.post("/v2/refund", json=make_refund_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "invalid_provider_response"


def test_refund_empty_provider_response(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=REFUND_URL, content=b"")

    resp = client.post("/v2/refund", json=make_refund_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "invalid_provider_response"


def test_refund_provider_timeout(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"), method="POST", url=REFUND_URL)

    resp = client.post("/v2/refund", json=make_refund_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["amount"] == "10.00"
    assert data["code"] == "provider_timeout"


@pytest.mark.parametrize("provider_response", PROVIDER_UNAVAILABLE_RESPONSES)
def test_refund_provider_unavailable(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="POST", url=REFUND_URL, **provider_response)

    resp = client.post("/v2/refund", json=make_refund_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "provider_unavailable"
