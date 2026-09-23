import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.data import SBANK_API_BASE_URL
from tests.data import SBANK_RADMIN_BASE_URL

# Настройки нужно задать до импорта приложения: settings читаются при импорте
os.environ.update(
    {
        "SBANK_API_BASE_URL": SBANK_API_BASE_URL,
        "SBANK_RADMIN_BASE_URL": SBANK_RADMIN_BASE_URL,
        "SBANK_API_AUTH_TOKEN": "test-sbank-token",
        "ELASTIC_APM_ENABLED": "false",
    }
)

from main import app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
