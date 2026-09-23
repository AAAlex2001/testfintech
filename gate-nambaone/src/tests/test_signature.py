from gate_nambaone.signature import SALT_HEADER
from gate_nambaone.signature import SIGNATURE_HEADER
from gate_nambaone.signature import make_signature
from gate_nambaone.signature import make_signature_headers

# Данные из примера в документации Namba One
DOCS_SECRET_KEY = "some secret from Namba One team"
DOCS_PATH = "/public/merchant/payment/v1/39b826bf-6b00-4996-bee7-7bfab4e055f5/static"
DOCS_BODY = '{"externalId":"123","webhookUrl":"http://test.test.test","amount":"100","amountCanBeChanged":false}'
DOCS_SALT = "d5afd864-7559-43d3-9f30-76805f536db9"


def test_make_signature() -> None:
    signature = make_signature(DOCS_SECRET_KEY, DOCS_PATH, DOCS_BODY, DOCS_SALT)

    assert signature == "t8sXeFwOy1Y4MTFlLanOQoXev+F8kkI/xBEHmeEOkU+8sfJF4XI9Ki6tE007nks9sGTsdmK0jq0Wd3vpWZcKJg=="


def test_make_signature_headers_uses_new_salt_for_each_request() -> None:
    first = make_signature_headers(DOCS_SECRET_KEY, DOCS_PATH, DOCS_BODY)
    second = make_signature_headers(DOCS_SECRET_KEY, DOCS_PATH, DOCS_BODY)

    assert first[SALT_HEADER] != second[SALT_HEADER]
    assert first[SIGNATURE_HEADER] == make_signature(DOCS_SECRET_KEY, DOCS_PATH, DOCS_BODY, first[SALT_HEADER])
