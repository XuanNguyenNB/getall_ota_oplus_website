# Documentation Map

This directory holds the project harness and the product contract for the
controlled-access OPlus OTA discovery system.

## Main Files

- `HARNESS.md`: how humans and agents collaborate.
- `FEATURE_INTAKE.md`: how prompts become tiny, normal, or high-risk work.
- `ARCHITECTURE.md`: Harness architecture guidance and boundary rules.
- `TEST_MATRIX.md`: legacy proof map; current proof status is queried with
  `scripts/harness query matrix`.
- `HARNESS_BACKLOG.md`: legacy improvement list; current improvement records
  are stored with `scripts/harness backlog`.
- `GLOSSARY.md`: shared terms.

## Folders

- `product/`: current Concept B product truth.
- `reference/`: current runtime architecture, API, persistence and deployment
  reference material.
- `runbooks/`: operator smoke and launch gates.
- `stories/`: feature packets and backlog.
- `decisions/`: durable decisions and tradeoffs.
- `archive/design/`: superseded design-audit and initial-plan records.
- `demo/`: concrete walkthroughs that show how the harness transforms input
  into agent-ready work.
- `templates/`: reusable spec-intake, story, plan, decision, and validation
  formats.

## Current State

Harness tracks implemented Phase 1-3 behavior plus locally implemented public
gateway, Telegram, gated resolver and deployment artifacts. Private live smoke
on 2026-05-27 proved catalog import, expanded manifest inference, manual/worker
release persistence and scanner completion after the recovery/full-manifest
migrations were applied. Public launch remains an explicit operator gate.
