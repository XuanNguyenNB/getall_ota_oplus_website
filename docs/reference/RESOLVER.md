# Resolver

The resolver turns supported OTA component links into a final URL without
proxying the package contents. Code and HTTP surface are present, but release
is deliberately blocked until a bounded live component-link proof succeeds.

## Release Gate

Default configuration:

```text
ENABLE_RESOLVER=false
RESOLVER_LIVE_PROOF_CONFIRMED=false
```

Until both are true, `POST /api/resolve` returns `FEATURE_NOT_ENABLED` and the
browser does not show the resolver form.

The proof run must validate a real component link obtained during private
Phase 1-3 activation. The local Universal OTA script documents a transformation
from `componentotacostmanual` to `opexcostmanual`; the app implements that
transform behind the release gate and validates all subsequent redirects.
China legacy direct CDN links under `gauss-componentotacostmanual-cn` are
validated with download-client metadata headers because the CDN rejects normal
browser navigation with `403`. The browser UI therefore avoids opening those
links directly and routes them through resolver validation instead. The
resolver still does not proxy package contents.

## Web Interface

When enabled:

```text
POST /api/resolve
```

```json
{"url": "https://allowed-ota-host/path/update.zip", "source": "web"}
```

In public mode it also requires `X-Turnstile-Token` and the resolver quota.
Telegram `/resolve` remains deferred until the web surface has live proof.

## Safety Rules

Configured allowlist default:

```text
allawnofs.com,allawnos.com,allawntech.com,allawnfs.com,coloros.com,realmemobile.com,h2os.com
```

The implementation:

- accepts HTTP(S) only and rejects URL credentials or non-standard ports;
- validates host suffixes;
- resolves DNS and rejects every non-global IP result;
- validates the transformed URL and every redirect target;
- sends the OPlus metadata headers required by `downloadCheck` endpoints and
  follows only validated redirect metadata to a final URL;
- enforces timeout and redirect count;
- uses metadata requests and does not stream package bytes through the app.

Only validated URLs are stored in `resolve_requests`; blocked inputs receive
sanitized history and structured errors.
