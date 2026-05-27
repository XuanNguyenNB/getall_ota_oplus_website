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

## devices

Stores normalized device catalog entries.

Important columns:

- `id`: UUID primary key.
- `catalog_id`: integer from Oxygen Updater, nullable for manual devices.
- `brand`: text, one of `oppo`, `realme`, `oneplus`.
- `name`: display name.
- `product_model`: OPlus product model, for example `RMX3301` or `CPH2841TH`.
- `manifest_code`: manifest code, for example `1B`, `39`, `A7`, `97`.
- `scan_enabled`: boolean.
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
- `devices(scan_enabled)`
- `ota_releases(brand, discovered_at desc)`
- `ota_releases(product_model, discovered_at desc)`
- `scan_tasks(status)`
- `telegram_notifications(status)`
- `resolve_requests(created_at desc)`
- `public_action_requests(action, actor_hash, created_at desc)`
