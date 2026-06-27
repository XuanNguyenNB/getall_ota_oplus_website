"""Brand filter smoke test for the public site.

Clicking the OPPO segment must send ``brand=oppo`` on the
``/api/devices`` request and re-render the device list with only the
matching devices. We mock ``/api/devices`` via Playwright route
interception so the test does not depend on the backend's data.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

pytest.importorskip("playwright", reason="playwright not installed; install with .[dev]")
from playwright.sync_api import Page, Route, expect  # noqa: E402  (import after skip)

ALL_DEVICES = {
    "devices": [
        {
            "product_model": "CPH2659",
            "name": "Find X8 (OPPO)",
            "brand": "oppo",
            "manifest_code": "3C",
            "active_track": "H",
        },
        {
            "product_model": "RMX3800",
            "name": "GT 7 Pro (Realme)",
            "brand": "realme",
            "manifest_code": "3C",
            "active_track": "H",
        },
        {
            "product_model": "PKB110",
            "name": "OnePlus 13 (OnePlus)",
            "brand": "oneplus",
            "manifest_code": "3C",
            "active_track": "H",
        },
    ],
    "total": 3,
}

OPPO_ONLY = {
    "devices": [ALL_DEVICES["devices"][0]],
    "total": 1,
}


@pytest.fixture
def captured_device_requests() -> Iterator[list[dict[str, str]]]:
    """Per-test list to collect query params seen on /api/devices."""
    yield []


def test_brand_filter_narrows_device_list(
    page: Page,
    live_server_url: str,
    captured_device_requests: list[dict[str, str]],
) -> None:
    def handle_devices(route: Route) -> None:
        url = route.request.url
        # Capture the query so the assertion below can prove the brand
        # parameter actually made it into the request.
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        captured_device_requests.append(params)
        body = OPPO_ONLY if params.get("brand") == "oppo" else ALL_DEVICES
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/devices*", handle_devices)
    page.goto(live_server_url)

    # Wait for the initial unfiltered list to render (3 cards).
    expect(page.locator(".device-option")).to_have_count(3)

    # Click the OPPO segment. The app fires ``loadDevices()`` on click,
    # which sends a new request with ``brand=oppo``.
    page.get_by_role("button", name="OPPO", exact=True).click()

    expect(page.locator(".device-option")).to_have_count(1)
    expect(page.locator(".device-option strong")).to_have_text("CPH2659")

    # At least one request used brand=oppo. The initial call may or may
    # not be recorded depending on timing, so we check for the filtered
    # one explicitly.
    assert any(req.get("brand") == "oppo" for req in captured_device_requests)
