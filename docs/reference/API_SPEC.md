# API Spec

All endpoints return JSON. Offline/private mode preserves the original Phase
1-3 workflow. Public mode is enabled only with `PUBLIC_SITE_ENABLED=true` and
adds challenge/auth controls.

## Implemented Endpoints

### `GET /api/health`

Returns service identity and browser-safe feature flags:

```json
{
  "ok": true,
  "service": "getall_ota_oplus_website",
  "version": "0.1.0",
  "features": {
    "public_site": false,
    "resolver": false,
    "turnstile_site_key": null,
    "admin_auth_enabled": false
  }
}
```

The Turnstile site key is public widget configuration. No server secret is
returned. The Supabase URL and anon key are no longer echoed here; the admin
UI obtains them through `GET /api/admin/bootstrap` so the obvious liveness
URL cannot be scraped for credential pairs.

### `GET /api/admin/bootstrap`

Returns the Supabase Auth bootstrap config used by the admin UI to construct
a Supabase client before the operator signs in. Cannot itself require admin
auth (the JWT does not exist yet); the anon key is the documented public
Supabase credential and is protected by RLS plus admin allowlist tables.

```json
{
  "ok": true,
  "admin_auth": {
    "supabase_url": "https://project-ref.supabase.co",
    "supabase_anon_key": "anon-public-key"
  }
}
```

When Supabase is not configured, `admin_auth` is `null`.

### `GET /api/devices`

Lists catalog-visible devices with `q`, `brand`, `enabled_only`,
`scan_enabled_only`, `limit` and `offset`. `enabled_only=true` now means
`catalog_visible=true`; `scan_enabled_only=true` filters scan-capable
`active_scan` variants. Responses include `count`, `total`, `limit`, `offset`
and `devices`. Device items include `scan_group_key`, `scan_group_name`,
`scan_eligibility` and sanitized failure metadata so operator tooling can
group variants such as China/global/region models under one user-facing device
family and explain why a variant is not being crawled.

### `POST /api/ota`

Runs a manual OTA query and persists a parsed release when requested:

```json
{
  "product_model": "RMX3301",
  "manifest_code": "1B",
  "ota_track": "H",
  "rui_candidates": [8, 7],
  "language": "en-EN",
  "beta": false,
  "imei0": null,
  "imei1": null,
  "guid": null,
  "persist_result": true
}
```

When public mode is disabled, this keeps the Phase 1 behavior. When public
mode is enabled:

- header `X-Turnstile-Token` is required;
- `beta=true`, `imei0`, `imei1` and `guid` are rejected;
- standard requests are limited initially to 5/hour per hashed client
  boundary;
- a fresh matching release can be returned without another upstream request;
- response header `X-OTA-Source` is `cache` or `live`.

Public OTA queries strictly reject the operator-only fields `imei0`, `imei1`,
`guid` and `beta=true` at the schema boundary. They are stripped before reaching
the live provider and produce a `VALIDATION_ERROR` with HTTP 400. Identified
operator queries continue to use the same endpoint without public mode enabled.

### `GET /api/releases`

Lists persisted releases with `q`, `brand`, `product_model`, `manifest_code`,
`region_code`, `release_type`, `source`, `sort=discovered|published`, `limit`
and `offset`. Responses include pagination metadata and `releases`. Release
items include track, manifest, RUI/source archive metadata, about-update URL,
security patch and download URL. The browser UI does not display `source`, but
the field remains part of the API for internal provenance, debugging and
live-provider cache isolation.

### `GET /api/edl-roms`

Lists supplemental EDL ROM archive links with `q`, `brand`, `product_model`,
`region_code`, `sort=build|imported`, `limit` and `offset`. Responses include
pagination metadata and `roms`.

EDL items include brand, product model, optional device name, region, version
name, build date, direct download URL, source and source update time. These
links are displayed as archive links only; the API does not proxy, mirror or
resolve ROM contents.

### `GET /api/scan/status`

Reads the latest scanner run from the configured repository backend. In
private/offline mode it is available to the operator. In public mode it
requires an enabled Supabase Auth admin bearer token.

### `POST /api/admin/scan/enqueue`

Implemented admin-only endpoint. It creates a queued scan run for known
devices:

```json
{"product_models": ["RMX3301"], "reason": "manual"}
```

The worker processes that run with:

```powershell
python -m ota_backend.worker --once --scan-run-id <uuid>
```

### `POST /api/resolve`

Implemented behind the resolver release gate. Unless both
`ENABLE_RESOLVER=true` and `RESOLVER_LIVE_PROOF_CONFIRMED=true` are configured,
the endpoint returns `FEATURE_NOT_ENABLED`.

When enabled it accepts:

```json
{"url": "https://allowed-ota-host/path/update.zip", "source": "web"}
```

Public mode additionally requires `X-Turnstile-Token` and applies the
resolver quota. The service validates host, DNS/IP safety and every redirect
without proxying OTA contents.

## Admin Authentication

Admin endpoints accept:

```text
Authorization: Bearer <supabase-auth-user-jwt>
```

The JWT user must have an enabled server-side `admin_users` row. Supabase
secret/service-role keys are never browser credentials.

## Errors And Rate Limits

Errors use:

```json
{"ok": false, "error": {"code": "VALIDATION_ERROR", "message": "Invalid request."}}
```

Implemented or reserved codes include `AUTH_REQUIRED`, `FORBIDDEN`,
`CHALLENGE_FAILED`, `RATE_LIMITED`, `OTA_NOT_FOUND`, `UPSTREAM_TIMEOUT`,
`UPSTREAM_ERROR`, `DECRYPT_ERROR`, `RESOLVE_BLOCKED_HOST`, `RESOLVE_FAILED`
and `FEATURE_NOT_ENABLED`.

HTTP `429` responses include `Retry-After`, `X-RateLimit-Limit`,
`X-RateLimit-Remaining` and `X-RateLimit-Reset`.
