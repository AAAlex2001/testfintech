"""Тестовые данные: настройки терминала, запросы платформы и ответы Namba One."""

from typing import Any

import pytest

PROVIDER_BASE_URL = "https://api.namba-one.test"
MERCHANT_ACCOUNT_GUID = "159e7e3b-94e1-48c7-bec5-952949f7935f"
SECRET_KEY = "test-secret-key"
CALLBACK_URL = "https://gate.test/nambaone/callback/invoice"
FINISH_URL = "https://shop.test/finish"

SBANK_API_BASE_URL = "http://sbank-api.test"
SBANK_RADMIN_BASE_URL = "http://sbank-radmin.test"

INVOICE_ID = "8f1c2d3e-0000-4000-8000-000000000001"
PAYMENT_LINK_GUID = "f49b4586-3c2d-48b9-abed-28219c02a1f2"
PAYMENT_LINK_TOKEN = "https://app.nambaone.app/#000201010212"
PAYMENT_ORDER_GUID = "def45632-9604-4a4e-9890-65b03662d29b"
REFUND_ID = "8f1c2d3e-0000-4000-8000-000000000002"
REFUND_GUID = "8635e567-544d-4a98-ba9b-e741085e1cee"
TERMINAL_ID = "terminal-1"

PAYMENT_LINK_URL = f"{PROVIDER_BASE_URL}/public/merchant/payment/v2/{MERCHANT_ACCOUNT_GUID}/one-time"
PAYMENT_ORDER_URL = f"{PROVIDER_BASE_URL}/public/merchant/payment/v1/{MERCHANT_ACCOUNT_GUID}/one-time/{INVOICE_ID}"
REFUND_URL = f"{PROVIDER_BASE_URL}/public/merchant/payment/v1/{MERCHANT_ACCOUNT_GUID}/refund/{REFUND_ID}"

SBANK_INVOICE_URL = f"{SBANK_API_BASE_URL}/invoices/{INVOICE_ID}"
SBANK_INVOICE_INCOME_URL = f"{SBANK_API_BASE_URL}/invoices/{INVOICE_ID}/income"
SBANK_INVOICE_FAIL_URL = f"{SBANK_API_BASE_URL}/invoices/{INVOICE_ID}/fail"
SBANK_TERMINAL_URL = f"{SBANK_RADMIN_BASE_URL}/terminals/{TERMINAL_ID}"

# Ответы, которые не соответствуют документации: общие для всех методов
INVALID_PROVIDER_RESPONSES = [
    pytest.param({"text": "<html>Something went wrong</html>"}, id="not_json"),
    pytest.param({"json": ["OK"]}, id="json_array"),
    pytest.param({"json": {}}, id="empty_object"),
    pytest.param({"json": {"status": "SUCCESS"}}, id="unknown_status"),
]

# Ответы, после которых результат операции неизвестен
PROVIDER_UNAVAILABLE_RESPONSES = [
    pytest.param({"status_code": 500, "text": "Internal Server Error"}, id="http_500"),
    pytest.param({"status_code": 502, "json": {"status": "ERROR"}}, id="http_502"),
]


def make_terminal_data(**overrides: Any) -> dict[str, Any]:
    terminal_data = {
        "provider_base_url": PROVIDER_BASE_URL,
        "merchant_account_guid": MERCHANT_ACCOUNT_GUID,
        "secret_key": SECRET_KEY,
        "callback_url": CALLBACK_URL,
    }
    terminal_data.update(overrides)
    return terminal_data


def make_sale_request(**overrides: Any) -> dict[str, Any]:
    request = {
        "invoice_id": INVOICE_ID,
        "amount": "100.50",
        "currency_code": "KGS",
        "terminal_data": make_terminal_data(),
        "finish_url": FINISH_URL,
    }
    request.update(overrides)
    return request


def make_status_request(**overrides: Any) -> dict[str, Any]:
    request = {
        "invoice_id": INVOICE_ID,
        "external_id": PAYMENT_LINK_GUID,
        "currency_code": "KGS",
        "terminal_data": make_terminal_data(),
    }
    request.update(overrides)
    return request


def make_refund_request(**overrides: Any) -> dict[str, Any]:
    request = {
        "refund_id": REFUND_ID,
        "external_id": PAYMENT_ORDER_GUID,
        "amount": "10.00",
        "currency_code": "KGS",
        "terminal_data": make_terminal_data(),
        "comment": "Клиент вернул товар",
    }
    request.update(overrides)
    return request


def make_refund_status_request(**overrides: Any) -> dict[str, Any]:
    request = {
        "refund_id": REFUND_ID,
        "external_id": REFUND_GUID,
        "currency_code": "KGS",
        "terminal_data": make_terminal_data(),
    }
    request.update(overrides)
    return request


def make_ok_response(data: dict[str, Any] | None = None) -> dict[str, Any]:
    if data is None:
        return {"status": "OK"}
    return {"status": "OK", "data": data}


def make_error_response(error_code: str, message: str) -> dict[str, Any]:
    return {
        "status": "ERROR",
        "data": None,
        "error": {"message": message, "errorCode": error_code, "timestamp": "2021-02-02T07:26:00.849Z"},
    }


def make_payment_link() -> dict[str, Any]:
    return {
        "guid": PAYMENT_LINK_GUID,
        "token": PAYMENT_LINK_TOKEN,
        "type": "MERCHANT",
        "amount": "10050",
        "status": "ACTIVE",
        "oneTime": True,
        "currencyCode": "KGS",
    }


def make_payment_order(status: str = "COMPLETED", payment_amount: str = "10050") -> dict[str, Any]:
    return {
        "guid": PAYMENT_ORDER_GUID,
        "channel": "BALANCE",
        "currency": "KGS",
        "amount": "10050",
        "status": status,
        "paymentLinkGuid": PAYMENT_LINK_GUID,
        "merchantAccountGuid": MERCHANT_ACCOUNT_GUID,
        "paymentAmount": payment_amount,
        "refundAmount": "0",
    }


def make_refund_order(status: str = "CREATED", error_code: str | None = None) -> dict[str, Any]:
    return {
        "guid": REFUND_GUID,
        "currency": "KGS",
        "amount": "1000",
        "status": status,
        "version": "1",
        "externalGuid": REFUND_ID,
        "parentPaymentGuid": PAYMENT_ORDER_GUID,
        "errorCode": error_code,
        "merchantAccountGuid": MERCHANT_ACCOUNT_GUID,
    }


def make_invoice_info(status: str = "pending") -> dict[str, Any]:
    return {
        "id": INVOICE_ID,
        "status": status,
        "amount": "100.50",
        "currency_code": "KGS",
        "primary_terminal": TERMINAL_ID,
        "external_id": PAYMENT_LINK_GUID,
    }


def make_terminal_info() -> dict[str, Any]:
    return {"id": TERMINAL_ID, "data": make_terminal_data()}


def make_payment_webhook(status: str = "COMPLETED") -> dict[str, Any]:
    return {
        "createdAt": "2021-01-21T10:39:41.447Z",
        "type": "PAYMENT_ORDER",
        "version": "1",
        "data": {
            "guid": PAYMENT_ORDER_GUID,
            "externalId": INVOICE_ID,
            "channel": "BALANCE",
            "paymentLinkGuid": PAYMENT_LINK_GUID,
            "merchantAccountGuid": MERCHANT_ACCOUNT_GUID,
            "currency": "KGS",
            "amount": "10050",
            "paymentAmount": "10050",
            "refundAmount": "0",
            "status": status,
            "type": "PAYMENT_QR",
        },
    }
