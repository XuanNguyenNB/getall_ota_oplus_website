# Deployment

The production shape is a VPS running Docker Compose with Cloudflare Tunnel as
the only public ingress path.

## Services

`compose.yaml` provides:

- `web`: FastAPI application and static browser UI.
- `bot`: optional Telegram delivery consumer and long-polling commands,
  enabled with the `bot` profile after Telegram smoke succeeds.
- `worker`: one-shot scanner invoked by the host timer or operator.
- `cloudflared`: outbound-only ingress tunnel to `http://web:8000`.

The Compose file does not publish a host web port. `cloudflared` waits for the
web container health check before serving traffic, which prevents public
requests from reaching a half-started app and keeps Cloudflare as the only
ingress path.

## Required Secrets And Configuration

Rotate any previously exposed Supabase elevated key before live use.

```text
ENVIRONMENT=production
REPOSITORY_BACKEND=supabase
OTA_PROVIDER=realme
ALLOW_LIVE_OTA=true
SUPABASE_URL=https://project-ref.supabase.co
SUPABASE_SECRET_KEY=rotated-server-key

PUBLIC_SITE_ENABLED=true
TURNSTILE_SITE_KEY=public-site-key
TURNSTILE_SECRET_KEY=server-only-secret
TURNSTILE_EXPECTED_HOSTNAME=ota.example.com
PUBLIC_RATE_LIMIT_SALT=server-only-random-value

CLOUDFLARE_TUNNEL_TOKEN=server-only-token
SCAN_CYCLE_DAYS=1
SCAN_MAX_TASKS_PER_RUN=200
SCAN_FAILURE_RATE_THRESHOLD=0.10
SCAN_FAILURE_ARCHIVE_THRESHOLD=3
SCAN_TIMEOUT_RETRIES=1
```

Configure Telegram values only before starting the optional bot profile:

```text
TELEGRAM_BOT_TOKEN=server-only-token
TELEGRAM_COMMAND_CHAT_ID=7063171724
TELEGRAM_WORKER_LOG_CHAT_ID=7063171724
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_ADMIN_USER_IDS=123456789
TELEGRAM_WORKER_LOGS_ENABLED=true
TELEGRAM_WORKER_LOG_RELEASE_LIMIT=10
```

Keep `ENABLE_RESOLVER=false` and `RESOLVER_LIVE_PROOF_CONFIRMED=false` until
the resolver proof gate succeeds.

## Database Activation

Apply migrations in filename order through
`supabase/migrations/202605270007_scan_eligibility.sql`. Create the
operator account using Supabase Auth, then manually insert its user UUID into
`admin_users`. Do not expose RLS-bypassing server keys to browser code.

After migration, import the current data set as needed:

```bash
python -m ota_backend.catalog import-oxygen
python -m ota_backend.catalog import-domestic-cn
python -m ota_backend.catalog import-lsctool-archive
python -m ota_backend.catalog import-lsctool-edl
```

The UI hides OTA release provenance, but the database keeps `ota_releases.source`
so live-provider cache decisions do not mix third-party archive rows with live
OPlus results. EDL ROM links are stored separately in `edl_roms` and are not
proxied or mirrored by the web service.

Imports keep the public catalog/search archive current but do not automatically
enable unattended live scans. Use Telegram admin commands such as
`/scan search <query>`, `/scan on-group <scan_group_key>`, `/scan off-group`,
`/scan on <model...>`, `/scan off <model...>`, `/scan list on`, and
`/scan off-all CONFIRM` to manage the worker allowlist. If the allowlist is
small, set `SCAN_CYCLE_DAYS=1`; otherwise keep the default 7-day sharding.
After applying the scan-eligibility migration, repair old scan rows before
starting unattended scans:

```bash
python -m ota_backend.worker --cleanup-scan-eligibility --dry-run
python -m ota_backend.worker --cleanup-scan-eligibility
```

The cleanup disables enabled rows missing manifest codes and archives known
legacy OnePlus 7/8 variants that repeatedly fail upstream queries.

## Frontend Stylesheet

The browser UI is styled with Tailwind CSS v4 compiled by the standalone CLI
(no Node/npm). The source is `src/ota_backend/static/tailwind.input.css`; the
compiled `src/ota_backend/static/styles.css` is committed and served directly
by FastAPI, so the Docker image and Compose flow are unchanged.

Rebuild and commit `styles.css` whenever you edit `tailwind.input.css`,
`index.html`, or any class names emitted by `app.js`:

```bash
scripts/build-css.sh            # Linux/macOS/Git Bash, one-shot minified build
scripts/build-css.sh --watch    # rebuild on change while developing
```

```powershell
scripts/build-css.ps1           # Windows PowerShell, one-shot minified build
scripts/build-css.ps1 -Watch    # rebuild on change while developing
```

Both scripts download the pinned Tailwind standalone binary to
`scripts/bin/` (git-ignored) on first run. CI/build hosts do not need the
binary because the committed `styles.css` is what ships.

## Commands

Local image/config validation:

```bash
docker compose config --quiet
docker compose build web
```

Start online services:

```bash
docker compose up -d web cloudflared
```

Start Telegram only after target rows and token configuration are present:

```bash
docker compose --profile bot run --rm bot python -m ota_backend.telegram_bot --check-config
docker compose --profile bot run --rm bot python -m ota_backend.telegram_bot --once-delivery
docker compose --profile bot up -d bot
```

Run a bounded worker job:

```bash
docker compose --profile jobs run --rm worker python -m ota_backend.worker --once --max-tasks 1
```

Run a bounded shard smoke after scan cleanup:

```bash
docker compose --profile jobs run --rm worker python -m ota_backend.worker --once --cycle-day 0 --max-tasks 20
```

Process an admin-created run:

```bash
docker compose --profile jobs run --rm worker python -m ota_backend.worker --once --scan-run-id <uuid>
```

For scheduled daily scans install `deploy/systemd/ota-worker.service` and
`deploy/systemd/ota-worker.timer`; the service uses `flock` to reject
overlapping worker execution. When Telegram worker logs are enabled, each
scheduled run sends one concise scan summary and a bounded list of new releases
to the worker-log chat.

## Release Gates

Before public DNS is enabled:

1. Complete `docs/runbooks/phase1-live-smoke.md` privately.
2. Verify admin JWT protection and Turnstile rejection/success.
3. Verify the origin cannot be reached directly outside Cloudflare Tunnel.
4. Run a bounded worker job and confirm scan rows are written.
5. Run a bounded Telegram send only if the bot profile is being enabled.
6. Complete resolver proof before enabling its flag.
7. Record evidence in Harness.

Local automated tests do not prove any of these external checks occurred.
