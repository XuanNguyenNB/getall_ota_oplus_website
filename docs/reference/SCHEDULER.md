# Scheduler

The scanner runs through the worker path and stores live state in Supabase when
`REPOSITORY_BACKEND=supabase` is configured. It retains an offline in-memory
and fake-provider mode for deterministic local proof.

Production scheduling is represented by a one-shot worker command and the
host timer units under `deploy/systemd/`. The service uses `flock` so daily
executions do not overlap.

## Scan Cadence

The enabled catalog is scanned over a 7-day cycle.

Each day:

- select one stable shard of enabled devices
- create scan tasks for that shard
- process tasks with limited concurrency
- store discovered releases
- enqueue Telegram notifications

This avoids running one very large scan job and reduces upstream pressure.

## Sharding Strategy

Use a stable hash of `product_model`.

Example:

```text
cycle_day = sha256(upper(product_model)) % 7
```

On each day, scan devices where `cycle_day` equals the current cycle day.

Advantages:

- deterministic
- balanced enough for large catalogs
- safe after restarts
- easy to reason about

## Track Progression

Supported tracks:

```text
A -> C -> F -> H
```

Meaning:

- `A`: launch version
- `C`: first update track
- `F`: second update track
- `H`: third update track

Progression rule:

- If `C` exists, stop actively checking `A`.
- If `F` exists, stop actively checking `C` and `A`.
- If `H` exists, stop actively checking `F`, `C` and `A`.

For recurring scans, probe from newest to oldest among the active-or-newer
tracks. Active `C` checks `H,F,C`; active `F` checks `H,F`; active `H` checks
`H` only. This lets archive backfill suppress old-track scans while still
allowing newer tracks to be discovered.

## Bootstrap Strategy

New devices do not have a known active track.

For a new device:

1. Try `H`.
2. If not found, try `F`.
3. If not found, try `C`.
4. If not found, try `A`.
5. Store the highest track that returns a valid OTA.
6. Mark `bootstrap_done=true`.

This gives a reasonable starting point while avoiding repeated full-track scans forever.

## OS/RUI Candidate Strategy

OS/RUI candidates are configurable.

Default:

```text
RUI_CANDIDATES=8,7,6
```

The worker tries candidates from left to right.

If a candidate succeeds:

- store the winning `rui_version`
- avoid trying older candidates for the same track in the same task

If all candidates fail:

- mark task failed or no-update depending on the upstream response
- store a sanitized error code

## Concurrency

Default:

```text
SCAN_MAX_CONCURRENCY=3
```

Keep concurrency conservative because OPlus endpoints can rate limit or fail under load.

## Task States

Supported task states:

- `queued`
- `running`
- `completed`
- `failed`
- `skipped`

The worker should claim queued tasks atomically so two worker instances do not process the same task.

## Retry Policy

Recommended:

- retry transient network errors up to 2 times
- do not retry validation errors
- retry Telegram notification failures separately from OTA scan tasks

Transient examples:

- timeout
- connection reset
- HTTP 5xx

Non-retryable examples:

- invalid manifest code
- unsupported model format
- blocked resolver URL

## Release Detection

A release is new when the unique release key does not already exist.

Recommended unique key:

```text
product_model + manifest_code + real_ota_version + download_url
```

If the same release appears again, update `last_seen_at` instead of inserting a duplicate.

## Observability

Record:

- scan run start and finish time
- total tasks
- completed tasks
- failed tasks
- new release count
- per-task error codes
- average request latency if practical

The `/api/scan/status` endpoint should read from these tables.

In public mode that endpoint is admin-only. An admin-enqueued run is processed
with:

```text
python -m ota_backend.worker --once --scan-run-id <uuid>
```
