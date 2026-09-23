from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gate_lib import const as gate_lib_const
from tests.data import INVALID_PROVIDER_RESPONSES
from tests.data import PROVIDER_UNAVAILABLE_RESPONSES
from tests.data import REFUND_GUID
from tests.data import REFUND_URL
from tests.data import make_error_response
from tests.data import make_ok_response
from tests.data import make_refund_order
from tests.data import make_refund_status_request
from tests.data import make_terminal_data


def test_refund_status_success(client: TestClient, httpx_mock: HTTPXMock) -> None:
    refund_order = make_refund_order(status="COMPLETED")
    httpx_mock.add_response(method="GET", url=REFUND_URL, json=make_ok_response(refund_order))

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    assert resp.status_code == 200
    assert resp.json() == {
        "status": gate_lib_const.COMPLETE,
        "amount": "10.00",
        "currency_code": "KGS",
        "external_id": REFUND_GUID,
        "code": None,
        "message": None,
    }


@pytest.mark.parametrize(
    ("provider_status", "expected_status"),
    [
        ("CREATED", gate_lib_const.PENDING),
        ("STUCK", gate_lib_const.PENDING),
        ("SOMETHING_NEW", gate_lib_const.PENDING),
        ("CANCELED", gate_lib_const.FAILED),
        ("EXPIRED", gate_lib_const.FAILED),
    ],
)
def test_refund_status_mapping(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_status: str,
    expected_status: str,
) -> None:
    refund_order = make_refund_order(status=provider_status)
    httpx_mock.add_response(method="GET", url=REFUND_URL, json=make_ok_response(refund_order))

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    assert resp.json()["status"] == expected_status


@pytest.mark.parametrize(
    ("error_code", "expected_message"),
    [
        ("01", "Requisites not found"),
        ("02", "Supplier is unavailable"),
        ("03", "Unrecognized supplier response"),
        ("99", "Refund failed with error code 99"),
    ],
)
def test_refund_status_failed(
    client: TestClient,
    httpx_mock: HTTPXMock,
    error_code: str,
    expected_message: str,
) -> None:
    refund_order = make_refund_order(status="FAILED", error_code=error_code)
    httpx_mock.add_response(method="GET", url=REFUND_URL, json=make_ok_response(refund_order))

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == error_code
    assert data["message"] == expected_message


def test_refund_status_provider_error(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=REFUND_URL,
        status_code=400,
        json=make_error_response("MERCHANT_API_UNKNOWN_MERCHANT", "No merchant key was found"),
    )

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "MERCHANT_API_UNKNOWN_MERCHANT"
    assert data["external_id"] == REFUND_GUID


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(make_refund_status_request(refund_id=""), id="empty_refund_id"),
        pytest.param({"refund_id": "1"}, id="missing_fields"),
    ],
)
def test_refund_status_invalid_request(
    client: TestClient,
    httpx_mock: HTTPXMock,
    request_body: dict[str, Any],
) -> None:
    resp = client.post("/v2/refund_status", json=request_body)

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_refund_status_invalid_terminal_data(client: TestClient, httpx_mock: HTTPXMock) -> None:
    terminal_data = make_terminal_data(provider_base_url="ftp://namba-one.test")

    resp = client.post("/v2/refund_status", json=make_refund_status_request(terminal_data=terminal_data))

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "validation_error"


@pytest.mark.parametrize(
    "provider_response",
    [
        *INVALID_PROVIDER_RESPONSES,
        pytest.param({"json": make_ok_response()}, id="ok_without_data"),
    ],
)
def test_refund_status_invalid_provider_response(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="GET", url=REFUND_URL, **provider_response)

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "invalid_provider_response"


def test_refund_status_empty_provider_response(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=REFUND_URL, content=b"")

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "invalid_provider_response"


def test_refund_status_provider_timeout(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"), method="GET", url=REFUND_URL)

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "provider_timeout"


@pytest.mark.parametrize("provider_response", PROVIDER_UNAVAILABLE_RESPONSES)
def test_refund_status_provider_unavailable(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="GET", url=REFUND_URL, **provider_response)

    resp = client.post("/v2/refund_status", json=make_refund_status_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.PENDING
    assert data["code"] == "provider_unavailable"
