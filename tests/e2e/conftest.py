"""Pytest fixtures for the public-site Playwright smoke suite.

Spins up the FastAPI app on a free port using an in-memory backend so
Playwright can drive the real ``index.html`` against real JS without
hitting Supabase or a live OTA provider. Tests fully mock
``/api/devices`` and ``/api/edl-roms`` via ``page.route`` interception
so the backend's data layer never matters.

If ``playwright`` (or ``pytest-playwright``) is not installed, every
test in this folder is skipped via ``collect_ignore_glob`` below so the
regular ``pytest`` invocation keeps passing.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import closing

import pytest

# When playwright / pytest-playwright are missing, refuse to collect
# the test modules in this folder. We use ``collect_ignore_glob``
# (instead of ``pytest.importorskip`` at module level) because the
# latter raises during pytest's parse phase and surfaces as a hard
# error rather than a skip.
try:  # pragma: no cover - import guard
    import playwright  # noqa: F401
    import pytest_playwright  # noqa: F401

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover - import guard
    _PLAYWRIGHT_AVAILABLE = False

if not _PLAYWRIGHT_AVAILABLE:
    collect_ignore_glob = ["test_*.py"]

import uvicorn  # noqa: E402

from ota_backend.app import create_app  # noqa: E402
from ota_backend.config import Settings, get_settings  # noqa: E402
from ota_backend.providers.fake import FakeOtaProvider  # noqa: E402
from ota_backend.repositories.memory import (  # noqa: E402
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
)


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Mirror the regular suite's offline environment for create_app()."""
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


@pytest.fixture(scope="session")
def live_server_url() -> Iterator[str]:
    """Run the FastAPI app on a free localhost port for the test session."""
    app = create_app(
        settings=Settings(),
        device_repository=InMemoryDeviceRepository(),
        release_repository=InMemoryReleaseRepository(),
        ota_provider=FakeOtaProvider(),
    )
    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for uvicorn to flip ``started`` once the socket is bound.
    deadline = time.time() + 10.0
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:  # pragma: no cover - defensive
        server.should_exit = True
        raise RuntimeError("uvicorn server did not start within 10s")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
