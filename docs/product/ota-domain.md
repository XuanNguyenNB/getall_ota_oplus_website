# OTA Domain Contract

This document defines the planned OTA query rules independent of framework or
database implementation.

## Device Catalog

The primary catalog source is Oxygen Updater:

```text
https://oxygenupdater.com/api/v2.10/devices/all
```

Catalog import must:

- send the required Oxygen Updater headers.
- import enabled devices.
- split multi-value `product_names` into individual product models.
- infer brand from the catalog row and model pattern where possible.
- infer manifest code from a mapped product-model suffix or an explicit mapped
  catalog region label such as `(IN)`, `(EU)` or `(GLO)`.
- preserve manual overrides stored in Supabase.
- store catalog import history.

Domestic China import supplements Oxygen with official OPPO, OnePlus and
realme sources. Verified domestic rows use manifest `97`, keep source
provenance, and are scan-enabled by default.

Historical multi-release archive rows can be imported from the LSCTool static
dataset. These rows are marked as third-party archive data, keep original
download or `downloadCheck` links unchanged, and do not trigger Telegram
notifications during backfill.

## Manifest Map Coverage

The manifest map covers the complete 26-code Universal OTA `REGIONS` table:

| Code | Region label | Expected use |
| --- | --- | --- |
| `00` | EX | Export |
| `A4` | APC | Global |
| `A5` | OCA | Oceania/Central Australia |
| `A6` | MEA | Middle East/Africa |
| `A7` | ROW | Global |
| `1A` | TW | Taiwan |
| `1B` | IN | India |
| `1E` | AU | Australia |
| `2C` | SG | Singapore |
| `33` | ID | Indonesia |
| `37` | RU | Russia |
| `38` | MY | Malaysia |
| `39` | TH | Thailand |
| `3B` | JP | Japan |
| `3C` | VN | Vietnam |
| `3E` | PH | Philippines |
| `44` | EUEX | Europe |
| `51` | TR | Turkey |
| `75` | EG | Egypt |
| `7B` | MX | Mexico |
| `82` | HK | Hong Kong |
| `83` | SA | Saudi Arabia |
| `8D` | EU-NO | Europe Non-GDPR |
| `97` | CN | China |
| `9A` | LATAM | Latin America |
| `9E` | BR | Brazil |

Implementation must map each code to the correct OPlus NV ID and server region
before live OTA queries are enabled. Unknown suffixes should require explicit
manifest override instead of guessing.

### Live Mapping Status

The maintainer approved the Universal OTA DownloadeR `REGIONS` and `SERVERS`
mapping as the live request source. Server region values below are endpoint
selectors used by that workflow, not inferred geography:

| Code | NV ID | Server region |
| --- | --- | --- |
| `00` | `00000000` | `3` |
| `A4` | `10100100` | `3` |
| `A5` | `10100101` | `3` |
| `A6` | `10100110` | `3` |
| `A7` | `10100111` | `3` |
| `1A` | `00011010` | `3` |
| `1B` | `00011011` | `3` |
| `1E` | `00011110` | `3` |
| `2C` | `00101100` | `3` |
| `33` | `00110011` | `3` |
| `37` | `00110111` | `3` |
| `38` | `00111000` | `3` |
| `39` | `00111001` | `3` |
| `3B` | `00111011` | `3` |
| `3C` | `00111100` | `3` |
| `3E` | `00111110` | `3` |
| `44` | `01000100` | `0` |
| `51` | `01010001` | `0` |
| `75` | `01110101` | `3` |
| `7B` | `01111011` | `3` |
| `82` | `10000010` | `3` |
| `83` | `10000011` | `3` |
| `8D` | `10001101` | `3` |
| `97` | `10010111` | `1` |
| `9A` | `10011010` | `3` |
| `9E` | `10011110` | `3` |

Live OTA queries remain opt-in through `ALLOW_LIVE_OTA=true`.

## OTA Tracks

Supported tracks are:

```text
A -> C -> F -> H
```

New-device bootstrap checks tracks from highest to lowest priority:

```text
H, F, C, A
```

Recurring scans check the active track and the next track only.

### Phase 3 Scanner Status

The scanner implements the accepted bootstrap and recurring track rules against
both offline repositories and the opt-in Supabase/live-provider runtime.
Worker-discovered releases are persisted with `discovered_by="worker"`.

## OS/RUI Candidates

Requests use `rui_candidates`, not a single user-facing `rui_version` input.

Default:

```text
[8, 7]
```

The query flow tries candidates from left to right and stores the winning
candidate as `rui_version` on a discovered release.

## Seed Version Rule

The planned seed OTA version format is:

```text
{ota_model}_11.{track}.00_0000_000000000000
```

`ota_model` is derived from `product_model` by stripping known region suffixes
where the OPlus endpoint expects the base model. For live queries, the provider
first tries the selected catalog model and then its derived base model when
they differ, while preserving the selected catalog model on the stored result.
Catalog aliases such as `KZ`, `LK`, `IND` and `_IND` may participate in this
query fallback without being treated as evidence for a manifest code.

## Release Identity

A release is unique by:

```text
product_model + manifest_code + real_ota_version + download_url
```

If an existing release is rediscovered, the implementation should update
`last_seen_at` or equivalent scan evidence instead of inserting a duplicate.

The in-memory repository and live Supabase release-upsert RPC update
`last_seen_at` when a scanner sees an already-known release.

## Stored Metadata

The system stores OTA metadata and links, not OTA package contents.

Expected release metadata includes:

- brand
- product model
- manifest code
- OTA track
- winning `rui_version`
- real OTA version
- displayed version name
- computed OTA version
- version type ID
- about update URL
- download URL
- optional checksum, size, security patch, and sanitized raw response when
  explicitly enabled
