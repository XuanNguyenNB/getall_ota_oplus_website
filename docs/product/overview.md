# Product Overview

The product discovers OTA metadata for OPPO, Realme and OnePlus devices through
a browser interface, scheduled scans and Telegram delivery. Public use is
allowed only through controlled active operations.

## Implemented Locally

- FastAPI UI/API for health, devices, manual OTA query, releases and scan
  status.
- In-memory/fake default runtime and opt-in Supabase/Oxygen/direct
  `realme-ota` live adapters.
- Stable scanner, notification enqueue, catalog importer and migration/RPC
  artifacts.
- Turnstile validation, standard-only public OTA policy, hashed quota/cooldown
  persistence, fresh-result caching and Supabase Auth admin checks.
- Admin scan enqueue plus worker processing by `--scan-run-id`.
- Telegram queue delivery consumer, `/latest` and admin-only `/status`.
- Safety-validated resolver API/UI code guarded by explicit live-proof flags.
- Docker Compose, Cloudflare Tunnel ingress shape, worker timer and CI.

## Evidence Status

Offline automated proof exists for implemented code. Private smoke has proven
remote catalog import, expanded manifest inference, live OPlus release
persistence and bounded worker completion after operator-applied migrations.
Actual Telegram delivery, resolver component-link behavior and Cloudflare
public launch remain unproven.

## Surfaces And Access

- Anonymous public: health, device catalog and persisted releases.
- Anonymous protected: standard manual OTA lookup after Turnstile and quota;
  resolver only after its proof gate.
- Supabase Auth admin: scan status and scan enqueue.
- Configured Telegram chat: delivered release notifications and `/latest`;
  configured Telegram administrators also receive `/status`.

## Boundaries

- Public OTA requests do not accept beta, IMEI or GUID inputs.
- Resolver never proxies OTA file contents or resolves automatically for every
  notification.
- Telegram `/resolve` is deferred until the web resolver has live proof.
- `realme-ota` distribution remains subject to applicable GPLv3 obligations.
