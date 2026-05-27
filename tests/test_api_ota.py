def _request_payload() -> dict[str, object]:
    return {
        "product_model": "RMX3301",
        "manifest_code": "1B",
        "ota_track": "H",
        "rui_candidates": [8, 7],
        "language": "en-EN",
        "beta": False,
        "imei0": None,
        "imei1": None,
        "persist_result": True,
    }


def test_ota_query_uses_fake_provider_and_persists_release(client):
    response = client.post("/api/ota", json=_request_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["product_model"] == "RMX3301"
    assert body["result"]["manifest_code"] == "1B"
    assert body["result"]["real_ota_version"] == "RMX3301_11.H.21_4210_202602281641"
    assert body["result"]["is_new"] is True

    releases = client.get("/api/releases", params={"product_model": "RMX3301"}).json()
    assert releases["total"] == 1
    assert releases["releases"][0]["download_url"] == "https://example.com/update.zip"


def test_ota_query_deduplicates_existing_release(client):
    first = client.post("/api/ota", json=_request_payload()).json()
    second = client.post("/api/ota", json=_request_payload()).json()

    assert first["result"]["release_id"] == second["result"]["release_id"]
    assert second["result"]["is_new"] is False
    assert client.get("/api/releases").json()["total"] == 1


def test_ota_query_returns_safe_not_found_error(client):
    payload = _request_payload()
    payload["product_model"] = "CPH2805IN"

    response = client.post("/api/ota", json=payload)

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "error": {"code": "OTA_NOT_FOUND", "message": "No OTA release found."},
    }


def test_ota_query_rejects_invalid_manifest(client):
    payload = _request_payload()
    payload["manifest_code"] = "ZZ"

    response = client.post("/api/ota", json=payload)

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
