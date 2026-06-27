# Test Strategy

Automated local tests cover the implemented API, UI, scanner, live-adapter
boundaries, public gateway, Telegram delivery and proof-gated resolver. Live
external validation remains a separate release gate.

Current offline proof:

- `python -m pytest`
- FastAPI local startup smoke with `GET /api/health`
- fixture-backed endpoint tests for `/api/devices`, `/api/ota`, and
  `/api/releases`
- static serving tests for `/` and `/static/*`
- browser smoke of the web UI against local Uvicorn for device loading, OTA
  query success, OTA error display, archive refresh, and copy action
- single-command local validation with `python scripts/validate_phase2_ui.py`,
  which starts FastAPI, runs the realbrowser smoke flow, captures screenshots,
  console evidence, network evidence, server logs, and Harness story evidence,
  then shuts the server down
- complete approved manifest-map/server-selection tests
- migration structural test
- logging sanitizer test
- scanner domain and application tests for stable configurable sharding, bootstrap
  order, recurring track progression, task claiming, retry/non-retry outcomes,
  release upsert deduplication, notification queue deduplication, scan status
  API shape, and Phase 3 migration structure
- live-provider parsing tests through mocked decrypted responses
- Supabase RPC adapter and live-runtime migration security/RPC tests
- Oxygen catalog import normalization and manual-override preservation tests
- public Turnstile enforcement, sensitive-input rejection, cache source,
  quota headers and admin endpoint tests
- Telegram notification send/failure state tests
- Telegram scan allowlist command tests
- resolver transform, unsafe-DNS and feature-gate tests
- static tests for public/admin, Telegram delivery and resolver migrations

## Unit Proof

Unit tests should cover pure rules:

- manifest suffix to manifest code mapping.
- manifest code to NV ID and server region mapping.
- 26-code manifest map coverage, including catalog suffixes newly mapped from
  the complete Universal OTA table.
- product model to OTA model derivation.
- seed OTA version builder.
- OTA track progression and bootstrap ordering.
- `rui_candidates` parsing and default `[8, 7, 6]`.
- release identity and dedup key construction.
- resolver URL parser, unsafe host rejection and disabled-by-default gate.
- API error envelope builders.

## Integration Proof

Integration tests should avoid unnecessary live upstream traffic. Use saved
fixtures for OPlus responses where possible.

Coverage should include:

- Oxygen Updater catalog import normalization.
- Supabase repository upsert and uniqueness behavior.
- `POST /api/ota` with saved OTA response fixtures.
- scanner task claiming and restart-safe deduplication.
- Telegram notification delivery claim, send/failure retry and deduplication.
- resolver redirect handling with controlled local fixtures.
- rate-limit headers for limited endpoints.

## E2E Proof

Browser-level proof should cover:

- search or select device.
- inferred manifest with manual override.
- track and `rui_candidates` input.
- manual OTA query result display.
- per-device archive table and responsive action layout.
- copy download URL.
- resolver form success and blocked-host error after the resolver phase adds
  `POST /api/resolve`.

The canonical local E2E proof command is `python scripts/validate_phase2_ui.py`.
Proof artifacts are written to
`validation-artifacts/phase2-web-ui/<run-id>/` and include realbrowser
screenshots, `network-list.json`, `network.har`, `console-list.json`, DOM text
checks, server logs, and `summary.json`.

Telegram E2E or high-level integration proof should cover:

- release notification routed to the correct brand topic.
- `/latest <model>`.
- `/status`.
- `/resolve <url>` success and blocked-host failure only after the deferred
  Telegram resolver integration is selected.

## Platform Proof

Platform checks for the supplied deployment files should cover:

- web, optional bot profile, one-shot worker and cloudflared Compose shape.
- `/api/health` responds.
- worker records a scan run.
- bot can answer `/status` after Telegram activation.
- Tunnel-only origin exposure, Turnstile and admin protection configuration.

## Fixtures

Planned fixtures:

- Oxygen Updater device rows, including multi-model `product_names`.
- OPlus OTA success response.
- OPlus no-update response.
- malformed or changed OPlus response.
- resolver allowed URL with safe redirect.
- resolver URL resolving to private IP.
- Telegram send success and recoverable failure responses.

Private smoke evidence records completed catalog import and live OTA release
persistence. After the recovery/full-manifest migrations were applied on
2026-05-27, bounded worker runs completed successfully and expanded catalog
mapping reads were verified. Live Telegram sends, resolver proof and Tunnel
public ingress remain unproven until their runbook steps are performed and
recorded.
