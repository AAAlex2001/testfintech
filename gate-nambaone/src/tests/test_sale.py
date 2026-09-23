import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from gate_lib import const as gate_lib_const
from gate_nambaone.signature import SALT_HEADER
from gate_nambaone.signature import SIGNATURE_HEADER
from gate_nambaone.signature import make_signature
from tests.data import CALLBACK_URL
from tests.data import FINISH_URL
from tests.data import INVALID_PROVIDER_RESPONSES
from tests.data import INVOICE_ID
from tests.data import PAYMENT_LINK_GUID
from tests.data import PAYMENT_LINK_TOKEN
from tests.data import PAYMENT_LINK_URL
from tests.data import PROVIDER_UNAVAILABLE_RESPONSES
from tests.data import SECRET_KEY
from tests.data import make_error_response
from tests.data import make_ok_response
from tests.data import make_payment_link
from tests.data import make_sale_request
from tests.data import make_terminal_data


def test_sale_success(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=PAYMENT_LINK_URL, json=make_ok_response(make_payment_link()))

    resp = client.post("/v2/sale", json=make_sale_request())

    assert resp.status_code == 200
    assert resp.json() == {
        "status": gate_lib_const.PENDING,
        "amount": "100.50",
        "currency_code": "KGS",
        "external_id": PAYMENT_LINK_GUID,
        "code": None,
        "message": None,
        "redirect": {"url": PAYMENT_LINK_TOKEN, "method": "GET"},
    }


def test_sale_sends_signed_request_in_minor_units(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=PAYMENT_LINK_URL, json=make_ok_response(make_payment_link()))

    client.post("/v2/sale", json=make_sale_request())

    request = httpx_mock.get_request()
    body = request.content.decode()
    assert json.loads(body) == {
        "externalId": INVOICE_ID,
        "amount": "10050",
        "amountCanBeChanged": False,
        "webhookUrl": CALLBACK_URL,
        "webOptions": {"redirectLink": FINISH_URL, "autoRedirect": True},
    }
    expected_signature = make_signature(SECRET_KEY, request.url.raw_path.decode(), body, request.headers[SALT_HEADER])
    assert request.headers[SIGNATURE_HEADER] == expected_signature


def test_sale_provider_error(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=PAYMENT_LINK_URL,
        status_code=400,
        json=make_error_response("PAYMENT_LINK_EXTERNAL_ID_DUPLICATE_EXCEPTION", "External id duplicate"),
    )

    resp = client.post("/v2/sale", json=make_sale_request())

    data = resp.json()
    assert resp.status_code == 200
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "PAYMENT_LINK_EXTERNAL_ID_DUPLICATE_EXCEPTION"
    assert data["message"] == "External id duplicate"
    assert data["redirect"] is None


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(make_sale_request(invoice_id=""), id="empty_invoice_id"),
        pytest.param(make_sale_request(amount="-1"), id="negative_amount"),
        pytest.param(make_sale_request(amount="abc"), id="amount_not_a_number"),
        pytest.param({"invoice_id": INVOICE_ID}, id="missing_fields"),
    ],
)
def test_sale_invalid_request(client: TestClient, httpx_mock: HTTPXMock, request_body: dict[str, Any]) -> None:
    resp = client.post("/v2/sale", json=request_body)

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


@pytest.mark.parametrize(
    ("request_body", "expected_message"),
    [
        pytest.param(
            make_sale_request(terminal_data=make_terminal_data(merchant_account_guid="not-a-guid")),
            "Terminal data is not valid: merchant_account_guid",
            id="invalid_terminal_data",
        ),
        pytest.param(
            make_sale_request(currency_code="USD"),
            "Currency USD is not supported, only KGS",
            id="unsupported_currency",
        ),
        pytest.param(
            make_sale_request(amount="100.555"),
            "Amount must have at most 2 decimal places",
            id="fractional_tyiyn",
        ),
    ],
)
def test_sale_request_not_supported_by_provider(
    client: TestClient,
    httpx_mock: HTTPXMock,
    request_body: dict[str, Any],
    expected_message: str,
) -> None:
    resp = client.post("/v2/sale", json=request_body)

    data = resp.json()
    assert resp.status_code == 200
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "validation_error"
    assert data["message"] == expected_message


def test_sale_invalid_terminal_data_does_not_leak_secret(client: TestClient, httpx_mock: HTTPXMock) -> None:
    terminal_data = make_terminal_data(provider_base_url="not-a-url")

    resp = client.post("/v2/sale", json=make_sale_request(terminal_data=terminal_data))

    assert SECRET_KEY not in resp.text


@pytest.mark.parametrize(
    "provider_response",
    [
        *INVALID_PROVIDER_RESPONSES,
        pytest.param({"json": make_ok_response()}, id="ok_without_data"),
        pytest.param({"json": make_ok_response({"guid": PAYMENT_LINK_GUID})}, id="data_without_token"),
    ],
)
def test_sale_invalid_provider_response(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="POST", url=PAYMENT_LINK_URL, **provider_response)

    resp = client.post("/v2/sale", json=make_sale_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "invalid_provider_response"


def test_sale_empty_provider_response(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=PAYMENT_LINK_URL, content=b"")

    resp = client.post("/v2/sale", json=make_sale_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "invalid_provider_response"
    assert data["message"] == "Provider returned an empty response"


def test_sale_provider_timeout(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"), method="POST", url=PAYMENT_LINK_URL)

    resp = client.post("/v2/sale", json=make_sale_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "provider_timeout"


@pytest.mark.parametrize("provider_response", PROVIDER_UNAVAILABLE_RESPONSES)
def test_sale_provider_unavailable(
    client: TestClient,
    httpx_mock: HTTPXMock,
    provider_response: dict[str, Any],
) -> None:
    httpx_mock.add_response(method="POST", url=PAYMENT_LINK_URL, **provider_response)

    resp = client.post("/v2/sale", json=make_sale_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "provider_unavailable"


def test_sale_provider_connection_error(client: TestClient, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), method="POST", url=PAYMENT_LINK_URL)

    resp = client.post("/v2/sale", json=make_sale_request())

    data = resp.json()
    assert data["status"] == gate_lib_const.FAILED
    assert data["code"] == "provider_unavailable"
