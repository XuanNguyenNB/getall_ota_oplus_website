-- Phase 1 backend core tables for devices and manual OTA releases.

create extension if not exists pgcrypto;

create table if not exists public.devices (
    id uuid primary key default gen_random_uuid(),
    catalog_id integer,
    brand text not null check (brand in ('oppo', 'realme', 'oneplus')),
    name text not null,
    product_model text not null,
    manifest_code text,
    scan_enabled boolean not null default true,
    active_track text not null default 'C' check (active_track in ('A', 'C', 'F', 'H')),
    bootstrap_done boolean not null default false,
    manual_override boolean not null default false,
    source text not null default 'manual',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint devices_product_model_unique unique (product_model),
    constraint devices_manifest_code_shape check (
        manifest_code is null or manifest_code in ('00', 'A4', 'A5', 'A6', 'A7', '1B', '37', '39', '3C', '44', '51', '97')
    )
);

create table if not exists public.ota_releases (
    id uuid primary key default gen_random_uuid(),
    device_id uuid references public.devices(id) on delete set null,
    brand text not null check (brand in ('oppo', 'realme', 'oneplus')),
    product_model text not null,
    manifest_code text not null,
    ota_track text not null check (ota_track in ('A', 'C', 'F', 'H')),
    rui_version integer not null check (rui_version between 1 and 9),
    real_ota_version text not null,
    real_version_name text not null,
    computed_ota_version text not null,
    version_type_id text not null,
    about_update_url text,
    download_url text not null,
    md5 text,
    file_size bigint,
    security_patch text,
    raw_response jsonb,
    discovered_by text not null check (discovered_by in ('manual', 'worker', 'import')),
    discovered_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    constraint ota_releases_manifest_code_shape check (
        manifest_code in ('00', 'A4', 'A5', 'A6', 'A7', '1B', '37', '39', '3C', '44', '51', '97')
    ),
    constraint ota_releases_unique_release unique (
        product_model,
        manifest_code,
        real_ota_version,
        download_url
    )
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists devices_set_updated_at on public.devices;
create trigger devices_set_updated_at
before update on public.devices
for each row
execute function public.set_updated_at();

create index if not exists devices_brand_idx on public.devices(brand);
create index if not exists devices_product_model_idx on public.devices(product_model);
create index if not exists devices_scan_enabled_idx on public.devices(scan_enabled);
create index if not exists ota_releases_brand_discovered_at_idx on public.ota_releases(brand, discovered_at desc);
create index if not exists ota_releases_product_model_discovered_at_idx on public.ota_releases(product_model, discovered_at desc);
create index if not exists ota_releases_manifest_code_idx on public.ota_releases(manifest_code);
