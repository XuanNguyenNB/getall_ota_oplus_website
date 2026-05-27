# Implementation Plan

Status: historical reference. This plan records the design direction that was
later backfilled into `docs/product/*` and `docs/reference/*`. It is not the
living product contract and does not indicate that application code, tests,
Docker files, migrations, CI, package manifests, or runtime configuration
exist.

Lộ trình implement sau khi đã chốt thiết kế (Concept B: nền tảng đầy đủ).

## Quyết định đã chốt

| Quyết định | Chọn |
|---|---|
| Scope | Concept B — 3 service, Supabase, scheduler, Telegram, resolver |
| License | Import trực tiếp `realme-ota` + GPLv3 toàn bộ |
| Storage | Supabase (8 bảng, migrate dần theo phase) |
| Test | Viết cùng code, dùng saved fixture |
| UI | Giữ mockup làm target cuối, làm UI đơn giản cho Phase 2 |

## Tổng quan 6 Phase

```
Phase 1: Backend Core + Manual Query    [2 tuần]
Phase 2: Web UI                         [1 tuần]
Phase 3: Scheduled Scanner              [2 tuần]
Phase 4: Telegram Bot                   [1.5 tuần]
Phase 5: URL Resolver                   [1 tuần]
Phase 6: Hardening + Finalize           [1 tuần]
----------------------------------------
Tổng dự kiến: ~8.5 tuần
```

---

## Phase 1: Backend Core + Manual Query (2 tuần)

**Mục tiêu**: Backend chạy được, query OTA thủ công qua API trả về link.

### Công việc

1. Tạo project skeleton:
   - FastAPI app với structure rõ ràng (`services/`, `models/`, `routers/`)
   - Uvicorn entrypoint
   - Config từ environment variables
   - Structured JSON logging

2. Supabase schema (2 bảng đầu tiên):
   - `devices`: catalog device đã normalize
   - `ota_releases`: releases đã tìm thấy
   - Migration scripts

3. Service `device_catalog`:
   - Fetch Oxygen Updater API `/devices/all`
   - Headers: `User-Agent: Oxygen_updater_7.1.0`, `X-Requested-With: com.arjanvlek.oxygenupdater`
   - Normalize: parse multi `product_names`, infer brand, infer manifest code từ suffix
   - Upsert vào `devices` table
   - Cache TTL 24h, fallback local file nếu upstream error
   - Lưu lịch sử import vào `device_catalog_imports`

4. Service `manifest_mapper`:
   - Map đầy đủ 12 entries: `00`, `A4`, `A5`, `A6`, `A7`, `1B`, `37`, `39`, `3C`, `44`, `51`, `97`
   - Suffix model → manifest code
   - Manifest code → NV ID + server region
   - Cho phép override thủ công

5. Service `ota_query`:
   - Import `realme-ota` trực tiếp (GPLv3)
   - Build seed OTA version: `{ota_model}_11.{track}.00_0000_000000000000`
   - Strip region suffix từ product_model để có ota_model
   - Retry logic: nếu seed version chưa kết thúc bằng `0001_000000000001`, thử lại
   - Parse & decrypt response
   - Persist kết quả vào `ota_releases`
   - KHÔNG log IMEI/GUID

6. API endpoints:
   - `GET /api/health`
   - `GET /api/devices` (từ Supabase, filter/search/pagination + `total`)
   - `POST /api/ota` (manual query)
   - `GET /api/releases` (lịch sử, filter/pagination)

7. Tests:
   - Unit: `manifest_mapper` (suffix → code, code → NV ID, code → server region)
   - Unit: OTA seed version builder (strip suffix, format version)
   - Unit: Response parser (decrypt mock, parse fields)
   - Integration: `POST /api/ota` dùng saved response fixture

### Done criteria
- `POST /api/ota` với `RMX3301 / 1B / H / rui_candidates=[8,7]` → 200 + download URL
- `GET /api/devices` trả catalog từ Supabase
- Unit tests pass: `pytest`
- Không hardcoded secrets trong code
- IMEI không xuất hiện trong log

---

## Phase 2: Web UI (1 tuần)

**Mục tiêu**: Giao diện web thay thế workflow terminal.

### Công việc

1. Static frontend (HTML/CSS/vanilla JS):
   - Served from FastAPI static mount
   - Form components:
     - Search input (autocomplete từ `/api/devices`)
     - Brand filter (All/OPPO/Realme/OnePlus)
     - Product model input (auto-fill từ device)
     - Manifest dropdown (auto-fill từ suffix)
     - Track selector (A/C/F/H)
     - RUI candidates input (default `8,7`)
     - Find OTA button
   - Kết quả: OTA version, displayed version, download URL + copy button
   - Bảng latest releases từ `/api/releases`
   - Error states: validation, OTA_NOT_FOUND, upstream timeout
   - LocalStorage: query history, track preference
   - Responsive CSS

2. UX behaviors:
   - Chọn device → fill product_model + manifest
   - Brand filter → filter devices + releases cùng brand
   - Copy URL button → clipboard + toast notification
   - Lưu track preference, dùng lại lần sau

### Done criteria
- Chọn device → form tự động fill → chọn track → Find OTA → hiện link
- Click copy → URL vào clipboard
- Filter brand hoạt động
- Error states hiển thị rõ ràng
- Responsive trên mobile

---

## Phase 3: Scheduled Scanner (2 tuần)

**Mục tiêu**: Tự động phát hiện OTA mới mỗi ngày.

### Công việc

1. Tách worker container:
   - Dockerfile riêng hoặc cùng image khác entrypoint
   - Chia sẻ code modules với web service

2. Supabase tables:
   - `scan_runs`: mỗi lần scan
   - `scan_tasks`: per-device task trong scan run

3. Scheduler logic:
   - 7-day sharding: `cycle_day = hash(product_model) % 7`
   - Mỗi ngày scan 1 shard
   - Track progression: bootstrap H→F→C→A, recurring check active + next track
   - OS/RUI candidates: thử theo thứ tự `[8,7]`, dừng khi có kết quả

4. Concurrency & retry:
   - Max 3 concurrent requests đến OPlus
   - Retry 2 lần cho transient errors (timeout, connection reset, 5xx)
   - Không retry validation errors
   - Atomic task claiming (UPDATE ... WHERE status='queued' RETURNING *)

5. API bổ sung:
   - `GET /api/scan/status`
   - `POST /api/admin/scan/enqueue` (protected: network rule hoặc internal secret)

### Done criteria
- Worker scan 1 daily shard hoàn tất
- Releases mới được insert
- Restart container → không duplicate tasks
- Scan status endpoint trả đúng

---

## Phase 4: Telegram Bot (1.5 tuần)

**Mục tiêu**: Nhận notification OTA mới qua Telegram.

### Công việc

1. Telegram bot container (long polling):
   - Dùng `python-telegram-bot` hoặc raw API
   - Long polling loop

2. Supabase tables:
   - `telegram_targets`: 3 dòng (OPPO/Realme/OnePlus), `chat_id`, `message_thread_id`
   - `telegram_notifications`: tracking delivery

3. Notification pipeline:
   - Worker phát hiện release mới → insert vào `telegram_notifications` (status=queued)
   - Bot poll hoặc worker gửi trực tiếp → Telegram `sendMessage` với `message_thread_id`
   - Dedup: unique (release_id, telegram_target_id)
   - Store `telegram_message_id` sau khi gửi

4. Commands:
   - `/resolve <url>`: forward đến resolver service
   - `/latest <model>`: lookup `ota_releases`
   - `/status`: scan run summary

5. Notification format:
   ```
   New OTA detected
   Brand: Realme
   Device: Realme GT2 Pro
   Model: RMX3301
   Manifest: IN / 1B
   Track: H
   Version: RMX3301_15.0.0.1410(EX01)
   Download: https://...
   ```

### Done criteria
- OTA mới → Telegram notify đúng topic brand
- `/latest RMX3301` → trả latest release
- `/status` → scan status summary
- Không gửi duplicate notification

---

## Phase 5: URL Resolver (1 tuần)

**Mục tiêu**: Resolve link OTA hết hạn.

### Công việc

1. Resolver service (shared module):
   - Dùng chung giữa web API và Telegram bot

2. Supabase table: `resolve_requests`

3. Security validation:
   - Allowlist domain suffix: `allawnofs.com`, `allawnos.com`, `allawntech.com`, `coloros.com`, `realmemobile.com`, `h2os.com`
   - Block: non-HTTP(S), localhost, private IP, loopback, link-local, multicast
   - DNS resolve → check IP trước khi request
   - Max 5 redirects, check mỗi hop

4. API/Command:
   - Web: `POST /api/resolve`
   - Telegram: `/resolve <url>`
   - Rate limit riêng: 10 req/phút

### Done criteria
- URL OPlus hợp lệ → resolved URL
- URL không hợp lệ/private IP → `RESOLVE_BLOCKED_HOST`
- Rate limit hoạt động

---

## Phase 6: Hardening + Finalize (1 tuần)

### Công việc

1. Rate limit: toàn bộ endpoints (30 req/phút/IP default)
2. Structured JSON logging:
   - Log: timestamp, model, manifest, track, status, latency, error code
   - KHÔNG log: IMEI, GUID, bot token, Supabase service-role key
3. Docker:
   - Healthcheck cho cả 3 containers
   - Docker Compose với internal network
4. Environment validation: kiểm tra biến bắt buộc khi startup
5. Backup strategy: Supabase backup, local fallback files
6. Finalize tài liệu: align tất cả file .md cho nhất quán

---

## Các file cần sửa/thêm mới

| File | Hành động | Phase |
|---|---|---|
| `README.md` | Viết lại cho đúng Concept B | 1 |
| `IMPLEMENTATION_PLAN.md` | Thay bằng file này | 1 |
| `API_SPEC.md` | Thêm pagination total, rate limit headers, các endpoint mới | 1 |
| `ARCHITECTURE.md` | Cập nhật 3 service + Supabase | 1 |
| `DEPLOYMENT.md` | Cập nhật docker-compose 3 service | 3 |
| `SECURITY_NOTES.md` | Thêm quyết định GPLv3, resolver security, Telegram security | 1 |
| **Mới**: `TEST_STRATEGY.md` | Unit/integration/E2E approach, fixtures, mock strategy | 1 |
| **Mới**: `ERROR_HANDLING.md` | Edge case catalog, fallback behavior | 1 |
| `DATABASE_SCHEMA.md` | Giữ nguyên, verify constraints + indexes | 1 |
| `DATA_SOURCES.md` | Giữ nguyên, OK | — |
| `SCHEDULER.md` | Giữ nguyên, OK | — |
| `RESOLVER.md` | Giữ nguyên, OK | — |
| `TELEGRAM_BOT.md` | Giữ nguyên, OK | — |
| `ui-preview/` | Giữ nguyên làm target cuối | — |

---

## Tổng kết mâu thuẫn cần sửa

| Vấn đề | Fix |
|---|---|
| `rui_version=6` vs `rui_candidates=[8,7]` | Chuẩn hóa `rui_candidates` array, default `[8,7]` |
| JSON cache vs Supabase | Đã chốt Supabase |
| 1 service vs 3 service | Đã chốt 3 service |
| Manifest map thiếu `00`, `51` | Thêm đủ 12 entries |
| Pagination thiếu `total` | Thêm `total` field |
| Rate limit thiếu headers | Thêm `Retry-After`, `X-RateLimit-*` |
| README lệch scope | Viết lại |
| DEPLOYMENT 1 container | Cập nhật 3 service |
