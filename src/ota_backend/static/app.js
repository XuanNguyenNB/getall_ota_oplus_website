const state = {
  brand: "",
  devices: [],
  releases: [],
  selectedProductModel: "",
  selectedDownloadUrl: "",
  releaseRegion: "",
  releaseType: "",
  releaseSearch: "",
  deviceTimer: 0,
  publicSite: false,
  resolverEnabled: false,
  turnstileSiteKey: "",
  challengeTokens: { ota: "", resolve: "" },
};

const challengeElementIds = {
  ota: "otaChallenge",
  resolve: "resolverChallenge",
};

const els = {
  apiStatus: document.querySelector("#apiStatus"),
  runtimeStatus: document.querySelector("#runtimeStatus"),
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

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (label) button.textContent = label;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 1800);
}

function displayError(target, error) {
  const code = error?.code || "ERROR";
  const message = error?.message || "Request failed.";
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
    const fallback = { code: `HTTP_${response.status}`, message: response.statusText || "Request failed." };
    const error = body?.error || fallback;
    throw Object.assign(new Error(error.message), { apiError: error, status: response.status });
  }
  return body;
}

function activeHeaders(action) {
  if (!state.publicSite) return {};
  const token = state.challengeTokens[action];
  if (!token) {
    throw Object.assign(new Error("Complete human verification first."), {
      apiError: { code: "CHALLENGE_REQUIRED", message: "Complete human verification first." },
    });
  }
  return { "X-Turnstile-Token": token };
}

function resetChallenge(action) {
  state.challengeTokens[action] = "";
  const elementId = challengeElementIds[action];
  if (window.turnstile && elementId) window.turnstile.reset(`#${elementId}`);
}

function mountTurnstile() {
  if (!state.publicSite || !state.turnstileSiteKey || !window.turnstile) return;
  const actions = state.resolverEnabled ? ["ota", "resolve"] : ["ota"];
  actions.forEach((action) => {
    const elementId = challengeElementIds[action];
    if (!elementId) return;
    window.turnstile.render(`#${elementId}`, {
      sitekey: state.turnstileSiteKey,
      action,
      callback: (token) => { state.challengeTokens[action] = token; },
      "expired-callback": () => { state.challengeTokens[action] = ""; },
    });
  });
}

function configureFeatures(features) {
  state.publicSite = Boolean(features?.public_site);
  state.resolverEnabled = Boolean(features?.resolver);
  state.turnstileSiteKey = features?.turnstile_site_key || "";
  els.runtimeStatus.textContent = state.publicSite ? "Public protected runtime" : "Local operator runtime";
  els.resolverPanel.hidden = !state.resolverEnabled;
  els.otaChallengePanel.hidden = !state.publicSite;
  els.resolverChallengePanel.hidden = !(state.publicSite && state.resolverEnabled);
  if (!state.publicSite || !state.turnstileSiteKey) return;
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

function parseRuiCandidates(value) {
  const candidates = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number.parseInt(item, 10));
  if (!candidates.length || candidates.some((item) => !Number.isInteger(item) || item < 1)) {
    throw Object.assign(new Error("RUI candidates must be comma-separated positive integers."), {
      apiError: { code: "VALIDATION_ERROR", message: "RUI candidates must be comma-separated positive integers." },
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
    els.apiStatus.innerHTML = "<span></span>API unavailable";
  }
}

async function loadDevices() {
  els.deviceList.innerHTML = `<div class="empty-state">Loading devices...</div>`;
  const params = new URLSearchParams({ limit: "25" });
  if (state.brand) params.set("brand", state.brand);
  const query = els.deviceSearch.value.trim();
  if (query) params.set("q", query);

  try {
    const body = await api(`/api/devices?${params.toString()}`);
    state.devices = body.devices || [];
    renderDevices(body.total || 0);
  } catch (error) {
    els.deviceList.innerHTML = `<div class="empty-state error-text">${error.apiError?.message || "Could not load devices."}</div>`;
  }
}

function renderDevices(total) {
  if (!state.devices.length) {
    els.deviceList.innerHTML = `<div class="empty-state">No matching devices. Enter a product model manually.</div>`;
    return;
  }
  els.deviceList.innerHTML = state.devices
    .map(
      (device) => `
        <button class="device-option${state.selectedProductModel === device.product_model ? " selected" : ""}" type="button" data-model="${device.product_model}">
          <strong>${device.product_model}</strong>
          <span>${device.name} / ${brandLabel(device.brand)} / ${device.manifest_code || "manifest needed"}</span>
        </button>
      `,
    )
    .join("");
  if (total > state.devices.length) {
    els.deviceList.insertAdjacentHTML("beforeend", `<div class="empty-state">${state.devices.length} of ${total} matches shown</div>`);
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
    showToast(`Selected ${device.product_model}; select its manifest`);
    return;
  }
  if (device.active_track) els.otaTrack.value = device.active_track;
  showToast(`Selected ${device.product_model}`);
  loadReleases();
}

async function loadReleases() {
  clearError(els.releaseError);
  const selectedModel = state.selectedProductModel || els.productModel.value.trim().toUpperCase();
  
  if (!selectedModel) {
    els.releaseTitle.textContent = "Device OTA Archive";
    els.releaseSummary.textContent = "No device selected";
    els.releaseRows.innerHTML = `
      <tr>
        <td colspan="5" class="empty-cell">
          <div class="welcome-placeholder-card">
            <svg class="welcome-placeholder-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="2.5" ry="2.5"/>
              <path d="M12 17h.01M12 12h.01M12 7h.01"/>
            </svg>
            <strong>Welcome to OPlus OTA Monitor</strong>
            <span>Select a device on the left Control Deck to view its official and beta update history.</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  els.releaseTitle.textContent = "Device OTA Archive";
  els.releaseSummary.textContent = "Loading releases...";
  els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">Loading releases...</td></tr>`;

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
    state.releases = body.releases || [];
    renderReleaseRegionOptions();
    renderReleases(body.total || 0);
  } catch (error) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">Could not load releases.</td></tr>`;
    els.releaseSummary.textContent = "Release load failed";
    displayError(els.releaseError, error.apiError);
  }
}

function renderReleaseRegionOptions() {
  const selected = state.releaseRegion;
  const regions = Array.from(new Set(state.releases.map((release) => release.region_code).filter(Boolean))).sort();
  els.releaseRegion.innerHTML = [`<option value="">All</option>`]
    .concat(regions.map((region) => `<option value="${escapeHtml(region)}">${escapeHtml(region)}</option>`))
    .join("");
  els.releaseRegion.value = regions.includes(selected) ? selected : "";
  state.releaseRegion = els.releaseRegion.value;
}

function renderReleases(total) {
  const selectedModel = state.selectedProductModel || els.productModel.value.trim().toUpperCase();
  const suffix = selectedModel ? ` for ${selectedModel}` : "";
  els.releaseSummary.textContent = total ? `${total} persisted release${total === 1 ? "" : "s"}${suffix}` : `No persisted releases${suffix}`;
  if (!state.releases.length) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">No releases yet. Successful persisted queries will appear here.</td></tr>`;
    return;
  }

  els.releaseRows.innerHTML = state.releases
    .map(
      (release) => `
        <tr>
          <td data-label="Release">
            <strong class="version-cell">${escapeHtml(release.real_version_name)}</strong>
            <div class="release-subline">${escapeHtml(release.product_model)} / ${brandLabel(release.brand)} / ${escapeHtml(release.ota_track || "-")}</div>
            <div class="release-subline version-cell">${escapeHtml(release.real_ota_version || "-")}</div>
          </td>
          <td data-label="Region"><span class="release-badge">${escapeHtml(releaseRegionLabel(release))}</span></td>
          <td data-label="Type"><span class="release-badge ${release.release_type === "beta" ? "beta" : "official"}">${escapeHtml((release.release_type || "official").toUpperCase())}</span></td>
          <td data-label="Published">${formatDate(release.published_at || release.discovered_at)}</td>
          <td class="release-actions" data-label="Actions">
            <button class="row-action" type="button" data-copy-release="${release.id}" title="Copy download URL">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              <span>Copy</span>
            </button>
            <button class="row-action" type="button" data-open-release="${release.id}" title="Open download URL">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
              </svg>
              <span>Open</span>
            </button>
            ${String(release.download_url || "").includes("downloadCheck") && state.resolverEnabled ? `
            <button class="row-action" type="button" data-resolve-release="${release.id}" title="Resolve downloadCheck link">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
              </svg>
              <span>Resolve</span>
            </button>` : ""}
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderResult(result) {
  state.selectedDownloadUrl = result.download_url || "";
  els.resultState.textContent = result.is_new ? "new" : "known";
  els.resultState.className = result.is_new ? "micro-chip success" : "micro-chip";
  els.resultDetails.innerHTML = [
    ["Brand", brandLabel(result.brand)],
    ["Product model", result.product_model],
    ["Manifest", result.manifest_code],
    ["Track", result.ota_track],
    ["RUI", result.rui_version],
    ["Displayed version", result.real_version_name],
    ["OTA version", result.real_ota_version],
    ["Computed OTA", result.computed_ota_version],
    ["Version type", result.version_type_id],
    ["About update", result.about_update_url || "-"],
    ["Download", result.download_url],
  ]
    .map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`)
    .join("");
  els.copyResultButton.disabled = !state.selectedDownloadUrl;
  els.openResultButton.disabled = !state.selectedDownloadUrl;
}

async function submitOta(event) {
  event.preventDefault();
  clearError(els.otaError);
  els.resultState.textContent = "loading";
  setBusy(els.findButton, true, "Finding...");

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
      headers: { "Content-Type": "application/json", Accept: "application/json", ...activeHeaders("ota") },
      body: JSON.stringify(payload),
    });
    renderResult(body.result);
    showToast("OTA query completed");
    await loadReleases();
  } catch (error) {
    const apiError = error.apiError || { code: "INTERNAL_ERROR", message: "Unexpected client error." };
    els.resultState.textContent = "error";
    els.resultState.className = "micro-chip error";
    displayError(els.otaError, apiError);
  } finally {
    if (state.publicSite) resetChallenge("ota");
    setBusy(els.findButton, false, "Find OTA");
  }
}

async function submitResolver(event) {
  event.preventDefault();
  clearError(els.resolverError);
  setBusy(els.resolveButton, true, "Resolving...");
  try {
    const body = await api("/api/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", ...activeHeaders("resolve") },
      body: JSON.stringify({ url: els.resolverUrl.value.trim(), source: "web" }),
    });
    els.resolverDetails.innerHTML = `<dt>Resolved URL</dt><dd>${body.resolved_url}</dd>`;
    showToast("Link resolved");
  } catch (error) {
    displayError(els.resolverError, error.apiError);
  } finally {
    if (state.publicSite) resetChallenge("resolve");
    setBusy(els.resolveButton, false, "Resolve");
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
  showToast("Download URL copied");
}

document.querySelectorAll(".segment").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segment").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.brand = button.dataset.brand || "";
    loadDevices();
  });
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
  if (state.selectedDownloadUrl) window.open(state.selectedDownloadUrl, "_blank", "noopener,noreferrer");
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
    if (release?.download_url) window.open(release.download_url, "_blank", "noopener,noreferrer");
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

loadHealth();
loadDevices();
loadReleases();
