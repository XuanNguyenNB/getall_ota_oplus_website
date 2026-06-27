# getall_ota_oplus_website

OTA discovery application for OPPO, Realme, and OnePlus devices. It combines a
FastAPI web interface, persisted catalog/release/scan state, Telegram forum
notifications, and a safety-gated component-link resolver.

## Current Status

Implemented and proven offline:

- FastAPI endpoints and browser UI for devices, standard OTA queries, release
  archive browsing, and operator scan status.
- Memory/fake defaults plus opt-in Supabase, Oxygen Updater, and direct
  `realme-ota` live adapters.
- Full approved 26-code Universal OTA manifest map, catalog importer, smart
  scan allowlist, grouped Telegram scan controls, and bounded worker CLI.
- Third-party LSCTool archive importer and per-device multi-release archive UI.
- Third-party LSCTool EDL ROM archive importer and browser EDL link tab.
- Public controlled-access code: Turnstile validation, hashed quota/cooldown
  persistence, fresh-result OTA caching, Supabase Auth admin checks, and admin
  scan enqueue.
- Telegram delivery queue consumer and long-polling bot commands `/latest` and
  admin-only `/status`.
- Resolver implementation with host/DNS/IP/redirect protections, disabled
  until a bounded live component-link proof is explicitly confirmed.
- Supabase migration artifacts, Docker Compose, Cloudflare Tunnel ingress
  shape, VPS timer units, and CI workflow.

External activation status:

- On 2026-05-27, a private live smoke imported `1500` valid catalog models
  and persisted live manual OTA results. Operator-applied scanner recovery and
  full-manifest migrations were subsequently proven through expanded catalog
  reads and completed bounded worker runs.
- Rotating previously exposed Supabase elevated keys and configuring production
  secrets.
- Telegram delivery, resolver proof, Cloudflare Tunnel, and public-launch
  smoke tests remain operator-controlled gates.

## Runtime Modes

Offline development is the default:

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn ota_backend.main:app --host 127.0.0.1 --port 8000
python -m pytest
```

Live private activation for Phase 1-3 proceeds after all migrations, including
the scanner RPC recovery and full manifest-map expansion, are applied
with server-only configuration:

```text
REPOSITORY_BACKEND=supabase
OTA_PROVIDER=realme
ALLOW_LIVE_OTA=true
SUPABASE_URL=https://project-ref.supabase.co
SUPABASE_SECRET_KEY=rotated-server-key
```

```powershell
python -m ota_backend.catalog import-oxygen
python -m ota_backend.catalog import-domestic-cn
# or run catalog plus archive imports in order:
python -m ota_backend.catalog import-all
python -m ota_backend.catalog import-lsctool-archive --dry-run
python -m ota_backend.catalog import-lsctool-archive
python -m ota_backend.catalog import-lsctool-edl --dry-run
python -m ota_backend.catalog import-lsctool-edl
python -m ota_backend.worker --cleanup-scan-eligibility --dry-run
python -m ota_backend.worker --cleanup-scan-eligibility
python -m ota_backend.worker --once --max-tasks 1
```

Do not use a server key previously shared outside secure environment
configuration. Rotate it first.

Catalog imports populate searchable devices and archive rows; they do not
automatically opt every imported model into unattended live scanning. Use the
Telegram admin `/scan` commands to enable only the device groups or variants
you want the worker to crawl. The worker scans `active_scan` variants grouped
by device family, not every catalog row, and skips rows missing manifests or
rows with repeated upstream failures.

## Public Runtime

Public mode is intended to run only behind Cloudflare Tunnel and requires
server-side Turnstile validation:

```text
ENVIRONMENT=production
REPOSITORY_BACKEND=supabase
OTA_PROVIDER=realme
ALLOW_LIVE_OTA=true
SUPABASE_URL=https://project-ref.supabase.co
SUPABASE_SECRET_KEY=rotated-server-key
PUBLIC_SITE_ENABLED=true
TURNSTILE_SITE_KEY=public-widget-key
TURNSTILE_SECRET_KEY=server-only-key
TURNSTILE_EXPECTED_HOSTNAME=ota.example.com
PUBLIC_RATE_LIMIT_SALT=server-only-random-value
OTA_PUBLIC_CACHE_TTL_SECONDS=1800
OTA_PUBLIC_RATE_LIMIT_PER_HOUR=5
RESOLVER_PUBLIC_RATE_LIMIT_PER_HOUR=10
SCAN_CYCLE_DAYS=1
SCAN_MAX_TASKS_PER_RUN=200
SCAN_FAILURE_RATE_THRESHOLD=0.10
SCAN_FAILURE_ARCHIVE_THRESHOLD=3
SCAN_TIMEOUT_RETRIES=1
```

In public mode, anonymous users may read catalog/releases and submit standard
OTA queries after Turnstile validation. `beta`, IMEI and GUID-style query
inputs are not accepted. `GET /api/scan/status` and
`POST /api/admin/scan/enqueue` require a Supabase Auth user present in
`admin_users`.

The resolver remains disabled until:

```text
ENABLE_RESOLVER=true
RESOLVER_LIVE_PROOF_CONFIRMED=true
```

These values must only be set after the bounded proof in
`docs/runbooks/public-launch.md` succeeds.

## Telegram

The bot service drains queued Telegram notifications and handles `/latest`
and `/status`:

```text
TELEGRAM_BOT_TOKEN=server-only-token
TELEGRAM_COMMAND_CHAT_ID=7063171724
TELEGRAM_WORKER_LOG_CHAT_ID=7063171724
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_ADMIN_USER_IDS=123456789
TELEGRAM_WORKER_LOGS_ENABLED=true
TELEGRAM_WORKER_LOG_RELEASE_LIMIT=10
```

```powershell
python -m ota_backend.telegram_bot --check-config
python -m ota_backend.telegram_bot --once-delivery
python -m ota_backend.telegram_bot
```

The scanner only enqueues notifications. The bot owns actual sends, retry
state, `/latest`, `/status`, and admin-only scan allowlist commands such as
`/scan search`, `/scan on-group`, `/scan off-group`, `/scan on`, `/scan off`,
`/scan list on`, and `/scan off-all CONFIRM`. When worker logs are enabled,
each scheduled scanner run posts one bounded summary with shard coverage,
failed models and new releases to the worker-log chat. `/notify backfill-run
<scan_run_id> [limit]` can safely enqueue releases from an earlier run after
Telegram targets are seeded. Telegram `/resolve` remains deferred until the
web resolver has live proof.

## Deployment

`compose.yaml` defines `web`, `bot`, one-shot `worker`, and `cloudflared`.
`web` and `cloudflared` are the baseline public services. `bot` is an optional
profile that should be started only after Telegram target rows and a bounded
delivery smoke are ready. There is no host-published web port; public ingress
is through Cloudflare Tunnel. Install `deploy/systemd/ota-worker.timer` on the
VPS for daily scans. See `docs/reference/DEPLOYMENT.md` for activation and
release gates.

## Documentation

- `docs/product/`: living product contract.
- `docs/reference/`: architecture, API, database, deployment and operations
  references.
- `docs/reference/IMPLEMENTATION_PLAN.md`: implementation and rollout phases.
- `docs/runbooks/phase1-live-smoke.md`: private live activation steps.
- `docs/runbooks/public-launch.md`: public release gates.
- `docs/archive/design/`: superseded design audit and original concept plan.
- `docs/stories/`: validation/status records.

`realme-ota` is integrated directly as a pinned GPLv3 dependency. Distribution
of this project or its container image must preserve applicable GPLv3 notices
and corresponding-source obligations.
