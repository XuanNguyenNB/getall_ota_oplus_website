# Design

## Domain Model

Phase 1 owns the core device, release, manifest, and OTA query types. Manifest
code validation accepts the 12 product-approved codes, but live query enablement
is limited to codes with authoritative upstream evidence for both NV ID and
server region.

The read-only `realme-ota` reference confirms:

- server regions: `0=GL`, `1=CN`, `2=IN`, `3=EU`
- default NV IDs: `1B=00011011` for IN, `44=01000100` for EU, `97=10010111`
  for CN
- import surface: `realme_ota.utils.request.Request`

The remaining accepted manifest codes stay blocked for live OTA use until their
exact NV ID and server region are verified from authoritative references.

## Application Flow

API routes call application services, which use repository and provider
interfaces. The default local runtime uses in-memory repositories and a fake OTA
provider so the backend starts without Supabase credentials and tests do not
perform network traffic.

`POST /api/ota` validates request shape, calls the configured provider, and
persists the release through the release repository when `persist_result` is
true.

## Interface Contract

The Phase 1 routes preserve the accepted JSON envelopes, list pagination fields,
and sanitized error format from `docs/reference/API_SPEC.md` and
`docs/product/api-conventions.md`.

Validation and provider failures return:

- `VALIDATION_ERROR`
- `OTA_NOT_FOUND`
- `UPSTREAM_TIMEOUT`
- `UPSTREAM_ERROR`
- `DECRYPT_ERROR`
- `INTERNAL_ERROR`

## Data Model

The initial migration creates:

- `devices`
- `ota_releases`

The release uniqueness key is:

```text
product_model + manifest_code + real_ota_version + download_url
```

## UI / Platform Impact

No production UI, Docker, CI, worker, Telegram, or resolver platform work is in
scope. The service is locally runnable with Uvicorn.

## Observability

The backend emits structured JSON request logs with a request ID, method, path,
status code, duration, and sanitized fields. IMEI, GUID, tokens, authorization
headers, service keys, protected keys, and request bodies are redacted when
passed through the logging sanitizer.

## Alternatives Considered

1. Directly vendor or depend on `realme-ota` in Phase 1. Deferred because GPLv3
   project-level distribution obligations and incomplete manifest mapping need a
   maintainer decision before live query enablement.
2. Use live Supabase in tests. Rejected because Phase 1 proof must be offline
   and must not require production secrets.
