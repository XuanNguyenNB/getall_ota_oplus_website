// theme.js
//
// Light/dark theme persistence. Reads the user's prefers-color-scheme
// signal as a fallback when localStorage has not stored a choice yet,
// so the default isn't always light on systems that prefer dark. The
// inline bootstrap script in index.html handles the very first paint;
// these helpers manage subsequent toggles.

import { THEME_STORAGE_KEY } from "./state.js";

export function prefersDarkTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function currentThemeIsDark() {
  const stored = window.localStorage?.getItem(THEME_STORAGE_KEY);
  if (stored === "dark") return true;
  if (stored === "light") return false;
  return prefersDarkTheme();
}

export function applyTheme(dark, themeToggle) {
  document.documentElement.classList.toggle("dark", dark);
  if (themeToggle) {
    themeToggle.setAttribute("aria-pressed", dark ? "true" : "false");
  }
}

export function toggleTheme(themeToggle) {
  const dark = !document.documentElement.classList.contains("dark");
  window.localStorage?.setItem(THEME_STORAGE_KEY, dark ? "dark" : "light");
  applyTheme(dark, themeToggle);
}
