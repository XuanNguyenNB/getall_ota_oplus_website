# Release Gates Dashboard

## How this file is used

This file is the single dashboard for release readiness across the
private-validation and public-launch surfaces. Every item here is a release
gate: an operator-owned check that must complete before the dependent action
is performed. When a gate moves, update its status here and link the evidence
(Harness story ID, smoke artifact path, or commit/SHA) back to this file.

The detailed step-by-step procedures live in:

- `docs/runbooks/phase1-live-smoke.md` (private live activation)
- `docs/runbooks/public-launch.md` (Cloudflare/Turnstile/admin gateway smoke,
  worker smoke, Telegram smoke, resolver proof gate)
- `docs/reference/DEPLOYMENT.md` (deployment commands and release-gate
  preconditions)
- `docs/OPERATIONS/rollback.md` (what to do if a gate regresses post-launch)

This file does not replace those runbooks. It is a thin index so an operator
preparing a release can see "what's still red" at a glance and jump straight
to the right section.

Each entry below uses the form:

> **Gate** - one-line description. **Owner**: who is on point. **Detail**:
> link back to the authoritative runbook section.

## Pre-launch gates (must complete before public DNS)

These gates must all be green before Cloudflare DNS is pointed at the public
hostname.

- **Private live smoke** - All steps in
  `docs/runbooks/phase1-live-smoke.md` pass against a Supabase project with
  migrations applied through `202606270002_scan_run_counters_recompute.sql`.
  Bounded `POST /api/ota` writes one row to `ota_releases`; bounded worker
  run writes one row each to `scan_runs` and `scan_tasks`. Logs contain no
  IMEI/GUID/tokens. **Owner**: backend on-call. **Detail**:
  [phase1-live-smoke.md](./phase1-live-smoke.md#supabase-and-catalog-smoke).
- **Supabase elevated key rotation** - Any Supabase elevated key previously
  shared outside secret storage is rotated before public traffic.
  `SUPABASE_SECRET_KEY` (preferred) or legacy `SUPABASE_SERVICE_ROLE_KEY` is
  set only on the server. **Owner**: backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#preconditions),
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#required-secrets-and-configuration).
- **Migrations applied through phase-2** - Supabase migrations applied in
  filename order through `202606270002_scan_run_counters_recompute.sql`,
  including the partial scan-eligibility indexes and the idempotent
  `complete_scan_task` body. **Owner**: backend on-call. **Detail**:
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#database-activation),
  [DATABASE_SCHEMA.md](../reference/DATABASE_SCHEMA.md).
- **Supabase Auth admin seeded** - An operator account created in Supabase
  Auth, its UUID inserted into `admin_users` and the JWT verified against
  `/api/scan/status`. **Owner**: backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#preconditions),
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#database-activation).
- **Turnstile prod keys provisioned** - Production
  `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` issued for the production
  hostname; `TURNSTILE_EXPECTED_HOSTNAME` matches the published Tunnel
  hostname; `PUBLIC_RATE_LIMIT_SALT` set to a server-only random value.
  **Owner**: platform. **Detail**:
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#required-secrets-and-configuration),
  [SECURITY_NOTES.md](../reference/SECURITY_NOTES.md#rate-and-challenge-controls).
- **Cloudflare Tunnel configured** - `CLOUDFLARE_TUNNEL_TOKEN` set; the
  origin web port is not host-published in compose; cloudflared waits for the
  web health check before serving. **Owner**: platform. **Detail**:
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#services),
  [public-launch.md](./public-launch.md#gateway-smoke).
- **Public gateway smoke** - All steps in the public-launch gateway smoke
  section pass: anonymous reads work, public `POST /api/ota` rejects no-token
  and sensitive-input (`beta`, `imei0`, `imei1`, `guid`), Turnstile-protected
  query succeeds, `X-OTA-Source` flips to `cache` on repeat, scan status
  denies anonymous and accepts the admin JWT, origin port is not directly
  reachable. **Owner**: backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#gateway-smoke).
- **Worker smoke** - Scan-eligibility cleanup `--dry-run` then live;
  bounded `--once --max-tasks 1` writes a `scan_runs` + `scan_tasks` row;
  systemd timer installed only after the bounded run completes. **Owner**:
  backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#worker-smoke).
- **DNS rebind protection verified** - Resolver per-request DNS cache and
  pinned-IP transport in place (no fresh DNS resolution between safety check
  and HTTP fetch). Re-prove only if `services/resolver.py` is touched.
  **Owner**: backend on-call. **Detail**:
  [SECURITY_NOTES.md](../reference/SECURITY_NOTES.md#resolver-ssrf-boundary).
- **Public DNS not yet cut over** - Confirm the public hostname still
  resolves to the staging Tunnel (or to no destination at all) before the
  launch-day gate runs. **Owner**: platform. **Detail**:
  [public-launch.md](./public-launch.md#preconditions).

## Launch-day gates

These gates run on the day public DNS is cut over.

- **Public DNS cutover** - Repoint the public hostname at the production
  Cloudflare Tunnel; confirm the previous staging origin is no longer
  routable. **Owner**: platform. **Detail**:
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#release-gates).
- **End-to-end Turnstile flow** - One real browser request from outside the
  origin VPS completes Turnstile, gets a live OTA result, and a repeat
  request within 30 minutes returns `X-OTA-Source: cache`. **Owner**:
  backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#gateway-smoke).
- **Admin auth flow** - Operator signs into the admin UI with the seeded
  Supabase Auth account; `/api/scan/status` returns a recent run; an
  unauthenticated request to the same endpoint returns `AUTH_REQUIRED`.
  **Owner**: backend on-call. **Detail**:
  [API_SPEC.md](../reference/API_SPEC.md#admin-authentication),
  [public-launch.md](./public-launch.md#gateway-smoke).
- **Worker timer enabled** - `deploy/systemd/ota-worker.timer` enabled and
  next-trigger time matches the desired schedule; one full shard run
  completes without exceeding `SCAN_FAILURE_RATE_THRESHOLD`. **Owner**:
  backend on-call. **Detail**:
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#commands),
  [SCHEDULER.md](../reference/SCHEDULER.md#concurrency).
- **Telegram delivery smoke (if bot profile enabled)** - Bounded
  `--once-delivery` succeeds; one queued notification reaches the correct
  brand topic and the row becomes `sent` with a `telegram_message_id`.
  **Owner**: backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#telegram-smoke),
  [TELEGRAM_BOT.md](../reference/TELEGRAM_BOT.md#failure-and-deduplication).
- **Resolver proof gate (if enabling resolver)** - One real component link
  resolved end-to-end with `ENABLE_RESOLVER=true` and
  `RESOLVER_LIVE_PROOF_CONFIRMED=true`; every redirect hop validated;
  sanitized fixture stored. Otherwise leave both flags `false`. **Owner**:
  backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#resolver-proof-gate),
  [API_SPEC.md](../reference/API_SPEC.md#post-apiresolve).
- **Release evidence recorded** - Harness story updated with launch
  timestamp, Tunnel hostname, admin JWT subject, commit SHA, and the smoke
  artifact paths. **Owner**: backend on-call. **Detail**:
  [public-launch.md](./public-launch.md#release-evidence).

## Post-launch monitoring gates

These gates run continuously after launch. Each one has a documented
rollback path.

- **`/api/health` continuous probe** - External monitor against
  `GET /api/health` returns `ok: true` and the expected `features` shape.
  An outage triggers the deployment-rollback runbook. **Owner**: platform.
  **Detail**:
  [API_SPEC.md](../reference/API_SPEC.md#get-apihealth),
  [rollback.md](../OPERATIONS/rollback.md#rolling-back-a-deployment).
- **Worker run health** - Each scheduled run produces a `scan_runs` row
  with `status='completed'`; Telegram worker-log summary arrives within the
  expected window; failure-rate stays under `SCAN_FAILURE_RATE_THRESHOLD`.
  If breached, fall back to the concurrency-rollback runbook. **Owner**:
  backend on-call. **Detail**:
  [SCHEDULER.md](../reference/SCHEDULER.md#observability),
  [rollback.md](../OPERATIONS/rollback.md#rolling-back-scan-concurrency).
- **Telegram delivery health** - `telegram_notifications` queue does not
  grow unbounded; `sending` rows are aged out within the documented stale
  window; `failed` rows carry one of the documented cause labels.
  Sustained `TELEGRAM_AUTH` or `TELEGRAM_CHAT_BLOCKED` triggers the
  Telegram-outage rollback. **Owner**: backend on-call. **Detail**:
  [TELEGRAM_BOT.md](../reference/TELEGRAM_BOT.md#failure-and-deduplication),
  [rollback.md](../OPERATIONS/rollback.md#rolling-back-a-telegram-outage).
- **Public quota health** - `public_action_requests` rates stay within
  configured per-hour limits; sustained `RATE_LIMITED` 429 responses prompt
  a re-tune. **Owner**: platform. **Detail**:
  [SECURITY_NOTES.md](../reference/SECURITY_NOTES.md#rate-and-challenge-controls),
  [API_SPEC.md](../reference/API_SPEC.md#errors-and-rate-limits).
- **Origin non-bypass spot check** - Periodic external check that the
  origin web port is not reachable outside Cloudflare Tunnel. **Owner**:
  platform. **Detail**:
  [public-launch.md](./public-launch.md#gateway-smoke),
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#release-gates).
- **Migration drift monitor** - `supabase/migrations/` filename order
  matches the applied state in production. Any unrecognized migration in
  production is investigated before a new deploy. **Owner**: backend
  on-call. **Detail**:
  [DEPLOYMENT.md](../reference/DEPLOYMENT.md#database-activation),
  [rollback.md](../OPERATIONS/rollback.md#rolling-back-a-supabase-migration).
- **Resolver gate stays closed unless proven** - `ENABLE_RESOLVER` and
  `RESOLVER_LIVE_PROOF_CONFIRMED` remain `false` until the resolver proof
  gate is renewed; any code change to the resolver re-opens this gate.
  **Owner**: backend on-call. **Detail**:
  [SECURITY_NOTES.md](../reference/SECURITY_NOTES.md#resolver-ssrf-boundary),
  [public-launch.md](./public-launch.md#resolver-proof-gate).
