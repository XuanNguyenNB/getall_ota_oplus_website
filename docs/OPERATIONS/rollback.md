# Rollback Runbook

This runbook covers operator-initiated rollbacks for the four kinds of change
that can land on the live deployment: a Supabase migration, a deploy of the
FastAPI app or worker, a Telegram delivery outage, and a scan concurrency
change that overloads upstream OPlus endpoints.

Each section is self-contained. Run only the section that matches the actual
incident. None of these procedures require dropping live data; they restore a
previous known-good state by reversing the schema/config change that
introduced the regression.

## Rolling back a Supabase migration

The phase 2 (tech debt overhaul) migrations under `supabase/migrations/`
to roll back are:

- `202606270001_scan_eligibility_index.sql`
- `202606270002_scan_run_counters_recompute.sql`

Both migrations are guarded with `IF EXISTS` / `IF NOT EXISTS` clauses, so the
rollback statements below are safe to re-run.

### Rollback `202606270001_scan_eligibility_index.sql`

This migration adds two partial indexes on `devices`. Dropping them returns
the scanner to a full-scan plan but does not lose data.

```sql
DROP INDEX IF EXISTS public.devices_active_scan_partial_idx;
DROP INDEX IF EXISTS public.devices_active_scan_group_partial_idx;
```

After running, ask Supabase to refresh its schema cache:

```sql
NOTIFY pgrst, 'reload schema';
```

### Rollback `202606270002_scan_run_counters_recompute.sql`

This migration adds `scan_tasks.found_new_release` and replaces the
`complete_scan_task` RPC with an idempotent recomputation body. To roll back:

1. Restore the previous `complete_scan_task` body (the one shipped in
   `202605270001_scanner_rpc_recovery.sql`).
2. Drop the `found_new_release` column.

The exact previous body is reproduced here so an operator can copy/paste it
back without diffing migration history:

```sql
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

revoke all on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    from public, anon, authenticated;
grant execute on function public.complete_scan_task(uuid, text[], integer[], uuid, boolean)
    to service_role;

notify pgrst, 'reload schema';
```

Then drop the column the rolled-back RPC no longer references:

```sql
ALTER TABLE public.scan_tasks
    DROP COLUMN IF EXISTS found_new_release;

NOTIFY pgrst, 'reload schema';
```

Notes:

- The column drop is safe because the restored RPC body never reads or writes
  `found_new_release`.
- `scan_runs.new_releases` keeps whatever value it had at rollback time. If
  it has drifted (the column-derived recompute had produced a different
  value than the previous +1 counter), reconcile by hand based on
  `scan_tasks` rows. The drift is at most one per re-completed task, so a
  spot-check rather than a full recompute is usually enough.

## Rolling back a deployment

Use this section when a deploy of `web`, `worker`, or `bot` introduces a
regression. The goal is to return the running service to the last good
commit without touching Supabase data.

1. Identify the last good commit. The fastest source of truth is the deploy
   log (the commit SHA pinned on the previous good run) or
   `git log --oneline origin/main`. Confirm the SHA pre-dates the
   regression.
2. Redeploy from that ref. On the VPS:

   ```bash
   cd /srv/getall_ota_oplus_website
   git fetch --tags
   git checkout <last-good-sha>
   docker compose pull web worker
   docker compose up -d web cloudflared
   ```

   For container images built locally, rebuild instead of pulling:

   ```bash
   docker compose build web worker
   docker compose up -d web cloudflared
   ```

3. Restart the worker timer so the next scheduled run uses the rolled-back
   binary:

   ```bash
   sudo systemctl restart ota-worker.timer
   sudo systemctl status ota-worker.timer
   ```

4. Confirm `/api/health` returns `ok`:

   ```bash
   curl -fsS https://<tunnel-host>/api/health | jq '.ok'
   # expect: true
   ```

   The same check from inside the host (when cloudflared is not the
   regression) is:

   ```bash
   curl -fsS http://127.0.0.1:8000/api/health | jq '.ok'
   ```

5. If the optional bot profile is enabled, restart it:

   ```bash
   docker compose --profile bot up -d bot
   docker compose --profile bot logs --tail=50 bot
   ```

6. Record the rollback in Harness with the SHA you rolled back from and the
   SHA you rolled back to.

## Rolling back a Telegram outage

Use this section when the bot has stopped delivering and
`telegram_notifications` rows are stuck in `pending` (or `sending` past their
stale window). The goal is to mark them `failed` so retry/dedup state is
consistent, then re-enqueue them once the upstream cause is fixed.

Diagnose first:

```sql
SELECT status, count(*)
  FROM public.telegram_notifications
 GROUP BY status;
```

If many rows sit in `sending` with `last_attempt_at` older than 15 minutes,
the bot crashed mid-claim. Mark them `failed` so they can be retried by the
normal retry path:

```sql
UPDATE public.telegram_notifications
   SET status = 'failed',
       error_message = 'TELEGRAM_NETWORK',
       last_attempt_at = now(),
       next_attempt_at = now() + interval '5 minutes'
 WHERE status = 'sending'
   AND last_attempt_at < now() - interval '15 minutes';
```

To force-fail rows stuck in `queued`/`pending` because their target row is
broken (`TELEGRAM_CHAT_BLOCKED`), do it brand-scoped first so the rest of the
queue continues to drain:

```sql
UPDATE public.telegram_notifications n
   SET status = 'failed',
       error_message = 'TELEGRAM_CHAT_BLOCKED',
       last_attempt_at = now(),
       next_attempt_at = null
 FROM public.telegram_targets t
 WHERE n.telegram_target_id = t.id
   AND t.brand = 'oneplus'   -- example; scope to the broken target
   AND n.status IN ('queued', 'pending', 'sending');
```

Once the underlying cause (token rotated, bot re-added to the chat, topic
re-created) is resolved, re-enqueue the failed rows by clearing their retry
state. Notification deduplication remains intact because the unique
constraint on `(release_id, telegram_target_id)` prevents fresh inserts.

```sql
UPDATE public.telegram_notifications
   SET status = 'queued',
       error_message = null,
       last_attempt_at = null,
       next_attempt_at = now(),
       attempt_count = 0
 WHERE status = 'failed'
   AND error_message IN ('TELEGRAM_CHAT_BLOCKED', 'TELEGRAM_AUTH', 'TELEGRAM_NETWORK');
```

If a whole `scan_runs` row needs replaying, prefer the admin command path
instead of touching the table:

```text
/notify backfill-run <scan_run_id> [limit]
```

That command re-enqueues releases under the same unique identity, so already
sent rows stay `sent` and only the actually missing notifications are queued.

After re-enqueue, restart the bot consumer:

```bash
docker compose --profile bot restart bot
docker compose --profile bot logs --tail=50 bot
```

## Rolling back scan concurrency

`SCAN_MAX_CONCURRENCY` controls how many scan tasks the worker drives in
parallel within a run. If a higher value causes provider rate-limiting (run
ends in `failed` because the failure-rate threshold trips, or upstream HTTP
429/5xx is dominant in `scan_tasks.error_code`), roll back to the conservative
default.

1. Edit the worker's `.env` (or whichever env file the systemd unit reads):

   ```text
   SCAN_MAX_CONCURRENCY=1
   ```

2. Reload and restart the worker timer so the next run picks up the new
   value. The worker reads settings at process start.

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart ota-worker.timer
   sudo systemctl status ota-worker.timer
   ```

3. For a one-shot manual smoke at the rolled-back value, run a bounded job:

   ```bash
   docker compose --profile jobs run --rm worker \
       python -m ota_backend.worker --once --max-tasks 1
   ```

4. Confirm the worker log summary (sent to the configured worker-log chat,
   or in `journalctl -u ota-worker.service`) shows the next run completed
   without the rate-limit signal. Then leave the timer at
   `SCAN_MAX_CONCURRENCY=1` until the upstream cause has been investigated.

No database change or migration is involved. The previous concurrency value
can be re-introduced after a bounded smoke at the higher value proves the
upstream pressure issue is resolved.
