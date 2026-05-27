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
```

Configure Telegram values only before starting the optional bot profile:

```text
TELEGRAM_BOT_TOKEN=server-only-token
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_ADMIN_USER_IDS=123456789
```

Keep `ENABLE_RESOLVER=false` and `RESOLVER_LIVE_PROOF_CONFIRMED=false` until
the resolver proof gate succeeds.

## Database Activation

Apply migrations in filename order through
`supabase/migrations/202605270003_release_archive_metadata.sql`. Create the
operator account using Supabase Auth, then manually insert its user UUID into
`admin_users`. Do not expose RLS-bypassing server keys to browser code.

After migration, import the current data set as needed:

```bash
python -m ota_backend.catalog import-oxygen
python -m ota_backend.catalog import-domestic-cn
python -m ota_backend.catalog import-lsctool-archive
```

The UI hides release provenance, but the database keeps `ota_releases.source`
so live-provider cache decisions do not mix third-party archive rows with live
OPlus results.

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
docker compose --profile bot run --rm bot python -m ota_backend.telegram_bot --once-delivery
docker compose --profile bot up -d bot
```

Run a bounded worker job:

```bash
docker compose --profile jobs run --rm worker python -m ota_backend.worker --once --max-tasks 1
```

Process an admin-created run:

```bash
docker compose --profile jobs run --rm worker python -m ota_backend.worker --once --scan-run-id <uuid>
```

For scheduled daily scans install `deploy/systemd/ota-worker.service` and
`deploy/systemd/ota-worker.timer`; the service uses `flock` to reject
overlapping worker execution.

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
