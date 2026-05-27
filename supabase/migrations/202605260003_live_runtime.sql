-- Live Phase 1-3 runtime support: catalog history, server-only Data API access,
-- and RPC-backed race-sensitive scanner persistence operations.

create table if not exists public.device_catalog_imports (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    status text not null check (status in ('running', 'completed', 'failed')),
    fetched_count integer not null default 0 check (fetched_count >= 0),
    upserted_count integer not null default 0 check (upserted_count >= 0),
    disabled_count integer not null default 0 check (disabled_count >= 0),
    error_message text,
    started_at timestamptz not null default now(),
    finished_at timestamptz
);

create index if not exists device_catalog_imports_started_at_idx
    on public.device_catalog_imports(started_at desc);

alter table public.devices enable row level security;
alter table public.ota_releases enable row level security;
alter table public.scan_runs enable row level security;
alter table public.scan_tasks enable row level security;
alter table public.telegram_targets enable row level security;
alter table public.telegram_notifications enable row level security;
alter table public.device_catalog_imports enable row level security;

revoke all on table public.devices from anon, authenticated;
revoke all on table public.ota_releases from anon, authenticated;
revoke all on table public.scan_runs from anon, authenticated;
revoke all on table public.scan_tasks from anon, authenticated;
revoke all on table public.telegram_targets from anon, authenticated;
revoke all on table public.telegram_notifications from anon, authenticated;
revoke all on table public.device_catalog_imports from anon, authenticated;

grant select, insert, update, delete on table public.devices to service_role;
grant select, insert, update, delete on table public.ota_releases to service_role;
grant select, insert, update, delete on table public.scan_runs to service_role;
grant select, insert, update, delete on table public.scan_tasks to service_role;
grant select, insert, update, delete on table public.telegram_targets to service_role;
grant select, insert, update, delete on table public.telegram_notifications to service_role;
grant select, insert, update, delete on table public.device_catalog_imports to service_role;

create or replace function public.claim_scan_task(p_scan_run_id uuid)
returns setof public.scan_tasks
language plpgsql
security invoker
set search_path = public
as $$
begin
    return query
    update public.scan_tasks
       set status = 'running',
           attempt_count = attempt_count + 1,
           started_at = coalesce(started_at, now()),
           finished_at = null
     where id = (
        select id
          from public.scan_tasks
         where scan_run_id = p_scan_run_id
           and status = 'queued'
         order by id
         for update skip locked
         limit 1
     )
    returning *;
end;
$$;

create or replace function public.upsert_ota_release(
    p_brand text,
    p_product_model text,
    p_manifest_code text,
    p_ota_track text,
    p_rui_version integer,
    p_real_ota_version text,
    p_real_version_name text,
    p_computed_ota_version text,
    p_version_type_id text,
    p_about_update_url text,
    p_download_url text,
    p_md5 text,
    p_file_size bigint,
    p_security_patch text,
    p_raw_response jsonb,
    p_discovered_by text
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_release public.ota_releases%rowtype;
    v_is_new boolean := false;
begin
    insert into public.ota_releases (
        device_id, brand, product_model, manifest_code, ota_track, rui_version,
        real_ota_version, real_version_name, computed_ota_version,
        version_type_id, about_update_url, download_url, md5, file_size,
        security_patch, raw_response, discovered_by
    ) values (
        (select id from public.devices where product_model = p_product_model),
        p_brand, p_product_model, p_manifest_code, p_ota_track, p_rui_version,
        p_real_ota_version, p_real_version_name, p_computed_ota_version,
        p_version_type_id, p_about_update_url, p_download_url, p_md5, p_file_size,
        p_security_patch, p_raw_response, p_discovered_by
    )
    on conflict (product_model, manifest_code, real_ota_version, download_url)
    do nothing
    returning * into v_release;

    if found then
        v_is_new := true;
    else
        update public.ota_releases
           set last_seen_at = now(),
               device_id = coalesce(
                   device_id,
                   (select id from public.devices where product_model = p_product_model)
               )
         where product_model = p_product_model
           and manifest_code = p_manifest_code
           and real_ota_version = p_real_ota_version
           and download_url = p_download_url
        returning * into v_release;
    end if;

    return jsonb_build_object('release', to_jsonb(v_release), 'is_new', v_is_new);
end;
$$;

create or replace function public.complete_scan_task(
    p_task_id uuid,
    p_tracks_checked text[],
    p_rui_candidates_checked integer[],
    p_found_release_id uuid,
    p_new_release boolean
)
returns setof public.scan_tasks
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_task public.scan_tasks%rowtype;
begin
    update public.scan_tasks
       set status = 'completed',
           tracks_checked = p_tracks_checked,
           rui_candidates_checked = p_rui_candidates_checked,
           found_release_id = p_found_release_id,
           error_code = null,
           error_message = null,
           finished_at = now()
     where id = p_task_id
    returning * into v_task;

    if p_new_release then
        update public.scan_runs
           set new_releases = new_releases + 1
         where id = v_task.scan_run_id;
    end if;

    return next v_task;
end;
$$;

create or replace function public.enqueue_telegram_notification(
    p_release_id uuid,
    p_telegram_target_id uuid
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_notification public.telegram_notifications%rowtype;
    v_is_new boolean := false;
begin
    insert into public.telegram_notifications (release_id, telegram_target_id, status)
    values (p_release_id, p_telegram_target_id, 'queued')
    on conflict (release_id, telegram_target_id) do nothing
    returning * into v_notification;

    if found then
        v_is_new := true;
    else
        select *
          into v_notification
          from public.telegram_notifications
         where release_id = p_release_id
           and telegram_target_id = p_telegram_target_id;
    end if;

    return jsonb_build_object('notification', to_jsonb(v_notification), 'is_new', v_is_new);
end;
$$;

revoke all on function public.claim_scan_task(uuid) from public, anon, authenticated;
revoke all on function public.upsert_ota_release(
    text, text, text, text, integer, text, text, text, text, text, text, text, bigint, text, jsonb, text
) from public, anon, authenticated;
revoke all on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    from public, anon, authenticated;
revoke all on function public.enqueue_telegram_notification(uuid, uuid) from public, anon, authenticated;

grant execute on function public.claim_scan_task(uuid) to service_role;
grant execute on function public.upsert_ota_release(
    text, text, text, text, integer, text, text, text, text, text, text, text, bigint, text, jsonb, text
) to service_role;
grant execute on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    to service_role;
grant execute on function public.enqueue_telegram_notification(uuid, uuid) to service_role;
