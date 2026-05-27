# Validation

## Proof Strategy

Automated proof remains offline: external requests and Supabase RPC responses
are mocked or represented by repository doubles. Separate private live smoke
evidence is recorded below, including recovery/full-manifest migration
activation and bounded worker completion.

## Test Plan

| Layer | Cases |
| --- | --- |
| Unit | full 26-code mapping, provider response parsing/error handling, catalog normalization and override preservation |
| Integration | Supabase RPC adapter use, scanner paging/worker behavior, API regression, migration RLS/RPC content |
| E2E | Existing Phase 2 offline browser proof remains applicable; no UI change |
| Platform | worker CLI imports/runs in default offline mode |
| Logs/Audit | no secret or protected request content added to logs or docs |

## Commands

```text
python -m pytest
python -m compileall -q src tests
python -m pip install --dry-run -e ".[dev]"
python -m ota_backend.worker --once --cycle-day 4 --max-tasks 1
```

## Progress Log

- 2026-05-26: Harness intake #5 recorded as high-risk and story
  `PHASE1-3-LIVE-BACKING` created.
- 2026-05-26: Implemented opt-in Supabase repositories, RPC migration,
  full approved live manifest map, live `realme-ota` provider, catalog CLI,
  bounded worker arguments, and product/runbook updates.
- 2026-05-26: Fixed package metadata to permit the pinned Git dependency after
  editable-install dry-run surfaced Hatch direct-reference validation.
- 2026-05-26: Added `.env` ignore rules and placeholder-only `.env.example`
  for server-side live configuration.
- 2026-05-27: Constrained `supabase` below `2.19` after the current
  `2.30.0` dependency chain required a `pyiceberg` native build unavailable
  on the local Python 3.14 smoke environment.
- 2026-05-27: Private live smoke exposed invalid Oxygen aliases and serial
  import cost; importer now skips invalid aliases, batch-upserts valid models,
  and completed a live import of 1500 model records.
- 2026-05-27: Private live OTA query persisted a release for `RMX3840IN` after
  implementing the upstream fallback seed and decryptable no-update response
  behavior used by the live endpoint.
- 2026-05-27: Live worker discovered a release for `CPH2723IN` but could not
  finish its task because the remote Data API did not expose
  `complete_scan_task`; migration `202605270001_scanner_rpc_recovery.sql` is
  required before worker smoke resumes.
- 2026-05-27: The maintainer supplied the complete Universal OTA region table,
  corroborated by the local script; implementation now supports all 26
  manifest codes and provides `202605270002_full_manifest_map.sql` to expand
  live constraints/backfill known catalog suffixes.
- 2026-05-27: Operator-applied recovery/full-manifest migrations were verified
  by reimporting `1500` models, reading expanded `Find X8 Pro` mappings and
  completing a new one-task worker scan plus the previously interrupted run.
- 2026-05-27: Regional model probing was corrected to retry the upstream base
  model while retaining catalog identity; live `CPH2651ID / 33 / A` then
  returned `CPH2651_15.0.0.860(EX01)`. Reimport also filled 83 OnePlus
  manifests supported by explicit `(IN)`, `(EU)` and `(GLO)` catalog labels.
- 2026-05-27: Added domestic China catalog import from official OPPO CN specs,
  ColorOS ROM, OPPO Shop OnePlus/realme pages and maintainer-verified seed CSV.
- 2026-05-27: Ran the domestic China importer against Supabase after tightening
  model parsing. It imported `290` scan-enabled manifest `97` rows, removed two
  false positives from the earlier broad parser run (`PJ3E7P8IF`, `PRISM`), and
  verified current live candidates match stored domestic rows exactly.

## Acceptance Evidence

- `python -m pytest`: `83 passed` after domestic China catalog importer coverage.
- `python -m compileall -q src tests`: passed.
- `python -m pip install --dry-run -e ".[dev]"`: passed and resolved pinned
  upstream `realme-ota` revision plus Supabase dependencies without installing.
- `python -m ota_backend.worker --once --cycle-day 4 --max-tasks 1`: completed
  one offline fixture task with `completed=1 failed=0 new_releases=1`.
- Private live smoke on 2026-05-27 completed catalog import and persisted
  manual and worker-discovered releases. After both follow-up migrations were
  applied, worker run `93c6d3d4-0d18-4a31-82ad-a7156509275d` completed with
  one new release, and interrupted run `8f9149d7-f980-4865-a28d-94a22f798e87`
  resumed to completion without a duplicate new release.
- Domestic CN API smoke on 2026-05-27 returned `PKC110`, `PKG110`, and
  `RMX5200` from `/api/devices` with manifest `97`; bounded `PKC110 / 97 / C`
  OTA query reached the live provider and returned controlled `OTA_NOT_FOUND`.
  Worker run `a02aef86-bfe1-4582-990c-e58e7c87e002` completed `1` task and
  persisted one live release.
- Multi-OTA archive implementation on 2026-05-27 added LSCTool dry-run parsing,
  release archive metadata, per-device release filtering, and active-track
  skip policy. Offline validation passed with `92` tests. After applying
  `202605270003_release_archive_metadata.sql`, LSCTool archive import completed
  with `873` releases across `120` devices; `/api/releases` verified multi-OTA
  archive rows for `PKC110`, `PKG110`, `PLC110`, and `RMX5200`. Worker smoke
  `7f1ca961-6178-4e55-b186-303365abfade` completed one task with no duplicate
  new release after archive import.
- Archive regional normalization on 2026-05-27 routes LSCTool base-model
  buckets to an existing regional catalog device when base identity and
  manifest identify one target. `CPH2747` now contains only `GL/A7` archive
  rows while `CPH2747EEA` contains its `EEA/44` rows; all `873` imported
  archive rows were reconciled without a missing expected release.
