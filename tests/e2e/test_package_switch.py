"""Package-switch smoke test.

Clicking the EDL tab must:

1. Reveal the EDL warning notice (``#edlWarning``).
2. Trigger a request to ``/api/edl-roms`` for the currently selected
   product model.

We mock both ``/api/devices`` and ``/api/edl-roms`` via Playwright route
interception so the test is independent of the backend's data layer.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator

import pytest

pytest.importorskip("playwright", reason="playwright not installed; install with .[dev]")
from playwright.sync_api import Page, Route, expect  # noqa: E402

SINGLE_DEVICE = {
    "devices": [
        {
            "product_model": "CPH2659",
            "name": "Find X8 (OPPO)",
            "brand": "oppo",
            "manifest_code": "3C",
            "active_track": "H",
        },
    ],
    "total": 1,
}

EMPTY_EDL = {"roms": [], "total": 0}
EMPTY_RELEASES = {"releases": [], "total": 0}


@pytest.fixture
def edl_request_seen() -> Iterator[threading.Event]:
    yield threading.Event()


def test_edl_tab_toggles_warning_and_fetches_edl_roms(
    page: Page,
    live_server_url: str,
    edl_request_seen: threading.Event,
) -> None:
    page.route(
        "**/api/devices*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(SINGLE_DEVICE),
        ),
    )
    page.route(
        "**/api/releases*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(EMPTY_RELEASES),
        ),
    )

    def handle_edl(route: Route) -> None:
        edl_request_seen.set()
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(EMPTY_EDL),
        )

    page.route("**/api/edl-roms*", handle_edl)
    page.goto(live_server_url)

    # The EDL warning starts hidden because the default package mode is
    # OTA. Playwright treats ``hidden`` attribute as not visible.
    warning = page.locator("#edlWarning")
    expect(warning).to_be_hidden()

    # Pick the only device so loadReleases() / loadEdlRoms() have a
    # product model to query.
    page.locator(".device-option").first.click()

    # Switch to EDL.
    page.get_by_role("button", name="EDL ROM", exact=True).click()

    expect(warning).to_be_visible()
    assert edl_request_seen.wait(timeout=5), "Expected /api/edl-roms to be called"
