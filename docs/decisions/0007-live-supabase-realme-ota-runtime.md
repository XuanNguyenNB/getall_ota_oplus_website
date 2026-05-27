# 0007 Live Supabase And realme-ota Runtime

Date: 2026-05-26

## Status

Accepted

## Context

Phases 1-3 were proven with in-memory repositories and a fake provider. The
maintainer wants the private app to query real OPlus endpoints and persist
catalog, releases, and scanner state in a Supabase project.

The local Universal OTA DownloadeR script supplies the accepted 26-code
manifest/NV/server map. The local and upstream `realme-ota` package is GPLv3
and supplies request encryption and response decryption.

## Decision

- Add an opt-in `REPOSITORY_BACKEND=supabase` runtime using server-only
  Supabase secret/service-role credentials.
- Add an opt-in `OTA_PROVIDER=realme` plus `ALLOW_LIVE_OTA=true` runtime.
- Pin direct `realme-ota` integration to upstream revision
  `d2641674c279c998ff8e1a92bb761474d1b62268`.
- Treat the Universal OTA `REGIONS`/`SERVERS` map as the approved live mapping
  source, including its server endpoint choices rather than geographic
  inference.
- Retain the fake/in-memory runtime as deterministic offline proof.

## Consequences

- The maintainer must apply migrations and provide secrets outside committed
  files before live startup.
- Live scans are bounded and throttled; Telegram sending remains a later phase.
- Distribution of this project with the pinned `realme-ota` dependency must
  retain GPLv3 notices, attribution, and corresponding source obligations.
- Server credentials exposed outside secured configuration should be rotated
  before long-lived deployment.
