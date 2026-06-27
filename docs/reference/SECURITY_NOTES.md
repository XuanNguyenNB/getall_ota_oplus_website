# Security Notes

## Public Access Model

The application supports a public controlled-access mode. It must be deployed
behind Cloudflare Tunnel so origin requests cannot bypass Cloudflare controls.

- Anonymous reads: health, devices, releases and EDL ROM archive metadata.
- Anonymous active action: standard `POST /api/ota`, after server-validated
  Turnstile and quota/cooldown checks.
- Resolver action: disabled until bounded live proof, then protected by
  Turnstile and its own quota.
- Operator actions: scan status and manual scan enqueue require Supabase Auth
  plus enabled `admin_users` membership.

Public OTA requests never accept beta, IMEI or GUID inputs.

## Secrets

Server-only values include `SUPABASE_SECRET_KEY`, legacy
`SUPABASE_SERVICE_ROLE_KEY`, `TURNSTILE_SECRET_KEY`,
`PUBLIC_RATE_LIMIT_SALT`, `TELEGRAM_BOT_TOKEN` and
`CLOUDFLARE_TUNNEL_TOKEN`.

Elevated Supabase values previously shared outside secret storage must be
rotated before live use. Prefer `sb_secret_...` over legacy service-role JWTs.

## Rate And Challenge Controls

Turnstile tokens are validated server-side with expected action and configured
hostname. The browser renders Turnstile with manual execution and
`interaction-only` appearance, so verification runs when a protected action is
submitted and most legitimate visitors do not see a persistent widget. The
public action table stores a salted hash of the client boundary and normalized
query hash, not raw IP addresses or challenge tokens.

Initial limits:

- OTA: 5 submissions/hour/client hash with 30-minute live-query cooldown when
  no fresh matching result exists.
- Resolver: 10 submissions/hour/client hash.

## Resolver SSRF Boundary

The resolver is release-gated by `RESOLVER_LIVE_PROOF_CONFIRMED=true`. When
enabled it accepts only HTTP(S) URLs on configured OTA suffixes, restricts
ports, rejects non-global DNS results, revalidates redirects, limits redirects
and timeout, and performs metadata resolution only. It does not proxy package
contents.

DNS rebind protection is enforced at request time. Each `resolve` call uses a
per-request DNS cache so every hostname is resolved exactly once and its
validated IPs are reused for the actual TCP connect. The HTTP transport pins
the connection to that resolved IP literal (URL hostname rewritten to the IP,
original hostname preserved in `Host` header and TLS SNI). This closes the
TOCTOU window between safety validation and the fetch, so a rebind that
suddenly maps the hostname to a private/internal address cannot redirect the
resolver after validation has passed.

## Admin Bootstrap Surface

`GET /api/health` is the documented public liveness URL and intentionally does
not return Supabase credentials. The admin UI bootstrap (Supabase URL plus
browser-safe anon key) is served from `GET /api/admin/bootstrap` so the most
obvious scraping endpoint cannot be harvested for credential pairs. The anon
key is the documented public Supabase credential and is protected by RLS plus
the server-only `admin_users` membership table.

## EDL ROM Archive Boundary

EDL ROM rows are supplemental archive metadata only. The browser can copy or
open direct ZIP links supplied by the archive source, but the backend does not
proxy, mirror, cache or inspect ROM package contents and does not provide EDL
flashing bypass instructions.

## Telegram

The bot handles only its configured chat. Notification sending claims records
atomically, records sanitized delivery failures and retries, and stores sent
message IDs for audit/deduplication. Telegram `/status` and `/scan ...`
allowlist management are restricted by configured Telegram administrator IDs.

## Sensitive Logging And Licensing

Never log secret values, Turnstile tokens, IMEI, GUID, protected OTA payloads
or unvalidated resolver URLs. `realme-ota` is a pinned GPLv3 dependency;
distributed code or images must meet applicable notice and corresponding
source requirements.
