# Validation

## Proof Strategy

Phase 2 proof stays local and offline. The browser UI is served by the existing
FastAPI app and exercises only the fake-provider Phase 1 endpoints.

## Test Plan

| Layer | Cases |
| --- | --- |
| Unit | Not required; this story adds no pure domain rules. |
| Integration | `/` and `/static/*` serving, existing `/api/devices`, `/api/ota`, `/api/releases`, and `/api/health` behavior. |
| E2E | Browser smoke for device loading, successful OTA query, OTA error state, releases refresh, and copy action. |
| Platform | Local Uvicorn startup plus `GET /api/health` and served UI route. |
| Release | Full `python -m pytest`. |

## Progress Log

- 2026-05-26: Read required root, product, Harness, API, source, and UI preview
  references.
- 2026-05-26: Harness intake recorded as a normal spec slice and
  `PHASE2-WEB-UI` story status set to `in_progress`.
- 2026-05-26: Implemented FastAPI static UI serving and API-backed vanilla JS
  UI for device search/select, manual OTA query, latest releases, copy URL,
  loading, empty, and error states.
- 2026-05-26: Focused tests passed:
  `python -m pytest tests\test_web_ui.py tests\test_api_devices.py tests\test_api_ota.py tests\test_api_releases.py tests\test_api_health.py`
  returned `10 passed`.
- 2026-05-26: Full release proof passed: `python -m pytest` returned
  `15 passed`.
- 2026-05-26: Local Uvicorn proof on `127.0.0.1:8765` returned the documented
  `/api/health` envelope and served `/` as `200 text/html`.
- 2026-05-26: Playwright browser smoke passed for device loading, OTA query
  success, OTA 404 error display, releases refresh after persisted query, and
  copy download URL. Network evidence included `GET /api/health 200`,
  `GET /api/devices 200`, `GET /api/releases 200`, `POST /api/ota 200`, refresh
  `GET /api/releases 200`, and expected `POST /api/ota 404`.
- 2026-05-26: Harness story record `PHASE2-WEB-UI` updated to `implemented`
  with integration, E2E, and platform proof.
- 2026-05-26: Added `python scripts/validate_phase2_ui.py` as the canonical
  single-command local validation loop. It starts FastAPI, waits for readiness,
  runs realbrowser smoke interactions, captures screenshots, console/network/HAR
  evidence, writes proof artifacts, updates Harness story evidence, and stops
  FastAPI on success or failure.

## Acceptance Evidence

- `python -m pytest`: `15 passed`.
- `Invoke-RestMethod http://127.0.0.1:8765/api/health`:
  `{"ok":true,"service":"getall_ota_oplus_website","version":"0.1.0"}`.
- `Invoke-WebRequest http://127.0.0.1:8765/`: `200 text/html; charset=utf-8`
  and contained `OPlus OTA Monitor`.
- Playwright browser smoke: `1 passed`; verified device loading, OTA success,
  OTA error display, release refresh, and copy action. The only console error
  was Chromium's expected failed-resource message for the deliberate
  `/api/ota` 404 error-state request.
- `python scripts/validate_phase2_ui.py`: passed; latest proof artifacts are
  under `validation-artifacts/phase2-web-ui/<run-id>/` with `initial.png`,
  `success.png`, `initial-network.json`, `network-list.json`, `network.har`,
  `console-list.json`, server logs, DOM text proof, and `summary.json`.

## Known Gaps

- Resolver UI and resolver API behavior are intentionally deferred until the
  resolver phase.
- The UI uses the in-memory fake-provider runtime until live provider and
  Supabase repository stories are implemented.

<!-- PHASE2-LOCAL-VALIDATION:BEGIN -->
## Automated Local Validation

Single command:

```powershell
python scripts/validate_phase2_ui.py
```

Latest result:

- Run: `20260526T142727Z`
- Status: `passed`
- Artifacts: `validation-artifacts/phase2-web-ui/20260526T142727Z`
- Browser proof: `initial.png`, `success.png`, `after-success.txt`, `after-copy.txt`, `after-error.txt`, `initial-network.json`, `network-list.json`, `network.har`, `console-list.json`
- Server proof: `uvicorn.out.log`, `uvicorn.err.log`
- Harness proof: story `PHASE2-WEB-UI` is updated by the validation command after a passing run.

<!-- PHASE2-LOCAL-VALIDATION:END -->
