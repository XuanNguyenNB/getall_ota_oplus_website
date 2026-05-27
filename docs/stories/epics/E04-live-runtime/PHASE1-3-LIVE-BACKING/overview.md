# Overview

## Current Behavior

Phases 1-3 have deterministic offline implementations using memory
repositories and a fake OTA provider.

## Target Behavior

The same API, UI, and scanner surfaces can be switched to live Supabase
persistence and live `realme-ota` execution through explicit server
configuration. A CLI imports Oxygen Updater devices; a bounded worker batch
persists scan and notification queue state without sending Telegram messages.

## Affected Users

- Maintainer running the private instance.
- Web user issuing manual OTA queries.
- Operator checking scheduled scan state.

## Affected Product Docs

- `docs/product/overview.md`
- `docs/product/ota-domain.md`
- `docs/product/operations.md`
- `docs/product/security.md`
- `docs/product/test-strategy.md`

## Non-Goals

- Telegram Bot API sends or commands.
- Resolver behavior.
- Docker deployment and CI.
- UI redesign or protected admin endpoints.
