// i18n.js
//
// Translation runtime. The actual strings live in
// ``static/i18n/{vi,en}.json`` and are fetched on demand. This keeps
// the bundled JS small (the dictionaries were the largest part of
// ``app.js`` before) and lets non-developers update copy without
// editing JavaScript.
//
// Module shape:
//
// - ``loadLanguage(lang)`` fetches and caches a language dictionary.
//   Returns once the dictionary is in memory.
// - ``t(key, params)`` looks up a translation in the current language,
//   falling back to English and then to the key itself.
// - ``applyTranslations(root)`` rewrites the static parts of the DOM
//   for the current language.
//
// The orchestrator (``app.js``) awaits ``loadLanguage(state.language)``
// before the first render so the initial paint is never the raw keys.

import { state } from "./state.js";

// In-memory cache of fetched dictionaries keyed by language code. The
// first lookup for a language hits the network; subsequent lookups
// return the cached object synchronously.
export const translations = Object.create(null);

// Track in-flight fetches so concurrent ``loadLanguage`` calls for the
// same code share a single network request.
const inflight = Object.create(null);

const SUPPORTED_LANGUAGES = ["vi", "en"];

export function normalizeLanguage(language) {
  return language === "en" ? "en" : "vi";
}

async function fetchLanguage(language) {
  // ``/static/i18n/<lang>.json`` is mounted by FastAPI's StaticFiles
  // handler. We assume network errors (offline, 404) are
  // exceptional; the caller surfaces them by falling back to the raw
  // key via ``t``.
  const response = await fetch(`/static/i18n/${language}.json`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`i18n: failed to load ${language}: HTTP ${response.status}`);
  }
  const dictionary = await response.json();
  translations[language] = dictionary;
  return dictionary;
}

export function loadLanguage(language) {
  const normalized = SUPPORTED_LANGUAGES.includes(language) ? language : "vi";
  if (translations[normalized]) return Promise.resolve(translations[normalized]);
  if (inflight[normalized]) return inflight[normalized];
  const promise = fetchLanguage(normalized).finally(() => {
    delete inflight[normalized];
  });
  inflight[normalized] = promise;
  return promise;
}

// ``t`` is the only thing render code should reach for when emitting
// user-facing copy. The fallback chain (current language -> English
// -> raw key) means a missing key, a not-yet-loaded language, or a
// transient network failure show the key itself rather than throwing
// or producing ``undefined``.
export function t(key, params = {}) {
  const dictionary = translations[state.language] || translations.vi || {};
  const fallbackDictionary = translations.en || {};
  const template = dictionary[key] || fallbackDictionary[key] || key;
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, name) => params[name] ?? "");
}

// ``applyTranslations`` rewrites the static parts of the DOM
// (``data-i18n``, placeholders, titles, aria-labels) for the current
// language. The orchestrator owns the language button update because
// only it has the ``els`` cache; this base helper handles everything
// that is reachable from a generic root selector.
export function applyTranslations(root = document) {
  document.documentElement.lang = state.language;
  document.title = t("page.title");
  root.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  root.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.setAttribute("title", t(element.dataset.i18nTitle));
  });
  root.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
}
