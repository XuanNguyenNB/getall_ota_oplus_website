# Validation

## Proof Strategy

Phase 1 proof must be local and offline. Tests use in-memory repositories and a
fake OTA provider. No production secrets, live Supabase project, or live OPlus
OTA traffic are required.

## Test Plan

| Layer | Cases |
| --- | --- |
| Unit | manifest accepted-code coverage, authoritative live-query map status, seed OTA version construction, logging sanitizer |
| Integration | `/api/health`, `/api/devices`, `/api/ota`, `/api/releases`, release deduplication through repositories |
| E2E | Not in Phase 1 |
| Platform | FastAPI app imports and starts locally without production secrets |
| Performance | Not in Phase 1 |
| Logs/Audit | Sanitizer redacts IMEI, GUID, authorization, token, service key, protected key, and raw body fields |

## Fixtures

- In-memory device catalog with OPPO, Realme, and OnePlus rows.
- Fake OTA success response for `RMX3301`.
- Fake no-update path for unsupported fixture queries.

## Commands

```text
python -m pytest
python -m uvicorn ota_backend.main:app
```

## Progress Log

- 2026-05-26: Intake classified as high-risk and recorded in Harness.
- 2026-05-26: Read required product, architecture, Harness, and upstream
  `realme-ota` references. Upstream does not contain authoritative values for
  all 12 accepted manifest codes.

## Acceptance Evidence

- `python -m pytest`: 13 passed.
- Uvicorn local startup smoke on `127.0.0.1:8001`: `GET /api/health`
  returned `{"ok":true,"service":"getall_ota_oplus_website","version":"0.1.0"}`.
- No validation command required Supabase credentials or live OPlus OTA traffic.
