-- Allow Telegram release targets to point at ordinary channels/groups.
-- Forum topics still use message_thread_id; non-forum destinations store null.

alter table public.telegram_targets
    alter column message_thread_id drop not null;

notify pgrst, 'reload schema';
