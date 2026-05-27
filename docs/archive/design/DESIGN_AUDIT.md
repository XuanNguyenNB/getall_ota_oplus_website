# Design Audit

Status: historical reference. This audit records the design review that led to
the accepted Concept B direction. Current product truth lives in
`docs/product/*`, with current runtime references in `docs/reference/*`. This
file must not be read as evidence that application code or runtime behavior
exists.

Kết quả rà soát toàn bộ 13 file tài liệu thiết kế (2026-05-26).

## Vấn đề chính: Scope creep

Bộ tài liệu mô tả 2 phiên bản sản phẩm khác nhau mà không phân biệt rạch ròi:

| Thành phần | README (Concept A) | Các file còn lại (Concept B) |
|---|---|---|
| Database | JSON file cache | Supabase 8 bảng |
| Services | 1 container | 3 containers (web, worker, bot) |
| API endpoints | 3 | 7 + admin |
| Scheduled scan | Không | 7-day sharding cycle |
| Telegram | Không | Bot + 3 topic + dedup |
| Resolver | Không | DNS validation + IP safety |

**Đã chốt**: Làm Concept B (nền tảng đầy đủ), chia thành 6 phase.

## 10 vấn đề thiết kế

### 1. Scope creep nghiêm trọng (đã chốt: Concept B)

**Quyết định**: Làm đầy đủ 3 service (web, worker, bot) + Supabase + Telegram + Resolver. Chia 6 phase, mỗi phase kết thúc bằng code chạy được.

### 2. Supabase overengineering cho Phase 1

Tool này là private, nhóm nhỏ dùng. Supabase mang theo chi phí vận hành (migration, backup, connection pool), độ trễ network, phụ thuộc service bên ngoài.

**Quyết định**: Vẫn dùng Supabase vì đã chọn Concept B, nhưng chỉ migrate 2 bảng đầu tiên (`devices`, `ota_releases`) trong Phase 1. Các bảng còn lại migrate theo từng phase.

### 3. GPLv3 License (đã chốt: Import + GPLv3)

Import trực tiếp `realme-ota` (`import realme_ota`). Toàn bộ project public source dưới GPLv3. GPLv3 phù hợp với tool cộng đồng, không phải commercial product.

### 4. Tài liệu mâu thuẫn cần align

| Điểm | README | IMPLEMENTATION_PLAN | API_SPEC | Fix |
|---|---|---|---|---|
| `rui_version` | default `6` | candidates `8,7` | `rui_candidates: [8,7]` | Chuẩn hóa về `rui_candidates` array, default `[8,7]` |
| Storage | JSON cache | Supabase | Supabase | Đã chốt Supabase |
| Số service | 1 | 3 | 3 | Đã chốt 3 service |
| Manifest map | 10 entries | 10 entries (thiếu `00`, `51`) | 12 entries (đủ) | Chuẩn hóa 12 entries |

### 5. Thiếu test strategy

Toàn bộ tài liệu không nhắc đến test. Cần bổ sung:
- Unit test: manifest mapper, OTA seed version builder, response parser
- Integration test: OTA query dùng saved response fixture (không spam endpoint thật)
- E2E test: Flow FE→BE→OTA query

**Quyết định**: Viết test cùng với code.

### 6. Thiếu error handling & edge cases

- Oxygen Updater API trả 403 → fallback ra sao?
- OPlus endpoint thay đổi format → detect thế nào?
- Model có nhiều `product_names` → VD `"CPH2805IN, CPH2805"` → lấy cái nào?
- Cache expired + upstream down → TTL tối đa bao lâu?

→ Cần file `ERROR_HANDLING.md` mô tả edge case + fallback behavior.

### 7. Thiếu monitoring & observability

Ngoài `/api/health`, cần thêm:
- Metrics: query thành công/thất bại, latency, cache hit rate
- Structured JSON logging
- Health check mở rộng (Supabase connection, last catalog sync)

### 8. UI preview lệch scope

Mockup hiển thị scan queue 1,445 devices, Telegram topics, resolver — đều thuộc Concept B cuối. UI Phase 2 sẽ đơn giản hơn: form + kết quả + bảng releases.

**Quyết định**: Giữ mockup làm target cuối. Tạo UI riêng cho Phase 2.

### 9. DEPLOYMENT.md chưa cập nhật

Chỉ mô tả 1 container. Cần cập nhật docker-compose.yml cho 3 service (web, worker, bot) + network + shared volumes.

### 10. API spec thiếu metadata

- Pagination: có `limit`/`offset` nhưng không có `total` → frontend không biết có trang tiếp theo
- Rate limit: không có `Retry-After` hoặc `X-RateLimit-*` headers
