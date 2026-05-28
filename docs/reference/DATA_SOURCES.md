# Data Sources

This document lists the external and internal data sources used by the system.

## Oxygen Updater API

Used as the primary device catalog source.

Endpoint:

```text
https://oxygenupdater.com/api/v2.10/devices/all
```

Required headers:

```text
User-Agent: Oxygen_updater_7.1.0
X-Requested-With: com.arjanvlek.oxygenupdater
```

Example row:

```json
{
  "id": 1515,
  "name": "OnePlus Nord CE6 (IN)",
  "product_names": "CPH2805IN",
  "enabled": 1
}
```

Usage:

- Import enabled devices.
- Normalize multi-value `product_names` into one or more product models.
- Infer brand from name and product model.
- Infer manifest code from suffix when possible.
- Preserve manual overrides already stored in Supabase.

## China Domestic Catalog Sources

Used as supplemental official sources for domestic China models missing from
Oxygen Updater. Verified domestic rows use manifest `97` and are imported with
`scan_enabled=true`.

Commands:

```text
python -m ota_backend.catalog import-domestic-cn --dry-run
python -m ota_backend.catalog import-domestic-cn
python -m ota_backend.catalog import-all
```

Sources:

- OPPO China sitemap and smartphone `/specs/` pages, for example model codes
  such as `PKC110`.
- ColorOS ROM `brandList` and `productList` APIs for older OPPO firmware rows.
- OPPO-hosted OnePlus and realme listings plus OPPO Shop product pages, for
  domestic model codes such as `PLC110` and `RMX5200`.
- LSCTool `device_data.json` plus `default_regions.txt` as supplemental
  catalog coverage for China devices that are present in the OTA archive but
  missing from crawlable official listings, for example `RMX3800`.
- `data/domestic_cn_models.csv` for maintainer-verified seed rows that are no
  longer discoverable from crawlable official listing pages.

The importer records per-row provenance in `devices.source` using values such
as `oppo_cn_specs`, `coloros_rom`, `opposhop_cn`, `lsctool_cn_catalog`, and
`domestic_cn_seed`. Manual overrides are never overwritten.

## realme-ota

Used as the OTA request engine.

Repository:

```text
https://github.com/R0rt1z2/realme-ota
```

Required capabilities:

- Build OPlus OTA request body and headers.
- Encrypt requests with AES/RSA logic.
- POST to OPlus OTA endpoints.
- Decrypt OTA responses.
- Parse release metadata and download URLs.

The implementation imports `realme_ota.utils.request.Request` directly instead
of invoking the CLI or Bash wrapper. It only sends requests when
`ALLOW_LIVE_OTA=true`, and keeps GPLv3 attribution and corresponding-source
obligations as part of deployment.

## LSCTool OTA Archive

Used as a third-party supplemental archive for historical per-device OTA rows.
It is not treated as an official OPlus source.

Endpoints:

```text
https://ota.lsctool.online/data/ota_data.json
https://ota.lsctool.online/data/device_data.json
https://ota.lsctool.online/data/default_regions.txt
```

Commands:

```powershell
python -m ota_backend.catalog import-lsctool-archive --dry-run
python -m ota_backend.catalog import-lsctool-archive
```

The importer stores `.zip` and `downloadCheck` links exactly as supplied,
marks archive rows with `source=lsctool_archive`, maps region codes to manifest
codes, and records `official` versus `beta` type. Missing China devices created
from archive rows are visible and scan-enabled; non-China archive-only devices
remain hidden from the default device picker. It does not resolve links or
enqueue Telegram notifications during archive backfill.

## OPlus OTA Endpoints

The exact endpoint is selected by `realme-ota` based on OS/RUI version and region.

PC/component endpoints:

```text
https://component-otapc-sg.allawnos.com/update/v3
https://component-otapc-cn.allawntech.com/update/v3
https://component-otapc-in.allawnos.com/update/v3
https://component-otapc-eu.allawnos.com/update/v3
```

Legacy/component endpoints:

```text
https://component-ota-f.coloros.com/update/v3
https://component-ota.coloros.com/update/v3
https://component-ota-in.coloros.com/update/v3
https://component-ota-eu.coloros.com/update/v3
```

OnePlus legacy endpoint:

```text
https://otag.h2os.com/post/Query_Update
```

## Supabase

Supabase Postgres is the persistent database.

It stores:

- imported devices
- manual device overrides
- discovered OTA releases
- scan runs and scan tasks
- Telegram topic targets
- Telegram notification delivery state
- resolver request history

The new secret key or legacy service-role key must only be used server-side.
The live repositories are selected with `REPOSITORY_BACKEND=supabase`; browser
code still talks only to FastAPI.

## Telegram Bot API

Used for release notifications and user commands.

The bot sends messages to a forum supergroup with `chat_id` and `message_thread_id`. There are three target topics:

- OPPO
- Realme
- OnePlus

The implemented bot drains notification records and handles `/latest <model>`
and restricted `/status`. Telegram `/resolve` remains deferred until web
resolver live proof succeeds.

## Cloudflare Turnstile And Tunnel

Public active operations use Turnstile tokens validated only by FastAPI with a
server secret. Public deployment routes through Cloudflare Tunnel; the origin
web container is not host-published.

## Local Fallback Files

Local fallback files are optional operational aids, not the main database.

Possible files:

```text
data/devices_seed.txt
data/catalog_snapshot.json
```

These can be used to bootstrap Supabase or recover from upstream catalog issues.

## Reference-Only Sources

These sources are useful for validation but should not be treated as authoritative APIs:

- 4PDA attachments and scripts.
- `ota.lsctool.online` static OTA data.
- APK contents from OS Updater, except for identifying public API behavior.

## Manifest Map Requirement

The app must support the complete accepted manifest map before live OTA queries
are enabled:

```text
00, A4, A5, A6, A7, 1A, 1B, 1E, 2C, 33, 37, 38, 39, 3B,
3C, 3E, 44, 51, 75, 7B, 82, 83, 8D, 97, 9A, 9E
```

The implemented 26-code mapping uses the maintainer-approved local Universal
OTA DownloadeR `REGIONS` and `SERVERS` map. Known catalog suffixes such as
`EEA`, `ID`, `MX`, `MY`, `OCA`, `SG`, and `TW` are mapped to that table;
OnePlus name labels such as `(IN)`, `(EU)` and `(GLO)` are mapped when model
codes do not carry the region. Unknown suffixes such as `KZ`, `LK` and `NA`
still require an explicit manifest override instead of guessing, although the
live provider can retry a query using a stripped base model after an explicit
manifest selection.
