# Validation

## Proof Strategy

Phase 3 proof must stay local and offline. Tests use the existing fake OTA
provider path and in-memory repositories. No production secrets, live Supabase
project, live OPlus OTA traffic, or real Telegram sends are required.

## Test Plan

| Layer | Cases |
| --- | --- |
| Unit | 7-day stable shard selection, bootstrap track order, recurring track progression, retry classification |
| Integration | scan run/task persistence, atomic queued-task claiming, retry/non-retry task outcomes, release upsert duplicate `last_seen_at`, notification enqueue/dedup, `/api/scan/status` empty/latest-run shapes |
| E2E | Not in Phase 3 |
| Platform | Local worker module import and full pytest run |
| Performance | Not in Phase 3 |
| Logs/Audit | Migration and notification records contain no Telegram token or live-send behavior |

## Fixtures

- In-memory enabled Realme device `RMX3301` using the fake OTA success path.
- In-memory enabled OnePlus device `CPH2805IN` using the fake OTA not-found
  path.
- In-memory Telegram targets for OPPO, Realme, and OnePlus topics.

## Commands

```text
python -m pytest tests/test_scanner.py tests/test_api_scan_status.py tests/test_migrations.py
python -m pytest
```

## Progress Log

- 2026-05-26: Read required root docs, Harness docs, product docs, Phase 1/2
  story records, source layout, and Harness matrix. `scripts/harness query
  matrix` must be run via `bash scripts/harness query matrix` in this Windows
  PowerShell environment; direct `scripts/harness ...` timed out.
- 2026-05-26: Harness intake #4 recorded as high-risk and story
  `PHASE3-SCHEDULED-SCANNER` added.
- 2026-05-26: Created Phase 3 high-risk story packet under
  `docs/stories/epics/E03-scheduled-scanner/PHASE3-SCHEDULED-SCANNER/`.
- 2026-05-26: Implemented scanner domain rules, in-memory scan/task
  persistence, in-memory Telegram target/notification queue, offline
  `ScannerService`, local worker entrypoint, and `GET /api/scan/status`.
- 2026-05-26: Added Phase 3 Supabase migration for `scan_runs`, `scan_tasks`,
  `telegram_targets`, and `telegram_notifications`.
- 2026-05-26: Focused Phase 3 proof passed:
  `python -m pytest tests/test_scanner.py tests/test_api_scan_status.py tests/test_migrations.py`
  returned `11 passed`.
- 2026-05-26: Affected Phase 1/2 API and UI regression proof passed:
  `python -m pytest tests/test_api_devices.py tests/test_api_ota.py tests/test_api_releases.py tests/test_api_health.py tests/test_web_ui.py`
  returned `10 passed`.
- 2026-05-26: Full release proof passed: `python -m pytest` returned
  `25 passed`.
- 2026-05-26: Local worker module smoke passed: `python -m ota_backend.worker`
  exited successfully and printed a completed local scan run summary.
- 2026-05-26: Targeted worker `run_once` smoke for the `RMX3301` shard
  completed one offline task and found one new worker release:
  `status=completed total=1 completed=1 failed=0 new=1`.

## Acceptance Evidence

- `python -m pytest`: `25 passed`.
- Focused scanner/status/migration proof: `11 passed`.
- Affected API/UI regression proof: `10 passed`.
- `python -m ota_backend.worker`: completed without live Supabase credentials,
  live OPlus traffic, or real Telegram sends.
- `python -c "from ota_backend.worker import run_once; ..."` for the RMX3301
  shard: `status=completed total=1 completed=1 failed=0 new=1`.
- Covered behaviors:
  - 7-day stable shard selection.
  - bootstrap track order and recurring track progression.
  - scan run and scan task persistence semantics.
  - queued-task claim behavior.
  - retry and non-retry task outcomes.
  - release upsert and duplicate `last_seen_at` behavior.
  - queued Telegram notification creation and deduplication.
  - `GET /api/scan/status` empty and latest-run shapes.
  - migration coverage for scanner and notification tables.
