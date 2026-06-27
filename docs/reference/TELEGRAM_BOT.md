# Telegram Bot

The Telegram integration uses one command/admin chat plus one or more release
targets. The scanner queues a record when a new release is detected;
`python -m ota_backend.telegram_bot` owns actual delivery and command polling.

## Implemented Behavior

- Atomic queued-notification claim through Supabase RPC, with stale-send
  recovery and bounded retries.
- Brand-topic routing using `chat_id` and optional `message_thread_id`.
- Stored message ID, delivery timestamps, attempt count and sanitized failure
  code.
- `/latest <model>` in the configured chat.
- `/status` only for IDs in `TELEGRAM_ADMIN_USER_IDS`.
- `/status full` with latest run details, scan eligibility counts and recent
  cycle coverage.
- Admin-only scan allowlist management through `/scan ...` commands.
- Admin-only safe notification backfill through `/notify backfill-run ...`.

Telegram `/resolve` is not enabled in this implementation. It is scheduled
only after the web resolver has bounded live proof.

## Configuration

Populate one enabled `telegram_targets` row per brand, then configure:

```text
TELEGRAM_BOT_TOKEN=server-only-token
TELEGRAM_COMMAND_CHAT_ID=7063171724
TELEGRAM_WORKER_LOG_CHAT_ID=7063171724
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_ADMIN_USER_IDS=123456789,987654321
TELEGRAM_POLL_TIMEOUT_SECONDS=20
TELEGRAM_NOTIFICATION_MAX_ATTEMPTS=3
TELEGRAM_NOTIFICATION_RETRY_SECONDS=300
TELEGRAM_WORKER_LOGS_ENABLED=true
TELEGRAM_WORKER_LOG_RELEASE_LIMIT=10
```

Run one bounded delivery check before continuous polling:

```powershell
python -m ota_backend.telegram_bot --check-config
python -m ota_backend.telegram_bot --once-delivery
python -m ota_backend.telegram_bot
```

## Notification Format

Messages include brand, model, manifest, track, display version, OTA version
and direct download URL, with best-effort patch/time/file metadata when
available. They must not contain Supabase credentials, Telegram tokens,
IMEI/GUID values or internal errors.

## Scan Allowlist Commands

The worker scans only variants with `scan_enabled=true`,
`scan_eligibility=active_scan` and a valid manifest. Admins can manage that
allowlist from the configured chat:

```text
/scan search <query>
/scan on-group <scan_group_key>
/scan off-group <scan_group_key>
/scan on <model...>
/scan off <model...>
/scan list on [oppo|realme|oneplus]
/scan off-all CONFIRM
/notify backfill-run <scan_run_id> [limit]
```

Groups are user-facing model families, for example `OPPO Find X8`, with
variants such as `PKB110 / 97`, `CPH2651 / A7`, `CPH2651IN / 1B` and
`CPH2651TH / 39`. The worker still creates one task per variant so each query
uses the same model/manifest inputs as the website's manual OTA lookup. A
release target may be a forum topic or a plain channel/group; in the latter
case `message_thread_id` is null.

`/notify backfill-run <scan_run_id> [limit]` re-enqueues releases discovered
by an existing run after Telegram targets are seeded. It uses the same
release-target unique identity as live notifications, so rerunning it reports
already queued items instead of duplicating sends.

## Failure And Deduplication

`telegram_notifications` remains unique by release and target. A consumer
claims a row as `sending`, stores `sent` with the Telegram message ID after
success, or stores `failed` with a sanitized code and next retry time. Topic
configuration and permission failures require operator repair.

Delivery failures are stored with stable, sanitized cause labels so retry and
audit state can be filtered without parsing free-form messages:

- `TELEGRAM_AUTH`: revoked/invalid bot token. Requires operator key rotation.
- `TELEGRAM_RATE_LIMIT`: Telegram `RetryAfter`. Retried automatically after the
  configured backoff.
- `TELEGRAM_CHAT_BLOCKED`: bot kicked, chat migrated, blocked or topic deleted.
  Requires operator repair of the target row.
- `TELEGRAM_NETWORK`: transient timeout or connection error. Retried.
- `TELEGRAM_DELIVERY_FAILED`: catch-all for unclassified failures.

These labels are written to `telegram_notifications.error_message` along with
the attempt count and `next_attempt_at`. The original Python exception chain
is preserved in process logs through `__cause__` for incident inspection but
is never persisted in the database row.
