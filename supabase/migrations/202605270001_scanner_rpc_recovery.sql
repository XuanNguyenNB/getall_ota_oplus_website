-- Restore scanner completion RPC visibility and allow abandoned running tasks
-- to be reclaimed after an interrupted worker process.

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
           and (
                status = 'queued'
                or (status = 'running' and started_at < now() - interval '15 minutes')
           )
         order by case when status = 'queued' then 0 else 1 end, id
         for update skip locked
         limit 1
     )
    returning *;
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

revoke all on function public.claim_scan_task(uuid) from public, anon, authenticated;
revoke all on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    from public, anon, authenticated;

grant execute on function public.claim_scan_task(uuid) to service_role;
grant execute on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    to service_role;

notify pgrst, 'reload schema';
