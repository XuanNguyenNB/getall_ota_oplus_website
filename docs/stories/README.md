# Stories

Stories are work packets. They turn product intent into bounded implementation
and validation work.

Active and implemented story packets:

- `DOC-001`: `docs/stories/initiatives/DOC-001-docs-foundation/`
- `PHASE1-BACKEND-CORE`: `docs/stories/epics/E01-backend-core/PHASE1-BACKEND-CORE/`
- `PHASE2-WEB-UI`: `docs/stories/epics/E02-web-ui/PHASE2-WEB-UI/`

## Normal Story

Use `docs/templates/story.md` for normal feature work.

Suggested path:

```text
docs/stories/epics/E01-domain-name/US-001-short-story-title.md
```

## High-Risk Story

Use `docs/templates/high-risk-story/` when the feature intake classifies work as
high-risk.

Suggested path:

```text
docs/stories/epics/E02-risky-domain/US-012-risky-story-title/
  execplan.md
  overview.md
  design.md
  validation.md
```

## Status Flow

```text
planned -> in_progress -> implemented
                  |
                  v
               changed
                  |
                  v
               retired
```
