# API Conventions

The FastAPI web service uses JSON success/error envelopes and list pagination
with `count`, `total`, `limit` and `offset`.

## Implemented Surfaces

- `GET /api/health`, `GET /api/devices`, `GET /api/releases`.
- `POST /api/ota`: private behavior by default; public standard-only behavior
  with `X-Turnstile-Token`, quota and cache source headers when enabled.
- `GET /api/scan/status`: admin-only when public mode is enabled.
- `POST /api/admin/scan/enqueue`: always requires admin authorization.
- `POST /api/resolve`: exists but returns `FEATURE_NOT_ENABLED` until the
  resolver live-proof configuration is explicitly enabled.

Admin authorization is `Authorization: Bearer <Supabase Auth JWT>` plus an
enabled `admin_users` row, checked server-side.

## Errors

Errors have the form:

```json
{"ok": false, "error": {"code": "VALIDATION_ERROR", "message": "Invalid request."}}
```

Security-related codes include `CHALLENGE_FAILED`, `AUTH_REQUIRED`,
`FORBIDDEN`, `RATE_LIMITED`, `RESOLVE_BLOCKED_HOST` and
`FEATURE_NOT_ENABLED`. Error text must remain safe for public and Telegram
display.

Rate-limited responses include `Retry-After`, `X-RateLimit-Limit`,
`X-RateLimit-Remaining` and `X-RateLimit-Reset`.
