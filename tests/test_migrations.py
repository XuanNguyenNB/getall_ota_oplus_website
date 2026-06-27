from pathlib import Path


def test_phase1_migration_contains_required_tables_and_constraints():
    sql = Path("supabase/migrations/202605260001_phase1_backend_core.sql").read_text()

    assert "create table if not exists public.devices" in sql
    assert "create table if not exists public.ota_releases" in sql
    assert "devices_product_model_unique" in sql
    assert "ota_releases_unique_release" in sql
    assert "product_model" in sql
    assert "manifest_code" in sql
    assert "real_ota_version" in sql
    assert "download_url" in sql


def test_phase3_migration_contains_scanner_and_notification_tables():
    sql = Path("supabase/migrations/202605260002_phase3_scheduled_scanner.sql").read_text()

    assert "create table if not exists public.scan_runs" in sql
    assert "create table if not exists public.scan_tasks" in sql
    assert "create table if not exists public.telegram_targets" in sql
    assert "create table if not exists public.telegram_notifications" in sql
    assert "cycle_day integer not null check (cycle_day between 0 and 6)" in sql
    assert "scan_tasks_one_device_per_run" in sql
    assert "telegram_targets_brand_unique" in sql
    assert "telegram_notifications_release_target_unique" in sql
    assert "release_id" in sql
    assert "telegram_target_id" in sql


def test_live_runtime_migration_contains_security_catalog_and_atomic_rpcs():
    sql = Path("supabase/migrations/202605260003_live_runtime.sql").read_text()

    assert "create table if not exists public.device_catalog_imports" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.devices from anon, authenticated" in sql
    assert "grant select, insert, update, delete on table public.devices to service_role" in sql
    assert "function public.claim_scan_task" in sql
    assert "for update skip locked" in sql
    assert "function public.upsert_ota_release" in sql
    assert "function public.complete_scan_task" in sql
    assert "function public.enqueue_telegram_notification" in sql


def test_public_gateway_migration_contains_admin_and_atomic_quota_controls():
    sql = Path("supabase/migrations/202605260004_public_gateway.sql").read_text()

    assert "create table if not exists public.admin_users" in sql
    assert "references auth.users" in sql
    assert "create table if not exists public.public_action_requests" in sql
    assert "actor_hash text not null" in sql
    assert "function public.claim_public_action" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "revoke all on table public.admin_users from anon, authenticated" in sql


def test_telegram_delivery_migration_contains_retryable_atomic_queue_rpcs():
    sql = Path("supabase/migrations/202605260005_telegram_delivery.sql").read_text()

    assert "attempt_count integer" in sql
    assert "'sending'" in sql
    assert "function public.claim_telegram_notification" in sql
    assert "for update of n skip locked" in sql
    assert "function public.complete_telegram_notification" in sql
    assert "function public.fail_telegram_notification" in sql


def test_nullable_telegram_target_topics_migration_supports_channel_targets():
    sql = Path("supabase/migrations/202605270006_nullable_telegram_target_topics.sql").read_text()

    assert "alter column message_thread_id drop not null" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_scan_eligibility_migration_adds_failure_metadata_and_indexes():
    sql = Path("supabase/migrations/202605270007_scan_eligibility.sql").read_text()

    assert "add column if not exists scan_eligibility text" in sql
    assert "add column if not exists consecutive_failures integer" in sql
    assert "last_scan_error_code text" in sql
    assert "last_scan_failed_at timestamptz" in sql
    assert "devices_scan_eligibility_check" in sql
    for state in ("active_scan", "archive_only", "invalid_for_scan"):
        assert state in sql
    assert "where manifest_code is null" in sql
    assert "devices_scan_group_eligibility_idx" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_resolver_migration_is_server_only_history_storage():
    sql = Path("supabase/migrations/202605260006_resolver.sql").read_text()

    assert "create table if not exists public.resolve_requests" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.resolve_requests from anon, authenticated" in sql


def test_scanner_recovery_migration_restores_completion_and_stale_claim_support():
    sql = Path("supabase/migrations/202605270001_scanner_rpc_recovery.sql").read_text()

    assert "function public.complete_scan_task" in sql
    assert "function public.claim_scan_task" in sql
    assert "interval '15 minutes'" in sql
    assert "for update skip locked" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_full_manifest_map_migration_expands_constraints_and_backfills_catalog_rows():
    sql = Path("supabase/migrations/202605270002_full_manifest_map.sql").read_text()

    assert "drop constraint if exists devices_manifest_code_shape" in sql
    assert "drop constraint if exists ota_releases_manifest_code_shape" in sql
    for code in (
        "1A",
        "1E",
        "2C",
        "33",
        "38",
        "3B",
        "3E",
        "75",
        "7B",
        "82",
        "83",
        "8D",
        "9A",
        "9E",
    ):
        assert f"'{code}'" in sql
    assert "where manual_override = false" in sql
    assert "and manifest_code is null" in sql


def test_release_archive_metadata_migration_extends_releases_and_upsert_rpc():
    sql = Path("supabase/migrations/202605270003_release_archive_metadata.sql").read_text()

    assert "add column if not exists source text" in sql
    assert "add column if not exists region_code text" in sql
    assert "add column if not exists release_type text" in sql
    assert "add column if not exists published_at timestamptz" in sql
    assert "ota_releases_release_type_check" in sql
    assert "rui_version between 1 and 99" in sql
    assert "p_source text default 'live_provider'" in sql
    assert "p_region_code text default null" in sql
    assert "p_release_type text default 'official'" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_edl_rom_archive_migration_adds_server_only_archive_table():
    sql = Path("supabase/migrations/202605270004_edl_rom_archive.sql").read_text()

    assert "create table if not exists public.edl_roms" in sql
    assert "product_model text not null" in sql
    assert "version_name text not null" in sql
    assert "download_url text not null" in sql
    assert "edl_roms_unique_rom unique (product_model, version_name, download_url)" in sql
    assert "edl_roms_product_build_idx" in sql
    assert "alter table public.edl_roms enable row level security" in sql
    assert "revoke all on table public.edl_roms from anon, authenticated" in sql
    assert "grant select, insert, update, delete on table public.edl_roms to service_role" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_smart_scan_groups_migration_separates_visibility_from_scan_allowlist():
    sql = Path("supabase/migrations/202605270005_smart_scan_groups.sql").read_text()

    assert "add column if not exists catalog_visible boolean" in sql
    assert "add column if not exists scan_group_key text" in sql
    assert "add column if not exists scan_group_name text" in sql
    assert "function public.infer_device_scan_group_name" in sql
    assert "function public.infer_device_scan_group_key" in sql
    assert "devices_scan_group_key_idx" in sql
    assert "devices_scan_group_scan_enabled_idx" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_scan_eligibility_index_migration_creates_partial_indexes_for_active_scan_slice():
    """The Phase 2 tech-debt overhaul pushes the (scan_enabled,
    scan_eligibility, manifest_code) filter down to SQL. Without a
    backing partial index the active-scan slice would still scan the full
    devices table at large catalog sizes; this migration introduces it."""

    sql = Path("supabase/migrations/202606270001_scan_eligibility_index.sql").read_text()

    assert "devices_active_scan_partial_idx" in sql
    assert "devices_active_scan_group_partial_idx" in sql
    assert "where scan_enabled = true" in sql.lower()
    assert "scan_eligibility = 'active_scan'" in sql
    assert "manifest_code is not null" in sql.lower()


def test_scan_run_counters_recompute_migration_introduces_idempotent_new_release_column():
    """scan_runs.new_releases must be derivable from tasks so retries
    cannot leak stale +1 increments. The migration adds the
    found_new_release column on the task, backfills it for historical
    completions, and rewrites complete_scan_task to recompute the
    counter from that column."""

    sql = Path("supabase/migrations/202606270002_scan_run_counters_recompute.sql").read_text()

    assert "found_new_release boolean not null default false" in sql.lower()
    assert "function public.complete_scan_task" in sql
    # The new implementation must select-count from tasks instead of
    # incrementing the run counter directly.
    assert "select count(*)" in sql.lower()
    assert "new_releases = v_new_count" in sql
    assert "notify pgrst, 'reload schema'" in sql
