# Product Docs

This directory is the living product contract for the OPPO, Realme and
OnePlus OTA discovery application.

The accepted direction is public controlled access: web, one-shot worker and
bot responsibilities; Supabase persistence; Telegram forum notifications;
Cloudflare Tunnel/Turnstile protection; Supabase Auth administration; and a
web-first resolver that cannot be enabled before bounded live proof.

Phase 1-3 and continuation code artifacts are implemented locally. Private
smoke on 2026-05-27 proved remote catalog import and live OTA persistence;
operator-applied recovery/full-manifest migrations then enabled expanded
catalog mappings and completed bounded worker scans. Telegram,
resolver and public deployment verification remain operator-controlled gates.

## Contract Files

- `overview.md`: product surfaces, status and boundaries.
- `api-conventions.md`: HTTP access and response contract.
- `ota-domain.md`: manifest, track and release identity rules.
- `operations.md`: runtime services, bot, scheduler and deployment.
- `security.md`: public controls, secrets and SSRF boundaries.
- `test-strategy.md`: local proof and live activation gates.
- `error-handling.md`: stable failure behavior.

Root documentation remains consistent reference material. `ui-preview/` is
visual reference only and is not implementation evidence.
