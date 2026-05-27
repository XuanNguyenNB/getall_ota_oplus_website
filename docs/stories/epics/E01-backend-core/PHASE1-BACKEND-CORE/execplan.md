# Exec Plan

## Goal

Create the first runnable backend slice for Phase 1 manual OTA discovery.

## Scope

In scope:

- FastAPI app scaffolding.
- Server-side settings.
- Structured sanitized JSON logging.
- Domain, provider, and repository interfaces.
- In-memory repositories for local and test use.
- Fake OTA provider fixtures.
- Gated `realme-ota` adapter import boundary.
- `GET /api/health`.
- `GET /api/devices`.
- `POST /api/ota`.
- `GET /api/releases`.
- Initial Supabase/Postgres migration for devices and releases.
- Offline pytest coverage.
- Manual live smoke-check documentation for later maintainer use.

Out of scope:

- Production UI.
- Scheduler or worker.
- Telegram bot.
- Resolver endpoint.
- Docker deployment.
- CI.
- Live OPlus OTA traffic.
- App-level authentication.

## Risk Classification

Risk flags:

- Data model.
- External systems.
- Public contracts.
- Audit/security logging.
- Weak proof.
- Multi-domain.

Hard gates:

- Data model.
- External provider behavior.
- Audit/security.

Lane: high-risk.

## Work Phases

1. Discovery.
2. Story and validation planning.
3. Backend scaffolding.
4. Domain/provider/repository implementation.
5. Migration and docs updates.
6. Offline tests and local startup verification.
7. Harness trace.

## Stop Conditions

Pause for human confirmation if:

- Understanding `realme-ota` behavior requires live OTA traffic.
- Accepted manifest NV ID or server-region values are missing or ambiguous.
- GPLv3 integration requires a project-level licensing decision.
- Supabase behavior cannot be modeled locally without real credentials.
- Implementing an endpoint requires changing the accepted API contract.
- Scope pressure pulls in UI, worker, Telegram, resolver, Docker, CI, or
  production deployment work.
