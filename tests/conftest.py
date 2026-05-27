from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings, get_settings
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.repositories.memory import InMemoryDeviceRepository, InMemoryReleaseRepository


@pytest.fixture(autouse=True)
def offline_test_runtime(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("OTA_PROVIDER", "fake")
    monkeypatch.setenv("ALLOW_LIVE_OTA", "false")
    monkeypatch.setenv("PUBLIC_SITE_ENABLED", "false")
    monkeypatch.setenv("ENABLE_RESOLVER", "false")
    monkeypatch.setenv("RESOLVER_LIVE_PROOF_CONFIRMED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    app = create_app(
        settings=Settings(),
        device_repository=InMemoryDeviceRepository(),
        release_repository=InMemoryReleaseRepository(),
        ota_provider=FakeOtaProvider(),
    )
    return TestClient(app)
