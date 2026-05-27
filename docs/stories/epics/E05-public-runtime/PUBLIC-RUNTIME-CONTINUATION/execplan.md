# Execution Plan

Status: local implementation complete; external activation pending.

1. Add domain/repository/config boundaries for public actions, admins,
   Telegram delivery and resolver history.
2. Add API controls, UI capability handling, worker queued-run consumption and
   bot process.
3. Add server-only migration/RPC artifacts and local automated proof.
4. Add deployment and scheduling artifacts and synchronize living docs.
5. Require operator-run live activation and public release gates before
   enabling real public traffic.

Stop conditions: no real secrets in tracked files; no claim of live validation
without remote evidence; resolver remains disabled before proof.
