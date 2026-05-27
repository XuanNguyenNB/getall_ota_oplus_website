# Exec Plan

## Goal

Implement the local/offline Phase 3 scheduled scanner slice against existing
in-memory repositories and the fake OTA provider path.

## Scope

In scope:

- Scanner domain records and rules.
- In-memory scan and Telegram notification repositories.
- Offline worker/scanner service.
- `GET /api/scan/status`.
- Supabase migration coverage for scanner and notification tables.
- Unit and integration tests for scanner rules, persistence semantics, API
  status shape, and migration content.
- Product, story, and Harness updates.

Out of scope:

- Live OPlus or `realme-ota` traffic.
- Live Supabase repository implementation.
- Real Telegram delivery.
- Admin enqueue endpoints.
- UI changes.
- Auth, resolver, Docker, and CI.

## Risk Classification

Risk flags:

- Data model.
- External systems.
- Public contracts.
- Existing behavior.
- Weak proof.
- Multi-domain.

Hard gates:

- Data model.
- External provider behavior.

Lane: high-risk.

## Work Phases

1. Read required product, Harness, story, and source context.
2. Record Harness intake and story row.
3. Create Phase 3 story packet.
4. Add scanner and notification repositories and service.
5. Add status API and worker entrypoint.
6. Add migrations and tests.
7. Update docs, story validation, Harness evidence, and trace.

## Stop Conditions

Pause for human confirmation if:

- Live OPlus or `realme-ota` traffic is required.
- GPLv3 integration or distribution behavior must be decided.
- Supabase service-role behavior or production database connectivity becomes
  required.
- Protected admin endpoints, auth, authorization, or network security changes
  are needed.
- Real Telegram Bot API sending is needed.
- The accepted 7-day cadence, shard rule, bootstrap order, or track progression
  rule needs to change.
