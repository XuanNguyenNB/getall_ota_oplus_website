# Design

Anonymous public reads remain simple. Active actions run through server-side
Turnstile checks and an atomic action-claim repository storing only salted
actor hashes and operation hashes. Fresh OTA results avoid unnecessary
upstream traffic; uncached requests are cooled down.

Admin authorization verifies a Supabase Auth bearer JWT and an enabled
`admin_users` row. Admin enqueue creates queued run tasks that a one-shot
worker can consume by run ID.

Telegram delivery is separated from scanning: scanner enqueue remains
idempotent and the bot atomically claims, sends and retries delivery records.

Resolver URL parsing, DNS/IP and redirect safety is implemented, but endpoint
enablement requires a live-proof configuration flag. Deployment uses
Cloudflare Tunnel without publishing the origin port.
