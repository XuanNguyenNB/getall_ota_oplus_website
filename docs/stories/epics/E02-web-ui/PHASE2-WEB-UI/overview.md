# PHASE2-WEB-UI FastAPI-Served Private Browser UI

## Status

implemented

## Lane

normal

## Product Contract

FastAPI serves a private browser UI for the Phase 2 manual operator workflow.
The UI is backed only by existing offline Phase 1 APIs:

- `GET /api/health`
- `GET /api/devices`
- `POST /api/ota`
- `GET /api/releases`

The UI must not depend on resolver, worker, Telegram, live OPlus traffic,
Supabase repository implementation, Docker, CI, auth, deployment, or
client-side secrets.

## Relevant Product Docs

- `docs/product/overview.md`
- `docs/product/api-conventions.md`
- `docs/product/test-strategy.md`
- `docs/reference/IMPLEMENTATION_PLAN.md`
- `docs/reference/API_SPEC.md`

## Acceptance Criteria

- FastAPI serves the browser UI at `/` and package-owned static assets at
  `/static/*`.
- The UI searches and selects devices from `/api/devices`.
- The UI supports manual product model entry, manifest override, OTA track
  selection, and comma-separated `rui_candidates`.
- The UI submits manual OTA queries to `/api/ota` using `product_model`,
  `manifest_code`, `ota_track`, and `rui_candidates`.
- Successful OTA results display release metadata and copyable download URL.
- API validation, not-found, and upstream-style errors display as clear
  user-facing states.
- Latest releases are listed from `/api/releases` and refresh after successful
  persisted queries.
- Phase 1 API behavior and tests remain preserved.

## Design Notes

- Commands: `python -m pytest`; `python -m uvicorn ota_backend.main:app`.
- Queries: static UI calls only the existing Phase 1 HTTP endpoints.
- API: no API contract changes.
- Tables: no schema changes.
- Domain rules: no resolver, worker, Telegram, live provider, auth, or Supabase
  repository changes.
- UI surfaces: manual query form, device picker, latest releases table, result
  detail panel, copy actions, loading/empty/error states.

## Harness Delta

- Harness intake recorded the request as a normal spec slice.
- Harness story record `PHASE2-WEB-UI` was added and marked `in_progress`.
- `docs/TEST_MATRIX.md` gained a Phase 2 Web UI proof row.
