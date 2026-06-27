"""Capture before/after screenshots for the redesign verification.

Spawns the FastAPI app on a free port using the same offline backend
as the regular e2e tests, then drives a headless Chromium across three
viewports for both / and /admin. Saves PNGs into .codex/artifacts/
with the naming convention requested by the redesign plan.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import closing
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from ota_backend.app import create_app
from ota_backend.config import Settings, get_settings
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.repositories.memory import (
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
)

import os

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("REPOSITORY_BACKEND", "memory")
os.environ.setdefault("OTA_PROVIDER", "fake")
os.environ.setdefault("ALLOW_LIVE_OTA", "false")
os.environ.setdefault("PUBLIC_SITE_ENABLED", "false")
os.environ.setdefault("ENABLE_RESOLVER", "false")
os.environ.setdefault("RESOLVER_LIVE_PROOF_CONFIRMED", "false")
get_settings.cache_clear()


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


VIEWPORTS = {
    360: {"width": 360, "height": 800},
    768: {"width": 768, "height": 1024},
    1280: {"width": 1280, "height": 900},
}

PAGES = {"public": "/", "admin": "/admin"}

OUTPUT_DIR = Path(".codex/artifacts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    settings = Settings()
    app = create_app(
        settings=settings,
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

    deadline = time.time() + 10.0
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("uvicorn server failed to start")

    base = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for vp_label, vp in VIEWPORTS.items():
                for page_name, path in PAGES.items():
                    context = browser.new_context(viewport=vp)
                    page = context.new_page()
                    page.goto(f"{base}{path}", wait_until="networkidle")
                    # Give the UI a moment to settle (devices fetched, etc.).
                    page.wait_for_timeout(800)
                    target = OUTPUT_DIR / f"ui-redesign-after-{vp_label}-{page_name}.png"
                    page.screenshot(path=str(target), full_page=True)
                    print(f"saved {target}")
                    context.close()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
