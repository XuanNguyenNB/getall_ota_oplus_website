// url-safety.js
//
// Defense-in-depth URL helpers. The backend already filters the
// download_url and resolver inputs, but we re-check here so a poisoned
// download URL (javascript:, data:, file:, custom schemes) can never
// reach window.open or the clipboard. The functions here are pure and
// browser-only — they belong in their own module so app.js does not
// have to re-define what "safe" means in three different places.

const RESOLVABLE_FRAGMENTS = [
  "downloadcheck",
  "servlet/download",
  "componentotacostmanual",
  "compotacostauto",
];

const BROWSER_BLOCKED_FRAGMENTS = [
  "gauss-componentotacostmanual-cn.",
  "gauss-compotacostauto-cn.",
  "gauss-opexcostmanual-cn.",
];

export function isResolvableDownloadUrl(value) {
  const lower = String(value || "").toLowerCase();
  return RESOLVABLE_FRAGMENTS.some((fragment) => lower.includes(fragment));
}

export function isBrowserBlockedDownloadUrl(value) {
  const lower = String(value || "").toLowerCase();
  if (BROWSER_BLOCKED_FRAGMENTS.some((fragment) => lower.includes(fragment))) {
    return true;
  }
  // Anything that is not a safe http(s) URL (e.g. javascript:, data:, file:,
  // empty, malformed) must be treated as browser-blocked so callers never
  // render an "Open" affordance that would invoke window.open with it.
  return !isSafeNetworkUrl(value);
}

export function isSafeNetworkUrl(value) {
  if (typeof value !== "string" || value.length === 0) return false;
  const trimmed = value.trim();
  if (trimmed.length === 0) return false;
  try {
    const parsed = new URL(trimmed, window.location.origin);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch (_error) {
    return false;
  }
}

export function safeWindowOpen(url) {
  if (!isSafeNetworkUrl(url)) return false;
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}
