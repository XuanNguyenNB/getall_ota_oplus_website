# Public Runtime Continuation

Lane: high-risk

This story implements the local/code-artifact portion of the controlled public
runtime: active-request protection, admin APIs, Telegram delivery, proof-gated
resolver and deployment shape.

## Included

- Turnstile validation, quota/cooldown/cache behavior and standard-only public
  OTA requests.
- Supabase Auth admin checks for scan status and manual enqueue.
- Telegram notification consumer plus `/latest` and restricted `/status`.
- Resolver service/API/UI behind an explicit live-proof gate.
- Supabase migrations, Compose/Tunnel/timer/CI artifacts and current docs.

## Not Claimed Complete

- Scanner RPC recovery completion, key rotation execution, Telegram sends,
  resolver proof and public deployment smoke. Catalog import and manual/worker
  release persistence were observed during private smoke on 2026-05-27.
