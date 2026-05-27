-- Feature-gated resolver request history. Enable the endpoint only after live proof.

create table if not exists public.resolve_requests (
    id uuid primary key default gen_random_uuid(),
    source text not null check (source in ('web', 'telegram', 'internal')),
    telegram_user_id bigint,
    telegram_chat_id bigint,
    input_url text,
    resolved_url text,
    status text not null check (status in ('success', 'failed', 'blocked')),
    error_code text,
    error_message text,
    expires_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists resolve_requests_created_at_idx
    on public.resolve_requests(created_at desc);

alter table public.resolve_requests enable row level security;
revoke all on table public.resolve_requests from anon, authenticated;
grant select, insert, update, delete on table public.resolve_requests to service_role;
