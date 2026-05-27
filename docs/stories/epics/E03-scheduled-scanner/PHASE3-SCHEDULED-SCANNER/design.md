# Design

## Domain Model

The scanner uses the existing `Device`, `OtaQuery`, and `Release` records plus
new scan and notification records:

- `ScanRun`: one scheduled scan execution with cycle day, status, counters,
  timestamps, and error summary.
- `ScanTask`: one per device in a run, with claim status, attempt count,
  checked tracks/RUI candidates, optional release ID, and sanitized error.
- `TelegramTarget`: brand to Telegram forum topic routing record.
- `TelegramNotification`: queued/sent/failed notification audit record
  deduplicated by release and target.

Stable shard selection is:

```text
sha256(upper(product_model)) % 7
```

Bootstrap devices check tracks in `H, F, C, A` order. Recurring devices check
the active track and the next track in `A -> C -> F -> H`.

## Application Flow

`ScannerService.run_scheduled_scan(cycle_day=...)`:

1. Select enabled devices whose stable shard matches the cycle day.
2. Create a `scan_runs` record and one queued `scan_tasks` record per selected
   device.
3. Claim queued tasks through the scan repository.
4. Query the existing fake OTA provider for the task's track progression and
   default RUI candidates.
5. Upsert newly found releases with `discovered_by="worker"`.
6. Enqueue a Telegram notification record for new releases and the matching
   enabled brand target.
7. Mark tasks and run counters completed or failed.

## Interface Contract

`GET /api/scan/status` returns:

```json
{
  "ok": true,
  "latest_run": null
}
```

or:

```json
{
  "ok": true,
  "latest_run": {
    "id": "uuid",
    "status": "completed",
    "cycle_day": 3,
    "started_at": "2026-05-26T00:00:00Z",
    "completed_tasks": 1,
    "failed_tasks": 0,
    "pending_tasks": 0
  }
}
```

No admin enqueue route is added in this phase.

## Data Model

The Phase 3 migration adds:

- `scan_runs`
- `scan_tasks`
- `telegram_targets`
- `telegram_notifications`

The migration keeps release deduplication on the existing release key and adds
notification deduplication on `(release_id, telegram_target_id)`.

## UI / Platform Impact

No browser UI change is in scope. A local worker entrypoint is added for future
scheduled execution, but Docker and service supervision remain deferred.

## Observability

The scanner records run counters, task statuses, task error codes, new release
count, timestamps, and queued notification records. No Telegram token or live
provider secret is needed.

## Alternatives Considered

1. Add a protected admin enqueue endpoint now. Rejected because the Phase 3
   goal explicitly excludes admin enqueue endpoints.
2. Send Telegram messages from the worker. Rejected for offline validation; this
   slice queues deduplicated notification records only.
