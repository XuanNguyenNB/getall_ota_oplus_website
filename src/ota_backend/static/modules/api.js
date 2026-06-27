// api.js
//
// Single fetch wrapper for the public site. Every error is surfaced
// as a plain Error with an ``apiError`` payload so render code can
// uniformly format it via displayError().

import { t } from "./i18n.js";

export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.ok === false) {
    const fallback = {
      code: `HTTP_${response.status}`,
      message: response.statusText || t("error.requestFailed"),
    };
    const error = body?.error || fallback;
    throw Object.assign(new Error(error.message), { apiError: error, status: response.status });
  }
  return body;
}

export function clientError(code, message) {
  return Object.assign(new Error(message), {
    apiError: { code, message },
  });
}
