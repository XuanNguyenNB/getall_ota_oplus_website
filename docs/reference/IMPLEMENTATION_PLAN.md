# Implementation Plan

## Delivered Locally

Phase 1-3 behavior and live adapters are implemented with offline proof:
FastAPI/UI, device and release persistence interfaces, scheduled scanner,
Supabase/Oxygen/`realme-ota` adapters, migrations and worker CLI.

The continuation initiative is also implemented at local/code-artifact level:

- public Turnstile, quota/cooldown/cache and admin authorization paths;
- Telegram delivery bot and queue RPC artifacts;
- resolver service and HTTP surface protected by an explicit live-proof gate;
- Docker/Cloudflare Tunnel/timer/CI deployment artifacts.

Private activation has proven catalog import and live release persistence.
Operator-applied scanner recovery and full manifest-map migrations have been
proven through expanded catalog reads plus completed bounded worker runs.
Public activation remains blocked until secrets are rotated and its live smoke
checks pass.

## Phase A: Private Live Activation

- Rotate exposed Supabase elevated keys.
- Confirm the operator-applied migrations through
  `202605270003_release_archive_metadata.sql` are present in the target project.
- Configure Supabase and `realme-ota` server runtime.
- Import Oxygen catalog and run one bounded manual query and worker scan.
- Import China domestic catalog rows with `python -m ota_backend.catalog
  import-domestic-cn` when CN model coverage is required.
- Import third-party historical per-device OTA archive rows with
  `python -m ota_backend.catalog import-lsctool-archive` after applying the
  release archive metadata migration.
- Verify database records before running any unattended or public traffic.

## Phase B: Public Controlled Gateway

- Deploy behind Cloudflare Tunnel only; do not publish the origin port.
- Run with `ENVIRONMENT=production`, Supabase persistence, live `realme-ota`
  provider and explicit `ALLOW_LIVE_OTA=true`.
- Configure Turnstile and public rate-limit salt.
- Bootstrap a Supabase Auth operator and an enabled `admin_users` row.
- Public reads remain anonymous; public OTA writes require Turnstile and
  standard inputs only.
- Public OTA live traffic uses a 30-minute result freshness/cooldown window and
  a baseline of five submissions per IP hash per hour.

## Phase C: Telegram Delivery

- Populate three enabled `telegram_targets` rows before starting the optional
  bot profile.
- Configure bot token, configured chat and Telegram admin IDs.
- Run a bounded `--once-delivery` test before continuous polling.
- Bot owns sending, retry state, `/latest` and admin-only `/status`; scanner
  continues to enqueue only.

## Phase D: Resolver Release Gate

- Obtain one real component link during private live validation.
- Confirm the documented component hostname transformation and safe resolution
  flow using a bounded request; retain a sanitized fixture.
- Only then set `ENABLE_RESOLVER=true` and
  `RESOLVER_LIVE_PROOF_CONFIRMED=true`.
- Expose web `POST /api/resolve` with Turnstile/quota. Add Telegram `/resolve`
  only after web integration and live proof succeed.

## Phase E: Production Release

- Build containers, start `web` and `cloudflared`; install the host timer for
  one-shot daily worker runs.
- Start `bot` only after a bounded delivery check succeeds.
- Run health, auth, challenge, quota, worker and origin non-bypass checks.
  Run notification and resolver checks only when those gated services are
  enabled.
- Enable public DNS only after all live evidence is recorded in Harness.

## Validation

Local evidence command set:

```powershell
python -m pytest
python -m compileall -q src tests
node --check src/ota_backend/static/app.js
python -m pip install --dry-run -e ".[dev]"
docker compose config --quiet
docker compose build web
```

On 2026-05-27 private smoke proved Oxygen catalog import and live OPlus release
persistence. It also exposed a missing scanner completion RPC and incomplete
manifest subset; after the operator applied
`202605270001_scanner_rpc_recovery.sql` and
`202605270002_full_manifest_map.sql`, bounded worker runs completed and Phase A
private activation evidence is recorded. The release archive migration
`202605270003_release_archive_metadata.sql` and LSCTool import provide
multi-release archive rows while keeping source provenance internal. Telegram
sends, Cloudflare deployment and resolver live proof remain
operator-controlled checks.
