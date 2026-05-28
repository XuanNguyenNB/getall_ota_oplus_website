const state = {
  brand: "",
  devices: [],
  devicesTotal: 0,
  releases: [],
  releasesTotal: 0,
  selectedProductModel: "",
  selectedDownloadUrl: "",
  lastResult: null,
  resolverResolvedUrl: "",
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

const challengeElementIds = {
  ota: "otaChallenge",
  resolve: "resolverChallenge",
};

const LANGUAGE_STORAGE_KEY = "oplus_ota_language";

const translations = {
  vi: {
    "page.title": "OPlus OTA Monitor",
    "page.subtitle": "Kho OTA công khai và tra cứu bản cập nhật chuẩn cho OPPO, Realme và OnePlus",
    "status.ariaLabel": "Trạng thái dịch vụ",
    "status.checkingApi": "Đang kiểm tra API",
    "status.apiUnavailable": "API không khả dụng",
    "runtime.publicProtected": "Môi trường công khai được bảo vệ",
    "runtime.localOperator": "Môi trường vận hành nội bộ",
    "language.ariaLabel": "Ngôn ngữ",
    "actions.support": "Support",
    "actions.refresh": "Làm mới",
    "actions.findOta": "Tìm OTA",
    "actions.finding": "Đang tìm...",
    "actions.copyUrl": "Sao chép URL",
    "actions.copy": "Sao chép",
    "actions.open": "Mở",
    "actions.resolve": "Resolve",
    "actions.resolving": "Đang resolve...",
    "control.title": "Bảng điều khiển",
    "control.protected": "Được bảo vệ",
    "brand.ariaLabel": "Lọc thương hiệu",
    "brand.all": "Tất cả",
    "field.searchDevices": "Tìm thiết bị",
    "field.productModel": "Mã model",
    "field.manifest": "Manifest",
    "field.selectManifest": "Chọn manifest",
    "field.track": "Track",
    "field.ruiCandidates": "RUI candidates",
    "placeholder.deviceSearch": "Tên máy hoặc mã model",
    "placeholder.releaseSearch": "Lọc phiên bản",
    "archive.title": "Kho OTA của thiết bị",
    "archive.selectDevice": "Chọn thiết bị để xem các bản cập nhật",
    "archive.filtersAria": "Bộ lọc bản cập nhật",
    "archive.region": "Khu vực",
    "archive.type": "Loại",
    "archive.version": "Phiên bản",
    "archive.all": "Tất cả",
    "archive.official": "Chính thức",
    "archive.beta": "Beta",
    "archive.release": "Bản cập nhật",
    "archive.published": "Ngày phát hành",
    "archive.actions": "Thao tác",
    "archive.noDeviceSelected": "Chưa chọn thiết bị",
    "archive.loading": "Đang tải bản cập nhật...",
    "archive.loadFailed": "Tải bản cập nhật thất bại",
    "archive.couldNotLoad": "Không thể tải bản cập nhật.",
    "archive.welcomeTitle": "Chào mừng đến OPlus OTA Monitor",
    "archive.welcomeText": "Chọn thiết bị ở bảng điều khiển để xem lịch sử cập nhật chính thức và beta.",
    "archive.noReleases": "Chưa có bản cập nhật nào. Truy vấn thành công và được lưu sẽ xuất hiện tại đây.",
    "archive.summary": "{count} bản cập nhật đã lưu{suffix}",
    "archive.summaryOne": "1 bản cập nhật đã lưu{suffix}",
    "archive.summaryNone": "Chưa có bản cập nhật đã lưu{suffix}",
    "archive.forModel": " cho {model}",
    "device.loading": "Đang tải thiết bị...",
    "device.loadFailed": "Không thể tải thiết bị.",
    "device.none": "Không có thiết bị phù hợp. Bạn có thể nhập mã model thủ công.",
    "device.manifestNeeded": "cần manifest",
    "device.matchesShown": "Đang hiển thị {shown} / {total} kết quả",
    "device.selected": "Đã chọn {model}",
    "device.selectedManifestRequired": "Đã chọn {model}; hãy chọn manifest",
    "result.title": "Kết quả OTA",
    "result.status": "Trạng thái",
    "result.defaultStatus": "Chọn thiết bị ở bảng điều khiển rồi gửi truy vấn chuẩn.",
    "result.state.idle": "chờ",
    "result.state.loading": "đang tải",
    "result.state.error": "lỗi",
    "result.state.new": "mới",
    "result.state.known": "đã biết",
    "result.brand": "Thương hiệu",
    "result.productModel": "Mã model",
    "result.manifest": "Manifest",
    "result.track": "Track",
    "result.rui": "RUI",
    "result.displayedVersion": "Phiên bản hiển thị",
    "result.otaVersion": "OTA version",
    "result.computedOta": "Computed OTA",
    "result.versionType": "Loại version",
    "result.aboutUpdate": "Thông tin cập nhật",
    "result.download": "Download",
    "resolver.title": "Resolve link",
    "resolver.infoLabel": "Giải thích Resolve link",
    "resolver.infoText": "Resolver kiểm tra link OTA dạng downloadCheck/component protected và trả final URL tải trực tiếp khi OPlus cho phép. Ứng dụng không proxy hoặc tải hộ file ROM.",
    "resolver.otaUrl": "OTA URL",
    "resolver.resolvedUrl": "URL đã resolve",
    "tools.title": "Công cụ hỗ trợ",
    "tools.fastboot": "Fastboot Firmware Flasher",
    "tools.resolverDownloader": "Link Resolver and Downloader",
    "tools.driver": "Driver",
    "tools.platformTools": "Platform Tools",
    "toast.otaCompleted": "Truy vấn OTA hoàn tất",
    "toast.linkResolved": "Đã resolve link",
    "toast.downloadCopied": "Đã sao chép URL tải xuống",
    "error.requestFailed": "Yêu cầu thất bại.",
    "error.internal": "Lỗi client không xác định.",
    "error.ruiCandidates": "RUI candidates phải là các số nguyên dương, phân tách bằng dấu phẩy.",
    "challenge.loading": "Xác minh người dùng vẫn đang tải. Hãy thử lại.",
    "challenge.notReady": "Xác minh người dùng chưa sẵn sàng. Hãy thử lại.",
    "challenge.restarted": "Xác minh người dùng đã được khởi động lại.",
    "challenge.timeout": "Xác minh người dùng quá thời gian. Hãy thử lại.",
    "challenge.failed": "Xác minh người dùng thất bại. Hãy thử lại.",
    "challenge.unsupported": "Trình duyệt này không thể hoàn tất xác minh người dùng.",
    "release.copyTitle": "Sao chép URL tải xuống",
    "release.openTitle": "Mở URL tải xuống",
    "release.resolveTitle": "Resolve hoặc kiểm tra OTA URL",
    "release.type.official": "CHÍNH THỨC",
    "release.type.beta": "BETA",
  },
  en: {
    "page.title": "OPlus OTA Monitor",
    "page.subtitle": "Public OTA archive and standard update lookup for OPPO, Realme, and OnePlus",
    "status.ariaLabel": "Service status",
    "status.checkingApi": "Checking API",
    "status.apiUnavailable": "API unavailable",
    "runtime.publicProtected": "Public protected runtime",
    "runtime.localOperator": "Local operator runtime",
    "language.ariaLabel": "Language",
    "actions.support": "Support",
    "actions.refresh": "Refresh",
    "actions.findOta": "Find OTA",
    "actions.finding": "Finding...",
    "actions.copyUrl": "Copy URL",
    "actions.copy": "Copy",
    "actions.open": "Open",
    "actions.resolve": "Resolve",
    "actions.resolving": "Resolving...",
    "control.title": "Control Deck",
    "control.protected": "Protected",
    "brand.ariaLabel": "Brand filter",
    "brand.all": "All",
    "field.searchDevices": "Search devices",
    "field.productModel": "Product model",
    "field.manifest": "Manifest",
    "field.selectManifest": "Select manifest",
    "field.track": "Track",
    "field.ruiCandidates": "RUI candidates",
    "placeholder.deviceSearch": "Name or product model",
    "placeholder.releaseSearch": "Filter version",
    "archive.title": "Device OTA Archive",
    "archive.selectDevice": "Select a device to view updates",
    "archive.filtersAria": "Release filters",
    "archive.region": "Region",
    "archive.type": "Type",
    "archive.version": "Version",
    "archive.all": "All",
    "archive.official": "Official",
    "archive.beta": "Beta",
    "archive.release": "Release",
    "archive.published": "Published",
    "archive.actions": "Actions",
    "archive.noDeviceSelected": "No device selected",
    "archive.loading": "Loading releases...",
    "archive.loadFailed": "Release load failed",
    "archive.couldNotLoad": "Could not load releases.",
    "archive.welcomeTitle": "Welcome to OPlus OTA Monitor",
    "archive.welcomeText": "Select a device on the left Control Deck to view its official and beta update history.",
    "archive.noReleases": "No releases yet. Successful persisted queries will appear here.",
    "archive.summary": "{count} persisted releases{suffix}",
    "archive.summaryOne": "1 persisted release{suffix}",
    "archive.summaryNone": "No persisted releases{suffix}",
    "archive.forModel": " for {model}",
    "device.loading": "Loading devices...",
    "device.loadFailed": "Could not load devices.",
    "device.none": "No matching devices. Enter a product model manually.",
    "device.manifestNeeded": "manifest needed",
    "device.matchesShown": "{shown} of {total} matches shown",
    "device.selected": "Selected {model}",
    "device.selectedManifestRequired": "Selected {model}; select its manifest",
    "result.title": "OTA Result",
    "result.status": "Status",
    "result.defaultStatus": "Select a device on the left control deck and submit standard query.",
    "result.state.idle": "idle",
    "result.state.loading": "loading",
    "result.state.error": "error",
    "result.state.new": "new",
    "result.state.known": "known",
    "result.brand": "Brand",
    "result.productModel": "Product model",
    "result.manifest": "Manifest",
    "result.track": "Track",
    "result.rui": "RUI",
    "result.displayedVersion": "Displayed version",
    "result.otaVersion": "OTA version",
    "result.computedOta": "Computed OTA",
    "result.versionType": "Version type",
    "result.aboutUpdate": "About update",
    "result.download": "Download",
    "resolver.title": "Resolve Link",
    "resolver.infoLabel": "Resolve link info",
    "resolver.infoText": "Resolver checks protected OTA links such as downloadCheck/component links and returns the final direct download URL when OPlus allows it. This app does not proxy or download ROM files for you.",
    "resolver.otaUrl": "OTA URL",
    "resolver.resolvedUrl": "Resolved URL",
    "tools.title": "Support tools",
    "tools.fastboot": "Fastboot Firmware Flasher",
    "tools.resolverDownloader": "Link Resolver and Downloader",
    "tools.driver": "Driver",
    "tools.platformTools": "Platform Tools",
    "toast.otaCompleted": "OTA query completed",
    "toast.linkResolved": "Link resolved",
    "toast.downloadCopied": "Download URL copied",
    "error.requestFailed": "Request failed.",
    "error.internal": "Unexpected client error.",
    "error.ruiCandidates": "RUI candidates must be comma-separated positive integers.",
    "challenge.loading": "Human verification is still loading. Try again.",
    "challenge.notReady": "Human verification is not ready. Try again.",
    "challenge.restarted": "Human verification was restarted.",
    "challenge.timeout": "Human verification timed out. Try again.",
    "challenge.failed": "Human verification failed. Try again.",
    "challenge.unsupported": "This browser cannot complete human verification.",
    "release.copyTitle": "Copy download URL",
    "release.openTitle": "Open download URL",
    "release.resolveTitle": "Resolve or validate OTA URL",
    "release.type.official": "OFFICIAL",
    "release.type.beta": "BETA",
  },
};

const els = {
  apiStatus: document.querySelector("#apiStatus"),
  runtimeStatus: document.querySelector("#runtimeStatus"),
  languageButtons: document.querySelectorAll("[data-language]"),
  refreshButton: document.querySelector("#refreshButton"),
  deviceSearch: document.querySelector("#deviceSearch"),
  deviceList: document.querySelector("#deviceList"),
  productModel: document.querySelector("#productModel"),
  manifestCode: document.querySelector("#manifestCode"),
  otaTrack: document.querySelector("#otaTrack"),
  ruiCandidates: document.querySelector("#ruiCandidates"),
  form: document.querySelector("#otaForm"),
  findButton: document.querySelector("#findButton"),
  releaseRows: document.querySelector("#releaseRows"),
  releaseTitle: document.querySelector("#releaseTitle"),
  releaseSummary: document.querySelector("#releaseSummary"),
  releaseRegion: document.querySelector("#releaseRegion"),
  releaseType: document.querySelector("#releaseType"),
  releaseSearch: document.querySelector("#releaseSearch"),
  releaseError: document.querySelector("#releaseError"),
  otaError: document.querySelector("#otaError"),
  resultState: document.querySelector("#resultState"),
  resultDetails: document.querySelector("#resultDetails"),
  copyResultButton: document.querySelector("#copyResultButton"),
  openResultButton: document.querySelector("#openResultButton"),
  toast: document.querySelector("#toast"),
  otaChallengePanel: document.querySelector("#otaChallengePanel"),
  resolverPanel: document.querySelector("#resolverPanel"),
  resolverForm: document.querySelector("#resolverForm"),
  resolverUrl: document.querySelector("#resolverUrl"),
  resolveButton: document.querySelector("#resolveButton"),
  resolverChallengePanel: document.querySelector("#resolverChallengePanel"),
  resolverError: document.querySelector("#resolverError"),
  resolverDetails: document.querySelector("#resolverDetails"),
};

function normalizeLanguage(language) {
  return language === "en" ? "en" : "vi";
}

function t(key, params = {}) {
  const dictionary = translations[state.language] || translations.vi;
  const fallback = translations.en[key] || key;
  const template = dictionary[key] || fallback;
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, name) => params[name] ?? "");
}

function applyTranslations(root = document) {
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
  els.languageButtons.forEach((button) => {
    const active = button.dataset.language === state.language;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function setLanguage(language) {
  state.language = normalizeLanguage(language);
  window.localStorage?.setItem(LANGUAGE_STORAGE_KEY, state.language);
  applyTranslations();
  configureFeatures({ public_site: state.publicSite, resolver: state.resolverEnabled, turnstile_site_key: state.turnstileSiteKey });
  renderDevices(state.devicesTotal);
  if (state.selectedProductModel || els.productModel.value.trim()) {
    renderReleaseRegionOptions();
    renderReleases(state.releasesTotal);
  } else {
    loadReleases();
  }
  if (state.lastResult) {
    renderResult(state.lastResult);
  } else {
    renderDefaultResult();
  }
  renderResolverResult();
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (!label) return;
  const labelElement = button.querySelector("span");
  if (labelElement) {
    labelElement.textContent = label;
  } else {
    button.textContent = label;
  }
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 1800);
}

function displayError(target, error) {
  const code = error?.code || "ERROR";
  const message = error?.message || t("error.requestFailed");
  target.textContent = `${code}: ${message}`;
  target.hidden = false;
}

function clearError(target) {
  target.textContent = "";
  target.hidden = true;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.ok === false) {
    const fallback = { code: `HTTP_${response.status}`, message: response.statusText || t("error.requestFailed") };
    const error = body?.error || fallback;
    throw Object.assign(new Error(error.message), { apiError: error, status: response.status });
  }
  return body;
}

function clientError(code, message) {
  return Object.assign(new Error(message), {
    apiError: { code, message },
  });
}

async function activeHeaders(action) {
  if (!state.publicSite) return {};
  const token = await requestChallengeToken(action);
  return { "X-Turnstile-Token": token };
}

function resetChallenge(action) {
  state.challengeTokens[action] = "";
  const widget = state.challengeWidgets[action];
  if (window.turnstile && widget !== null && widget !== undefined) window.turnstile.reset(widget);
}

function settleChallenge(action, token, error) {
  const waiter = state.challengeWaiters[action];
  state.challengeWaiters[action] = null;
  window.clearTimeout(waiter?.timer);
  if (!waiter) return;
  if (error) {
    waiter.reject(error);
    return;
  }
  waiter.resolve(token);
}

function requestChallengeToken(action) {
  if (!state.publicSite) return Promise.resolve("");
  if (!window.turnstile) {
    return Promise.reject(
      clientError("CHALLENGE_UNAVAILABLE", t("challenge.loading")),
    );
  }
  const widget = state.challengeWidgets[action];
  if (widget === null || widget === undefined) {
    return Promise.reject(
      clientError("CHALLENGE_UNAVAILABLE", t("challenge.notReady")),
    );
  }
  if (state.challengeWaiters[action]) {
    state.challengeWaiters[action].reject(
      clientError("CHALLENGE_RESTARTED", t("challenge.restarted")),
    );
  }
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      settleChallenge(
        action,
        "",
        clientError("CHALLENGE_TIMEOUT", t("challenge.timeout")),
      );
    }, 120000);
    state.challengeWaiters[action] = { resolve, reject, timer };
    state.challengeTokens[action] = "";
    window.turnstile.reset(widget);
    window.turnstile.execute(widget);
  });
}

function mountTurnstile() {
  if (!state.publicSite || !state.turnstileSiteKey || !window.turnstile) return;
  const actions = state.resolverEnabled ? ["ota", "resolve"] : ["ota"];
  actions.forEach((action) => {
    const elementId = challengeElementIds[action];
    if (!elementId) return;
    if (state.challengeWidgets[action] !== null && state.challengeWidgets[action] !== undefined) return;
    state.challengeWidgets[action] = window.turnstile.render(`#${elementId}`, {
      sitekey: state.turnstileSiteKey,
      action,
      execution: "execute",
      appearance: "interaction-only",
      theme: "dark",
      callback: (token) => {
        state.challengeTokens[action] = token;
        settleChallenge(action, token, null);
      },
      "expired-callback": () => { state.challengeTokens[action] = ""; },
      "error-callback": () => {
        settleChallenge(
          action,
          "",
          clientError("CHALLENGE_FAILED", t("challenge.failed")),
        );
      },
      "timeout-callback": () => {
        settleChallenge(
          action,
          "",
          clientError("CHALLENGE_TIMEOUT", t("challenge.timeout")),
        );
      },
      "unsupported-callback": () => {
        settleChallenge(
          action,
          "",
          clientError("CHALLENGE_UNSUPPORTED", t("challenge.unsupported")),
        );
      },
    });
  });
}

function configureChallengePanel(panel, enabled) {
  panel.hidden = !enabled;
  panel.classList.toggle("silent-challenge-panel", enabled);
  panel.setAttribute("aria-hidden", "true");
}

function configureFeatures(features) {
  state.publicSite = Boolean(features?.public_site);
  state.resolverEnabled = Boolean(features?.resolver);
  state.turnstileSiteKey = features?.turnstile_site_key || "";
  els.runtimeStatus.textContent = state.publicSite ? t("runtime.publicProtected") : t("runtime.localOperator");
  els.resolverPanel.hidden = !state.resolverEnabled;
  configureChallengePanel(els.otaChallengePanel, state.publicSite);
  configureChallengePanel(els.resolverChallengePanel, state.publicSite && state.resolverEnabled);
  if (!state.publicSite || !state.turnstileSiteKey || state.turnstileScriptRequested) return;
  state.turnstileScriptRequested = true;
  window.onTurnstileLoaded = mountTurnstile;
  const script = document.createElement("script");
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoaded&render=explicit";
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);
}

function brandLabel(brand) {
  const lower = String(brand || "").toLowerCase().trim();
  if (lower === "oppo") return `<span class="brand-badge oppo">OPPO</span>`;
  if (lower === "realme") return `<span class="brand-badge realme">Realme</span>`;
  if (lower === "oneplus") return `<span class="brand-badge oneplus">OnePlus</span>`;
  return brand || "-";
}

function releaseRegionLabel(release) {
  const manifestLabels = {
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
  const manifestCode = release.manifest_code || "";
  const manifestLabel = manifestLabels[manifestCode] || manifestCode || "";
  const regionCode = release.region_code || "";
  if (!manifestCode) return regionCode || "-";
  if (!regionCode || regionCode === manifestLabel) return `${manifestLabel} / ${manifestCode}`;
  return `${manifestLabel} (${regionCode}) / ${manifestCode}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function releaseSortTimestamp(release) {
  const direct = Date.parse(release.published_at || "");
  if (!Number.isNaN(direct)) return direct;
  const aboutMatch = String(release.about_update_url || "").match(/\/(?:component-ota|ota)\/(\d{2})\/(\d{2})\/(\d{2})\//);
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

function releasePublishedLabel(release) {
  if (release.published_at) return formatDate(release.published_at);
  const timestamp = releaseSortTimestamp(release);
  return timestamp ? formatDate(new Date(timestamp).toISOString()) : "-";
}

function isResolvableDownloadUrl(value) {
  const lower = String(value || "").toLowerCase();
  return (
    lower.includes("downloadcheck")
    || lower.includes("servlet/download")
    || lower.includes("componentotacostmanual")
    || lower.includes("compotacostauto")
  );
}

function isBrowserBlockedDownloadUrl(value) {
  const lower = String(value || "").toLowerCase();
  return (
    lower.includes("gauss-componentotacostmanual-cn.")
    || lower.includes("gauss-compotacostauto-cn.")
    || lower.includes("gauss-opexcostmanual-cn.")
  );
}

function renderReleaseActions(release) {
  const downloadUrl = release.download_url || "";
  const canOpen = downloadUrl && !isBrowserBlockedDownloadUrl(downloadUrl);
  const canResolve = state.resolverEnabled && isResolvableDownloadUrl(downloadUrl);
  return `
    <button class="row-action" type="button" data-copy-release="${release.id}" title="${escapeHtml(t("release.copyTitle"))}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
      <span>${escapeHtml(t("actions.copy"))}</span>
    </button>
    ${canOpen ? `
    <button class="row-action" type="button" data-open-release="${release.id}" title="${escapeHtml(t("release.openTitle"))}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
      </svg>
      <span>${escapeHtml(t("actions.open"))}</span>
    </button>` : ""}
    ${canResolve ? `
    <button class="row-action" type="button" data-resolve-release="${release.id}" title="${escapeHtml(t("release.resolveTitle"))}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      <span>${escapeHtml(t("actions.resolve"))}</span>
    </button>` : ""}
  `;
}

function parseRuiCandidates(value) {
  const candidates = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number.parseInt(item, 10));
  if (!candidates.length || candidates.some((item) => !Number.isInteger(item) || item < 1)) {
    throw Object.assign(new Error(t("error.ruiCandidates")), {
      apiError: { code: "VALIDATION_ERROR", message: t("error.ruiCandidates") },
    });
  }
  return candidates;
}

async function loadHealth() {
  try {
    const body = await api("/api/health");
    els.apiStatus.className = "status-pill ok";
    els.apiStatus.innerHTML = `<span></span>${body.service} ${body.version}`;
    configureFeatures(body.features);
  } catch (error) {
    els.apiStatus.className = "status-pill error";
    els.apiStatus.innerHTML = `<span></span>${escapeHtml(t("status.apiUnavailable"))}`;
  }
}

async function loadDevices() {
  els.deviceList.innerHTML = `<div class="empty-state">${escapeHtml(t("device.loading"))}</div>`;
  const params = new URLSearchParams({ limit: "25" });
  if (state.brand) params.set("brand", state.brand);
  const query = els.deviceSearch.value.trim();
  if (query) params.set("q", query);

  try {
    const body = await api(`/api/devices?${params.toString()}`);
    state.devices = body.devices || [];
    state.devicesTotal = body.total || 0;
    renderDevices(state.devicesTotal);
  } catch (error) {
    els.deviceList.innerHTML = `<div class="empty-state error-text">${escapeHtml(error.apiError?.message || t("device.loadFailed"))}</div>`;
  }
}

function renderDevices(total) {
  if (!state.devices.length) {
    els.deviceList.innerHTML = `<div class="empty-state">${escapeHtml(t("device.none"))}</div>`;
    return;
  }
  els.deviceList.innerHTML = state.devices
    .map(
      (device) => `
        <button class="device-option${state.selectedProductModel === device.product_model ? " selected" : ""}" type="button" data-model="${device.product_model}">
          <strong>${device.product_model}</strong>
          <span>${escapeHtml(device.name)} / ${brandLabel(device.brand)} / ${escapeHtml(device.manifest_code || t("device.manifestNeeded"))}</span>
        </button>
      `,
    )
    .join("");
  if (total > state.devices.length) {
    els.deviceList.insertAdjacentHTML("beforeend", `<div class="empty-state">${escapeHtml(t("device.matchesShown", { shown: state.devices.length, total }))}</div>`);
  }
}

function selectDevice(productModel) {
  const device = state.devices.find((item) => item.product_model === productModel);
  if (!device) return;
  state.selectedProductModel = device.product_model;
  document.querySelectorAll(".device-option").forEach((option) => {
    option.classList.toggle("selected", option.dataset.model === device.product_model);
  });
  els.productModel.value = device.product_model;
  if (device.manifest_code) {
    els.manifestCode.value = device.manifest_code;
  } else {
    els.manifestCode.value = "";
    showToast(t("device.selectedManifestRequired", { model: device.product_model }));
    return;
  }
  if (device.active_track) els.otaTrack.value = device.active_track;
  showToast(t("device.selected", { model: device.product_model }));
  loadReleases();
}

async function loadReleases() {
  clearError(els.releaseError);
  const selectedModel = state.selectedProductModel || els.productModel.value.trim().toUpperCase();
  
  if (!selectedModel) {
    els.releaseTitle.textContent = t("archive.title");
    els.releaseSummary.textContent = t("archive.noDeviceSelected");
    els.releaseRows.innerHTML = `
      <tr>
        <td colspan="5" class="empty-cell">
          <div class="welcome-placeholder-card">
            <svg class="welcome-placeholder-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="2.5" ry="2.5"/>
              <path d="M12 17h.01M12 12h.01M12 7h.01"/>
            </svg>
            <strong>${escapeHtml(t("archive.welcomeTitle"))}</strong>
            <span>${escapeHtml(t("archive.welcomeText"))}</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  els.releaseTitle.textContent = t("archive.title");
  els.releaseSummary.textContent = t("archive.loading");
  els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("archive.loading"))}</td></tr>`;

  const params = new URLSearchParams({
    limit: "200",
    sort: "published",
    product_model: selectedModel,
  });
  if (state.releaseRegion) params.set("region_code", state.releaseRegion);
  if (state.releaseType) params.set("release_type", state.releaseType);
  if (state.releaseSearch) params.set("q", state.releaseSearch);

  try {
    const body = await api(`/api/releases?${params.toString()}`);
    state.releases = (body.releases || []).sort(
      (left, right) => releaseSortTimestamp(right) - releaseSortTimestamp(left),
    );
    state.releasesTotal = body.total || 0;
    renderReleaseRegionOptions();
    renderReleases(state.releasesTotal);
  } catch (error) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("archive.couldNotLoad"))}</td></tr>`;
    els.releaseSummary.textContent = t("archive.loadFailed");
    displayError(els.releaseError, error.apiError);
  }
}

function renderReleaseRegionOptions() {
  const selected = state.releaseRegion;
  const regions = Array.from(new Set(state.releases.map((release) => release.region_code).filter(Boolean))).sort();
  els.releaseRegion.innerHTML = [`<option value="">${escapeHtml(t("archive.all"))}</option>`]
    .concat(regions.map((region) => `<option value="${escapeHtml(region)}">${escapeHtml(region)}</option>`))
    .join("");
  els.releaseRegion.value = regions.includes(selected) ? selected : "";
  state.releaseRegion = els.releaseRegion.value;
}

function renderReleases(total) {
  const selectedModel = state.selectedProductModel || els.productModel.value.trim().toUpperCase();
  const suffix = selectedModel ? t("archive.forModel", { model: selectedModel }) : "";
  els.releaseSummary.textContent = total
    ? t(total === 1 ? "archive.summaryOne" : "archive.summary", { count: total, suffix })
    : t("archive.summaryNone", { suffix });
  if (!state.releases.length) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("archive.noReleases"))}</td></tr>`;
    return;
  }

  els.releaseRows.innerHTML = state.releases
    .map(
      (release) => `
        <tr>
          <td data-label="${escapeHtml(t("archive.release"))}">
            <strong class="version-cell">${escapeHtml(release.real_version_name)}</strong>
            <div class="release-subline">${escapeHtml(release.product_model)} / ${brandLabel(release.brand)} / ${escapeHtml(release.ota_track || "-")}</div>
            <div class="release-subline version-cell">${escapeHtml(release.real_ota_version || "-")}</div>
          </td>
          <td data-label="${escapeHtml(t("archive.region"))}"><span class="release-badge">${escapeHtml(releaseRegionLabel(release))}</span></td>
          <td data-label="${escapeHtml(t("archive.type"))}"><span class="release-badge ${release.release_type === "beta" ? "beta" : "official"}">${escapeHtml(t(`release.type.${release.release_type || "official"}`))}</span></td>
          <td data-label="${escapeHtml(t("archive.published"))}">${releasePublishedLabel(release)}</td>
          <td class="release-actions" data-label="${escapeHtml(t("archive.actions"))}">
            ${renderReleaseActions(release)}
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderDefaultResult() {
  state.lastResult = null;
  state.selectedDownloadUrl = "";
  els.resultState.textContent = t("result.state.idle");
  els.resultState.className = "micro-chip";
  els.resultDetails.innerHTML = `
    <dt>${escapeHtml(t("result.status"))}</dt>
    <dd>${escapeHtml(t("result.defaultStatus"))}</dd>
  `;
  els.copyResultButton.disabled = true;
  els.openResultButton.disabled = true;
}

function renderResult(result) {
  state.lastResult = result;
  state.selectedDownloadUrl = result.download_url || "";
  els.resultState.textContent = result.is_new ? t("result.state.new") : t("result.state.known");
  els.resultState.className = result.is_new ? "micro-chip success" : "micro-chip";
  els.resultDetails.innerHTML = [
    [t("result.brand"), brandLabel(result.brand)],
    [t("result.productModel"), result.product_model],
    [t("result.manifest"), result.manifest_code],
    [t("result.track"), result.ota_track],
    [t("result.rui"), result.rui_version],
    [t("result.displayedVersion"), result.real_version_name],
    [t("result.otaVersion"), result.real_ota_version],
    [t("result.computedOta"), result.computed_ota_version],
    [t("result.versionType"), result.version_type_id],
    [t("result.aboutUpdate"), result.about_update_url || "-"],
    [t("result.download"), result.download_url],
  ]
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${value}</dd>`)
    .join("");
  els.copyResultButton.disabled = !state.selectedDownloadUrl;
  els.openResultButton.disabled = !state.selectedDownloadUrl || isBrowserBlockedDownloadUrl(state.selectedDownloadUrl);
}

function renderResolverResult() {
  if (!state.resolverResolvedUrl) return;
  els.resolverDetails.innerHTML = `<dt>${escapeHtml(t("resolver.resolvedUrl"))}</dt><dd>${escapeHtml(state.resolverResolvedUrl)}</dd>`;
}

async function submitOta(event) {
  event.preventDefault();
  clearError(els.otaError);
  els.resultState.textContent = t("result.state.loading");
  setBusy(els.findButton, true, t("actions.finding"));

  try {
    const payload = {
      product_model: els.productModel.value.trim(),
      manifest_code: els.manifestCode.value,
      ota_track: els.otaTrack.value,
      rui_candidates: parseRuiCandidates(els.ruiCandidates.value),
      language: "en-EN",
      beta: false,
      imei0: null,
      imei1: null,
      persist_result: true,
    };
    const body = await api("/api/ota", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", ...(await activeHeaders("ota")) },
      body: JSON.stringify(payload),
    });
    renderResult(body.result);
    showToast(t("toast.otaCompleted"));
    await loadReleases();
  } catch (error) {
    const apiError = error.apiError || { code: "INTERNAL_ERROR", message: t("error.internal") };
    els.resultState.textContent = t("result.state.error");
    els.resultState.className = "micro-chip error";
    displayError(els.otaError, apiError);
  } finally {
    if (state.publicSite) resetChallenge("ota");
    setBusy(els.findButton, false, t("actions.findOta"));
  }
}

async function submitResolver(event) {
  event.preventDefault();
  clearError(els.resolverError);
  setBusy(els.resolveButton, true, t("actions.resolving"));
  try {
    const body = await api("/api/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", ...(await activeHeaders("resolve")) },
      body: JSON.stringify({ url: els.resolverUrl.value.trim(), source: "web" }),
    });
    state.resolverResolvedUrl = body.resolved_url || "";
    renderResolverResult();
    showToast(t("toast.linkResolved"));
  } catch (error) {
    displayError(els.resolverError, error.apiError);
  } finally {
    if (state.publicSite) resetChallenge("resolve");
    setBusy(els.resolveButton, false, t("actions.resolve"));
  }
}

async function copyText(text) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (_error) {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  showToast(t("toast.downloadCopied"));
}

document.querySelectorAll(".segment").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segment").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.brand = button.dataset.brand || "";
    loadDevices();
  });
});

els.languageButtons.forEach((button) => {
  button.addEventListener("click", () => setLanguage(button.dataset.language));
});

els.deviceSearch.addEventListener("input", () => {
  window.clearTimeout(state.deviceTimer);
  state.deviceTimer = window.setTimeout(loadDevices, 250);
});

els.deviceList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-model]");
  if (button) selectDevice(button.dataset.model);
});

els.releaseRegion.addEventListener("change", () => {
  state.releaseRegion = els.releaseRegion.value;
  loadReleases();
});

els.releaseType.addEventListener("change", () => {
  state.releaseType = els.releaseType.value;
  loadReleases();
});

els.releaseSearch.addEventListener("input", () => {
  state.releaseSearch = els.releaseSearch.value.trim();
  window.clearTimeout(els.releaseSearch.timer);
  els.releaseSearch.timer = window.setTimeout(loadReleases, 250);
});

els.form.addEventListener("submit", submitOta);
els.resolverForm.addEventListener("submit", submitResolver);
els.refreshButton.addEventListener("click", loadReleases);
els.copyResultButton.addEventListener("click", () => copyText(state.selectedDownloadUrl));
els.openResultButton.addEventListener("click", () => {
  if (state.selectedDownloadUrl && !isBrowserBlockedDownloadUrl(state.selectedDownloadUrl)) {
    window.open(state.selectedDownloadUrl, "_blank", "noopener,noreferrer");
  }
});

els.releaseRows.addEventListener("click", (event) => {
  const copyButton = event.target.closest("[data-copy-release]");
  if (copyButton) {
    const release = state.releases.find((item) => item.id === copyButton.dataset.copyRelease);
    copyText(release?.download_url || "");
    return;
  }
  const openButton = event.target.closest("[data-open-release]");
  if (openButton) {
    const release = state.releases.find((item) => item.id === openButton.dataset.openRelease);
    if (release?.download_url && !isBrowserBlockedDownloadUrl(release.download_url)) {
      window.open(release.download_url, "_blank", "noopener,noreferrer");
    }
    return;
  }
  const resolveButton = event.target.closest("[data-resolve-release]");
  if (resolveButton) {
    const release = state.releases.find((item) => item.id === resolveButton.dataset.resolveRelease);
    if (!release?.download_url) return;
    els.resolverUrl.value = release.download_url;
    submitResolver(new Event("submit"));
  }
});

state.language = normalizeLanguage(window.localStorage?.getItem(LANGUAGE_STORAGE_KEY));
applyTranslations();
renderDefaultResult();
loadHealth();
loadDevices();
loadReleases();
