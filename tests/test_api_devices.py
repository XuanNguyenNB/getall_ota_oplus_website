def test_devices_returns_paginated_enabled_devices(client):
    response = client.get("/api/devices")

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["count"] == 2
    assert body["total"] == 2
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert {device["product_model"] for device in body["devices"]} == {
        "CPH2805IN",
        "RMX3301",
    }


def test_devices_supports_brand_filter_and_disabled_rows(client):
    response = client.get("/api/devices", params={"brand": "oppo", "enabled_only": False})

    body = response.json()
    assert response.status_code == 200
    assert body["count"] == 1
    assert body["devices"][0]["brand"] == "oppo"
    assert body["devices"][0]["scan_enabled"] is False
