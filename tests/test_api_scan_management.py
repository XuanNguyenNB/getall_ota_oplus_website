from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.repositories.memory import (
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
)


class AllowAdmin:
    def require_admin(self, authorization: str | None) -> UUID:
        if authorization != "Bearer valid-admin":
            raise AssertionError("test must send the configured admin token")
        return UUID("99999999-9999-4999-8999-999999999999")


ADMIN = {"Authorization": "Bearer valid-admin"}


def _client(admin_authorizer=None) -> TestClient:
    return TestClient(
        create_app(
            settings=Settings(),
            device_repository=InMemoryDeviceRepository(),
            release_repository=InMemoryReleaseRepository(),
            ota_provider=FakeOtaProvider(),
            admin_authorizer=admin_authorizer,
        )
    )


def test_scan_groups_requires_admin():
    client = _client()  # default DenyAdminAuthorizer

    response = client.get("/api/admin/scan/groups", params={"enabled_only": True})

    assert response.status_code == 401


def test_scan_groups_search_returns_grouped_variants():
    client = _client(AllowAdmin())

    response = client.get("/api/admin/scan/groups", params={"q": "RMX3301"}, headers=ADMIN)
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert any(
        variant["product_model"] == "RMX3301"
        for group in body["groups"]
        for variant in group["variants"]
    )
    assert "enabled_total" in body


def test_scan_groups_requires_query_or_enabled_only():
    client = _client(AllowAdmin())

    response = client.get("/api/admin/scan/groups", headers=ADMIN)

    assert response.status_code == 400


def test_toggle_models_off_then_on_updates_state():
    client = _client(AllowAdmin())

    off = client.post(
        "/api/admin/scan/models",
        json={"product_models": ["RMX3301"], "enabled": False},
        headers=ADMIN,
    )
    assert off.status_code == 200
    assert off.json()["updated"] == 1

    enabled_after_off = off.json()["enabled_total"]

    on = client.post(
        "/api/admin/scan/models",
        json={"product_models": ["RMX3301"], "enabled": True},
        headers=ADMIN,
    )
    assert on.status_code == 200
    assert on.json()["enabled_total"] == enabled_after_off + 1


def test_toggle_models_reports_missing_and_without_manifest():
    client = _client(AllowAdmin())

    response = client.post(
        "/api/admin/scan/models",
        json={"product_models": ["NOPE123"], "enabled": True},
        headers=ADMIN,
    )
    body = response.json()

    assert response.status_code == 200
    assert "NOPE123" in body["missing"]
    assert body["updated"] == 0


def test_disable_all_requires_confirm_and_zeroes_enabled():
    client = _client(AllowAdmin())

    rejected = client.post("/api/admin/scan/disable-all", json={"confirm": False}, headers=ADMIN)
    assert rejected.status_code == 400

    confirmed = client.post("/api/admin/scan/disable-all", json={"confirm": True}, headers=ADMIN)
    assert confirmed.status_code == 200
    assert confirmed.json()["enabled_total"] == 0


def test_toggle_group_enables_all_variants():
    client = _client(AllowAdmin())

    groups = client.get("/api/admin/scan/groups", params={"q": "RMX3301"}, headers=ADMIN).json()[
        "groups"
    ]
    assert groups
    key = groups[0]["key"]

    response = client.post(
        "/api/admin/scan/group",
        json={"scan_group_key": key, "enabled": False},
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
