# Security Contract

## Access

The public application must be reached through Cloudflare Tunnel only.
Anonymous users may read catalog/release data. Standard OTA lookup and an
enabled resolver require server-validated Turnstile tokens and hashed quota
claims. Scan status and scan enqueue require Supabase Auth JWT validation plus
enabled `admin_users` membership.

## Sensitive Data

Keep Supabase elevated keys, Turnstile secret, public rate-limit salt,
Telegram bot token and Cloudflare Tunnel token server-only. Rotate any exposed
Supabase elevated key before live use. Public OTA requests reject beta, IMEI
and GUID-style inputs.

Logs and audit tables must not contain raw secrets, challenge tokens, IMEI,
GUID, protected request bodies, or unvalidated resolver URLs. Public quota
records persist only salted actor hashes and normalized operation hashes.

## Resolver

Resolver code cannot be enabled without `RESOLVER_LIVE_PROOF_CONFIRMED=true`.
It accepts only allowlisted HTTP(S) OTA hosts on permitted ports, rejects
non-global DNS results, checks every redirect and never proxies package bytes.

## Telegram And License

The bot operates only in its configured chat, restricts `/status` to configured
administrator IDs, and records sanitized delivery failures. Direct pinned
`realme-ota` integration requires preserving applicable GPLv3 obligations when
code or images are distributed.
