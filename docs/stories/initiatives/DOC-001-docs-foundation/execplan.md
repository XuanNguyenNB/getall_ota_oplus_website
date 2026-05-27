# Exec Plan

## Goal

Backfill the docs-only product foundation so the Harness-installed repo has
current product truth, project-specific architecture guidance, clear boundaries,
and seeded Harness records before app scaffolding begins.

## Scope

In scope:

- classify and record the request through Harness intake.
- create one bounded docs-foundation story/proof record.
- seed `docs/product/*` with Concept B product contract files.
- update `docs/ARCHITECTURE.md` from generic placeholder to project guidance.
- align root docs with planned-only status and Concept B boundaries.
- record a Harness trace.

Out of scope:

- application code.
- Supabase migrations.
- Docker or deployment files.
- CI or package manifests.
- test files or runnable validation scripts.
- broad feature slicing beyond this docs foundation.

## Risk Classification

Risk flags:

- Data model.
- Audit/security.
- External systems.
- Public contracts.
- Weak proof.
- Multi-domain.

Hard gates:

- Security and resolver validation must not be weakened.
- Concept B architecture direction must not be replaced.
- Source-of-truth hierarchy must remain Harness v0 compatible.

## Work Phases

1. Read required docs and current Harness state.
2. Record intake and docs-foundation story.
3. Patch product, architecture, story, and validation docs.
4. Search for stale contradictions and fake implementation claims.
5. Confirm no runtime scaffolding was created.
6. Record Harness trace and final query proof.

## Stop Conditions

Pause for human confirmation if:

- a doc change would alter or replace Concept B.
- product rules conflict and are not settled by
  `docs/archive/design/DESIGN_AUDIT.md` or
  `docs/archive/design/DESIGN_PLAN.md`.
- security, resolver SSRF protection, or validation expectations would be
  weakened.
- completion would require real app code, migrations, tests, Docker, CI, or
  runtime config.
