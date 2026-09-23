"""Подпись запросов к Namba One: https://merchant-api-docs.rps.kg/src-pages-signature-index"""

import base64
import hashlib
import hmac
import uuid

SALT_HEADER = "x-merchant-api-salt"
SIGNATURE_HEADER = "x-merchant-api-signature"


def make_signature(secret_key: str, path: str, body: str, salt: str) -> str:
    """HMAC-SHA512 от строки path + body + salt, закодированный в Base64."""
    message = f"{path}{body}{salt}".encode()
    digest = hmac.new(secret_key.encode(), message, hashlib.sha512).digest()
    return base64.b64encode(digest).decode()


def make_signature_headers(secret_key: str, path: str, body: str) -> dict[str, str]:
    """Заголовки подписи с новой солью для каждого запроса."""
    salt = str(uuid.uuid4())
    return {
        SALT_HEADER: salt,
        SIGNATURE_HEADER: make_signature(secret_key, path, body, salt),
    }
