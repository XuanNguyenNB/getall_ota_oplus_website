# Overview

## Current Behavior

The repo contains planning documents for a private OPlus OTA discovery system
and an installed Harness durable layer. Root docs describe the accepted Concept
B direction, while the Harness product folder and architecture guide were still
generic Harness placeholders.

No application code, migrations, Docker files, tests, CI, package manifests, or
runtime scaffolding exist.

## Target Behavior

The docs-only foundation captures current product truth before implementation:

- Concept B is the accepted direction.
- `docs/product/*` is the living product contract.
- `docs/ARCHITECTURE.md` is project-specific.
- implementation boundaries and non-goals are explicit.
- validation expectations are documented but not marked implemented.
- Harness intake, story, decision, and trace records describe this foundation
  work.

## Affected Users

- Maintainer.
- Future implementation agents.
- Future reviewers.

## Affected Product Docs

- `docs/product/README.md`
- `docs/product/overview.md`
- `docs/product/api-conventions.md`
- `docs/product/ota-domain.md`
- `docs/product/operations.md`
- `docs/product/security.md`
- `docs/product/test-strategy.md`
- `docs/product/error-handling.md`
- `docs/ARCHITECTURE.md`
- technical references in `docs/reference/`

## Non-Goals

- Creating FastAPI, Supabase, Docker, migrations, tests, CI, package manifests,
  app folders, or runtime configuration.
- Changing the accepted Concept B direction.
- Implementing or proving runtime behavior.
- Slicing every future feature into story packets.
