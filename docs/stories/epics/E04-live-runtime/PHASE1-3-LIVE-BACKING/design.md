# Design

## Domain Model

Existing device, release, scan, and notification records are retained. A
`DeviceCatalogImport` record stores each Oxygen Updater import outcome. The
26-code live manifest map uses the complete approved Universal OTA server selection.

## Application Flow

- `python -m ota_backend.catalog import-oxygen` fetches enabled catalog rows,
  normalizes model entries, preserves manual overrides, and persists import
  history.
- `POST /api/ota` uses Supabase release persistence and the live provider when
  explicitly enabled.
- `python -m ota_backend.worker --once [--cycle-day N] [--max-tasks N]`
  scans a bounded shard, throttles upstream queries, persists worker releases,
  and queues deduplicated notification records.

## Interface Contract

New server environment settings are `REPOSITORY_BACKEND`, `OTA_PROVIDER`,
`ALLOW_LIVE_OTA`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` with legacy
`SUPABASE_SERVICE_ROLE_KEY`, `RUI_CANDIDATES`,
`REALME_OTA_TIMEOUT_SECONDS`, and `SCAN_REQUEST_INTERVAL_SECONDS`.
Existing JSON API shapes do not change.

## Data Model

The live migration adds `device_catalog_imports`, enables RLS and server-only
grants on operational tables, and defines RPCs for atomic task claim, release
completion/count updates, release upsert/last-seen handling, and notification
enqueue deduplication.

## UI / Platform Impact

The existing UI is unchanged; it reads live data when the backend selects
Supabase. SQL is delivered as a manual migration artifact and is not applied
automatically.

## Observability

Errors remain sanitized. IMEI, GUID, encrypted payloads, protected keys, and
Supabase credentials are never logging fields.

## Alternatives Considered

1. Vendor `realme-ota`. Rejected in favor of a pinned upstream dependency with
   explicit GPLv3 documentation.
2. Use geographic region inference for every code. Rejected because the
   maintainer approved the existing Universal OTA endpoint map.
