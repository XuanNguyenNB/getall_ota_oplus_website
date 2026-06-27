"""URL scheme guard smoke test.

If the API ever returns a release whose ``download_url`` starts with
``javascript:`` (or another browser-blocked scheme), clicking the Open
button must NOT invoke ``window.open`` and must NOT navigate the page.

We:

1. Mock ``/api/devices`` with a single device.
2. Mock ``/api/releases`` so the table renders exactly one release with
   a poisoned ``download_url``.
3. Override ``window.open`` in the page context to record calls.
4. Click the "Open" button if it renders. (The app SHOULD also hide
   the button via ``isBrowserBlockedDownloadUrl``; assert either the
   button is absent or, if present, that clicking it produced no
   ``window.open`` call.)
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright", reason="playwright not installed; install with .[dev]")
from playwright.sync_api import Page, expect  # noqa: E402

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

POISONED_RELEASES = {
    "releases": [
        {
            "id": "rel-1",
            "product_model": "CPH2659",
            "brand": "oppo",
            "manifest_code": "3C",
            "region_code": "VN",
            "ota_track": "H",
            "release_type": "official",
            "real_version_name": "ColorOS 15 (poisoned)",
            "real_ota_version": "CPH2659_15.0.1.300",
            "download_url": "javascript:alert(1)",
            "source_published_at": None,
            "published_at": None,
        },
    ],
    "total": 1,
}


def test_javascript_download_url_does_not_open_window(page: Page, live_server_url: str) -> None:
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
            body=json.dumps(POISONED_RELEASES),
        ),
    )
    page.route(
        "**/api/edl-roms*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"roms": [], "total": 0}),
        ),
    )

    # Install the window.open spy via init_script so it runs BEFORE any
    # page JS (incl. Chromium's internal popup tracker which can otherwise
    # invoke window.open(null) once for a poisoned javascript: URL the
    # renderer pre-parses). add_init_script also survives navigations and
    # is the documented Playwright pattern for instrumenting globals.
    page.add_init_script(
        """
        window.__openCalls = [];
        window.open = function (...args) {
          window.__openCalls.push(args);
          return null;
        };
        """
    )

    page.goto(live_server_url)

    # Pick the only device — that loads /api/releases (mocked).
    page.locator(".device-option").first.click()

    # Wait until at least one row is rendered with the poisoned
    # version name so we know renderReleases() has executed.
    expect(page.locator(".release-table tbody tr")).to_have_count(1)
    expect(page.locator(".release-table tbody")).to_contain_text("ColorOS 15 (poisoned)")

    # The Open button SHOULD be omitted by renderReleaseActions()
    # because ``isBrowserBlockedDownloadUrl("javascript:alert(1)")``
    # returns true (via ``isSafeNetworkUrl``). Belt-and-suspenders: if
    # for some reason it WAS rendered, clicking it must not call
    # window.open.
    open_button = page.locator("[data-open-release='rel-1']")
    if open_button.count() > 0:
        open_button.first.click()

    # Even if a click somehow leaked through, window.open must not have
    # been called for the poisoned URL.
    calls = page.evaluate("window.__openCalls")
    assert calls == [], f"window.open was called with poisoned URL: {calls!r}"
