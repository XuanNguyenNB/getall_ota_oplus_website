# Story Backlog

This backlog lists broad candidate implementation epics. Do not slice every
future feature up front; create story packets only when work is selected.

Do not create every possible story packet up front. Create story packets when
the work is selected or when a product decision needs a durable place to land.

## Candidate Epics

| Epic | Description | Status |
| --- | --- | --- |
| E01-backend-core | Backend core, schema, catalog, manifest mapping, and OTA query | implemented locally; live proof pending |
| E02-web-ui | Browser UI for manual query and latest releases | implemented locally |
| E03-scheduler | Worker scanner with 7-day sharding and resumable tasks | implemented locally; live proof pending |
| E04-telegram | Telegram notification delivery, forum topic routing, and commands | implemented locally; live proof pending |
| E05-resolver | Web-first resolver with SSRF protection and history | implemented gated; live proof pending |
| E06-hardening | Public gateway, auth, deployment, and security verification | implemented locally; launch proof pending |
