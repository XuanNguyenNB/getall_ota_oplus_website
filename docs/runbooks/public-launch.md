# Public Launch Runbook

Do not run this checklist until private live activation has completed.

## Preconditions

1. Rotate all previously exposed Supabase elevated keys.
2. Apply all migration files through
   `202605270003_release_archive_metadata.sql`.
3. Create a Supabase Auth operator and insert its UUID into `admin_users`.
4. Configure server-only `.env` values for production runtime, Turnstile and
   Tunnel. Use `ENVIRONMENT=production`, Supabase live persistence and the
   realme live provider.
5. Keep `ENABLE_RESOLVER=false` until resolver proof below passes.
6. Leave Telegram settings empty unless the optional bot profile is being
   activated.

## Gateway Smoke

1. Start `web` behind Cloudflare Tunnel with no host-published origin port.
2. Verify anonymous `GET /api/health`, `/api/devices` and `/api/releases`.
3. Verify public `POST /api/ota` rejects no-token and sensitive-input requests.
4. Complete a Turnstile-protected standard OTA query and confirm `X-OTA-Source`.
5. Repeat the query within 30 minutes and confirm a cached result.
6. Verify `/api/scan/status` denies anonymous access and allows an enabled
   Supabase Auth admin JWT.
7. Verify the visible release archive does not expose the internal `source`
   field, while API/debug tooling can still use `source` for provenance.
8. Confirm the origin web port is not reachable directly from the Internet.

## Worker Smoke

1. Run `docker compose --profile jobs run --rm worker python -m ota_backend.worker --once --max-tasks 1`.
2. Confirm `scan_runs` and `scan_tasks` rows are written.
3. Install and enable `deploy/systemd/ota-worker.timer` only after the bounded
   run completes.

## Telegram Smoke

1. Seed enabled target topics in `telegram_targets`.
2. Generate one controlled queued notification.
3. Run `docker compose --profile bot run --rm bot python -m ota_backend.telegram_bot --once-delivery`.
4. Confirm the correct topic receives one message and the row becomes `sent`.
5. Start continuous polling with `docker compose --profile bot up -d bot`.

## Resolver Proof Gate

1. Capture one real component link from a bounded private OTA query.
2. With resolver disabled publicly, verify the transformed/redirect flow using
   only that link and save a sanitized fixture/evidence record.
3. Confirm every host and DNS result passes the configured safety policy.
4. Only after proof, set `ENABLE_RESOLVER=true` and
   `RESOLVER_LIVE_PROOF_CONFIRMED=true`, then repeat through the protected web
   endpoint.

## Release Evidence

Record dates and results in Harness. Local unit tests, mocked HTTP behavior and
container configuration alone do not establish that public launch is safe.
