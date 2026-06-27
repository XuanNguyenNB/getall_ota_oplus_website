# Scheduler

The scanner runs through the worker path and stores live state in Supabase when
`REPOSITORY_BACKEND=supabase` is configured. It retains an offline in-memory
and fake-provider mode for deterministic local proof.

Production scheduling is represented by a one-shot worker command and the
host timer units under `deploy/systemd/`. The service uses `flock` so daily
executions do not overlap.

## Scan Cadence

The enabled scan allowlist is scanned over a configurable cycle. The default
is still 7 days, but deployments that keep a small manual allowlist can set
`SCAN_CYCLE_DAYS=1` to scan every enabled variant once per day.

Each day:

- select one stable shard of `scan_eligibility=active_scan` device groups
- create scan tasks for that shard
- process tasks with limited concurrency
- store discovered releases
- enqueue Telegram notifications

This avoids running one very large scan job and reduces upstream pressure.

The VPS timer runs one shard per day. The public searchable catalog can be much
larger than the live scan allowlist because `catalog_visible=true` and
`scan_enabled=true` are separate fields. Importing catalog/archive data does
not automatically enable live scans; operators use Telegram `/scan` commands
to enable only selected device groups or variants.

## Scan Eligibility

Catalog/archive visibility is separate from unattended live scanning.

Device scan states:

- `active_scan`: eligible for scheduled live OTA crawling.
- `archive_only`: visible on the website, but not crawled automatically.
- `invalid_for_scan`: visible only when useful, but missing scan-critical data
  such as manifest code.

The worker ignores rows without a manifest, rows outside `active_scan`, and
rows whose consecutive failure counter has reached the configured archive
threshold. Telegram `/scan on ...` can re-enable a model and reset its failure
counter when an operator wants to retry it.

## Sharding Strategy

Use a stable hash of `scan_group_key`, falling back to `product_model` only
when grouping metadata is absent.

Example:

```text
cycle_day = sha256(upper(scan_group_key)) % SCAN_CYCLE_DAYS
```

On each run, scan all active variants in groups where `cycle_day` equals the
current cycle day. This keeps regional variants of the same device family
together, for example China, global, India and Thailand variants of one Find
X8 generation. `SCAN_MAX_TASKS_PER_RUN` can cap the run for bounded smoke
checks, but production runs should leave it unset or high enough to avoid
splitting a group unnecessarily.

## Telegram Scan Allowlist

The bot exposes admin-only controls for the worker allowlist:

```text
/scan search <query>
/scan on-group <scan_group_key>
/scan off-group <scan_group_key>
/scan on <model...>
/scan off <model...>
/scan list on [oppo|realme|oneplus]
/scan off-all CONFIRM
```

Groups are derived from normalized device names. Region suffixes such as
`(CN)`, `(IN)`, `(EU)` and `(GLO)` are removed, so variants like `PKB110`,
`CPH2651`, `CPH2651IN` and `CPH2651TH` can be managed under `OPPO Find X8`.
Model tiers remain separate: `Find X8`, `Find X8 Pro` and `Find X8 Ultra` are
different groups.

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
SCAN_MAX_CONCURRENCY=1
SCAN_CYCLE_DAYS=7
SCAN_MAX_TASKS_PER_RUN=
```

`SCAN_MAX_CONCURRENCY` controls how many scan tasks the worker drives in
parallel within a single run. The default is `1` (fully serial) because OPlus
endpoints throttle aggressive callers; operators who have validated higher
fan-out against a live shard can raise this value (range 1-20). Each in-flight
task still respects `SCAN_REQUEST_INTERVAL_SECONDS` between live-provider
calls.

`SCAN_MAX_TASKS_PER_RUN` is optional; leave it unset for the full selected
shard or set a positive integer as an operational safety cap.

Rollback guidance: if a higher concurrency setting causes upstream
rate-limiting or run-level failure-rate breach, set `SCAN_MAX_CONCURRENCY=1`
and restart the timer. The setting is read at worker start, so no migration
or data fix is required. See `docs/OPERATIONS/rollback.md` for the full
procedure.

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

- retry timeout once inside the same task before marking the attempt failed
- retry queued task attempts through the existing task retry mechanism
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

## Telegram Worker Logs

When `TELEGRAM_WORKER_LOGS_ENABLED=true`, the worker sends one Telegram summary
after each run. The summary includes run ID, status, cycle day, start/finish
time, completed/failed counts, no-update count, scan-capable coverage and the
number of new releases. Low task failure rates complete the run with a warning
instead of marking the whole batch failed. The summary lists up to
`TELEGRAM_WORKER_LOG_RELEASE_LIMIT` new releases and the top failed models from
that run. It is sent to the worker-log chat, which may be the same as the
command chat during simple deployments.

The worker does not send per-task logs because a full shard can include many
hundreds of models. Detailed operational logs remain in systemd:

```text
sudo journalctl -u ota-worker.service -f
```
