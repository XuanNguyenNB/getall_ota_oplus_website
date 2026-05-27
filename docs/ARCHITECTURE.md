# Architecture

This repository includes the FastAPI API, public-capable browser UI, one-shot
scanner, Supabase/Oxygen/live `realme-ota` adapters, public gateway/admin code,
Telegram delivery code, a proof-gated resolver, and Docker/Tunnel/timer/CI
artifacts. Private smoke on 2026-05-27 proved catalog import, expanded
manifest inference, live OTA release persistence and bounded scanner
completion after operator-applied recovery/full-manifest migrations.

The accepted product direction is Concept B: three VPS services, Supabase
Postgres, a scheduled scanner, Telegram delivery, controlled public ingress,
and a web-first OTA URL resolver gated by live proof.

## Runtime Shape

```text
Browser
  -> Cloudflare Tunnel / Turnstile edge boundary
  -> web/API service
      -> Supabase Postgres
      -> realme-ota logic
      -> OPlus OTA endpoints
      -> resolver module (when proof-gated on)

worker service
  -> Supabase scan queue and release tables
  -> realme-ota logic
  -> OPlus OTA endpoints
  -> Telegram notification enqueueing

bot service
  -> Telegram Bot API
  -> Supabase lookup tables
  -> notification queue and implemented commands
```

Supabase is the managed system of record. Application responsibilities are
`web`, one-shot `worker`, and optional `bot`; `cloudflared` is deployment
ingress.

## Product Domains

Implementation stories should preserve these domain boundaries:

- Device catalog: imported Oxygen Updater rows, normalized models, brand
  classification, manifest inference, and manual overrides.
- OTA query: manifest mapping, OTA track selection, `rui_candidates`,
  request/response parsing, release persistence, and deduplication.
- Scanner: 7-day sharding, task claiming, retry policy, track progression, and
  scan observability.
- Telegram: brand topic routing, notification delivery, `/latest`, restricted
  `/status`, retry and audit state.
- Resolver: allowlisted URL resolution with SSRF protection and request
  history.
- Security and operations: public Turnstile/quota policy, admin authentication,
  secrets, logs, Tunnel-only ingress and deployment boundaries.

## Source Hierarchy

Product truth lives in this order:

1. Current user prompt and accepted decisions.
2. `docs/product/*`.
3. Story packets in `docs/stories/*`.
4. Harness durable records from `scripts/harness query matrix`.
5. Root planning docs.
6. `ui-preview/` as visual and product intent reference only.

Root planning docs should remain consistent with `docs/product/*`, but future
implementation work should update the smaller product docs first.

## Dependency Rule

When code is introduced, keep provider clients and framework details outside
pure product rules.

| Layer | Owns | Must not own |
| --- | --- | --- |
| Domain | manifest maps, track rules, release identity, resolver safety decisions | FastAPI handlers, Supabase client calls, Telegram API calls |
| Application | manual query use cases, catalog import, scan orchestration, notification enqueueing | raw HTTP parsing, process environment reads |
| Infrastructure | Supabase repositories, realme-ota adapter, Telegram sender, HTTP clients, logging | UI state or route DTO shape |
| Interface | API routes, Telegram commands, web DTOs, error envelopes | domain rule reimplementation |
| Surface | browser interactions and localStorage-only preferences | service-role secrets or domain internals |

## Boundary Parsing

Parse unknown data before it enters application or domain code:

- HTTP request bodies, query strings, and path values.
- Telegram command text and callback payloads.
- Environment variables.
- Supabase rows.
- Oxygen Updater rows.
- OPlus OTA responses.
- Resolver URLs and redirect targets.

Boundary parsers must normalize product model strings, manifest codes, OTA
tracks, `rui_candidates`, pagination values, and resolver hosts before deeper
logic sees them.

## Security Boundaries

- Browser code never receives `SUPABASE_SECRET_KEY` or
  `SUPABASE_SERVICE_ROLE_KEY`.
- Admin endpoints require Supabase Auth JWT verification and enabled membership.
- IMEI and GUID values are optional, must not be stored, and must not be logged.
- Resolver code must remain disabled before proof and validate scheme,
  allowlisted suffix, DNS result, IP range,
  and every redirect hop before fetching.
- Telegram messages must not include secrets, raw protected request bodies, or
  unvalidated resolver URLs.

## Validation Boundaries

Validation status is recorded in Harness. Local implementation proof does not
constitute remote migration, third-party traffic, or public-launch proof.

- Unit proof: manifest map, seed OTA version builder, track rules, resolver URL
  safety, response parsing.
- Integration proof: Supabase persistence, OTA adapter with saved fixtures,
  scanner task claiming, Telegram delivery deduplication.
- E2E proof: browser manual query, release lookup, resolver flow, Telegram
  command flow.
- Platform proof: Docker service startup, health checks, Tunnel-only origin
  exposure, protected public actions, and worker restart behavior.
