from fastapi.testclient import TestClient

from gate_nambaone.schemas.terminal_data import TERMINAL_DATA_SCHEMA


def test_ping(client: TestClient) -> None:
    resp = client.get("/v2/ping")

    assert resp.status_code == 200
    assert resp.text == "pong"


def test_terminal_data_schema(client: TestClient) -> None:
    resp = client.get("/v2/terminal_data_schema")

    assert resp.status_code == 200
    assert resp.json() == TERMINAL_DATA_SCHEMA


def test_terminal_data_schema_has_gate_connection_url(client: TestClient) -> None:
    resp = client.get("/v2/terminal_data_schema")

    field_names = [field["name"] for group in resp.json()["groups"] for field in group["fields"]]
    assert "gate_connection.url" in field_names


def test_trace_id_is_returned(client: TestClient) -> None:
    resp = client.get("/v2/ping", headers={"X-Trace-ID": "trace-1"})

    assert resp.headers["X-Trace-ID"] == "trace-1"
