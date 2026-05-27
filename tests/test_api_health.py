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
        },
    }
