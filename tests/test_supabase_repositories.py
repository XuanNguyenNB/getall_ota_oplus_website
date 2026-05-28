from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from ota_backend.domain.models import OtaProviderRelease
from ota_backend.repositories.supabase import (
    SupabaseDeviceRepository,
    SupabasePublicActionRepository,
    SupabaseReleaseRepository,
    SupabaseScanRepository,
    SupabaseTelegramRepository,
)


RELEASE_ROW = {
    "id": "11111111-1111-4111-8111-111111111111",
    "brand": "realme",
    "product_model": "RMX3301",
    "manifest_code": "1B",
    "ota_track": "H",
    "rui_version": 7,
    "real_ota_version": "RMX3301_11.H.21_4210_202602281641",
    "real_version_name": "release",
    "computed_ota_version": "computed",
    "version_type_id": "non_display",
    "about_update_url": None,
    "download_url": "https://example.com/update.zip",
    "discovered_by": "worker",
    "discovered_at": "2026-05-26T00:00:00Z",
    "last_seen_at": "2026-05-26T00:00:00Z",
    "source": "live_provider",
    "region_code": "IN",
    "release_type": "official",
    "published_at": None,
    "source_last_event_kind": None,
    "source_last_event_at": None,
}


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


class Client:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return Rpc(self.results[name])


class UpdateTable:
    def __init__(self, row):
        self.row = dict(row)
        self.payload = None
        self.filters = []

    def update(self, payload):
        self.payload = payload
        self.row = {**self.row, **payload}
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def execute(self):
        return SimpleNamespace(data=[self.row])


class RefreshClient(Client):
    def __init__(self, results, row):
        super().__init__(results)
        self.releases = UpdateTable(row)

    def table(self, name):
        assert name == "ota_releases"
        return self.releases


class DeviceTable:
    def __init__(self):
        self.update_payload = None
        self.existing = {
            "id": "55555555-5555-4555-8555-555555555555",
            "catalog_id": 1,
            "brand": "realme",
            "name": "Existing",
            "product_model": "RMX3301",
            "manifest_code": "1B",
            "scan_enabled": True,
            "active_track": "H",
            "bootstrap_done": True,
            "manual_override": False,
            "source": "oxygen_updater",
        }

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self.update_payload = payload
        self.existing = {**self.existing, **payload}
        return self

    def execute(self):
        return SimpleNamespace(data=[self.existing])


class DeviceClient:
    def __init__(self):
        self.devices = DeviceTable()

    def table(self, name):
        assert name == "devices"
        return self.devices


def test_release_repository_uses_atomic_upsert_rpc():
    client = Client({"upsert_ota_release": {"release": RELEASE_ROW, "is_new": True}})
    repository = SupabaseReleaseRepository(client)
    result = repository.upsert_release(
        OtaProviderRelease(
            brand="realme",
            product_model="RMX3301",
            manifest_code="1B",
            ota_track="H",
            rui_version=7,
            real_ota_version=RELEASE_ROW["real_ota_version"],
            real_version_name="release",
            computed_ota_version="computed",
            version_type_id="non_display",
            about_update_url=None,
            download_url=RELEASE_ROW["download_url"],
            region_code="IN",
        ),
        discovered_by="worker",
    )

    assert result.is_new is True
    assert client.calls[0][0] == "upsert_ota_release"
    assert client.calls[0][1]["p_source"] == "live_provider"
    assert client.calls[0][1]["p_region_code"] == "IN"
    assert client.calls[0][1]["p_release_type"] == "official"
    assert result.release.id == UUID(RELEASE_ROW["id"])


def test_release_repository_refreshes_existing_technical_display_metadata():
    stale = {
        **RELEASE_ROW,
        "brand": "oppo",
        "product_model": "PKJ110",
        "manifest_code": "97",
        "ota_track": "C",
        "rui_version": 8,
        "real_ota_version": "PKJ110_11.C.65_1650_202604091920",
        "real_version_name": "PKJ110_11.C.65_1650_202604091920",
        "computed_ota_version": "PKJ110_11.C.65_CN_202604091920",
        "about_update_url": "https://example.test/component-ota/26/05/07/update.html",
        "download_url": "https://example.test/update.zip",
        "region_code": None,
        "published_at": None,
    }
    client = RefreshClient(
        {"upsert_ota_release": {"release": stale, "is_new": False}},
        stale,
    )
    repository = SupabaseReleaseRepository(client)

    result = repository.upsert_release(
        OtaProviderRelease(
            brand="oppo",
            product_model="PKJ110",
            manifest_code="97",
            ota_track="C",
            rui_version=8,
            real_ota_version=stale["real_ota_version"],
            real_version_name="PKJ110_16.0.5.702(CN01)",
            computed_ota_version=stale["computed_ota_version"],
            version_type_id="non_display",
            about_update_url=stale["about_update_url"],
            download_url=stale["download_url"],
            region_code="CN",
            published_at=SimpleNamespace(isoformat=lambda: "2026-05-07T00:00:00+00:00"),
        ),
        discovered_by="manual",
    )

    assert result.is_new is False
    assert result.release.real_version_name == "PKJ110_16.0.5.702(CN01)"
    assert client.releases.payload["real_version_name"] == "PKJ110_16.0.5.702(CN01)"
    assert client.releases.payload["region_code"] == "CN"
    assert client.releases.filters == [("id", stale["id"])]


def test_catalog_refresh_does_not_overwrite_existing_scan_progression():
    client = DeviceClient()
    repository = SupabaseDeviceRepository(client)

    updated = repository.upsert_catalog_device(
        catalog_id=2,
        brand="realme",
        name="Renamed",
        product_model="RMX3301",
        manifest_code="1B",
        scan_enabled=True,
    )

    assert updated.active_track == "H"
    assert updated.bootstrap_done is True
    assert "active_track" not in client.devices.update_payload
    assert "bootstrap_done" not in client.devices.update_payload


def test_scan_repository_uses_atomic_claim_rpc():
    task = {
        "id": "22222222-2222-4222-8222-222222222222",
        "scan_run_id": "33333333-3333-4333-8333-333333333333",
        "device_id": "44444444-4444-4444-8444-444444444444",
        "status": "running",
        "attempt_count": 1,
        "tracks_checked": [],
        "rui_candidates_checked": [],
    }
    client = Client({"claim_scan_task": [task]})
    repository = SupabaseScanRepository(client)

    result = repository.claim_next_queued_task(UUID(task["scan_run_id"]))

    assert result is not None
    assert result.status == "running"
    assert client.calls[0][0] == "claim_scan_task"


def test_scan_repository_completes_new_release_task_through_atomic_rpc():
    task = {
        "id": "22222222-2222-4222-8222-222222222222",
        "scan_run_id": "33333333-3333-4333-8333-333333333333",
        "device_id": "44444444-4444-4444-8444-444444444444",
        "status": "completed",
        "attempt_count": 1,
        "tracks_checked": ["H"],
        "rui_candidates_checked": [8, 7],
        "found_release_id": RELEASE_ROW["id"],
    }
    client = Client({"complete_scan_task": [task]})
    repository = SupabaseScanRepository(client)

    result = repository.complete_task(
        UUID(task["id"]),
        tracks_checked=["H"],
        rui_candidates_checked=[8, 7],
        found_release_id=UUID(RELEASE_ROW["id"]),
        new_release=True,
    )

    assert result.status == "completed"
    assert client.calls[0][0] == "complete_scan_task"


def test_public_action_repository_uses_atomic_claim_rpc():
    client = Client({"claim_public_action": {"allowed": False, "retry_after_seconds": 27}})
    repository = SupabasePublicActionRepository(client)

    result = repository.claim(
        action="ota",
        actor_hash="actor",
        query_key="query",
        limit=5,
        window_seconds=3600,
        cooldown_seconds=1800,
    )

    assert result.allowed is False
    assert result.retry_after_seconds == 27
    assert client.calls[0][0] == "claim_public_action"


def test_telegram_repository_claims_joined_delivery_through_rpc():
    notification = {
        "id": "99999999-9999-4999-8999-999999999999",
        "release_id": RELEASE_ROW["id"],
        "telegram_target_id": "88888888-8888-4888-8888-888888888888",
        "status": "sending",
        "created_at": "2026-05-26T00:00:00Z",
        "attempt_count": 1,
    }
    target = {
        "id": notification["telegram_target_id"],
        "brand": "realme",
        "chat_id": -1001,
        "message_thread_id": 222,
        "enabled": True,
        "created_at": "2026-05-26T00:00:00Z",
        "updated_at": "2026-05-26T00:00:00Z",
    }
    client = Client(
        {
            "claim_telegram_notification": {
                "notification": notification,
                "release": RELEASE_ROW,
                "target": target,
            }
        }
    )
    repository = SupabaseTelegramRepository(client)

    delivery = repository.claim_next_notification(max_attempts=3)

    assert delivery is not None
    assert delivery.target.message_thread_id == 222
    assert delivery.notification.status == "sending"
    assert client.calls[0][0] == "claim_telegram_notification"
