# Database Schema

Supabase Postgres is the persistent database for the system.

This document describes the intended table design. The Phase 1 migration exists
at `supabase/migrations/202605260001_phase1_backend_core.sql` and covers the
initial `devices` and `ota_releases` tables needed by the local backend slice.
The Phase 3 migration exists at
`supabase/migrations/202605260002_phase3_scheduled_scanner.sql` and covers
`scan_runs`, `scan_tasks`, `telegram_targets`, and
`telegram_notifications`. The live runtime migration at
`supabase/migrations/202605260003_live_runtime.sql` adds
`device_catalog_imports`, server-only Data API grants/RLS, and atomic RPCs for
task claiming/completion, release upsert, and notification enqueue.
`202605260004_public_gateway.sql` adds server-only admin membership and hashed
public-action quota records. `202605260005_telegram_delivery.sql` adds
retryable Telegram delivery state and atomic RPCs.
`202605260006_resolver.sql` adds feature-gated resolver history.
`202605270001_scanner_rpc_recovery.sql` restores completion RPC visibility and
allows interrupted running tasks to be reclaimed after 15 minutes.
`202605270002_full_manifest_map.sql` expands device/release manifest
constraints to the full Universal OTA table and backfills known catalog
suffixes without changing manual overrides.
`202605270003_release_archive_metadata.sql` adds release archive metadata and
extends the release upsert RPC for LSCTool archive imports.
`202605270004_edl_rom_archive.sql` adds a separate EDL ROM archive table for
direct ROM package links. `202605270005_smart_scan_groups.sql` separates
catalog visibility from unattended scan eligibility and adds scan group
metadata for Telegram-managed auto scan allowlists.
`202605270007_scan_eligibility.sql` adds explicit scan lifecycle state and
failure metadata used by the smarter scheduler.
`202606270001_scan_eligibility_index.sql` adds two partial indexes on
`devices` (keyed on `name` and `scan_group_key`) that match the
`scan_enabled = true AND scan_eligibility = 'active_scan' AND
manifest_code IS NOT NULL` predicate. The supabase repository pushes that
predicate to SQL, so this index makes the active-scan slice O(matches)
instead of O(catalog_size) and gives the cycle-day shard scan a btree seek
instead of a sequential scan.
`202606270002_scan_run_counters_recompute.sql` makes
`scan_runs.new_releases` idempotent. It adds `scan_tasks.found_new_release`,
backfills it conservatively from existing completed rows, recomputes
`scan_runs.new_releases` from that column, and rewrites
`complete_scan_task` to recompute the run-level counter from task state on
every completion. Replaying a completion (e.g. operator-triggered retry)
now produces the same final counter value. The previous body of
`complete_scan_task` is preserved in `docs/OPERATIONS/rollback.md` so a
rollback can restore it byte-for-byte.

## devices

Stores normalized device catalog entries.

Important columns:

- `id`: UUID primary key.
- `catalog_id`: integer from Oxygen Updater, nullable for manual devices.
- `brand`: text, one of `oppo`, `realme`, `oneplus`.
- `name`: display name.
- `product_model`: OPlus product model, for example `RMX3301` or `CPH2841TH`.
- `manifest_code`: manifest code, for example `1B`, `39`, `A7`, `97`.
- `catalog_visible`: boolean; visible/searchable in the public catalog.
- `scan_enabled`: boolean; eligible for unattended worker live scans.
- `scan_eligibility`: `active_scan`, `archive_only`, or `invalid_for_scan`.
- `consecutive_failures`: repeated scan failure counter used to suppress
  broken legacy rows.
- `last_scan_error_code`, `last_scan_error_message`, `last_scan_failed_at`:
  sanitized last failure metadata for observability.
- `scan_group_key`: stable group key for Telegram commands, for example
  `oppo-find-x8`.
- `scan_group_name`: display group, for example `OPPO Find X8`.
- `active_track`: current preferred track, one of `A`, `C`, `F`, `H`.
- `bootstrap_done`: boolean.
- `manual_override`: boolean.
- `source`: text, for example `oxygen_updater`, `manual`, or `seed`.
- `created_at`: timestamp.
- `updated_at`: timestamp.

Constraints:

- unique `product_model`.
- `brand` must be one of the supported brands.
- `active_track` must be one of the supported tracks.

Catalog importers keep devices searchable but do not automatically opt new
rows into `scan_enabled=true`; operators enable groups or variants through
Telegram admin commands.

Scheduled workers require both `scan_enabled=true` and
`scan_eligibility='active_scan'`. Rows missing manifest codes are migrated to
`invalid_for_scan`; rows intentionally kept for archive browsing remain
`archive_only`.

## ota_releases

Stores discovered OTA releases.

Important columns:

- `id`: UUID primary key.
- `device_id`: foreign key to `devices`.
- `brand`: denormalized brand for filtering.
- `product_model`: denormalized product model.
- `manifest_code`: manifest code used for discovery.
- `ota_track`: track used for discovery.
- `rui_version`: OS/RUI candidate that returned the result.
- `real_ota_version`: OTA version returned by OPlus.
- `real_version_name`: displayed version returned by OPlus.
- `computed_ota_version`: normalized version built by the app.
- `version_type_id`: OPlus version type.
- `about_update_url`: update notes URL.
- `download_url`: OTA package URL.
- `md5`: optional package checksum.
- `file_size`: optional package size.
- `security_patch`: optional security patch value.
- `raw_response`: optional JSONB.
- `source`: `live_provider` or archive source such as `lsctool_archive`.
- `region_code`: region label from archive sources, for example `CN`.
- `release_type`: `official` or `beta`.
- `published_at`: source-published timestamp when available.
- `source_last_event_kind`: optional source event marker.
- `source_last_event_at`: optional source event timestamp.
- `discovered_by`: `manual`, `worker`, or `import`.
- `discovered_at`: timestamp.
- `last_seen_at`: timestamp updated when an already-known release is observed
  again.

Constraints:

- unique release key on `product_model`, `manifest_code`, `real_ota_version`, and `download_url`.

## edl_roms

Stores third-party supplemental EDL ROM archive links separately from OTA
release rows.

Important columns:

- `id`: UUID primary key.
- `brand`: `oppo`, `realme`, or `oneplus`.
- `product_model`: device model, for example `PKB110` or `RMX3800`.
- `device_name`: optional display name from the source catalog.
- `region_code`: source region label, for example `CN`.
- `version_name`: source ROM version label.
- `build_date`: timestamp parsed from the source build date when available.
- `download_url`: direct ZIP link as supplied by the archive source.
- `source`: currently `lsctool_edl`.
- `source_updated_at`: timestamp from the source archive when available.
- `raw_response`: sanitized raw source row for audit/debugging.

Constraints:

- unique EDL key on `product_model`, `version_name`, and `download_url`.

## scan_runs

Stores one scheduled scan execution.

Important columns:

- `id`: UUID primary key.
- `status`: `queued`, `running`, `completed`, `failed`, or `cancelled`.
- `cycle_day`: integer from `0` to `6`.
- `started_at`: timestamp.
- `finished_at`: timestamp.
- `total_tasks`: integer.
- `completed_tasks`: integer.
- `failed_tasks`: integer.
- `new_releases`: integer.
- `error_message`: nullable text.

## scan_tasks

Stores per-device scan tasks.

Important columns:

- `id`: UUID primary key.
- `scan_run_id`: foreign key to `scan_runs`.
- `device_id`: foreign key to `devices`.
- `status`: `queued`, `running`, `completed`, `failed`, or `skipped`.
- `attempt_count`: integer.
- `tracks_checked`: text array.
- `rui_candidates_checked`: integer array.
- `found_release_id`: nullable foreign key to `ota_releases`.
- `error_code`: nullable text.
- `error_message`: nullable text.
- `started_at`: timestamp.
- `finished_at`: timestamp.

Constraints:

- one task per scan run and device.

## telegram_targets

Maps a brand to a Telegram forum topic.

Important columns:

- `id`: UUID primary key.
- `brand`: `oppo`, `realme`, or `oneplus`.
- `chat_id`: Telegram supergroup ID.
- `message_thread_id`: Telegram topic ID.
- `enabled`: boolean.
- `created_at`: timestamp.
- `updated_at`: timestamp.

Constraints:

- unique `brand`.

## telegram_notifications

Tracks notification delivery for releases.

Important columns:

- `id`: UUID primary key.
- `release_id`: foreign key to `ota_releases`.
- `telegram_target_id`: foreign key to `telegram_targets`.
- `status`: `queued`, `sending`, `sent`, or `failed`.
- `telegram_message_id`: nullable integer.
- `error_message`: nullable text.
- `created_at`: timestamp.
- `sent_at`: nullable timestamp.
- `attempt_count`, `last_attempt_at`, `next_attempt_at`: retry and atomic-claim
  state.

Constraints:

- unique `release_id` and `telegram_target_id`.

## resolve_requests

Stores resolver request history.

Important columns:

- `id`: UUID primary key.
- `source`: `web`, `telegram`, or `internal`.
- `telegram_user_id`: nullable bigint.
- `telegram_chat_id`: nullable bigint.
- `input_url`: text.
- `resolved_url`: nullable text.
- `status`: `success`, `failed`, or `blocked`.
- `error_code`: nullable text.
- `error_message`: nullable text.
- `expires_at`: nullable timestamp.
- `created_at`: timestamp.

The app writes this table only after the resolver proof gate is enabled.

## admin_users

Maps an authenticated Supabase user UUID to enabled operator/admin access.
FastAPI reads this table server-side after verifying the caller's Auth JWT;
browser clients have no table permissions.

## public_action_requests

Stores `ota` and `resolve` quota events with a salted `actor_hash`, hashed
normalized `query_key`, and timestamp. It never stores raw IP addresses,
Turnstile tokens, IMEI values, or GUID values.

## device_catalog_imports

Stores catalog import history.

Important columns:

- `id`: UUID primary key.
- `source`: text, usually `oxygen_updater`.
- `status`: `running`, `completed`, or `failed`.
- `fetched_count`: integer.
- `upserted_count`: integer.
- `disabled_count`: integer.
- `error_message`: nullable text.
- `started_at`: timestamp.
- `finished_at`: timestamp.

## Recommended Indexes

- `devices(brand)`
- `devices(product_model)`
- `devices(catalog_visible)`
- `devices(scan_enabled)`
- `devices(scan_eligibility, scan_enabled)`
- `devices(scan_group_key)`
- `devices(scan_group_key, scan_eligibility, scan_enabled)`
- `devices(name) WHERE scan_enabled AND scan_eligibility='active_scan' AND manifest_code IS NOT NULL` (partial; phase-2)
- `devices(scan_group_key) WHERE scan_enabled AND scan_eligibility='active_scan' AND manifest_code IS NOT NULL` (partial; phase-2)
- `ota_releases(brand, discovered_at desc)`
- `ota_releases(product_model, discovered_at desc)`
- `edl_roms(product_model, build_date desc)`
- `scan_tasks(status)`
- `telegram_notifications(status)`
- `resolve_requests(created_at desc)`
- `public_action_requests(action, actor_hash, created_at desc)`
