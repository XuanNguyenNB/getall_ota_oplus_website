-- Release archive metadata for imported historical OTA rows.

alter table public.ota_releases
    add column if not exists source text not null default 'live_provider',
    add column if not exists region_code text,
    add column if not exists release_type text not null default 'official',
    add column if not exists published_at timestamptz,
    add column if not exists source_last_event_kind text,
    add column if not exists source_last_event_at timestamptz;

update public.ota_releases
   set source = coalesce(nullif(source, ''), 'live_provider'),
       release_type = coalesce(nullif(release_type, ''), 'official');

alter table public.ota_releases
    drop constraint if exists ota_releases_release_type_check,
    add constraint ota_releases_release_type_check
        check (release_type in ('official', 'beta'));

alter table public.ota_releases
    drop constraint if exists ota_releases_rui_version_check,
    add constraint ota_releases_rui_version_check
        check (rui_version between 1 and 99);

create index if not exists ota_releases_region_type_published_idx
    on public.ota_releases(region_code, release_type, published_at desc);

create index if not exists ota_releases_source_idx
    on public.ota_releases(source);

drop function if exists public.upsert_ota_release(
    text, text, text, text, integer, text, text, text, text, text, text, text,
    bigint, text, jsonb, text
);

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
    p_discovered_by text,
    p_source text default 'live_provider',
    p_region_code text default null,
    p_release_type text default 'official',
    p_published_at timestamptz default null,
    p_source_last_event_kind text default null,
    p_source_last_event_at timestamptz default null
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
        security_patch, raw_response, discovered_by, source, region_code,
        release_type, published_at, source_last_event_kind, source_last_event_at
    ) values (
        (select id from public.devices where product_model = p_product_model),
        p_brand, p_product_model, p_manifest_code, p_ota_track, p_rui_version,
        p_real_ota_version, p_real_version_name, p_computed_ota_version,
        p_version_type_id, p_about_update_url, p_download_url, p_md5, p_file_size,
        p_security_patch, p_raw_response, p_discovered_by,
        coalesce(nullif(p_source, ''), 'live_provider'), upper(nullif(p_region_code, '')),
        coalesce(nullif(p_release_type, ''), 'official'), p_published_at,
        nullif(p_source_last_event_kind, ''), p_source_last_event_at
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
               ),
               region_code = coalesce(region_code, upper(nullif(p_region_code, ''))),
               published_at = coalesce(published_at, p_published_at),
               source_last_event_kind = coalesce(
                   source_last_event_kind,
                   nullif(p_source_last_event_kind, '')
               ),
               source_last_event_at = coalesce(source_last_event_at, p_source_last_event_at),
               raw_response = coalesce(raw_response, p_raw_response)
         where product_model = p_product_model
           and manifest_code = p_manifest_code
           and real_ota_version = p_real_ota_version
           and download_url = p_download_url
        returning * into v_release;
    end if;

    return jsonb_build_object('release', to_jsonb(v_release), 'is_new', v_is_new);
end;
$$;

revoke all on function public.upsert_ota_release(
    text, text, text, text, integer, text, text, text, text, text, text, text,
    bigint, text, jsonb, text, text, text, text, timestamptz, text, timestamptz
) from public, anon, authenticated;

grant execute on function public.upsert_ota_release(
    text, text, text, text, integer, text, text, text, text, text, text, text,
    bigint, text, jsonb, text, text, text, text, timestamptz, text, timestamptz
) to service_role;

notify pgrst, 'reload schema';
