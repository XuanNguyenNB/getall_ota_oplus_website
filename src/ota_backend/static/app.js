// app.js
//
// Thin orchestrator for the public site. The split modules under
// ``static/modules/`` own their own concerns (state, i18n, theme,
// api, challenge, format, url-safety). This file wires them together,
// owns the cached DOM references, and registers all DOM event
// handlers. Render functions stay here because they are tightly
// coupled to the ``els`` map and the template strings; lifting them
// out doesn't help without first introducing a real templating layer.

import { api, clientError as _clientError } from "./modules/api.js";
import {
  activeHeaders,
  mountTurnstile,
  requestChallengeToken,
  resetChallenge,
} from "./modules/challenge.js";
import {
  brandLabel,
  edlDateLabel,
  edlSortTimestamp,
  escapeHtml,
  formatDate,
  releasePublishedLabel,
  releaseRegionLabel,
  releaseSortTimestamp,
} from "./modules/format.js";
import { applyTranslations as applyTranslationsBase, loadLanguage, normalizeLanguage, t } from "./modules/i18n.js";
import {
  LANGUAGE_STORAGE_KEY,
  state,
} from "./modules/state.js";
import { applyTheme, currentThemeIsDark, toggleTheme } from "./modules/theme.js";
import {
  isBrowserBlockedDownloadUrl,
  isResolvableDownloadUrl,
  isSafeNetworkUrl,
  safeWindowOpen,
} from "./modules/url-safety.js";

const els = {
  apiStatus: document.querySelector("#apiStatus"),
  runtimeStatus: document.querySelector("#runtimeStatus"),
  languageButtons: document.querySelectorAll("[data-language]"),
  packageButtons: document.querySelectorAll("[data-package]"),
  refreshButton: document.querySelector("#refreshButton"),
  themeToggle: document.querySelector("#themeToggle"),
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
  releaseTypeFilter: document.querySelector("#releaseTypeFilter"),
  releaseMetaHeader: document.querySelector("#releaseMetaHeader"),
  releaseSearch: document.querySelector("#releaseSearch"),
  releaseError: document.querySelector("#releaseError"),
  edlWarning: document.querySelector("#edlWarning"),
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

function applyTranslations(root = document) {
  applyTranslationsBase(root);
  els.languageButtons.forEach((button) => {
    const active = button.dataset.language === state.language;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  renderPackageChrome();
}

function setLanguage(language) {
  state.language = normalizeLanguage(language);
  window.localStorage?.setItem(LANGUAGE_STORAGE_KEY, state.language);
  // Fire-and-forget: ``loadLanguage`` caches, so re-rendering once
  // the dictionary lands is cheap. If the user toggles before the
  // fetch settles, the second toggle will still wait on the first
  // request via the inflight cache.
  loadLanguage(state.language).then(() => {
    applyTranslations();
    configureFeatures({
      public_site: state.publicSite,
      resolver: state.resolverEnabled,
      turnstile_site_key: state.turnstileSiteKey,
    });
    renderDevices(state.devicesTotal);
    if (state.selectedProductModel || els.productModel.value.trim()) {
      if (state.packageMode === "edl") {
        renderEdlRegionOptions();
        renderEdlRoms(state.edlRomsTotal);
      } else {
        renderReleaseRegionOptions();
        renderReleases(state.releasesTotal);
      }
    } else {
      loadReleases();
    }
    if (state.lastResult) {
      renderResult(state.lastResult);
    } else {
      renderDefaultResult();
    }
    renderResolverResult();
  });
}

function setPackageMode(mode) {
  state.packageMode = mode === "edl" ? "edl" : "ota";
  state.releaseRegion = "";
  state.releaseType = "";
  els.releaseRegion.value = "";
  els.releaseType.value = "";
  renderPackageChrome();
  loadReleases();
}

function renderPackageChrome() {
  if (!els.packageButtons?.length) return;
  const edlMode = state.packageMode === "edl";
  els.packageButtons.forEach((button) => {
    const active = button.dataset.package === state.packageMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  if (els.edlWarning) els.edlWarning.hidden = !edlMode;
  if (els.releaseTypeFilter) els.releaseTypeFilter.hidden = edlMode;
  if (els.releaseMetaHeader) {
    els.releaseMetaHeader.textContent = t(edlMode ? "archive.updated" : "archive.type");
  }
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

function configureChallengePanel(panel, enabled) {
  panel.hidden = !enabled;
  panel.classList.toggle("silent-challenge-panel", enabled);
  panel.setAttribute("aria-hidden", "true");
}

function configureFeatures(features) {
  state.publicSite = Boolean(features?.public_site);
  state.resolverEnabled = Boolean(features?.resolver);
  state.turnstileSiteKey = features?.turnstile_site_key || "";
  const runtimeLabel = state.publicSite
    ? t("runtime.publicProtected")
    : t("runtime.localOperator");
  els.runtimeStatus.innerHTML = `<span></span>${escapeHtml(runtimeLabel)}`;
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

function renderEdlActions(rom) {
  return `
    <button class="row-action" type="button" data-copy-edl="${rom.id}" title="${escapeHtml(t("edl.copyTitle"))}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
      <span>${escapeHtml(t("actions.copy"))}</span>
    </button>
    <button class="row-action" type="button" data-open-edl="${rom.id}" title="${escapeHtml(t("edl.openTitle"))}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="btn-icon">
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
      </svg>
      <span>${escapeHtml(t("actions.open"))}</span>
    </button>
  `;
}

function releaseGroupKey(release) {
  return [
    release.product_model || "",
    release.manifest_code || "",
    release.region_code || "",
    release.release_type || "official",
    release.real_ota_version || release.real_version_name || "",
  ].join("::");
}

function buildReleaseGroups(releases) {
  const groupsByKey = new Map();
  releases.forEach((release) => {
    const key = releaseGroupKey(release);
    const variants = groupsByKey.get(key) || [];
    variants.push(release);
    groupsByKey.set(key, variants);
  });
  return Array.from(groupsByKey.values())
    .map((variants) => {
      const sorted = [...variants].sort(
        (left, right) => releaseSortTimestamp(right) - releaseSortTimestamp(left),
      );
      return { primary: sorted[0], variants: sorted };
    })
    .sort((left, right) => releaseSortTimestamp(right.primary) - releaseSortTimestamp(left.primary));
}

function renderReleaseVariantLinks(group) {
  if (group.variants.length <= 1) return "";
  const links = group.variants.length;
  const events = new Set(group.variants.map((release) => releasePublishedLabel(release))).size;
  const badge = t("release.duplicateBadge", { links, events });
  return `
    <details class="release-variants">
      <summary>
        <span>${escapeHtml(t("release.showVariants"))}</span>
        <span class="release-variant-badge">${escapeHtml(badge)}</span>
      </summary>
      <div class="release-variant-list">
        ${group.variants.map((release, index) => `
          <div class="release-variant-row">
            <div class="release-variant-meta">
              <strong>${escapeHtml(index === 0 ? t("release.primaryLink") : t("release.alternateLink"))}</strong>
              <span>${releasePublishedLabel(release)} · ${escapeHtml(t(`release.type.${release.release_type || "official"}`))}</span>
            </div>
            <div class="release-variant-actions">
              ${renderReleaseActions(release)}
            </div>
          </div>
        `).join("")}
      </div>
    </details>
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
  } catch (_error) {
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
    els.deviceList.insertAdjacentHTML(
      "beforeend",
      `<div class="empty-state">${escapeHtml(t("device.matchesShown", { shown: state.devices.length, total }))}</div>`,
    );
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
  renderPackageChrome();

  if (!selectedModel) {
    els.releaseTitle.textContent = t(state.packageMode === "edl" ? "edl.title" : "archive.title");
    els.releaseSummary.textContent = t(
      state.packageMode === "edl" ? "edl.selectDevice" : "archive.noDeviceSelected",
    );
    els.releaseRows.innerHTML = `
      <tr>
        <td colspan="5" class="empty-cell">
          <div class="welcome-placeholder-card">
            <svg class="welcome-placeholder-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="2.5" ry="2.5"/>
              <path d="M12 17h.01M12 12h.01M12 7h.01"/>
            </svg>
            <strong>${escapeHtml(t("archive.welcomeTitle"))}</strong>
            <span>${escapeHtml(t(state.packageMode === "edl" ? "edl.selectDevice" : "archive.welcomeText"))}</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  if (state.packageMode === "edl") {
    await loadEdlRoms(selectedModel);
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

async function loadEdlRoms(selectedModel) {
  els.releaseTitle.textContent = t("edl.title");
  els.releaseSummary.textContent = t("archive.loading");
  els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("archive.loading"))}</td></tr>`;

  const params = new URLSearchParams({
    limit: "200",
    sort: "build",
    product_model: selectedModel,
  });
  if (state.releaseRegion) params.set("region_code", state.releaseRegion);
  if (state.releaseSearch) params.set("q", state.releaseSearch);

  try {
    const body = await api(`/api/edl-roms?${params.toString()}`);
    state.edlRoms = (body.roms || []).sort(
      (left, right) => edlSortTimestamp(right) - edlSortTimestamp(left),
    );
    state.edlRomsTotal = body.total || 0;
    renderEdlRegionOptions();
    renderEdlRoms(state.edlRomsTotal);
  } catch (error) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("archive.couldNotLoad"))}</td></tr>`;
    els.releaseSummary.textContent = t("archive.loadFailed");
    displayError(els.releaseError, error.apiError);
  }
}

function renderReleaseRegionOptions() {
  const selected = state.releaseRegion;
  const regions = Array.from(
    new Set(state.releases.map((release) => release.region_code).filter(Boolean)),
  ).sort();
  els.releaseRegion.innerHTML = [`<option value="">${escapeHtml(t("archive.all"))}</option>`]
    .concat(regions.map((region) => `<option value="${escapeHtml(region)}">${escapeHtml(region)}</option>`))
    .join("");
  els.releaseRegion.value = regions.includes(selected) ? selected : "";
  state.releaseRegion = els.releaseRegion.value;
}

function renderEdlRegionOptions() {
  const selected = state.releaseRegion;
  const regions = Array.from(new Set(state.edlRoms.map((rom) => rom.region_code).filter(Boolean))).sort();
  els.releaseRegion.innerHTML = [`<option value="">${escapeHtml(t("archive.all"))}</option>`]
    .concat(regions.map((region) => `<option value="${escapeHtml(region)}">${escapeHtml(region)}</option>`))
    .join("");
  els.releaseRegion.value = regions.includes(selected) ? selected : "";
  state.releaseRegion = els.releaseRegion.value;
}

function renderReleases(total) {
  const selectedModel = state.selectedProductModel || els.productModel.value.trim().toUpperCase();
  const suffix = selectedModel ? t("archive.forModel", { model: selectedModel }) : "";
  const releaseGroups = buildReleaseGroups(state.releases);
  els.releaseSummary.textContent = total
    ? (releaseGroups.length < state.releases.length
      ? t("archive.summaryGrouped", { groupCount: releaseGroups.length, rawCount: total, suffix })
      : t(total === 1 ? "archive.summaryOne" : "archive.summary", { count: total, suffix }))
    : t("archive.summaryNone", { suffix });
  if (!releaseGroups.length) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("archive.noReleases"))}</td></tr>`;
    return;
  }

  els.releaseRows.innerHTML = releaseGroups
    .map(
      (group) => {
        const release = group.primary;
        return `
        <tr>
          <td data-label="${escapeHtml(t("archive.release"))}">
            <strong class="version-cell">${escapeHtml(release.real_version_name)}</strong>
            <div class="release-subline">${escapeHtml(release.product_model)} / ${brandLabel(release.brand)} / ${escapeHtml(release.ota_track || "-")}</div>
            <div class="release-subline version-cell">${escapeHtml(release.real_ota_version || "-")}</div>
            ${renderReleaseVariantLinks(group)}
          </td>
          <td data-label="${escapeHtml(t("archive.region"))}"><span class="release-badge">${escapeHtml(releaseRegionLabel(release))}</span></td>
          <td data-label="${escapeHtml(t("archive.type"))}"><span class="release-badge ${release.release_type === "beta" ? "beta" : "official"}">${escapeHtml(t(`release.type.${release.release_type || "official"}`))}</span></td>
          <td data-label="${escapeHtml(t("archive.published"))}">${releasePublishedLabel(release)}</td>
          <td class="release-actions" data-label="${escapeHtml(t("archive.actions"))}">
            ${renderReleaseActions(release)}
          </td>
        </tr>
      `;
      },
    )
    .join("");
}

function renderEdlRoms(total) {
  const selectedModel = state.selectedProductModel || els.productModel.value.trim().toUpperCase();
  const suffix = selectedModel ? t("archive.forModel", { model: selectedModel }) : "";
  els.releaseSummary.textContent = total
    ? t(total === 1 ? "edl.summaryOne" : "edl.summary", { count: total, suffix })
    : t("edl.summaryNone", { suffix });
  if (!state.edlRoms.length) {
    els.releaseRows.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("edl.noRoms"))}</td></tr>`;
    return;
  }

  els.releaseRows.innerHTML = state.edlRoms
    .map(
      (rom) => `
        <tr>
          <td data-label="${escapeHtml(t("archive.release"))}">
            <strong class="version-cell">${escapeHtml(rom.version_name)}</strong>
            <div class="release-subline">${escapeHtml(rom.product_model)} / ${brandLabel(rom.brand)}${rom.device_name ? ` / ${escapeHtml(rom.device_name)}` : ""}</div>
          </td>
          <td data-label="${escapeHtml(t("archive.region"))}"><span class="release-badge">${escapeHtml(rom.region_code || "-")}</span></td>
          <td data-label="${escapeHtml(t("archive.updated"))}">${rom.source_updated_at ? formatDate(rom.source_updated_at) : "-"}</td>
          <td data-label="${escapeHtml(t("archive.published"))}">${edlDateLabel(rom)}</td>
          <td class="release-actions" data-label="${escapeHtml(t("archive.actions"))}">
            ${renderEdlActions(rom)}
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
  els.openResultButton.disabled =
    !state.selectedDownloadUrl || isBrowserBlockedDownloadUrl(state.selectedDownloadUrl);
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
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(await activeHeaders("ota")),
      },
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
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(await activeHeaders("resolve")),
      },
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
  if (!isSafeNetworkUrl(text)) {
    // Refuse to copy non-network URLs so a poisoned download_url cannot end
    // up on the clipboard and later be pasted into a browser bar. No toast
    // since this is an unexpected/edge case, not a user-driven outcome.
    return;
  }
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

// --- DOM wiring -------------------------------------------------------

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

els.packageButtons.forEach((button) => {
  button.addEventListener("click", () => setPackageMode(button.dataset.package));
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
els.themeToggle?.addEventListener("click", () => toggleTheme(els.themeToggle));
els.copyResultButton.addEventListener("click", () => copyText(state.selectedDownloadUrl));
els.openResultButton.addEventListener("click", () => {
  if (state.selectedDownloadUrl && !isBrowserBlockedDownloadUrl(state.selectedDownloadUrl)) {
    safeWindowOpen(state.selectedDownloadUrl);
  }
});

els.releaseRows.addEventListener("click", (event) => {
  const copyEdlButton = event.target.closest("[data-copy-edl]");
  if (copyEdlButton) {
    const rom = state.edlRoms.find((item) => item.id === copyEdlButton.dataset.copyEdl);
    copyText(rom?.download_url || "");
    return;
  }
  const openEdlButton = event.target.closest("[data-open-edl]");
  if (openEdlButton) {
    const rom = state.edlRoms.find((item) => item.id === openEdlButton.dataset.openEdl);
    if (rom?.download_url) {
      safeWindowOpen(rom.download_url);
    }
    return;
  }
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
      safeWindowOpen(release.download_url);
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
applyTheme(currentThemeIsDark(), els.themeToggle);
// Top-level await: the first paint deserves real translations, not
// raw keys. ``loadLanguage`` also pre-warms English so the t()
// fallback chain works for any keys missing from the active language.
await Promise.all([loadLanguage(state.language), loadLanguage("en")]);
applyTranslations();
renderDefaultResult();
loadHealth();
loadDevices();
loadReleases();

// Surface a few helpers under window for debugging in DevTools. The
// internal modules are the source of truth — these are read-only mirrors.
window.__app = {
  state,
  requestChallengeToken,
  isSafeNetworkUrl,
};
