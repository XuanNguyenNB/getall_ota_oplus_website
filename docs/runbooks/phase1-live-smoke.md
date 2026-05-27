# Phase 1-3 Live Smoke Checks

These checks are for a maintainer to run after applying the live runtime SQL to
a Supabase project and explicitly enabling OPlus traffic. They are not part of
offline automated proof.

## Prerequisites

- A Supabase project created for smoke testing.
- All migrations applied from `supabase/migrations/`, through
  `202605270003_release_archive_metadata.sql`.
- `SUPABASE_URL` and `SUPABASE_SECRET_KEY` configured only on the server
  (`SUPABASE_SERVICE_ROLE_KEY` is a legacy fallback).
- A private network boundary around the API service.
- GPLv3 attribution and corresponding-source handling retained for the pinned
  `realme-ota` dependency.
- Rotate any Supabase server key previously exposed outside secure environment
  configuration before long-lived operation.

## Offline Startup

```powershell
python -m uvicorn ota_backend.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected response:

```json
{
  "ok": true,
  "service": "getall_ota_oplus_website",
  "version": "0.1.0",
  "features": {
    "public_site": false,
    "resolver": false,
    "turnstile_site_key": null
  }
}
```

## Live Configuration

Set these values in a local/server `.env` that is not committed:

```text
REPOSITORY_BACKEND=supabase
OTA_PROVIDER=realme
ALLOW_LIVE_OTA=true
SUPABASE_URL=https://project-ref.supabase.co
SUPABASE_SECRET_KEY=server-side-only
RUI_CANDIDATES=8,7
SCAN_REQUEST_INTERVAL_SECONDS=1
```

## Supabase And Catalog Smoke

1. Apply all migration files in filename order.
2. Run `python -m ota_backend.catalog import-oxygen`.
3. Run `python -m ota_backend.catalog import-domestic-cn` when China domestic
   coverage is required.
4. Run `python -m ota_backend.catalog import-lsctool-archive` when historical
   per-device archive rows are required.
5. Confirm rows exist in `devices` and one completed row exists in
   `device_catalog_imports`.
6. Start FastAPI and confirm `GET /api/devices` returns catalog rows through
   the configured Supabase repository.

## OPlus Smoke

1. Install project dependencies, which install the pinned `realme-ota`
   dependency.
2. Use a non-sensitive request without IMEI or GUID.
3. Query one known model through `POST /api/ota` and confirm a row exists in
   `ota_releases`.
4. Run `python -m ota_backend.worker --once --max-tasks 1` and confirm a row
   exists in `scan_runs` and `scan_tasks`. If a matching enabled
   `telegram_targets` row was seeded and a new release is found, confirm a
   queued `telegram_notifications` row.
5. Confirm logs do not contain IMEI, GUID, tokens, server keys, protected
   keys, encrypted request bodies, or raw protected payloads.
6. Disable live OTA traffic immediately after the smoke check unless the
   controlled deployment boundary is ready.
