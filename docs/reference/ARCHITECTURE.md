# Architecture

The system is an OTA discovery platform with three application
responsibilities, Supabase Postgres as managed state, and Cloudflare Tunnel as
the required public ingress.

This repository contains the FastAPI API, public-capable browser UI, one-shot
scanner, offline defaults, Supabase and live `realme-ota` adapters, public
gateway/auth code, Telegram delivery and command code, a proof-gated resolver,
Docker/Cloudflare/timer artifacts, and CI. Private live smoke has proven
catalog import and OTA release persistence, expanded manifest inference and
bounded scanner completion after the recovery/full-manifest migrations were
applied. Public activation remains separately gated by secret rotation and
public-surface proof.

## High-Level Diagram

```text
Browser
  |
  | Cloudflare Tunnel / Turnstile protected active actions
  v
FastAPI web service
  |
  +--> Supabase Postgres
  +--> realme-ota logic
  +--> OPlus OTA endpoints
  +--> URL resolver (after live proof gate)

VPS worker
  |
  +--> Supabase scan queue
  +--> realme-ota logic
  +--> Supabase releases
  +--> Telegram notification queue

Telegram bot service
  |
  +--> Telegram Bot API
  +--> Supabase lookup tables
  +--> Commands (`/latest`, `/status`)
```

## Web/API Service

The web/API service handles interactive user actions.

Responsibilities:

- Serve the web UI.
- Search devices and releases.
- Run standard OTA queries.
- Browse per-device release archives.
- Expose scan status.
- Resolve supported OTA URLs only after the proof gate is enabled.
- Validate request input.
- Write releases found through manual queries into Supabase.

The web service must not expose Supabase service-role credentials to the browser.

## Worker Service

The worker runs scheduled scans on the VPS.

Responsibilities:

- Import or refresh the Oxygen Updater device catalog.
- Split enabled devices into a 7-day scan cycle.
- Query OTA endpoints in controlled batches.
- Persist new releases.
- Enqueue Telegram notifications for delivery by the bot service.
- Record scan status, errors, and timing.

The worker should be resumable. Restarting the container must not duplicate completed scan tasks or resend already delivered notifications.

## Telegram Bot Service

The Telegram bot is a separate long-polling process and notification consumer.

Responsibilities:

- Process `/latest <model>`.
- Process `/status`.
- Send claimed notification records to configured brand topics.
- Defer `/resolve` until the web resolver has live proof.

The bot process does not need to receive webhooks and should be started only
after Telegram target rows, token configuration and a bounded delivery smoke
are ready.

## Supabase Postgres

Supabase is the persistent system of record.

It stores:

- device catalog
- manual overrides
- OTA releases
- scan run state
- scan tasks
- Telegram target topics
- notification delivery state
- resolver request history
- admin memberships and hashed public action audit records

Supabase Cron is not required for the main scanner because the scanner runs on the VPS, but Supabase remains useful for observability and persisted state.

## Data Flow: Catalog Import

1. Worker calls Oxygen Updater `/devices/all`.
2. Worker normalizes each row.
3. Worker infers brand and manifest code.
4. Worker upserts the device row.
5. Manual overrides are preserved.

## Data Flow: Daily Scan

1. Worker creates a `scan_runs` record.
2. Worker selects the daily shard of enabled devices.
3. Worker creates or claims `scan_tasks`.
4. Worker queries OTA endpoints for each selected model.
5. New releases are inserted into `ota_releases`.
6. Notifications are inserted into `telegram_notifications`.
7. Bot claims queued notifications and sends them into the correct brand topic.
8. Run and task statuses are updated.

## Data Flow: Telegram Notification

1. A new release is inserted.
2. The release brand maps to a Telegram target topic.
3. The dispatcher formats a message.
4. The dispatcher calls Telegram `sendMessage` with:
   - `chat_id`
   - `message_thread_id`
   - message text
   - optional inline buttons
5. The Telegram message ID is stored for deduplication and auditing.

## Data Flow: Resolver

1. User submits a web resolver request after the resolver proof gate is enabled.
2. Resolver validates scheme, hostname, and IP safety.
3. Resolver follows the known OTA resolution flow.
4. Resolver stores the request and result.
5. Resolver returns the resolved URL or a structured error.

## Runtime Boundaries

- Browser clients never receive Supabase service-role credentials.
- Public active browser operations require Turnstile validation and quota
  controls.
- The worker owns scheduled scanning.
- The Telegram bot owns notification delivery and incoming commands.
- The resolver never fetches arbitrary hosts.
- The backend stores OTA metadata, not OTA file contents.
- Application responsibilities are `web`, one-shot `worker`, and `bot`;
  `bot` is optional at initial public launch. `cloudflared` is ingress
  infrastructure and Supabase is managed state.
