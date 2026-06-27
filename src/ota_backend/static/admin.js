"use strict";

const state = {
  sb: null,
  session: null,
  lastGroups: [],
  // Tracks which list is currently rendered in #resultsPanel. We avoid
  // sniffing the visible title text so i18n / refactors don't quietly
  // break `refreshCurrentView`.
  //   "none"    – nothing rendered yet
  //   "enabled" – `listEnabled()` result
  //   "search"  – `search()` result
  //   "empty"   – rendered with an empty group list
  currentView: "none",
};

const $ = (id) => document.getElementById(id);

function toast(message, isError) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("err", !!isError);
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 3500);
}

async function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (state.session && state.session.access_token) {
    headers["Authorization"] = "Bearer " + state.session.access_token;
  }
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, Object.assign({}, options, { headers }));
  let data = null;
  try {
    data = await res.json();
  } catch (_e) {
    data = null;
  }
  if (!res.ok) {
    const code = data && data.error ? data.error.code : res.status;
    const msg = data && data.error ? data.error.message : "Request failed";
    const err = new Error(msg);
    err.code = code;
    err.status = res.status;
    throw err;
  }
  return data;
}

async function bootstrap() {
  let health;
  try {
    const res = await fetch("/api/health");
    if (!res.ok) {
      toast("Không kết nối được API", true);
      return;
    }
    try {
      health = await res.json();
    } catch (_e) {
      toast("API trả về dữ liệu không hợp lệ", true);
      return;
    }
  } catch (_e) {
    toast("Không kết nối được API", true);
    return;
  }
  const adminEnabled = !!(health && health.features && health.features.admin_auth_enabled);
  if (!adminEnabled) {
    // Admin auth disabled on the server (e.g. missing SUPABASE_ANON_KEY).
    // Show the login view with a clear message and exit cleanly so
    // state.sb stays null instead of crashing later callers.
    $("loginView").classList.remove("hidden");
    $("loginErr").textContent =
      "Thiếu cấu hình SUPABASE_ANON_KEY phía server. Không thể đăng nhập.";
    return;
  }
  let auth = null;
  try {
    const res = await fetch("/api/admin/bootstrap");
    if (!res.ok) {
      toast("Không tải được cấu hình admin", true);
      $("loginView").classList.remove("hidden");
      $("loginErr").textContent =
        "Không tải được cấu hình admin (HTTP " + res.status + ").";
      return;
    }
    let body = null;
    try {
      body = await res.json();
    } catch (_e) {
      toast("Cấu hình admin không hợp lệ", true);
      $("loginView").classList.remove("hidden");
      $("loginErr").textContent = "Phản hồi /api/admin/bootstrap không phải JSON hợp lệ.";
      return;
    }
    auth = body && body.admin_auth;
  } catch (_e) {
    toast("Không tải được cấu hình admin", true);
    $("loginView").classList.remove("hidden");
    $("loginErr").textContent = "Không kết nối được tới /api/admin/bootstrap.";
    return;
  }
  if (!auth || !auth.supabase_url || !auth.supabase_anon_key) {
    $("loginView").classList.remove("hidden");
    $("loginErr").textContent =
      "Thiếu cấu hình SUPABASE_ANON_KEY phía server. Không thể đăng nhập.";
    return;
  }
  state.sb = window.supabase.createClient(auth.supabase_url, auth.supabase_anon_key);
  const { data } = await state.sb.auth.getSession();
  state.session = data.session;
  if (state.session) {
    showApp();
  } else {
    $("loginView").classList.remove("hidden");
  }
  state.sb.auth.onAuthStateChange((_event, session) => {
    state.session = session;
  });
}

function showApp() {
  $("loginView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("logoutBtn").classList.remove("hidden");
  const email = state.session && state.session.user ? state.session.user.email : "";
  $("whoami").textContent = email || "";
  refreshStatus();
}

async function doLogin(event) {
  event.preventDefault();
  $("loginErr").textContent = "";
  const email = $("email").value.trim();
  const password = $("password").value;
  const { data, error } = await state.sb.auth.signInWithPassword({ email, password });
  if (error) {
    $("loginErr").textContent = "Đăng nhập thất bại: " + error.message;
    return;
  }
  state.session = data.session;
  showApp();
}

async function doLogout() {
  if (state.sb) await state.sb.auth.signOut();
  state.session = null;
  $("appView").classList.add("hidden");
  $("logoutBtn").classList.add("hidden");
  $("whoami").textContent = "";
  $("loginView").classList.remove("hidden");
}

async function refreshStatus() {
  try {
    const status = await apiFetch("/api/scan/status");
    const run = status.latest_run;
    if (run) {
      $("statRunStatus").textContent = run.status;
      $("statRunTasks").textContent =
        run.completed_tasks + "/" + run.failed_tasks + "/" + run.pending_tasks;
    } else {
      $("statRunStatus").textContent = "—";
      $("statRunTasks").textContent = "—";
    }
  } catch (e) {
    if (e.status === 401) return doLogout();
  }
  // enabled count comes back from any group call; fetch the enabled list head
  try {
    const data = await apiFetch("/api/admin/scan/groups?enabled_only=true&limit=1");
    $("statEnabled").textContent = data.enabled_total;
  } catch (e) {
    if (e.status === 401) return doLogout();
  }
}

function setEnabledTotal(n) {
  if (typeof n === "number") $("statEnabled").textContent = n;
}

function variantRow(group, variant) {
  const wrap = document.createElement("div");
  wrap.className = "admin-variant";
  const left = document.createElement("div");
  left.innerHTML =
    "<code>" + variant.product_model + "</code> " +
    '<span class="admin-muted">' + (variant.manifest_code || "no-manifest") + "</span> " +
    escapeHtml(variant.name || "");
  const right = document.createElement("div");
  right.className = "admin-row tight";
  const pill = document.createElement("span");
  pill.className = "admin-pill " + (variant.scan_enabled ? "on" : "off");
  pill.textContent = variant.scan_enabled ? "ON" : "OFF";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "admin-button sm " + (variant.scan_enabled ? "ghost" : "");
  btn.textContent = variant.scan_enabled ? "Tắt" : "Bật";
  btn.disabled = !variant.manifest_code && !variant.scan_enabled;
  btn.onclick = () => toggleModels([variant.product_model], !variant.scan_enabled);
  right.appendChild(pill);
  right.appendChild(btn);
  wrap.appendChild(left);
  wrap.appendChild(right);
  return wrap;
}

function renderGroups(groups, title, view) {
  state.lastGroups = groups;
  state.currentView = groups.length ? (view || "search") : "empty";
  $("resultsPanel").classList.remove("hidden");
  $("resultsTitle").textContent = title + " (" + groups.length + ")";
  const box = $("results");
  box.innerHTML = "";
  if (!groups.length) {
    box.innerHTML = '<p class="admin-muted">Không có nhóm nào.</p>';
    return;
  }
  for (const group of groups) {
    const el = document.createElement("div");
    el.className = "admin-group";
    const head = document.createElement("div");
    head.className = "admin-group-head";
    head.innerHTML =
      '<span class="admin-group-title">' + escapeHtml(group.name) + "</span>" +
      '<span class="admin-muted">' + group.enabled_count + "/" + group.variant_count + " ON</span>";
    const actions = document.createElement("div");
    actions.className = "admin-row tight";
    const onBtn = document.createElement("button");
    onBtn.type = "button";
    onBtn.className = "admin-button sm";
    onBtn.textContent = "Bật cả nhóm";
    onBtn.onclick = () => toggleGroup(group.key, true);
    const offBtn = document.createElement("button");
    offBtn.type = "button";
    offBtn.className = "admin-button sm ghost";
    offBtn.textContent = "Tắt cả nhóm";
    offBtn.onclick = () => toggleGroup(group.key, false);
    const scanBtn = document.createElement("button");
    scanBtn.type = "button";
    scanBtn.className = "admin-button sm ghost";
    scanBtn.textContent = "Scan ngay";
    scanBtn.title = "Quét OTA ngay cho các model trong nhóm";
    scanBtn.onclick = () =>
      enqueueScan(group.variants.map((v) => v.product_model));
    actions.appendChild(onBtn);
    actions.appendChild(offBtn);
    actions.appendChild(scanBtn);
    head.appendChild(actions);
    el.appendChild(head);
    for (const variant of group.variants) el.appendChild(variantRow(group, variant));
    box.appendChild(el);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

async function search() {
  const q = $("searchInput").value.trim();
  if (!q) return toast("Nhập từ khóa tìm kiếm", true);
  try {
    const data = await apiFetch("/api/admin/scan/groups?q=" + encodeURIComponent(q));
    setEnabledTotal(data.enabled_total);
    renderGroups(data.groups, "Kết quả: " + q, "search");
  } catch (e) {
    if (e.status === 401) return doLogout();
    toast(e.message, true);
  }
}

async function listEnabled() {
  try {
    const data = await apiFetch("/api/admin/scan/groups?enabled_only=true&limit=200");
    setEnabledTotal(data.enabled_total);
    renderGroups(data.groups, "Đang bật", "enabled");
  } catch (e) {
    if (e.status === 401) return doLogout();
    toast(e.message, true);
  }
}

async function refreshCurrentView() {
  // Drive the refresh off state.currentView so we don't depend on the
  // displayed title (which can be translated / contain user input).
  if (state.currentView === "enabled") return listEnabled();
  if (state.currentView === "search" && $("searchInput").value.trim()) return search();
}

async function toggleModels(models, enabled) {
  try {
    const data = await apiFetch("/api/admin/scan/models", {
      method: "POST",
      body: JSON.stringify({ product_models: models, enabled }),
    });
    setEnabledTotal(data.enabled_total);
    let msg = (enabled ? "Đã bật " : "Đã tắt ") + data.updated + " model";
    if (data.without_manifest && data.without_manifest.length)
      msg += " — bỏ qua (thiếu manifest): " + data.without_manifest.join(", ");
    toast(msg);
    await refreshCurrentView();
    refreshStatus();
  } catch (e) {
    if (e.status === 401) return doLogout();
    toast(e.message, true);
  }
}

async function toggleGroup(key, enabled) {
  try {
    const data = await apiFetch("/api/admin/scan/group", {
      method: "POST",
      body: JSON.stringify({ scan_group_key: key, enabled }),
    });
    setEnabledTotal(data.enabled_total);
    toast((enabled ? "Đã bật " : "Đã tắt ") + data.updated + " model trong nhóm");
    await refreshCurrentView();
    refreshStatus();
  } catch (e) {
    if (e.status === 401) return doLogout();
    toast(e.message, true);
  }
}

async function enableModelsFromInput() {
  const raw = $("modelInput").value.trim();
  if (!raw) return toast("Nhập ít nhất 1 model", true);
  const models = raw.split(/[,\s]+/).filter(Boolean);
  await toggleModels(models, true);
  $("modelInput").value = "";
}

async function disableAll() {
  if (!window.confirm("Tắt TOÀN BỘ scan? Tất cả model sẽ ngừng auto-scan.")) return;
  try {
    const data = await apiFetch("/api/admin/scan/disable-all", {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    });
    setEnabledTotal(data.enabled_total);
    toast("Đã tắt " + data.disabled + " model");
    await refreshCurrentView();
    refreshStatus();
  } catch (e) {
    if (e.status === 401) return doLogout();
    toast(e.message, true);
  }
}

async function enqueueScan(models) {
  if (!models || !models.length) return;
  try {
    const data = await apiFetch("/api/admin/scan/enqueue", {
      method: "POST",
      body: JSON.stringify({ product_models: models, reason: "admin-ui" }),
    });
    toast("Đã tạo run scan: " + data.created_tasks + " task");
    refreshStatus();
  } catch (e) {
    if (e.status === 401) return doLogout();
    toast(e.message, true);
  }
}

$("loginForm").addEventListener("submit", doLogin);
$("logoutBtn").addEventListener("click", doLogout);
$("refreshBtn").addEventListener("click", refreshStatus);
$("disableAllBtn").addEventListener("click", disableAll);
$("searchBtn").addEventListener("click", search);
$("searchInput").addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
$("listOnBtn").addEventListener("click", listEnabled);
$("enableModelsBtn").addEventListener("click", enableModelsFromInput);
$("modelInput").addEventListener("keydown", (e) => { if (e.key === "Enter") enableModelsFromInput(); });

bootstrap();
