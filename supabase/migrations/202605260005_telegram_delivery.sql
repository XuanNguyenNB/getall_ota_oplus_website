-- Telegram Bot API delivery queue state and atomic delivery RPCs.

alter table public.telegram_notifications
    add column if not exists attempt_count integer not null default 0 check (attempt_count >= 0),
    add column if not exists last_attempt_at timestamptz,
    add column if not exists next_attempt_at timestamptz;

alter table public.telegram_notifications
    drop constraint if exists telegram_notifications_status_check;
alter table public.telegram_notifications
    add constraint telegram_notifications_status_check
    check (status in ('queued', 'sending', 'sent', 'failed'));

create index if not exists telegram_notifications_delivery_idx
    on public.telegram_notifications(status, next_attempt_at, created_at);

create or replace function public.claim_telegram_notification(p_max_attempts integer)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_notification public.telegram_notifications%rowtype;
    v_release public.ota_releases%rowtype;
    v_target public.telegram_targets%rowtype;
begin
    update public.telegram_notifications
       set status = 'sending',
           attempt_count = attempt_count + 1,
           last_attempt_at = now(),
           next_attempt_at = null
     where id = (
         select n.id
           from public.telegram_notifications n
           join public.telegram_targets t on t.id = n.telegram_target_id
          where t.enabled = true
            and n.attempt_count < p_max_attempts
            and (
                n.status = 'queued'
                or (n.status = 'failed' and n.next_attempt_at <= now())
                or (n.status = 'sending' and n.last_attempt_at <= now() - interval '15 minutes')
            )
          order by n.created_at
          for update of n skip locked
          limit 1
     )
    returning * into v_notification;

    if not found then
        return '{}'::jsonb;
    end if;

    select * into v_release from public.ota_releases where id = v_notification.release_id;
    select * into v_target from public.telegram_targets where id = v_notification.telegram_target_id;
    return jsonb_build_object(
        'notification', to_jsonb(v_notification),
        'release', to_jsonb(v_release),
        'target', to_jsonb(v_target)
    );
end;
$$;

create or replace function public.complete_telegram_notification(
    p_notification_id uuid,
    p_telegram_message_id bigint
)
returns setof public.telegram_notifications
language sql
security invoker
set search_path = public
as $$
    update public.telegram_notifications
       set status = 'sent',
           telegram_message_id = p_telegram_message_id,
           error_message = null,
           sent_at = now(),
           next_attempt_at = null
     where id = p_notification_id
    returning *;
$$;

create or replace function public.fail_telegram_notification(
    p_notification_id uuid,
    p_error_message text,
    p_retry_seconds integer
)
returns setof public.telegram_notifications
language sql
security invoker
set search_path = public
as $$
    update public.telegram_notifications
       set status = 'failed',
           error_message = p_error_message,
           next_attempt_at = now() + make_interval(secs => p_retry_seconds)
     where id = p_notification_id
    returning *;
$$;

revoke all on function public.claim_telegram_notification(integer) from public, anon, authenticated;
revoke all on function public.complete_telegram_notification(uuid, bigint) from public, anon, authenticated;
revoke all on function public.fail_telegram_notification(uuid, text, integer) from public, anon, authenticated;
grant execute on function public.claim_telegram_notification(integer) to service_role;
grant execute on function public.complete_telegram_notification(uuid, bigint) to service_role;
grant execute on function public.fail_telegram_notification(uuid, text, integer) to service_role;
