from gate_lib import const as gate_lib_const

# Namba One работает только с киргизским сомом, суммы передаются в тыйынах
CURRENCY_CODE = "KGS"
MINOR_UNITS_IN_MAJOR = 100

RESPONSE_STATUS_OK = "OK"
RESPONSE_STATUS_ERROR = "ERROR"

# Тип исходного платежа для возврата: оплата по платёжной ссылке (QR)
REFUND_PARENT_TYPE = "PAYMENT_QR"

PAYMENT_STATUS_MAPPING = {
    "CREATED": gate_lib_const.PENDING,
    "PAYER_DEBIT": gate_lib_const.PENDING,
    "PAYER_DEBIT_SUCCESSFUL": gate_lib_const.PENDING,
    "PROCESSING": gate_lib_const.PENDING,
    "CANCELLATION_ATTEMPTED": gate_lib_const.PENDING,
    "CANCELLATION_FAILED": gate_lib_const.PENDING,
    "COMPLETED": gate_lib_const.COMPLETE,
    # Платёж прошёл, а возврат по нему отслеживается отдельно через refund_status
    "REFUNDED": gate_lib_const.COMPLETE,
    "CANCELED": gate_lib_const.FAILED,
    "FAILED": gate_lib_const.FAILED,
    "EXPIRED": gate_lib_const.FAILED,
}

REFUND_STATUS_MAPPING = {
    "CREATED": gate_lib_const.PENDING,
    "PROCESSING": gate_lib_const.PENDING,
    # Возврат завис у провайдера: нужен ручной разбор, поэтому не финализируем
    "STUCK": gate_lib_const.PENDING,
    "COMPLETED": gate_lib_const.COMPLETE,
    "CANCELED": gate_lib_const.FAILED,
    "FAILED": gate_lib_const.FAILED,
    "EXPIRED": gate_lib_const.FAILED,
}

REFUND_ERROR_MESSAGES = {
    "01": "Requisites not found",
    "02": "Supplier is unavailable",
    "03": "Unrecognized supplier response",
}
