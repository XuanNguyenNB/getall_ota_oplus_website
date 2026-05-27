-- Public controlled-access support: authenticated admins and hashed action quotas.

create table if not exists public.admin_users (
    user_id uuid primary key references auth.users(id) on delete cascade,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.public_action_requests (
    id uuid primary key default gen_random_uuid(),
    action text not null check (action in ('ota', 'resolve')),
    actor_hash text not null,
    query_key text not null,
    created_at timestamptz not null default now()
);

drop trigger if exists admin_users_set_updated_at on public.admin_users;
create trigger admin_users_set_updated_at
before update on public.admin_users
for each row execute function public.set_updated_at();

create index if not exists public_action_requests_actor_action_created_idx
    on public.public_action_requests(action, actor_hash, created_at desc);
create index if not exists public_action_requests_query_created_idx
    on public.public_action_requests(action, actor_hash, query_key, created_at desc);

alter table public.admin_users enable row level security;
alter table public.public_action_requests enable row level security;

revoke all on table public.admin_users from anon, authenticated;
revoke all on table public.public_action_requests from anon, authenticated;
grant select, insert, update, delete on table public.admin_users to service_role;
grant select, insert, delete on table public.public_action_requests to service_role;

create or replace function public.claim_public_action(
    p_action text,
    p_actor_hash text,
    p_query_key text,
    p_limit integer,
    p_window_seconds integer,
    p_cooldown_seconds integer
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_now timestamptz := now();
    v_oldest timestamptz;
    v_latest_query timestamptz;
    v_retry integer;
begin
    perform pg_advisory_xact_lock(hashtextextended(p_action || ':' || p_actor_hash, 0));

    select min(created_at)
      into v_oldest
      from (
          select created_at
            from public.public_action_requests
           where action = p_action
             and actor_hash = p_actor_hash
             and created_at >= v_now - make_interval(secs => p_window_seconds)
           order by created_at desc
           limit p_limit
      ) recent;

    if (
        select count(*)
          from public.public_action_requests
         where action = p_action
           and actor_hash = p_actor_hash
           and created_at >= v_now - make_interval(secs => p_window_seconds)
    ) >= p_limit then
        v_retry := greatest(1, ceil(extract(epoch from (
            v_oldest + make_interval(secs => p_window_seconds) - v_now
        )))::integer);
        return jsonb_build_object('allowed', false, 'retry_after_seconds', v_retry);
    end if;

    if p_cooldown_seconds > 0 then
        select max(created_at)
          into v_latest_query
          from public.public_action_requests
         where action = p_action
           and actor_hash = p_actor_hash
           and query_key = p_query_key;
        if v_latest_query is not null
           and v_latest_query + make_interval(secs => p_cooldown_seconds) > v_now then
            v_retry := greatest(1, ceil(extract(epoch from (
                v_latest_query + make_interval(secs => p_cooldown_seconds) - v_now
            )))::integer);
            return jsonb_build_object('allowed', false, 'retry_after_seconds', v_retry);
        end if;
    end if;

    insert into public.public_action_requests(action, actor_hash, query_key)
    values (p_action, p_actor_hash, p_query_key);
    return jsonb_build_object('allowed', true, 'retry_after_seconds', 0);
end;
$$;

revoke all on function public.claim_public_action(text, text, text, integer, integer, integer)
    from public, anon, authenticated;
grant execute on function public.claim_public_action(text, text, text, integer, integer, integer)
    to service_role;
