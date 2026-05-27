# 0008: Public Controlled Runtime And Release Gates

Status: accepted

Date: 2026-05-26

## Context

The live-capable Phase 1-3 implementation was designed for private operation.
The selected continuation allows public anonymous OTA lookup and resolver use,
which exposes upstream traffic and SSRF/abuse risks.

## Decision

- Public ingress uses Cloudflare Tunnel; the origin web port is not published.
- Public active requests require server-validated Cloudflare Turnstile.
- Anonymous OTA queries support standard releases only and use conservative
  hashed quotas plus a fresh-result/cooldown policy.
- Operational API access uses Supabase Auth plus `admin_users` membership.
- The bot service, not the scanner worker, delivers Telegram queue records.
- Resolver ships web-first behind `RESOLVER_LIVE_PROOF_CONFIRMED`; Telegram
  `/resolve` is deferred until web live proof succeeds.

## Consequences

- The implementation adds migrations for admins, action quotas, delivery retry
  state and resolver history.
- Docker/Cloudflare/Tunnel/timer artifacts can be tested locally, but public
  release requires operator-run external validation.
- Previously exposed Supabase elevated keys must be rotated before activation.
