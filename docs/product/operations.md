# Operations Contract

## Runtime Shape

- `web`: FastAPI HTTP API and browser UI.
- `worker`: one-shot Oxygen import or OTA scan command.
- `bot`: optional Telegram notification consumer and long-polling command
  handler.
- `cloudflared`: public ingress infrastructure routed to `web`.
- Supabase: durable state for catalogs, releases, scans, quotas, admin
  membership, notification delivery and resolver history.

The origin web port is not host-published in the production Compose shape.

## Scanner

The worker scans stable shards of Telegram-managed `active_scan` device groups
using `sha256(upper(scan_group_key)) % SCAN_CYCLE_DAYS`, then creates one task
per valid regional variant in that group. It applies track progression,
throttles live provider calls and persists task state atomically.
Production scheduling uses `deploy/systemd/ota-worker.timer`, whose service
holds a lock against overlap.

`SCAN_MAX_CONCURRENCY` (default `1`) controls intra-run task fan-out. Keep it
low when running against live OPlus endpoints; raise it only after a bounded
shard has been validated at the higher value. See
`docs/reference/SCHEDULER.md` and `docs/OPERATIONS/rollback.md` for tuning and
rollback steps.

An admin may enqueue known devices through `POST /api/admin/scan/enqueue` and
process the returned queued run with:

```text
python -m ota_backend.worker --once --scan-run-id <uuid>
```

## Telegram

The bot claims queued notifications, sends brand-routed topic messages, and
stores message IDs or sanitized retry state. Implemented commands are
`/latest <model>`, administrator-only `/status`, administrator-only
`/scan ...` allowlist management and `/notify backfill-run` notification
backfill. `/resolve` is deferred. Start the bot
profile only after Telegram target rows, token configuration and a bounded
`--once-delivery` smoke succeed.

## Resolver

The web resolver remains disabled unless bounded live proof has been confirmed.
When enabled, it enforces host/DNS/IP/redirect safety and its public quota.

## Activation

The operator must rotate exposed server keys, apply all migrations through
`202605270007_scan_eligibility.sql`, run private live smoke, validate
Tunnel ingress and verify public Turnstile/admin controls before public DNS is
enabled. Telegram and resolver remain separate gates.
