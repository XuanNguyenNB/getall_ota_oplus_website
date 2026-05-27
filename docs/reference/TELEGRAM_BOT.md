# Telegram Bot

The Telegram integration uses one configured forum supergroup with OPPO,
Realme and OnePlus topics. The scanner queues a record when a new release is
detected; `python -m ota_backend.telegram_bot` owns actual delivery and command
polling.

## Implemented Behavior

- Atomic queued-notification claim through Supabase RPC, with stale-send
  recovery and bounded retries.
- Brand-topic routing using `chat_id` and `message_thread_id`.
- Stored message ID, delivery timestamps, attempt count and sanitized failure
  code.
- `/latest <model>` in the configured chat.
- `/status` only for IDs in `TELEGRAM_ADMIN_USER_IDS`.

Telegram `/resolve` is not enabled in this implementation. It is scheduled
only after the web resolver has bounded live proof.

## Configuration

Populate one enabled `telegram_targets` row per brand, then configure:

```text
TELEGRAM_BOT_TOKEN=server-only-token
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_ADMIN_USER_IDS=123456789,987654321
TELEGRAM_POLL_TIMEOUT_SECONDS=20
TELEGRAM_NOTIFICATION_MAX_ATTEMPTS=3
TELEGRAM_NOTIFICATION_RETRY_SECONDS=300
```

Run one bounded delivery check before continuous polling:

```powershell
python -m ota_backend.telegram_bot --once-delivery
python -m ota_backend.telegram_bot
```

## Notification Format

Messages include brand, model, manifest, track, display version, OTA version
and download URL. They must not contain Supabase credentials, Telegram tokens,
IMEI/GUID values or internal errors.

## Failure And Deduplication

`telegram_notifications` remains unique by release and target. A consumer
claims a row as `sending`, stores `sent` with the Telegram message ID after
success, or stores `failed` with a sanitized code and next retry time. Topic
configuration and permission failures require operator repair.
