// format.js
//
// Pure helpers used by render code. ``escapeHtml`` is the standard
// guard for anywhere we interpolate untrusted data into template
// strings, including for download URLs and version strings that can
// contain user-controlled characters.

const MANIFEST_LABELS = {
  "00": "EX",
  A4: "APC",
  A5: "OCA",
  A6: "MEA",
  A7: "ROW",
  "1A": "TW",
  "1B": "IN",
  "1E": "AU",
  "2C": "SG",
  "33": "ID",
  "37": "RU",
  "38": "MY",
  "39": "TH",
  "3B": "JP",
  "3C": "VN",
  "3E": "PH",
  "44": "EUEX",
  "51": "TR",
  "75": "EG",
  "7B": "MX",
  "82": "HK",
  "83": "SA",
  "8D": "EU-NO",
  "97": "CN",
  "9A": "LATAM",
  "9E": "BR",
};

export function brandLabel(brand) {
  const lower = String(brand || "").toLowerCase().trim();
  if (lower === "oppo") return `<span class="brand-badge oppo">OPPO</span>`;
  if (lower === "realme") return `<span class="brand-badge realme">Realme</span>`;
  if (lower === "oneplus") return `<span class="brand-badge oneplus">OnePlus</span>`;
  return brand || "-";
}

export function releaseRegionLabel(release) {
  const manifestCode = release.manifest_code || "";
  const manifestLabel = MANIFEST_LABELS[manifestCode] || manifestCode || "";
  const regionCode = release.region_code || "";
  if (!manifestCode) return regionCode || "-";
  if (!regionCode || regionCode === manifestLabel) return `${manifestLabel} / ${manifestCode}`;
  return `${manifestLabel} (${regionCode}) / ${manifestCode}`;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function releaseSortTimestamp(release) {
  const direct = Date.parse(release.published_at || "");
  if (!Number.isNaN(direct)) return direct;
  const aboutMatch = String(release.about_update_url || "").match(
    /\/(?:component-ota|ota)\/(\d{2})\/(\d{2})\/(\d{2})\//,
  );
  if (aboutMatch) {
    const parsed = Date.UTC(2000 + Number(aboutMatch[1]), Number(aboutMatch[2]) - 1, Number(aboutMatch[3]));
    if (!Number.isNaN(parsed)) return parsed;
  }
  const otaMatch = String(release.real_ota_version || "").match(/_(\d{12})$/);
  if (otaMatch) {
    const raw = otaMatch[1];
    const parsed = Date.UTC(
      Number(raw.slice(0, 4)),
      Number(raw.slice(4, 6)) - 1,
      Number(raw.slice(6, 8)),
      Number(raw.slice(8, 10)),
      Number(raw.slice(10, 12)),
    );
    if (!Number.isNaN(parsed)) return parsed;
  }
  const discovered = Date.parse(release.discovered_at || "");
  return Number.isNaN(discovered) ? 0 : discovered;
}

export function releasePublishedLabel(release) {
  if (release.published_at) return formatDate(release.published_at);
  const timestamp = releaseSortTimestamp(release);
  return timestamp ? formatDate(new Date(timestamp).toISOString()) : "-";
}

export function edlSortTimestamp(rom) {
  const build = Date.parse(rom.build_date || "");
  if (!Number.isNaN(build)) return build;
  const updated = Date.parse(rom.source_updated_at || "");
  if (!Number.isNaN(updated)) return updated;
  return 0;
}

export function edlDateLabel(rom) {
  const timestamp = edlSortTimestamp(rom);
  return timestamp ? formatDate(new Date(timestamp).toISOString()) : "-";
}
