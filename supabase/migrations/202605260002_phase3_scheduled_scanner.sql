-- Phase 3 scheduled scanner and Telegram notification queue tables.

create table if not exists public.scan_runs (
    id uuid primary key default gen_random_uuid(),
    status text not null check (status in ('queued', 'running', 'completed', 'failed', 'cancelled')),
    cycle_day integer not null check (cycle_day between 0 and 6),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    total_tasks integer not null default 0 check (total_tasks >= 0),
    completed_tasks integer not null default 0 check (completed_tasks >= 0),
    failed_tasks integer not null default 0 check (failed_tasks >= 0),
    new_releases integer not null default 0 check (new_releases >= 0),
    error_message text
);

create table if not exists public.scan_tasks (
    id uuid primary key default gen_random_uuid(),
    scan_run_id uuid not null references public.scan_runs(id) on delete cascade,
    device_id uuid not null references public.devices(id) on delete cascade,
    status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'failed', 'skipped')),
    attempt_count integer not null default 0 check (attempt_count >= 0),
    tracks_checked text[] not null default '{}',
    rui_candidates_checked integer[] not null default '{}',
    found_release_id uuid references public.ota_releases(id) on delete set null,
    error_code text,
    error_message text,
    started_at timestamptz,
    finished_at timestamptz,
    constraint scan_tasks_one_device_per_run unique (scan_run_id, device_id)
);

create table if not exists public.telegram_targets (
    id uuid primary key default gen_random_uuid(),
    brand text not null check (brand in ('oppo', 'realme', 'oneplus')),
    chat_id bigint not null,
    message_thread_id integer not null,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint telegram_targets_brand_unique unique (brand)
);

create table if not exists public.telegram_notifications (
    id uuid primary key default gen_random_uuid(),
    release_id uuid not null references public.ota_releases(id) on delete cascade,
    telegram_target_id uuid not null references public.telegram_targets(id) on delete cascade,
    status text not null default 'queued' check (status in ('queued', 'sent', 'failed')),
    telegram_message_id bigint,
    error_message text,
    created_at timestamptz not null default now(),
    sent_at timestamptz,
    constraint telegram_notifications_release_target_unique unique (
        release_id,
        telegram_target_id
    )
);

drop trigger if exists telegram_targets_set_updated_at on public.telegram_targets;
create trigger telegram_targets_set_updated_at
before update on public.telegram_targets
for each row
execute function public.set_updated_at();

create index if not exists scan_runs_started_at_idx on public.scan_runs(started_at desc);
create index if not exists scan_tasks_status_idx on public.scan_tasks(status);
create index if not exists scan_tasks_scan_run_status_idx on public.scan_tasks(scan_run_id, status);
create index if not exists telegram_notifications_status_idx on public.telegram_notifications(status);
