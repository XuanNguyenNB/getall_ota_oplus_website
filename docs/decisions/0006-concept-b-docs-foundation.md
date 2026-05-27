# 0006 Concept B Docs Foundation

Date: 2026-05-26

## Status

Accepted

## Context

The technical reference docs and archived design audit settle on Concept B for the OPlus OTA
discovery product, but the Harness product folder and Harness architecture
guide still carried generic placeholder language. Implementation should not
begin until product truth, architecture boundaries, validation expectations,
and Harness records agree.

## Decision

Use `docs/product/*` as the living product contract for Concept B:

- three planned VPS services: `web`, `worker`, and `bot`.
- Supabase Postgres as the managed system of record.
- scheduled scanner over a 7-day cycle.
- Telegram forum topic notifications and commands.
- command-based resolver with SSRF protection.
- planned validation requirements documented before app scaffolding.

Documents in `docs/reference/` remain technical references and must stay
consistent with the product contract. `ui-preview/` remains visual/product
intent reference only.

## Alternatives Considered

1. Keep extending broad technical reference docs as the living contract.
2. Create a new monolithic spec file.
3. Slice all future implementation phases into story packets now.

## Consequences

Positive:

- Future agents have a smaller product-contract surface to update first.
- Harness records can track proof without claiming runtime implementation.
- Implementation boundaries are explicit before scaffolding starts.

Tradeoffs:

- Some technical reference docs duplicate product-contract facts and must be kept aligned.
- Future implementation stories still need to create executable proof.

## Follow-Up

- Create implementation story packets only when each phase is selected.
- Keep Harness proof rows planned until code and validation commands exist.
