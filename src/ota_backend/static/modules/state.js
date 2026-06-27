// state.js
//
// Single source of truth for the public site's runtime state. All UI
// modules import this same object so updates flow without callbacks.
// Kept as a mutable singleton (not a class) because the public site is
// small and the alternative — passing state to every render function —
// adds boilerplate without clarity gains.

export const state = {
  brand: "",
  devices: [],
  devicesTotal: 0,
  releases: [],
  releasesTotal: 0,
  edlRoms: [],
  edlRomsTotal: 0,
  selectedProductModel: "",
  selectedDownloadUrl: "",
  lastResult: null,
  resolverResolvedUrl: "",
  packageMode: "ota",
  releaseRegion: "",
  releaseType: "",
  releaseSearch: "",
  language: "vi",
  deviceTimer: 0,
  publicSite: false,
  resolverEnabled: false,
  turnstileSiteKey: "",
  challengeTokens: { ota: "", resolve: "" },
  challengeWidgets: { ota: null, resolve: null },
  challengeWaiters: { ota: null, resolve: null },
  turnstileScriptRequested: false,
};

export const challengeElementIds = {
  ota: "otaChallenge",
  resolve: "resolverChallenge",
};

export const LANGUAGE_STORAGE_KEY = "oplus_ota_language";
export const THEME_STORAGE_KEY = "oplus_ota_theme";
