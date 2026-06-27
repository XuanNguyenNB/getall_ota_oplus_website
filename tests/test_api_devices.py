def test_devices_returns_paginated_enabled_devices(client):
    response = client.get("/api/devices")

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["count"] == 3
    assert body["total"] == 3
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert {device["product_model"] for device in body["devices"]} == {
        "CPH2805IN",
        "CPH2305EU",
        "RMX3301",
    }
    assert all(device["catalog_visible"] is True for device in body["devices"])
    assert all(device["scan_group_key"] for device in body["devices"])


def test_devices_supports_brand_filter_and_disabled_rows(client):
    response = client.get("/api/devices", params={"brand": "oppo", "enabled_only": False})

    body = response.json()
    assert response.status_code == 200
    assert body["count"] == 1
    assert body["devices"][0]["brand"] == "oppo"
    assert body["devices"][0]["scan_enabled"] is False


def test_devices_can_filter_scan_enabled_allowlist(client):
    response = client.get("/api/devices", params={"scan_enabled_only": True})

    body = response.json()
    assert response.status_code == 200
    assert body["count"] == 2
    assert {device["product_model"] for device in body["devices"]} == {
        "CPH2805IN",
        "RMX3301",
    }


def test_memory_device_repository_bulk_get_by_ids_returns_known_rows_only():
    """The bulk lookup is the scanner's primary mechanism for resolving
    task_devices in O(1) queries instead of O(n) get_by_id round-trips.
    Missing IDs must simply be absent from the result, not raise."""

    from uuid import UUID

    from ota_backend.repositories.memory import InMemoryDeviceRepository

    repository = InMemoryDeviceRepository()
    seeded = repository.list_devices(q=None, brand=None, enabled_only=False, limit=10, offset=0)
    known = [device.id for device in seeded.items[:2]]
    unknown = UUID("99999999-9999-4999-8999-999999999999")

    found = repository.get_by_ids(known + [unknown])

    assert set(found.keys()) == set(known)
    assert unknown not in found


def test_memory_device_repository_bulk_get_by_ids_handles_empty_request():
    from ota_backend.repositories.memory import InMemoryDeviceRepository

    repository = InMemoryDeviceRepository()

    assert repository.get_by_ids([]) == {}
