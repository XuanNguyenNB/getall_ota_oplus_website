# Overview

## Current Behavior

Phase 1 and Phase 2 provide a local FastAPI API and private browser UI backed
by in-memory repositories and the fake OTA provider. The repository has no
worker/scanner path, scan state repository, Telegram notification queue, or
implemented `GET /api/scan/status` behavior.

## Target Behavior

Phase 3 adds an offline scheduled scanner slice that can:

- create a local scan run for the selected 7-day shard.
- create and claim per-device scan tasks without duplicate claims.
- use the existing fake OTA provider path only.
- persist worker-discovered releases with `discovered_by="worker"`.
- enqueue brand-routed Telegram notification records without sending messages.
- expose `GET /api/scan/status` from local scan state.
- include Supabase migrations for scanner and Telegram notification tables.

## Affected Users

- Maintainer.
- Future worker implementer.
- API caller checking scanner status.

## Affected Product Docs

- `docs/product/api-conventions.md`
- `docs/product/operations.md`
- `docs/product/ota-domain.md`
- `docs/product/overview.md`
- `docs/product/test-strategy.md`
- `docs/reference/API_SPEC.md`
- `docs/reference/DATABASE_SCHEMA.md`
- `docs/reference/SCHEDULER.md`
- `docs/reference/TELEGRAM_BOT.md`

## Non-Goals

- Live `realme-ota` or OPlus traffic.
- Supabase credentials or live Supabase validation.
- Real Telegram Bot API sends.
- Admin enqueue endpoints.
- Browser UI changes.
- Resolver, bot command, Docker, CI, or auth work.
