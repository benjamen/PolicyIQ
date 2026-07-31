from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_allowed_origin_gets_cors_headers():
    resp = client.get("/health", headers={"Origin": "https://benjamen.github.io"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://benjamen.github.io"
    assert resp.headers["access-control-allow-credentials"] == "true"


def test_real_production_frontend_origin_gets_cors_headers():
    """Real gap found 2026-07-31 via a live end-to-end browser test against
    https://policyiq.nz/?live=1: the default origin list only ever had the
    GitHub Pages fallback domain (benjamen.github.io), never the actual
    custom domain the frontend is served from - the site's own live-data
    mode had been silently broken (CORS-blocked) since deployment."""
    for origin in ("https://policyiq.nz", "https://www.policyiq.nz"):
        resp = client.get("/health", headers={"Origin": origin})
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == origin


def test_null_origin_allowed_for_local_file_testing():
    resp = client.get("/health", headers={"Origin": "null"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "null"


def test_disallowed_origin_gets_no_cors_header():
    resp = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers
