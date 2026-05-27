# Error Handling

Errors must be structured, sanitized, and useful for both browser and Telegram
callers. Internal traces can contain more operational detail, but secrets and
sensitive identifiers must still be excluded.

## Catalog Import

If Oxygen Updater returns `403`, times out, or changes response shape:

- keep existing Supabase catalog rows.
- record a failed `device_catalog_imports` entry with a sanitized error code.
- use the last successful catalog snapshot if an implementation has one.
- avoid disabling devices solely because one import failed.

Multi-value `product_names` must be split into separate candidate product
models. If brand or manifest inference is ambiguous, preserve the row with a
null or override-required manifest state instead of guessing.

## OTA Query

Manual OTA query should return:

- `VALIDATION_ERROR` for invalid model, manifest, track, or candidate input.
- `OTA_NOT_FOUND` when the provider returns a valid no-update result.
- `UPSTREAM_TIMEOUT` for request timeout.
- `UPSTREAM_ERROR` for retry-exhausted provider failures.
- `DECRYPT_ERROR` for response decryption or parse failure.

The implementation should store a new release only after parsing and safety
checks succeed.

## Scheduler

Scanner tasks should distinguish:

- completed with release.
- completed with no update.
- failed with retryable upstream error.
- failed with non-retryable validation error.
- skipped because the device is disabled or missing required manifest data.

Worker restart must not duplicate completed tasks, releases, or successful
Telegram notifications.

## Telegram

Recoverable Telegram delivery failures should leave notification records
retryable. Permission, missing topic, or invalid chat errors should be visible
in operational status and require configuration repair.

Telegram replies must use public error codes and safe messages only.

## Resolver

Resolver failures should map to stable codes:

- `RESOLVE_BLOCKED_HOST` for disallowed domains or unsafe IP ranges.
- `VALIDATION_ERROR` for invalid URL shape or scheme.
- `RESOLVE_FAILED` for timeout, redirect exhaustion, or unsupported provider
  response.
- `RATE_LIMITED` for resolver quota failures.

Every redirect hop must be validated before following.

## API Rate Limits

Rate-limited responses should use HTTP `429`, the standard error envelope, and
`Retry-After` plus `X-RateLimit-*` headers.

Public active requests must fail with `CHALLENGE_FAILED` when server-side
Turnstile validation does not succeed. Public OTA requests with beta or
identifier inputs fail with `VALIDATION_ERROR`; they are never sent upstream.

Admin routes fail with `AUTH_REQUIRED` for a missing/invalid Supabase Auth JWT
and `FORBIDDEN` when the authenticated user is not enabled in `admin_users`.

## Logging

Logs may include sanitized product metadata and error codes. Logs must not
include IMEI, GUID, Supabase keys, Telegram tokens, raw resolver URLs before
validation, raw encrypted request bodies, or full upstream protected payloads.
