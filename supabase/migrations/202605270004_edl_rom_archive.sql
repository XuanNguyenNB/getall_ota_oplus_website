-- EDL ROM supplemental archive metadata.

create table if not exists public.edl_roms (
    id uuid primary key default gen_random_uuid(),
    brand text not null check (brand in ('oppo', 'realme', 'oneplus')),
    product_model text not null,
    device_name text,
    region_code text,
    version_name text not null,
    build_date timestamptz,
    download_url text not null,
    source text not null default 'lsctool_edl',
    source_updated_at timestamptz,
    raw_response jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint edl_roms_unique_rom unique (product_model, version_name, download_url)
);

create index if not exists edl_roms_product_build_idx
    on public.edl_roms(product_model, build_date desc);

create index if not exists edl_roms_region_idx
    on public.edl_roms(region_code);

create index if not exists edl_roms_source_idx
    on public.edl_roms(source);

alter table public.edl_roms enable row level security;

revoke all on table public.edl_roms from anon, authenticated;
grant select, insert, update, delete on table public.edl_roms to service_role;

notify pgrst, 'reload schema';
