alter table public.devices
    add column if not exists scan_eligibility text not null default 'archive_only',
    add column if not exists consecutive_failures integer not null default 0,
    add column if not exists last_scan_error_code text,
    add column if not exists last_scan_error_message text,
    add column if not exists last_scan_failed_at timestamptz;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'devices_scan_eligibility_check'
    ) then
        alter table public.devices
            add constraint devices_scan_eligibility_check
            check (scan_eligibility in ('active_scan', 'archive_only', 'invalid_for_scan'));
    end if;
end $$;

update public.devices
set scan_eligibility = case
    when manifest_code is null then 'invalid_for_scan'
    when scan_enabled then 'active_scan'
    else 'archive_only'
end,
    consecutive_failures = coalesce(consecutive_failures, 0);

update public.devices
set scan_enabled = false
where manifest_code is null;

create index if not exists devices_scan_eligibility_idx
    on public.devices (scan_eligibility, scan_enabled);

create index if not exists devices_scan_group_eligibility_idx
    on public.devices (scan_group_key, scan_eligibility, scan_enabled);

notify pgrst, 'reload schema';
