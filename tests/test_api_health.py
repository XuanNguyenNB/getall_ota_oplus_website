def test_health_returns_documented_envelope(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "getall_ota_oplus_website",
        "version": "0.1.0",
        "features": {
            "public_site": False,
            "resolver": False,
            "turnstile_site_key": None,
            "admin_auth_enabled": False,
        },
    }


def test_health_advertises_admin_auth_capability_but_not_credentials():
    """The health probe must reveal only whether admin auth is configured,
    not the Supabase URL or anon key. Those live behind /api/admin/bootstrap."""

    from fastapi.testclient import TestClient

    from ota_backend.app import create_app
    from ota_backend.config import Settings

    app = create_app(
        settings=Settings(
            SUPABASE_URL="https://project-ref.supabase.co",
            SUPABASE_ANON_KEY="anon-public-key",
        )
    )
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["features"]["admin_auth_enabled"] is True
    # Defensive: no credential material should leak through health.
    flat = repr(body)
    assert "anon-public-key" not in flat
    assert "project-ref.supabase.co" not in flat


def test_admin_bootstrap_returns_supabase_pair_when_configured():
    from fastapi.testclient import TestClient

    from ota_backend.app import create_app
    from ota_backend.config import Settings

    app = create_app(
        settings=Settings(
            SUPABASE_URL="https://project-ref.supabase.co",
            SUPABASE_ANON_KEY="anon-public-key",
        )
    )
    response = TestClient(app).get("/api/admin/bootstrap")

    assert response.status_code == 200
    assert response.json()["admin_auth"] == {
        "supabase_url": "https://project-ref.supabase.co",
        "supabase_anon_key": "anon-public-key",
    }


def test_admin_bootstrap_returns_null_when_not_configured(client):
    response = client.get("/api/admin/bootstrap")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "admin_auth": None}
