# Exec Plan

## Goal

Make Phase 1-3 live-capable through explicit Supabase and OPlus provider
configuration while preserving offline proof.

## Scope

In scope:

- Full approved 26-code manifest map.
- Pinned direct GPLv3 `realme-ota` integration.
- Supabase repositories and atomic SQL RPCs.
- Oxygen catalog import command and import history.
- Bounded live-compatible worker command.
- Unit/integration proof with mocked external boundaries.

Out of scope:

- Applying SQL to the remote project.
- Real live smoke requests during automated proof.
- Telegram delivery, resolver, Docker, CI, and admin/API auth.

## Risk Classification

Risk flags:

- Data model and migration.
- External provider behavior.
- Server-side secrets.
- Existing API/scanner behavior.
- GPLv3 distribution boundary.

Hard gates:

- External provider behavior.
- Elevated Supabase access.

Lane: high-risk.

## Work Phases

1. Record Harness intake and accepted decisions.
2. Implement config, live provider, and persistence adapters.
3. Add migration/RPC/security support and importer/worker commands.
4. Update product/runbook documentation.
5. Verify through offline mocked-boundary proof.

## Stop Conditions

Pause if Telegram sending, resolver exposure, public access/authentication, or
remote migration application is requested as part of this story.
