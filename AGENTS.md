# Agent Instructions

## Project Context

This repository contains a controlled-access OTA discovery web application for
OPPO, Realme, and OnePlus devices. Current code includes the FastAPI web UI,
Supabase/live `realme-ota` adapters, scheduled scanner, Telegram consumer,
public gateway controls and a proof-gated resolver. Private live validation is
partially proven; public deployment remains gated.

Before implementation work, read the project entrypoint and current reference
documents:

- `README.md`
- `docs/reference/ARCHITECTURE.md`
- `docs/reference/IMPLEMENTATION_PLAN.md`
- `docs/reference/API_SPEC.md`
- `docs/reference/DATABASE_SCHEMA.md`
- `docs/reference/DATA_SOURCES.md`
- `docs/reference/SCHEDULER.md`
- `docs/reference/TELEGRAM_BOT.md`
- `docs/reference/RESOLVER.md`
- `docs/reference/DEPLOYMENT.md`
- `docs/reference/SECURITY_NOTES.md`

<!-- HARNESS:BEGIN -->
## Harness

This repo uses Harness. Before work, read:

- `README.md`
- `docs/HARNESS.md`
- `docs/FEATURE_INTAKE.md`
- `docs/ARCHITECTURE.md`
- `scripts/harness query matrix`

Use the Rust Harness CLI as the main operational tool. Run it through the
stable repo-local entrypoint `scripts/harness`, which uses the prebuilt Rust
binary at `scripts/bin/harness-cli` in installed projects.
<!-- HARNESS:END -->
