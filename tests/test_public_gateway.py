from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.repositories.memory import (
    InMemoryDeviceRepository,
    InMemoryPublicActionRepository,
    InMemoryReleaseRepository,
)


class PassingChallenge:
    def verify(self, *, token: str, remote_ip: str | None, action: str) -> bool:
        return token == "valid-token" and action in {"ota", "resolve"}


class AllowAdmin:
    def require_admin(self, authorization: str | None) -> UUID:
        if authorization != "Bearer valid-admin":
            raise AssertionError("test must send the configured admin token")
        return UUID("99999999-9999-4999-8999-999999999999")


def _settings(**overrides) -> Settings:
    values = {
        "public_site_enabled": True,
        "TURNSTILE_SITE_KEY": "site",
        "TURNSTILE_SECRET_KEY": "secret",
        "TURNSTILE_EXPECTED_HOSTNAME": "ota.example.test",
        "PUBLIC_RATE_LIMIT_SALT": "test-salt",
    }
    values.update(overrides)
    return Settings(**values)


def _payload() -> dict[str, object]:
    return {
        "product_model": "RMX3301",
        "manifest_code": "1B",
        "ota_track": "H",
        "rui_candidates": [8, 7],
        "language": "en-EN",
        "beta": False,
        "imei0": None,
        "imei1": None,
        "guid": None,
        "persist_result": True,
    }


def _client(*, settings: Settings | None = None, admin_authorizer=None) -> TestClient:
    return TestClient(
        create_app(
            settings=settings or _settings(),
            device_repository=InMemoryDeviceRepository(),
            release_repository=InMemoryReleaseRepository(),
            public_action_repository=InMemoryPublicActionRepository(),
            ota_provider=FakeOtaProvider(),
            challenge_verifier=PassingChallenge(),
            admin_authorizer=admin_authorizer,
        )
    )


def test_public_ota_requires_turnstile_and_rejects_sensitive_query_inputs():
    client = _client()

    missing = client.post("/api/ota", json=_payload())
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "CHALLENGE_FAILED"

    payload = _payload()
    payload["imei0"] = "sensitive"
    rejected = client.post("/api/ota", json=payload, headers={"X-Turnstile-Token": "valid-token"})
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"

    guid_payload = _payload()
    guid_payload["guid"] = "sensitive-guid"
    rejected_guid = client.post(
        "/api/ota", json=guid_payload, headers={"X-Turnstile-Token": "valid-token"}
    )
    assert rejected_guid.status_code == 400
    assert rejected_guid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_public_ota_returns_fresh_cached_result_without_second_provider_query():
    client = _client()
    headers = {"X-Turnstile-Token": "valid-token"}

    first = client.post("/api/ota", json=_payload(), headers=headers)
    second = client.post("/api/ota", json=_payload(), headers=headers)

    assert first.status_code == 200
    assert first.headers["X-OTA-Source"] == "live"
    assert second.status_code == 200
    assert second.headers["X-OTA-Source"] == "cache"
    assert second.json()["result"]["is_new"] is False


def test_public_ota_rate_limit_returns_retry_headers_when_cache_disabled():
    client = _client(
        settings=_settings(ota_public_cache_ttl_seconds=0, ota_public_rate_limit_per_hour=1)
    )
    headers = {"X-Turnstile-Token": "valid-token"}

    assert client.post("/api/ota", json=_payload(), headers=headers).status_code == 200
    limited = client.post("/api/ota", json=_payload(), headers=headers)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.headers["Retry-After"]
    assert limited.headers["X-RateLimit-Reset"]


def test_public_scan_status_is_admin_only_and_admin_can_enqueue_known_device():
    denied = _client()
    assert denied.get("/api/scan/status").status_code == 401

    client = _client(admin_authorizer=AllowAdmin())
    queued = client.post(
        "/api/admin/scan/enqueue",
        headers={"Authorization": "Bearer valid-admin"},
        json={"product_models": ["RMX3301"], "reason": "operator"},
    )

    assert queued.status_code == 202
    assert queued.json()["created_tasks"] == 1
