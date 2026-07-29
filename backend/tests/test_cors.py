from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_allowed_origin_gets_cors_headers():
    resp = client.get("/health", headers={"Origin": "https://benjamen.github.io"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://benjamen.github.io"
    assert resp.headers["access-control-allow-credentials"] == "true"


def test_null_origin_allowed_for_local_file_testing():
    resp = client.get("/health", headers={"Origin": "null"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "null"


def test_disallowed_origin_gets_no_cors_header():
    resp = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers
