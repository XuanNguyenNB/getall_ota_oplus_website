# Overview

## Current Behavior

The repository contains product and architecture documentation for the OTA
discovery system, but no runnable backend, API routes, migrations, or tests.

## Target Behavior

Phase 1 introduces the first locally runnable FastAPI backend slice:

- `GET /api/health`
- `GET /api/devices`
- `POST /api/ota`
- `GET /api/releases`

The backend must run without production secrets, use offline fake provider
fixtures for tests, persist through repository interfaces, emit sanitized JSON
logs, and include initial Supabase/Postgres migration files for the Phase 1
tables.

## Affected Users

- Maintainer.
- Web API caller.
- Future worker and UI implementers.

## Affected Product Docs

- `docs/product/api-conventions.md`
- `docs/product/error-handling.md`
- `docs/product/operations.md`
- `docs/product/ota-domain.md`
- `docs/product/overview.md`
- `docs/product/security.md`
- `docs/product/test-strategy.md`

## Non-Goals

- Production UI.
- Scheduler or worker service.
- Telegram bot.
- Resolver endpoint.
- Docker deployment or CI.
- Live Supabase requirements for tests.
- Live OPlus OTA traffic.
- App-level authentication.
