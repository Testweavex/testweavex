import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Disable the keep-alive loop so the generator terminates immediately
    # after yielding the connected event.  Without this the generator loops
    # forever and TestClient never delivers any data to the test.
    monkeypatch.setenv("TW_SSE_KEEPALIVE", "0")
    # Re-import events module so the module-level _KEEPALIVE_INTERVAL
    # constant picks up the patched env var.
    import importlib
    import testweavex.web.api.events as events_mod
    importlib.reload(events_mod)
    from testweavex.web.app import create_app
    return TestClient(create_app())


def test_sse_returns_event_stream(client):
    with client.stream("GET", "/api/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        chunk = next(response.iter_text())
        assert "connected" in chunk
