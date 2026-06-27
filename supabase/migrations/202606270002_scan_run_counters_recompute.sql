-- 202606270002_scan_run_counters_recompute.sql
--
-- Phase 2 (tech debt overhaul): make scan_runs.new_releases idempotent.
--
-- The previous complete_scan_task RPC incremented scan_runs.new_releases
-- by 1 on every completion that reported a new release. That meant a
-- task being re-completed after a retry (or, hypothetically, a duplicate
-- claim due to operator restart) could leave a stale +1 in the counter
-- with no way to clean it up.
--
-- This migration:
--   1. Adds scan_tasks.found_new_release so the "new" outcome is stored
--      on the task itself.
--   2. Backfills the new column from existing rows: a completed task
--      with a found_release_id is conservatively treated as new (this
--      is a one-shot, post-hoc estimate; the running-forward counter is
--      what matters for new traffic).
--   3. Rewrites complete_scan_task to write found_new_release on the
--      task and recompute scan_runs.new_releases from that column,
--      so the counter is now derived state and any number of retries
--      produces the same final value.

alter table public.scan_tasks
    add column if not exists found_new_release boolean not null default false;

-- Conservative backfill: any historical completion with a release id is
-- treated as new exactly once. Subsequent completions of the same task
-- (if any) cannot retroactively over-count because the column is set on
-- the row, not on a separate counter.
update public.scan_tasks
   set found_new_release = true
 where status = 'completed'
   and found_release_id is not null
   and found_new_release = false;

-- Also recompute every existing scan_runs.new_releases from the backfilled
-- task rows so the migration leaves the counter consistent with the
-- column-derived view.
update public.scan_runs as r
   set new_releases = sub.new_count
  from (
        select scan_run_id, count(*) as new_count
          from public.scan_tasks
         where status = 'completed'
           and found_new_release = true
         group by scan_run_id
       ) as sub
 where r.id = sub.scan_run_id;

-- Runs with no new releases get explicit 0 (the subquery would not
-- produce a row for them).
update public.scan_runs as r
   set new_releases = 0
 where not exists (
        select 1
          from public.scan_tasks t
         where t.scan_run_id = r.id
           and t.status = 'completed'
           and t.found_new_release = true
       )
   and r.new_releases <> 0;

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
    v_new_count integer;
begin
    update public.scan_tasks
       set status = 'completed',
           tracks_checked = p_tracks_checked,
           rui_candidates_checked = p_rui_candidates_checked,
           found_release_id = p_found_release_id,
           found_new_release = coalesce(p_new_release, false),
           error_code = null,
           error_message = null,
           finished_at = now()
     where id = p_task_id
    returning * into v_task;

    -- Recompute the run-level counter from tasks. This is idempotent: if
    -- the same task is completed twice (or a retry path lands a non-new
    -- outcome), the counter stays consistent with task state.
    select count(*)
      into v_new_count
      from public.scan_tasks
     where scan_run_id = v_task.scan_run_id
       and status = 'completed'
       and found_new_release = true;

    update public.scan_runs
       set new_releases = v_new_count
     where id = v_task.scan_run_id;

    return next v_task;
end;
$$;

revoke all on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    from public, anon, authenticated;
grant execute on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    to service_role;

notify pgrst, 'reload schema';
