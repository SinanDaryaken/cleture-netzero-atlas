(() => {
  "use strict";

  const els = {
    health: document.querySelector("#catalog-health"),
    form: document.querySelector("#catalog-filters"),
    source: document.querySelector("#catalog-source"),
    sourceSummary: document.querySelector("#source-summary"),
    sector: document.querySelector("#catalog-sector"),
    sectorSummary: document.querySelector("#sector-summary"),
    category: document.querySelector("#catalog-category"),
    scope: document.querySelector("#catalog-scope"),
    query: document.querySelector("#catalog-query"),
    reset: document.querySelector("#catalog-reset"),
    count: document.querySelector("#catalog-count"),
    yearBreakdown: document.querySelector("#catalog-year-breakdown"),
    activeFilters: document.querySelector("#catalog-active-filters"),
    list: document.querySelector("#catalog-list"),
    more: document.querySelector("#catalog-more"),
    detail: document.querySelector("#catalog-detail-body"),
    copy: document.querySelector("#copy-factor-id"),
    toast: document.querySelector("#catalog-toast"),
  };

  const state = {
    sources: [],
    sectors: [],
    allItems: [],
    items: [],
    nextCursor: null,
    yearFilter: "",
    selectedKey: null,
    selectedFactor: null,
    queryResolution: null,
    conceptResolution: null,
    searchSerial: 0,
  };

  const EM_DASH = "—";
  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const display = (value) => {
    if (value === null || value === undefined || value === "") return EM_DASH;
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) return value.length ? value.join(", ") : EM_DASH;
    if (typeof value === "object") return JSON.stringify(value, null, 2);
    return String(value);
  };

  const prettyJson = (value) => esc(JSON.stringify(value, null, 2));
  const factorKey = (factor) => `${factor.factor_id}|${factor.reference_year ?? "UNDATED"}|${factor.factor_version_id ?? ""}`;
  const factorYear = (factor) => factor.reference_year ?? "UNDATED";

  function factorScope(factor) {
    const declared = factor.methodology?.scope;
    if (declared) {
      const match = String(declared).match(/scope[_\s-]*(\d)/i);
      return match ? `Scope ${match[1]}` : String(declared).replaceAll("_", " ");
    }
    if (factor.methodology?.system_boundary === "national_inventory_implied_factor") {
      return "Scope 1 · inferred";
    }
    return "Unspecified";
  }

  const geographyRoleLabels = {
    production_origin: "ORIGIN",
    market: "MARKET",
    calculation_applicability: "APPLICABLE",
    jurisdiction: "JURISDICTION",
    grid: "GRID",
    route_origin: "ROUTE FROM",
    route_destination: "ROUTE TO",
  };

  function factorGeography(factor) {
    const assignment = (factor.geography_roles || [])[0];
    if (assignment?.geography?.code) {
      return `${geographyRoleLabels[assignment.role] || assignment.role.toUpperCase()} · ${assignment.geography.code}`;
    }
    if (factor.origin_geography?.code) return `ORIGIN · ${factor.origin_geography.code}`;
    const applicable = (factor.applicable_geographies || [])[0];
    if (applicable?.code) return `APPLICABLE · ${applicable.code}`;
    return "UNKNOWN";
  }

  function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return display(value);
    return new Intl.NumberFormat("en-US", { maximumSignificantDigits: 9 }).format(number);
  }

  async function api(path) {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      let reason = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        reason = payload.detail || reason;
      } catch (_) {
        // Keep the HTTP reason when the response is not JSON.
      }
      throw new Error(reason);
    }
    return response.json();
  }

  function toast(message) {
    els.toast.textContent = message;
    els.toast.classList.add("show");
    window.setTimeout(() => els.toast.classList.remove("show"), 1800);
  }

  function emptyState(title, text) {
    return `<div class="catalog-empty"><i></i><strong>${esc(title)}</strong><p>${esc(text)}</p></div>`;
  }

  function loadingCards() {
    return '<div class="catalog-loading"><i></i><i></i><i></i><i></i></div>';
  }

  function renderActiveFilters() {
    const chips = ["Published", "Factor + LCA records"];
    if (els.source.value) chips.push(`Source · ${els.source.value}`);
    if (els.sector.value) chips.push(`Sector · ${els.sector.options[els.sector.selectedIndex].text}`);
    if (els.category.value) chips.push(`Category · ${els.category.options[els.category.selectedIndex].text}`);
    if (els.scope.value) chips.push(`Scope · ${els.scope.options[els.scope.selectedIndex].text}`);
    if (els.query.value.trim()) chips.push(`Text · ${els.query.value.trim()}`);
    if (state.queryResolution) {
      chips.push(`Resolved geography · ${state.queryResolution.geography_name} (${state.queryResolution.geography_code})`);
    }
    const appliedConcepts = state.conceptResolution?.applied_concept_codes || [];
    if (appliedConcepts.length) {
      const candidate = (state.conceptResolution.candidates || [])
        .find((item) => item.concept_code === appliedConcepts[0]);
      const matchedTerm = candidate?.matched_term || state.conceptResolution.query;
      chips.push(`Resolved concept · ${matchedTerm} → ${appliedConcepts.join(", ")}`);
    }
    if (state.yearFilter) chips.push(`Year · ${state.yearFilter}`);
    els.activeFilters.innerHTML = chips.map((chip) => `<span>${esc(chip)}</span>`).join("");
  }

  function renderResults() {
    renderActiveFilters();
    els.count.textContent = String(state.items.length);
    renderYearBreakdown();
    els.more.hidden = !state.nextCursor;
    if (!state.items.length) {
      els.list.innerHTML = emptyState(
        "No published emission factor",
        "Change the source, scope or text filter. The catalog does not apply calculation-profile eligibility rules.",
      );
      return;
    }
    els.list.innerHTML = state.items.map((factor, index) => {
      const selected = factorKey(factor) === state.selectedKey ? " selected" : "";
      return `
        <button class="catalog-factor${selected}" data-key="${esc(factorKey(factor))}" type="button" style="animation-delay:${Math.min(index, 12) * 18}ms">
          <span class="catalog-factor-index">${String(index + 1).padStart(2, "0")}</span>
          <span class="catalog-factor-main">
            <span class="catalog-factor-source">${esc(factor.source_code)} · ${esc(factorYear(factor))}</span>
            <strong>${esc(factor.name)}</strong>
            <span class="catalog-factor-meta">
              <span>${esc(factorScope(factor))}</span><span>·</span>
              <span>${esc(factor.sector?.sector_code || "UNCLASSIFIED")}</span><span>·</span>
              <span>${esc(factorGeography(factor))}</span><span>·</span>
              <span>${esc(factor.entity_type)}</span>
            </span>
          </span>
          <span class="catalog-factor-value">${esc(formatNumber(factor.factor_value))}<small>${esc(factor.factor_unit)}</small></span>
        </button>`;
    }).join("");
  }

  function applyYearFilter() {
    state.items = state.yearFilter
      ? state.allItems.filter((factor) => String(factorYear(factor)) === state.yearFilter)
      : [...state.allItems];
  }

  function renderYearBreakdown() {
    const counts = new Map();
    state.allItems.forEach((factor) => {
      const year = String(factorYear(factor));
      counts.set(year, (counts.get(year) || 0) + 1);
    });
    if (counts.size < 2) {
      els.yearBreakdown.hidden = true;
      els.yearBreakdown.textContent = "";
      return;
    }
    const ordered = [...counts.entries()].sort(([left], [right]) => {
      if (left === "UNDATED") return 1;
      if (right === "UNDATED") return -1;
      return Number(right) - Number(left);
    });
    els.yearBreakdown.innerHTML = `<span>Filter by year</span>
      <button class="${state.yearFilter ? "" : "active"}" type="button" data-year="" aria-pressed="${state.yearFilter ? "false" : "true"}">All <i>${state.allItems.length}</i></button>${ordered
      .map(([year, count]) => `<button class="${state.yearFilter === year ? "active" : ""}" type="button" data-year="${esc(year)}" aria-pressed="${state.yearFilter === year ? "true" : "false"}">${esc(year)} <i>${count}</i></button>`)
      .join("")}`;
    els.yearBreakdown.hidden = false;
  }

  function recordGrid(entries) {
    return `<dl class="record-grid">${entries.map(([label, value]) => `
      <div><dt>${esc(label)}</dt><dd>${esc(display(value))}</dd></div>`).join("")}</dl>`;
  }

  function inspectorList(entries) {
    return `<dl class="inspector-list">${entries.map(([label, value]) => `
      <div><dt>${esc(label)}</dt><dd>${esc(display(value))}</dd></div>`).join("")}</dl>`;
  }

  function inspectorSection(title, body, count = "") {
    return `<section class="inspector-section"><header><span>${esc(title)}</span><b>${esc(count)}</b></header>${body}</section>`;
  }

  function renderDetail(factor, versions, source) {
    state.selectedFactor = factor;
    els.copy.hidden = false;

    const gases = Object.entries(factor.gases || {}).filter(([, value]) => value !== null && value !== undefined);
    const geographies = factor.applicable_geographies || [];
    const geographyRoles = factor.geography_roles || [];
    const provenance = factor.provenance || [];
    const methodology = factor.methodology || {};
    const sourceLicense = source?.license || {};

    const identity = [
      ["Factor ID", factor.factor_id],
      ["Source factor ID", factor.source_factor_id],
      ["Factor version ID", factor.factor_version_id],
      ["Dataset version ID", factor.dataset_version_id],
      ["Cursor", factor.cursor],
      ["Source", factor.source_code],
      ["Source health", factor.source_health],
      ["Version status", factor.version_status],
    ];
    const classification = [
      ["Entity type", factor.entity_type],
      ["Factor value kind", factor.factor_value_kind],
      ["Intended use", factor.intended_use],
      ["Default match eligible", factor.default_match_eligible],
      ["License eligible", factor.license_eligible],
      ["Taxonomy code", factor.taxonomy_code],
      ["Sector", factor.sector?.sector_code],
      ["Sector category", factor.sector?.category_code],
      ["Sector confidence", factor.sector ? `${factor.sector.confidence}%` : null],
      ["Sector rule", factor.sector?.evidence?.rule],
      ["Sector mapping version", factor.sector?.mapping_version],
      ["Concept code", factor.concept_code],
      ["Data quality", factor.data_quality],
    ];
    const methodEntries = [
      ["Declared scope", methodology.scope],
      ["Catalog scope", factorScope(factor)],
      ["Methodology", methodology.methodology],
      ["System boundary", methodology.system_boundary],
      ["Lifecycle stage", methodology.lifecycle_stage],
      ["GWP standard", methodology.gwp_standard],
      ["Uncertainty", methodology.uncertainty],
      ["Methodology details", methodology.details],
    ];
    const sourceEntries = source ? [
      ["Code", source.code],
      ["Name", source.name],
      ["Publisher", source.publisher],
      ["Status", source.status],
      ["Health", source.health],
      ["Country / region", [source.country, source.region].filter(Boolean).join(" · ")],
      ["Data types", source.data_types],
      ["Use contexts", source.use_contexts],
      ["Standards", source.standards],
      ["License kind", sourceLicense.kind],
      ["License URL", sourceLicense.url],
    ] : [["Source definition", "Unavailable"]];

    const geographyBody = geographies.length
      ? `<div class="geography-stack">${geographies.map((geo) => `<span>${esc(geo.code)} · ${esc(geo.name || geo.level)}</span>`).join("")}</div>`
      : `<div class="geography-stack"><span>No applicable geography declared</span></div>`;
    const geographyRolesBody = geographyRoles.length
      ? `<div class="geography-stack">${geographyRoles.map((assignment) => `
          <span>${esc(geographyRoleLabels[assignment.role] || assignment.role)} · ${esc(assignment.geography?.code || "UNKNOWN")} · ${esc(assignment.geography?.name || assignment.geography?.level || "Unknown")} · ${esc(assignment.derivation)} · ${esc(assignment.source_field)}</span>`).join("")}</div>`
      : `<div class="geography-stack"><span>No verified semantic role; no value was inferred</span></div>`;
    const gasBody = gases.length
      ? `<div class="gas-stack">${gases.map(([gas, value]) => `<span>${esc(gas.toUpperCase())} <b>${esc(formatNumber(value))}</b></span>`).join("")}</div>`
      : `<div class="gas-stack"><span>No gas breakdown declared</span></div>`;
    const versionBody = versions.length
      ? `<div class="version-stack">${versions.map((version) => `
          <div class="version-row"><strong>${esc(factorYear(version))}</strong><span>${esc(version.factor_version_id || version.dataset_version_id || EM_DASH)}</span><b>${esc(formatNumber(version.factor_value))} ${esc(version.factor_unit || "")}</b></div>`).join("")}</div>`
      : `<div class="geography-stack"><span>No version history returned</span></div>`;
    const provenanceBody = provenance.length
      ? inspectorList(provenance.map((entry, index) => [`Step ${index + 1}`, entry]))
      : inspectorList([["Provenance", "No provenance records attached"]]);

    els.detail.innerHTML = `
      <article class="factor-hero">
        <div>
          <div class="factor-hero-eyebrow">
            <span class="factor-scope">${esc(factorScope(factor))}</span>
            <span class="record-chip">${esc(factor.source_code)}</span>
            <span class="record-chip">${esc(factorYear(factor))}</span>
          </div>
          <h3>${esc(factor.name)}</h3>
          <code class="factor-hero-id">${esc(factor.factor_id)}</code>
        </div>
        <div class="factor-hero-value">${esc(formatNumber(factor.factor_value))}<small>${esc(factor.factor_unit)}</small></div>
      </article>
      ${recordGrid([
        ["Activity type", factor.activity_type],
        ["Activity unit", factor.activity_unit],
        ["Reference year", factorYear(factor)],
        ["Origin geography", factor.origin_geography ? `${factor.origin_geography.name || factor.origin_geography.code} · ${factor.origin_geography.level}` : "Unknown · not inferred"],
        ["Valid from", factor.valid_from],
        ["Valid to", factor.valid_to],
        ["Published at", factor.published_at],
        ["Retrieved at", factor.retrieved_at],
        ["Effective from", factor.effective_from],
        ["Effective to", factor.effective_to],
        ["Superseded at", factor.superseded_at],
        ["Supersedes version", factor.supersedes_version_id],
      ])}
      <div class="inspector-columns">
        ${inspectorSection("Record identity", inspectorList(identity))}
        ${inspectorSection("Classification", inspectorList(classification))}
        ${inspectorSection("Methodology", inspectorList(methodEntries))}
        ${inspectorSection("Source registry", inspectorList(sourceEntries))}
        ${inspectorSection("Applicable geographies", geographyBody, `${geographies.length} records`)}
        ${inspectorSection("Geography semantics", geographyRolesBody, `${geographyRoles.length} verified roles`)}
        ${inspectorSection("Gas breakdown", gasBody, `${gases.length} gases`)}
        ${inspectorSection("Version history", versionBody, `${versions.length} versions`)}
        ${inspectorSection("Provenance", provenanceBody, `${provenance.length} steps`)}
      </div>
      <details class="raw-inspector"><summary>Raw factor record</summary><pre>${prettyJson(factor)}</pre></details>
      <details class="raw-inspector"><summary>Raw source definition</summary><pre>${prettyJson(source)}</pre></details>
      <details class="raw-inspector"><summary>Raw version history</summary><pre>${prettyJson(versions)}</pre></details>`;
  }

  async function selectFactor(item) {
    const key = factorKey(item);
    state.selectedKey = key;
    renderResults();
    els.copy.hidden = true;
    els.detail.innerHTML = loadingCards();
    const encodedId = encodeURIComponent(item.factor_id);
    const yearQuery = item.reference_year == null ? "" : `?reference_year=${encodeURIComponent(item.reference_year)}`;
    try {
      const [factor, versions, source] = await Promise.all([
        api(`/v1/factors/${encodedId}${yearQuery}`),
        api(`/v1/factors/${encodedId}/versions`),
        api(`/v1/sources/${encodeURIComponent(item.source_code)}`),
      ]);
      if (state.selectedKey !== key) return;
      renderDetail(factor, versions, source);
    } catch (error) {
      if (state.selectedKey !== key) return;
      els.detail.innerHTML = emptyState("Record could not be opened", error.message);
    }
  }

  function buildSearchPath(cursor = null) {
    const params = new URLSearchParams({ limit: "100", factor_records_only: "true" });
    const query = els.query.value.trim();
    if (query) params.set("query", query);
    if (els.source.value) params.set("source", els.source.value);
    if (els.sector.value) params.set("sector", els.sector.value);
    if (els.category.value) params.set("category", els.category.value);
    if (els.scope.value) params.set("scope", els.scope.value);
    if (cursor) params.set("cursor", cursor);
    return `/v1/factors?${params}`;
  }

  async function search({ append = false } = {}) {
    const serial = ++state.searchSerial;
    if (!append) {
      state.allItems = [];
      state.items = [];
      state.nextCursor = null;
      state.yearFilter = "";
      state.selectedKey = null;
      state.selectedFactor = null;
      state.queryResolution = null;
      state.conceptResolution = null;
      els.copy.hidden = true;
      els.list.innerHTML = loadingCards();
      els.detail.innerHTML = emptyState("Select a published record", "The complete factor, methodology, source definition, provenance and version history will appear here.");
    }
    els.more.disabled = true;
    renderActiveFilters();
    try {
      const payload = await api(buildSearchPath(append ? state.nextCursor : null));
      if (serial !== state.searchSerial) return;
      state.allItems = append
        ? state.allItems.concat(payload.items || [])
        : (payload.items || []);
      state.queryResolution = payload.query_resolution || null;
      state.conceptResolution = payload.concept_resolution || null;
      applyYearFilter();
      state.nextCursor = payload.next_cursor || null;
      renderResults();
      if (!append && state.items.length) await selectFactor(state.items[0]);
    } catch (error) {
      if (serial !== state.searchSerial) return;
      els.list.innerHTML = emptyState("Catalog request failed", error.message);
      els.count.textContent = "ERR";
      els.more.hidden = true;
    } finally {
      els.more.disabled = false;
    }
  }

  async function loadSources() {
    try {
      state.sources = await api("/v1/sources");
      const published = state.sources
        .filter((source) => ["active", "implemented"].includes(source.status) || source.health === "healthy")
        .sort((a, b) => a.name.localeCompare(b.name));
      els.source.insertAdjacentHTML("beforeend", published.map((source) =>
        `<option value="${esc(source.code)}">${esc(source.name)} · ${esc(source.code)}</option>`,
      ).join(""));
      els.sourceSummary.textContent = `${published.length} operational sources in registry`;
    } catch (error) {
      els.sourceSummary.textContent = `Source registry unavailable · ${error.message}`;
    }
  }

  function renderCategories() {
    const selectedSector = state.sectors.find((sector) => sector.code === els.sector.value);
    const categories = selectedSector
      ? selectedSector.categories
      : state.sectors.flatMap((sector) => sector.categories || []);
    const unique = [...new Map(
      categories
        .filter((category) => category.count > 0)
        .map((category) => [category.code, category]),
    ).values()]
      .sort((left, right) => left.name.localeCompare(right.name));
    els.category.innerHTML = '<option value="">All categories</option>' + unique.map((category) =>
      `<option value="${esc(category.code)}">${esc(category.name)} · ${esc(category.count)}</option>`,
    ).join("");
  }

  async function loadSectors() {
    try {
      const payload = await api("/v1/sectors?language=en");
      state.sectors = payload.items || [];
      els.sector.insertAdjacentHTML("beforeend", state.sectors.map((sector) =>
        `<option value="${esc(sector.code)}">${esc(sector.name)} · ${esc(sector.count)}</option>`,
      ).join(""));
      els.sectorSummary.textContent = `${state.sectors.length} sectors · registry ${payload.registry_version || "unknown"}`;
      renderCategories();
    } catch (error) {
      els.sectorSummary.textContent = `Sector registry unavailable · ${error.message}`;
    }
  }

  async function checkHealth() {
    try {
      await api("/health");
      els.health.textContent = "Connected";
    } catch (_) {
      els.health.textContent = "Unavailable";
      els.health.closest(".system-health")?.classList.add("offline");
    }
  }

  let debounceTimer;
  els.form.addEventListener("submit", (event) => event.preventDefault());
  els.query.addEventListener("input", () => {
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(() => search(), 260);
  });
  els.source.addEventListener("change", () => search());
  els.sector.addEventListener("change", () => {
    renderCategories();
    search();
  });
  els.category.addEventListener("change", () => search());
  els.scope.addEventListener("change", () => search());
  els.reset.addEventListener("click", () => {
    els.form.reset();
    search();
    els.query.focus();
  });
  els.more.addEventListener("click", () => search({ append: true }));
  els.yearBreakdown.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-year]");
    if (!button || button.dataset.year === state.yearFilter) return;
    state.yearFilter = button.dataset.year || "";
    state.selectedKey = null;
    state.selectedFactor = null;
    els.copy.hidden = true;
    applyYearFilter();
    renderResults();
    if (state.items.length) {
      selectFactor(state.items[0]);
    } else {
      els.detail.innerHTML = emptyState("No factor in this year", "Select another year from the filter above.");
    }
  });
  els.list.addEventListener("click", (event) => {
    const button = event.target.closest(".catalog-factor");
    if (!button) return;
    const item = state.items.find((factor) => factorKey(factor) === button.dataset.key);
    if (item) selectFactor(item);
  });
  els.copy.addEventListener("click", async () => {
    if (!state.selectedFactor) return;
    await navigator.clipboard.writeText(state.selectedFactor.factor_id);
    toast("Factor ID copied");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      els.query.focus();
    }
  });

  els.detail.innerHTML = emptyState("Select a published record", "The complete factor, methodology, source definition, provenance and version history will appear here.");
  Promise.allSettled([checkHealth(), loadSources(), loadSectors()]).then(() => search());
})();
