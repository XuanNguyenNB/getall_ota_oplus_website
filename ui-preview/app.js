const releases = [
  {
    brand: "realme",
    model: "RMX3301",
    name: "Realme GT2 Pro",
    version: "RMX3301_15.0.0.1410(EX01)",
    ota: "RMX3301_11.H.21_4210_202602281641",
    manifest: "IN / 1B",
    track: "H",
    seen: "3m",
    url: "https://gauss-componentotamanual.allawnofs.com/remove-05f5255d1433d908ba1414335b01b855/component-ota/26/03/02/0a22d5070bab4cff91e1d4e07d3c2ef0.zip",
  },
  {
    brand: "oppo",
    model: "CPH2841TH",
    name: "OPPO Find X9 Ultra",
    version: "CPH2841_16.0.0.302(EX01)",
    ota: "CPH2841_11.C.12_1120_202605250840",
    manifest: "TH / 39",
    track: "C",
    seen: "27m",
    url: "https://gauss-componentotamanual.allawnofs.com/component-ota/demo-oppo.zip",
  },
  {
    brand: "oneplus",
    model: "CPH2653",
    name: "OnePlus 13",
    version: "CPH2653_16.0.0.812(EX01)",
    ota: "CPH2653_11.A.89_0890_202605240932",
    manifest: "ROW / A7",
    track: "A",
    seen: "1h",
    url: "https://gauss-componentotamanual.allawnofs.com/component-ota/demo-oneplus.zip",
  },
  {
    brand: "realme",
    model: "RMX5131TH",
    name: "Realme 16 Pro+",
    version: "RMX5131_16.0.1.240(EX01)",
    ota: "RMX5131_11.F.07_1070_202605220715",
    manifest: "TH / 39",
    track: "F",
    seen: "5h",
    url: "https://gauss-componentotamanual.allawnofs.com/component-ota/demo-realme-16.zip",
  },
];

const rowsEl = document.querySelector("#releaseRows");
const detailEl = document.querySelector("#detailList");
const toastEl = document.querySelector("#toast");
let selectedIndex = 0;
let activeBrand = "all";

function brandLabel(brand) {
  if (brand === "oppo") return "OPPO";
  if (brand === "realme") return "Realme";
  return "OnePlus";
}

function filteredReleases() {
  const query = document.querySelector("#deviceSearch").value.trim().toLowerCase();
  return releases.filter((release) => {
    const brandMatch = activeBrand === "all" || release.brand === activeBrand;
    const queryMatch = !query || [release.model, release.name, release.version].some((value) => value.toLowerCase().includes(query));
    return brandMatch && queryMatch;
  });
}

function renderRows() {
  const data = filteredReleases();
  rowsEl.innerHTML = data
    .map((release, index) => {
      const active = release.model === releases[selectedIndex].model ? "active" : "";
      return `
        <tr class="${active}" data-model="${release.model}">
          <td><span class="brand-badge ${release.brand}">${brandLabel(release.brand)}</span></td>
          <td>
            <strong>${release.model}</strong>
            <div class="subtitle">${release.name}</div>
          </td>
          <td class="version-cell">${release.version}</td>
          <td>${release.manifest}</td>
          <td><strong>${release.track}</strong></td>
          <td>${release.seen}</td>
          <td>
            <div class="row-actions">
              <button class="row-action" type="button" title="Copy URL" data-copy="${release.model}">
                <i data-lucide="copy"></i>
              </button>
              <button class="row-action" type="button" title="Open URL">
                <i data-lucide="external-link"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  if (!data.some((item) => item.model === releases[selectedIndex].model) && data.length) {
    selectedIndex = releases.findIndex((item) => item.model === data[0].model);
  }

  bindRowEvents();
  refreshIcons();
}

function renderDetails() {
  const release = releases[selectedIndex];
  const items = [
    ["Device", `${release.name} (${release.model})`],
    ["Version", release.version],
    ["OTA", release.ota],
    ["Manifest", release.manifest],
    ["Track", release.track],
    ["Download", release.url],
  ];

  detailEl.innerHTML = items.map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`).join("");
}

function bindRowEvents() {
  rowsEl.querySelectorAll("tr[data-model]").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      const model = row.getAttribute("data-model");
      selectedIndex = releases.findIndex((release) => release.model === model);
      renderRows();
      renderDetails();
    });
  });

  rowsEl.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const model = button.getAttribute("data-copy");
      const release = releases.find((item) => item.model === model);
      navigator.clipboard?.writeText(release.url).catch(() => {});
      showToast("Download URL copied");
    });
  });
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toastEl.classList.remove("show"), 1700);
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

document.querySelectorAll(".segment").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segment").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeBrand = button.dataset.brand;
    renderRows();
  });
});

document.querySelector("#deviceSearch").addEventListener("input", renderRows);

document.querySelector("#findButton").addEventListener("click", () => {
  const model = document.querySelector("#productModel").value.trim() || "RMX3301";
  showToast(`Queued manual query for ${model}`);
});

document.querySelector("#resolveButton").addEventListener("click", () => {
  showToast("Resolver request prepared");
});

renderRows();
renderDetails();
refreshIcons();
