# Test Matrix

This file maps product behavior to proof.

Product behavior is defined in `docs/product/*`. Mark a row implemented only
after its tests or validation evidence exist.

## Status Values

| Status | Meaning |
| --- | --- |
| planned | Accepted as intended behavior, not implemented |
| in_progress | Actively being built |
| implemented | Implemented and proof exists |
| changed | Contract changed after earlier implementation |
| retired | No longer part of the product contract |

## Matrix

| Story | Contract | Unit | Integration | E2E | Platform | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | Docs-only Concept B product foundation | no | no | no | yes | implemented | Docs-only foundation completed; platform proof is absence of app/runtime scaffolding. Product runtime behavior remains planned only. |
| PHASE1-BACKEND-CORE | FastAPI backend core, config/logging, initial migrations, and fixture-backed Phase 1 endpoints | yes | yes | no | yes | implemented | `python -m pytest` passed; Uvicorn local `/api/health` smoke returned documented envelope. |
| PHASE2-WEB-UI | FastAPI-served browser UI for catalog search, standard OTA query and release archive browsing | no | yes | yes | yes | implemented | `python -m pytest` passed; `python scripts/validate_phase2_ui.py` passed and writes realbrowser screenshots, console/network evidence, HAR, server logs, and summary proof under `validation-artifacts/phase2-web-ui/<run-id>/`. |
| PHASE3-SCHEDULED-SCANNER | Offline scanner, scan-status API, migration shape, and queued notification records | yes | yes | no | yes | implemented | `python -m pytest` passed; offline worker smoke completed a fixture shard with one new release. |
| PHASE1-3-LIVE-BACKING | Opt-in Supabase/Oxygen/live `realme-ota` adapters and atomic runtime RPC migration | yes | yes | no | yes | implemented | Live smoke on 2026-05-27 completed catalog import and manual OTA persistence. Recovery/full-manifest migrations were applied and bounded worker runs completed. |
| PUBLIC-GATEWAY-ADMIN | Turnstile, hashed quotas/cache, Supabase Auth admin boundary, enqueue API | yes | yes | no | no | implemented | Automated API and migration proof; remote Auth/Turnstile/Tunnel smoke remains pending. |
| PHASE4-TELEGRAM-DELIVERY | Notification consumer, retry state, `/latest` and restricted `/status` | yes | yes | no | no | implemented | Mocked transport delivery/failure proof and RPC migration checks; no real Bot API send performed. |
| PHASE5-RESOLVER-GATED | Safe resolver module/API/UI behind live-proof release gate | yes | yes | no | no | implemented | Transform, unsafe DNS, gate and migration proof; endpoint must remain disabled until real component-link proof. |
| PHASE6-DEPLOYMENT-ARTIFACTS | Compose, Tunnel ingress shape, worker timer and CI | yes | no | no | no | implemented | Static artifact tests cover no host-published web port, web-health-gated Tunnel startup, optional bot profile, one-shot worker profile and CI config; container/Tunnel/VPS/public launch validation remains to be executed. |

## Evidence Rules

- Unit proof covers pure domain and application rules.
- Integration proof covers backend enforcement, data integrity, provider
  behavior, jobs, or service contracts.
- E2E proof covers user-visible browser flows.
- Platform proof covers only shell, deployment, mobile, desktop, or runtime
  behavior that cannot be proven in lower layers.
- A story can be implemented without every proof column if the story packet
  explains why.
