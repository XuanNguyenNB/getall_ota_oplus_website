# End-to-end smoke tests (Playwright)

Headless smoke tests for the public site. They drive the real
``index.html`` against the real JavaScript bundle while mocking the
backend HTTP endpoints (``/api/devices``, ``/api/releases``,
``/api/edl-roms``) via Playwright's route interception, so they don't
depend on a live database or OTA provider.

The whole folder is skipped automatically when ``playwright`` is not
installed (each test module starts with ``pytest.importorskip``), so
the regular pytest suite keeps working with the base ``pip install -e
".[dev]"`` install.

## Run locally

```bash
# Install dev extras (includes pytest-playwright).
pip install -e ".[dev]"

# Download the headless Chromium runtime (~150 MB) the first time.
playwright install chromium

# Run just the smoke suite.
pytest tests/e2e

# Or, headed (for debugging):
pytest tests/e2e --headed
```

## What's covered

- **Brand filter** (``test_brand_filter.py``): clicking the OPPO
  segment sends ``brand=oppo`` on ``/api/devices`` and narrows the
  rendered list to OPPO devices.
- **Package switch** (``test_package_switch.py``): clicking the EDL
  ROM tab toggles the warning notice on and triggers a request to
  ``/api/edl-roms`` for the selected model.
- **URL scheme guard** (``test_url_scheme_guard.py``): a release with
  ``download_url: "javascript:alert(1)"`` never causes ``window.open``
  to be called, even if a button is clicked.

## How it's wired

``conftest.py`` boots ``ota_backend.app.create_app()`` on a free
localhost port inside a daemon thread (uvicorn), then yields the base
URL as ``live_server_url``. The same ``offline_test_runtime`` env
toggles used by the unit suite apply so the in-memory repositories /
fake OTA provider are active.
