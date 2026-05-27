# Validation

## Proof Strategy

This story is docs-only. Proof is documentation consistency, Harness records,
and absence of runtime scaffolding. No runtime test can pass because no
application exists yet.

## Test Plan

| Layer | Cases |
| --- | --- |
| Unit | Planned only; no unit tests exist. |
| Integration | Planned only; no app or database integration exists. |
| E2E | Planned only; `ui-preview/` is mock reference material. |
| Platform | Confirm no Docker, CI, package, migration, app/service folder, or runtime scaffold was added. |
| Performance | Planned only. |
| Logs/Audit | Harness intake, story, decision, and trace records exist. |

## Fixtures

No executable fixtures exist yet. Planned future fixtures are listed in
`docs/product/test-strategy.md`.

## Commands

```text
scripts/harness query stats
scripts/harness query matrix
scripts/harness query decisions
scripts/harness query backlog
rg-based stale contradiction searches across root docs, product docs, story docs,
and Harness docs
```

## Acceptance Evidence

Accepted evidence for this docs-only story:

- Harness stats, matrix, decisions, and traces queries show the recorded
  DOC-001 work state.
- Contradiction searches show no current product-contract claim that runtime
  app behavior exists.
- Scaffold search shows no FastAPI app folder, Supabase migration folder,
  Docker file, package manifest, CI workflow, test suite, or runtime config.
- `ui-preview/` is marked as mock/reference material and remains outside the
  product source hierarchy.
