# Design

## Domain Model

The docs foundation defines these planned domains:

- device catalog
- OTA query and manifest mapping
- scheduled scanner
- Telegram notification and command bot
- resolver
- security and operations
- validation proof

## Application Flow

No application flow is implemented by this story. Planned implementation flow is
captured in `docs/product/overview.md` and
`docs/reference/IMPLEMENTATION_PLAN.md`.

## Interface Contract

`docs/product/api-conventions.md` and `docs/reference/API_SPEC.md` define the planned API
shape, including pagination `total`, rate-limit headers, and structured errors.

## Data Model

`docs/reference/DATABASE_SCHEMA.md` remains the table design reference. Product docs
clarify release identity, catalog import behavior, resolver history, Telegram
deduplication, and scan observability.

## UI / Platform Impact

`ui-preview/` remains a reference target only. The docs clarify that it is mock
data and not production frontend source.

## Observability

Harness durable records capture the docs-foundation intake, proof story,
decision, and trace. Runtime logs and metrics are planned in product docs but do
not exist yet.

## Alternatives Considered

1. Extend root docs only.
   - Rejected because the Harness source hierarchy prefers smaller
     `docs/product/*` contract files.
2. Create story packets for every future implementation phase.
   - Rejected because the request only needs the docs-foundation records and
     explicitly avoids slicing every future feature up front.
