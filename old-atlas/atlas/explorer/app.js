let FACILITIES = {};

const state = {
  facilityId: "FAC-001",
  countryOverride: null,
  context: "corporate_carbon",
  profile: "corporate_carbon.ghg_protocol.scope2_location",
  profiles: [],
  scope3Categories: [],
  scope3Category: null,
  scope3Haul: "",
  scope3WasteMaterial: "",
  scope3WasteTreatment: "",
  inputUnits: [],
  policyVersion: "—",
  debug: false,
  loading: false,
  items: [],
  selected: null,
  compatibility: null,
  calculation: null,
  conversionUnit: null,
  conversionParameterValue: "",
  conversionParameterUnit: "",
  detailError: null,
  searched: false,
  queryMeta: null,
};

const LAB_LANGUAGES = [
  { code: "en", label: "English", value: "Natural gas" },
  { code: "tr", label: "Türkçe", value: "Doğal gaz" },
  { code: "de", label: "Deutsch", value: "Erdgas" },
  { code: "fr", label: "Français", value: "Gaz naturel" },
  { code: "es", label: "Español", value: "Gas natural" },
  { code: "ru", label: "Русский", value: "Природный газ" },
  { code: "ar", label: "العربية", value: "الغاز الطبيعي" },
];

const LAB_CASES = [
  { id: "GAS-TR-L", name: "Gasoline · Türkiye · litre", text: "Benzin", language: "tr", quantity: 100, unit: "l", country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope1", concept: "energy.gasoline", source: "GHG_PROTOCOL", referenceYear: null, result: 230.2689453709515 },
  { id: "NG-TR", name: "Natural gas · Türkiye", text: "Natural gas", language: "en", quantity: 100, unit: "m3", country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope1", concept: "energy.natural_gas", source: "GHG_PROTOCOL" },
  { id: "NG-TR-TR", name: "Doğal gaz · Türkçe", text: "Doğal gaz", language: "tr", quantity: 100, unit: "m3", country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope1", concept: "energy.natural_gas", source: "GHG_PROTOCOL" },
  { id: "NG-TR-DE", name: "Erdgas · Deutsch", text: "Erdgas", language: "de", quantity: 100, unit: "m3", country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope1", concept: "energy.natural_gas", source: "GHG_PROTOCOL" },
  { id: "NG-TR-FR", name: "Gaz naturel · Français", text: "Gaz naturel", language: "fr", quantity: 100, unit: "m3", country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope1", concept: "energy.natural_gas", source: "GHG_PROTOCOL" },
  { id: "EL-TR-KWH", name: "Grid electricity · Türkiye · 2022", text: "Electricity", language: "en", quantity: 100, unit: "kWh", year: 2022, country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope2_location", concept: "energy.electricity", source: "ETKB", exactGeography: true, referenceYear: 2022, result: 47.8 },
  { id: "EL-TR-MWH", name: "Electricity · closest year · 2025", text: "Electricity", language: "en", quantity: 0.1, unit: "MWh", year: 2025, country: "TR", region: "İzmir", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope2_location", concept: "energy.electricity", source: "ETKB", exactGeography: true, referenceYear: 2023, result: 46.9 },
  { id: "EL-US", name: "Electricity · United States", text: "Electricity", language: "en", quantity: 100, unit: "kWh", country: "US", region: "Texas", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope2_location", concept: "energy.electricity" },
  { id: "NG-DE", name: "Natural gas · Germany", text: "Natural gas", language: "en", quantity: 1, unit: "GJ", country: "DE", region: "North Rhine-Westphalia", context: "corporate_carbon", profile: "corporate_carbon.ghg_protocol.scope1", concept: "energy.natural_gas" },
];

const labState = {
  running: false,
  pipeline: [],
  request: null,
  response: null,
  concept: null,
  compatibility: null,
  suiteResults: [],
  languageResults: [],
  coverage: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value) => String(value ?? "—").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));
const titleCase = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
const compactNumber = (value, maximumFractionDigits = 4) => Number(value).toLocaleString("en-US", { maximumFractionDigits });
const facility = () => FACILITIES[state.facilityId];
const countryCode = () => state.countryOverride || facility()?.code || "TR";
const activeProfile = () => state.profile || state.profiles[0]?.code || "";
const isScope3Profile = () => activeProfile().includes(".scope3");
const scope3CategoryDefinition = () =>
  state.scope3Categories.find((item) => item.code === state.scope3Category);
const scope3Qualifiers = () => {
  if (state.scope3Category === 6) {
    return state.scope3Haul ? { haul: state.scope3Haul } : {};
  }
  if ([5, 12].includes(state.scope3Category)) {
    return {
      ...(state.scope3WasteMaterial ? { material: state.scope3WasteMaterial } : {}),
      ...(state.scope3WasteTreatment ? { treatment: state.scope3WasteTreatment } : {}),
    };
  }
  return {};
};
const factorUnit = (factor) => factor?.factor_unit || "—";
const factorGeo = (factor) => factor?.origin_geography?.code || factor?.geography_code || "—";
const sourceName = (factor) => {
  const source = factor?.source_code || factor?.source_name || "Unknown source";
  const original = factor?.methodology?.details?.original_source || "";
  return source === "GHG_PROTOCOL" && original.toLowerCase().includes("ipcc")
    ? `${source} · IPCC-derived`
    : source;
};
const factorYear = (factor) => factor?.reference_year == null
  ? "UNDATED"
  : String(factor.reference_year);

const UNIT_GROUP_ORDER = [
  "energy",
  "volume",
  "mass",
  "distance",
  "passenger_count",
  "passenger_distance",
  "vehicle_distance",
  "transport_work",
  "container_distance",
  "volume_distance",
  "area",
  "area_time",
  "time",
  "count",
  "service",
  "person_time",
  "animal_time",
  "product",
  "product_mass",
  "fuel_consumption_rate",
  "currency",
  "dimensionless",
  "emission_mass",
];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.detail?.message;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove("visible"), 2600);
}

function jsonText(value) {
  return JSON.stringify(value, null, 2);
}

function labRecommendationBody(overrides = {}) {
  const input = currentInput();
  return {
    mode: "suggest",
    context: overrides.context || state.context,
    calculation_profile: overrides.profile || activeProfile(),
    language: overrides.language || null,
    year: overrides.year ?? Number($("#year").value),
    limit: 10,
    facility_context: {
      facility_id: overrides.facilityId || state.facilityId,
      country: overrides.country || countryCode(),
      region: overrides.region || facility().region,
    },
    activity: {
      text: overrides.text || input.query,
      quantity: overrides.quantity ?? input.quantity,
      unit: overrides.unit || input.unit,
      scope3_category: overrides.scope3Category ?? input.scope3Category ?? undefined,
      qualifiers: overrides.qualifiers || input.scope3Qualifiers,
    },
  };
}

function labStage(name, status, summary, details = null) {
  return { name, status, summary, details };
}

function buildLabPipeline(concept, response, compatibility) {
  const candidate = response.recommended;
  const factor = candidate?.factor;
  const gates = (response.trace || []).find((entry) => entry.stage === "candidate_gates")?.details || {};
  const conversion = candidate?.conversion;
  const calculation = response.calculation;
  const conceptCandidate = concept?.candidates?.[0];
  return [
    labStage("Language", concept?.detected_language ? "pass" : "warning", concept?.detected_language ? `${concept.detected_language.toUpperCase()} · ${concept.script}` : "Language not resolved", { normalized_query: concept?.normalized_query, tokens: concept?.tokens }),
    labStage("Canonical concept", conceptCandidate ? "pass" : "fail", conceptCandidate ? `${conceptCandidate.concept_code} · ${conceptCandidate.score}%` : "No approved concept matched", conceptCandidate),
    labStage("Context & profile", response.intent ? "pass" : "fail", response.intent ? `${response.intent.scope_category} · ${response.intent.scope3_category ? `category ${response.intent.scope3_category} · ` : ""}${response.intent.calculation_role}` : "Intent could not be built", response.intent),
    labStage("Candidate gates", Number(gates.eligible || 0) > 0 ? "pass" : "fail", `${gates.eligible || 0} eligible · ${Object.values(gates.rejected || {}).reduce((sum, count) => sum + Number(count), 0)} rejected`, gates.rejected),
    labStage("Geography", candidate?.geography?.fallback_used ? "warning" : candidate?.geography?.eligible ? "pass" : "fail", candidate ? `${candidate.geography.factor_geography} · ${candidate.geography.geographic_fit}` : "No geography decision", candidate?.geography),
    labStage("Unit path", conversion?.status === "conditional_conversion" ? "warning" : conversion?.status === "incompatible" || !conversion ? "fail" : "pass", conversion ? `${conversion.from_expression} → ${conversion.to_expression} · ${conversion.status}` : "No valid unit path", { ...conversion, supported: compatibility }),
    labStage("Factor selection", factor ? "pass" : "fail", factor ? `${factor.source_code} · ${factor.name}` : "No applicable factor", candidate?.rank),
    labStage("Calculation", calculation ? "pass" : response.status === "conversion_parameter_required" ? "warning" : "fail", calculation ? `${calculation.result_value} ${calculation.result_unit}` : response.status.replaceAll("_", " "), calculation || response.questions),
  ];
}

function renderLabPipeline() {
  const pipeline = $("#lab-pipeline");
  const outcome = $("#lab-outcome");
  if (labState.running) {
    pipeline.innerHTML = loadingState();
    outcome.innerHTML = `<div class="lab-verdict running"><span>Probe running</span><strong>Atlas is evaluating the live contract…</strong></div>`;
    return;
  }
  if (!labState.pipeline.length) {
    pipeline.innerHTML = emptyState("Ready for a live probe", "Run the current Explorer scenario to inspect every decision stage.");
    outcome.innerHTML = emptyState("No outcome yet", "The selected factor, fallback class, conversion and result will appear here.");
    return;
  }
  pipeline.innerHTML = labState.pipeline.map((item, index) => `
    <article class="pipeline-stage ${esc(item.status)}">
      <span class="pipeline-number">${String(index + 1).padStart(2, "0")}</span>
      <i></i>
      <div><span>${esc(item.name)}</span><strong>${esc(item.summary)}</strong></div>
      <b>${esc(item.status)}</b>
      ${item.details ? `<details><summary>Inspect stage data</summary><pre>${esc(jsonText(item.details))}</pre></details>` : ""}
    </article>`).join("");

  const response = labState.response || {};
  const selected = response.recommended || {};
  const factor = selected.factor || {};
  const calculation = response.calculation;
  const failed = labState.pipeline.some((item) => item.status === "fail");
  const warned = labState.pipeline.some((item) => item.status === "warning");
  outcome.innerHTML = `
    <div class="lab-verdict ${failed ? "fail" : warned ? "warning" : "pass"}">
      <span>${failed ? "Decision blocked" : warned ? "Decision needs attention" : "Calculation ready"}</span>
      <strong>${esc(response.status || "unknown")}</strong>
      <small>Policy ${esc(response.policy_version || "—")} · ${esc(selected.rank?.grade || "—")} / ${esc(selected.rank?.tier || "unranked")}</small>
    </div>
    ${factor.factor_id ? `<article class="lab-factor-card">
      <span>${esc(factor.source_code)} · ${esc(factorYear(factor))}</span>
      <h3>${esc(factor.name)}</h3>
      <strong>${compactNumber(factor.factor_value, 8)} <small>${esc(factor.factor_unit)}</small></strong>
      <dl>
        <div><dt>Concept</dt><dd>${esc(response.intent?.concept_code)}</dd></div>
        <div><dt>Geography</dt><dd>${esc(selected.geography?.factor_geography)} · ${esc(selected.geography?.geographic_fit)}</dd></div>
        <div><dt>Conversion</dt><dd>${esc(selected.conversion?.status)}</dd></div>
        <div><dt>Result</dt><dd>${calculation ? `${compactNumber(calculation.result_value, 8)} ${esc(calculation.result_unit)}` : "Pending input"}</dd></div>
      </dl>
    </article>` : emptyState("No factor selected", "Inspect the failed pipeline stage for the exact reason.")}`;
  $("#lab-raw-request").textContent = jsonText(labState.request);
  $("#lab-raw-response").textContent = jsonText(labState.response);
}

async function runLabCurrent() {
  const input = currentInput();
  if (!input.query || !input.unit || !(input.quantity > 0)) {
    toast("Enter text, quantity and unit in Explorer first");
    return;
  }
  labState.running = true;
  labState.pipeline = [];
  labState.request = labRecommendationBody();
  labState.response = null;
  renderLabPipeline();
  try {
    const [concept, response] = await Promise.all([
      api("/v1/concepts/resolve", { method: "POST", body: JSON.stringify({ text: input.query, limit: 5 }) }),
      api("/v1/recommendations", { method: "POST", body: JSON.stringify(labState.request) }),
    ]);
    let compatibility = null;
    if (response.recommended?.factor?.factor_id) {
      compatibility = await api("/v1/explorer/compatibility", {
        method: "POST",
        body: JSON.stringify({ factor_id: response.recommended.factor.factor_id }),
      });
    }
    labState.concept = concept;
    labState.response = response;
    labState.compatibility = compatibility;
    labState.pipeline = buildLabPipeline(concept, response, compatibility);
  } catch (error) {
    labState.pipeline = [labStage("API contract", "fail", error.message)];
    labState.response = { error: error.message };
  } finally {
    labState.running = false;
    renderLabPipeline();
  }
}

function renderLabScenario() {
  const input = currentInput();
  $("#lab-current-scenario").textContent = `${input.query || "—"} · ${input.quantity || "—"} ${input.unit || "—"} · ${countryCode()} · ${activeProfile().replaceAll(".", " / ")}`;
}

function renderSuite() {
  const results = labState.suiteResults;
  const passed = results.filter((item) => item.status === "pass").length;
  const failed = results.filter((item) => item.status === "fail").length;
  const pending = LAB_CASES.length - results.length;
  $("#lab-suite-summary").innerHTML = `
    <article><span>Total cases</span><strong>${LAB_CASES.length}</strong></article>
    <article class="pass"><span>Passed</span><strong>${passed}</strong></article>
    <article class="fail"><span>Failed</span><strong>${failed}</strong></article>
    <article><span>Pending</span><strong>${pending}</strong></article>`;
  $("#lab-suite-results").innerHTML = LAB_CASES.map((testCase) => {
    const result = results.find((item) => item.id === testCase.id);
    return `<tr class="${esc(result?.status || "pending")}">
      <td><span>${esc(testCase.id)}</span><strong>${esc(testCase.name)}</strong></td>
      <td>${esc(testCase.quantity)} ${esc(testCase.unit)} · ${esc(testCase.country)} · ${esc(testCase.year || $("#year").value)} · ${esc(testCase.profile.split(".").at(-1))}</td>
      <td>${esc(testCase.concept)}${testCase.source ? ` · ${esc(testCase.source)}` : ""}</td>
      <td>${result ? `${esc(result.concept || "unresolved")} · ${esc(result.source || result.error || "no factor")}` : "—"}</td>
      <td><span class="suite-status">${esc(result?.status || "pending")}</span></td>
    </tr>`;
  }).join("");
}

async function executeLabCase(testCase) {
  try {
    const body = labRecommendationBody(testCase);
    body.facility_context.facility_id = `LAB-${testCase.country}`;
    const [concept, response] = await Promise.all([
      api("/v1/concepts/resolve", { method: "POST", body: JSON.stringify({ text: testCase.text, language: testCase.language, limit: 3 }) }),
      api("/v1/recommendations", { method: "POST", body: JSON.stringify(body) }),
    ]);
    const observedConcept = response.intent?.concept_code || concept.candidates?.[0]?.concept_code;
    const observedSource = response.recommended?.factor?.source_code;
    const observedResult = Number(response.calculation?.result_value);
    const checks = [
      observedConcept === testCase.concept,
      response.status !== "no_applicable_factor",
      !testCase.source || observedSource === testCase.source,
      testCase.exactGeography == null || response.recommended?.geography?.exact_geography === testCase.exactGeography,
      !Object.hasOwn(testCase, "referenceYear") || response.recommended?.factor?.reference_year === testCase.referenceYear,
      testCase.result == null || Math.abs(observedResult - testCase.result) < 0.000001,
    ];
    return { id: testCase.id, status: checks.every(Boolean) ? "pass" : "fail", concept: observedConcept, source: observedSource, response };
  } catch (error) {
    return { id: testCase.id, status: "fail", error: error.message };
  }
}

async function runLabSuite() {
  labState.suiteResults = [];
  renderSuite();
  const button = $("#lab-run-suite");
  button.disabled = true;
  button.textContent = "Running live cases…";
  for (const testCase of LAB_CASES) {
    labState.suiteResults.push(await executeLabCase(testCase));
    renderSuite();
  }
  button.disabled = false;
  button.textContent = "Run all cases ↗";
}

function renderLanguageMatrix() {
  $("#lab-language-grid").innerHTML = LAB_LANGUAGES.map((language) => {
    const result = labState.languageResults.find((item) => item.language === language.code);
    return `<article class="language-probe ${esc(result?.status || "pending")}">
      <header><span>${esc(language.code)}</span><strong>${esc(language.label)}</strong><b>${esc(result?.status || "ready")}</b></header>
      <input data-language-input="${esc(language.code)}" value="${esc(language.value)}" dir="${language.code === "ar" ? "rtl" : "auto"}" />
      <dl>
        <div><dt>Detected</dt><dd>${esc(result?.detected || "—")}</dd></div>
        <div><dt>Resolved</dt><dd>${esc(result?.concept || "—")}</dd></div>
        <div><dt>Confidence</dt><dd>${result?.score != null ? `${esc(result.score)}%` : "—"}</dd></div>
      </dl>
    </article>`;
  }).join("");
}

async function runLanguageMatrix() {
  const target = $("#lab-language-target").value.trim();
  labState.languageResults = await Promise.all(LAB_LANGUAGES.map(async (language) => {
    const text = $(`[data-language-input="${language.code}"]`).value.trim();
    language.value = text;
    try {
      const response = await api("/v1/concepts/resolve", { method: "POST", body: JSON.stringify({ text, language: language.code, limit: 3 }) });
      const candidate = response.candidates?.[0];
      return { language: language.code, detected: response.detected_language, concept: candidate?.concept_code, score: candidate?.score, status: candidate?.concept_code === target ? "pass" : "fail" };
    } catch (error) {
      return { language: language.code, status: "fail", error: error.message };
    }
  }));
  renderLanguageMatrix();
}

function renderCoverage() {
  const coverage = labState.coverage;
  if (!coverage) {
    $("#lab-coverage-gates").innerHTML = emptyState("Coverage is protected", "Enter the local admin key to load live intelligence readiness.");
    $("#lab-coverage-metrics").innerHTML = "";
    return;
  }
  $("#lab-coverage-gates").innerHTML = Object.entries(coverage.gates || {}).map(([name, ready]) => `
    <article class="coverage-gate ${ready ? "pass" : "warning"}"><i></i><div><span>${esc(name.replaceAll("_", " "))}</span><strong>${ready ? "Ready" : "Needs review"}</strong></div></article>`).join("");
  const semantics = coverage.semantics || {};
  $("#lab-coverage-metrics").innerHTML = `
    <div class="coverage-totals">
      <article><span>Published factors</span><strong>${compactNumber(semantics.factors_total, 0)}</strong><small>${compactNumber(semantics.factors_with_approved_concept, 0)} concept-linked</small></article>
      <article><span>Canonical concepts</span><strong>${compactNumber(semantics.concepts_total, 0)}</strong><small>English is the semantic source</small></article>
      <article><span>Unit expressions</span><strong>${compactNumber(coverage.units?.inventory_total, 0)}</strong><small>${compactNumber(coverage.units?.classified_total, 0)} classified</small></article>
    </div>
    <div class="coverage-language-grid">${Object.entries(semantics.languages || {}).map(([language, counts]) => {
      const total = Number(counts.approved) + Number(counts.draft) + Number(counts.missing);
      const approved = total ? Math.round(Number(counts.approved) / total * 100) : 0;
      return `<article><header><strong>${esc(language.toUpperCase())}</strong><span>${approved}% runtime approved</span></header><div class="coverage-bar"><i style="width:${approved}%"></i></div><dl><div><dt>Approved</dt><dd>${esc(counts.approved)}</dd></div><div><dt>Draft</dt><dd>${esc(counts.draft)}</dd></div><div><dt>Missing</dt><dd>${esc(counts.missing)}</dd></div></dl></article>`;
    }).join("")}</div>`;
}

async function loadLabCoverage() {
  const key = $("#lab-admin-key").value;
  sessionStorage.setItem("atlas-admin-key", key);
  try {
    labState.coverage = await api("/v1/admin/intelligence/coverage", { headers: { "X-Atlas-Admin-Key": key } });
    renderCoverage();
  } catch (error) {
    toast(`Coverage unavailable: ${error.message}`);
  }
}

function selectLabTab(name) {
  $$('[data-lab-tab]').forEach((button) => button.classList.toggle("active", button.dataset.labTab === name));
  $$('[data-lab-panel]').forEach((panel) => panel.classList.toggle("active", panel.dataset.labPanel === name));
}

function openTestLab() {
  renderLabScenario();
  renderLabPipeline();
  renderSuite();
  renderLanguageMatrix();
  renderCoverage();
  $("#lab-admin-key").value = sessionStorage.getItem("atlas-admin-key") || "";
  $("#test-lab-dialog").showModal();
}

const terminologyHeaders = () => ({
  "X-Atlas-Admin-Key": $("#terminology-admin-key")?.value || "",
});

async function loadTerminology() {
  const language = $("#terminology-language").value;
  sessionStorage.setItem("atlas-admin-key", $("#terminology-admin-key").value);
  try {
    const [reviews, jobs, glossary] = await Promise.all([
      api(`/v1/admin/translations?review_status=draft&language=${language}&limit=250`, { headers: terminologyHeaders() }),
      api("/v1/admin/translation-jobs?limit=30", { headers: terminologyHeaders() }),
      api(`/v1/admin/translation-glossary?language=${language}`, { headers: terminologyHeaders() }),
    ]);
    renderTerminologyReviews(reviews.items || []);
    renderTerminologyJobs(jobs.items || []);
    renderTerminologyGlossary(glossary.items || []);
  } catch (error) {
    toast(`Terminology unavailable: ${error.message}`);
  }
}

function renderTerminologyReviews(items) {
  $("#terminology-reviews").innerHTML = items.length ? items.map((item) => `
    <article class="term-card">
      <header><span>${esc(item.concept_code)}</span><span>${esc(item.kind)} · ${esc(item.model)}</span></header>
      <input class="term-edit-label" data-term-label="${esc(item.label_id)}" value="${esc(item.label)}" />
      <textarea class="term-edit-definition" data-term-definition="${esc(item.label_id)}">${esc(item.definition || "")}</textarea>
      <p>English source: ${esc(item.canonical_name_en)}</p>
      ${(item.qa_flags || []).length ? `<div class="term-flags">${esc(item.qa_flags.join(" · "))}</div>` : ""}
      <footer>
        <button data-edit-label-id="${esc(item.label_id)}">Save edit</button>
        <button class="approve" data-label-id="${esc(item.label_id)}" data-decision="approved">Approve</button>
        <button class="reject" data-label-id="${esc(item.label_id)}" data-decision="rejected">Reject</button>
      </footer>
    </article>`).join("") : emptyState("No review drafts", "Create or sync an OpenAI batch for this language.");
  $$("[data-label-id]", $("#terminology-reviews")).forEach((button) => {
    button.addEventListener("click", () => decideTerm(button.dataset.labelId, button.dataset.decision));
  });
  $$("[data-edit-label-id]", $("#terminology-reviews")).forEach((button) => {
    button.addEventListener("click", () => editTerm(button.dataset.editLabelId));
  });
}

function renderTerminologyJobs(items) {
  $("#terminology-jobs").innerHTML = items.length ? items.map((item) => `
    <article class="term-card">
      <header><span>${esc(item.target_language)} · ${esc(item.model)}</span><span>${esc(item.status)}</span></header>
      <p>${esc(item.completed_count)} / ${esc(item.requested_count)} completed · ${esc(item.failed_count)} failed</p>
      <footer><button class="sync" data-job-id="${esc(item.job_id)}">Sync</button></footer>
    </article>`).join("") : `<p class="term-flags">No OpenAI terminology jobs yet.</p>`;
  $$("[data-job-id]", $("#terminology-jobs")).forEach((button) => {
    button.addEventListener("click", () => syncTranslationJob(button.dataset.jobId));
  });
}

function renderTerminologyGlossary(items) {
  $("#terminology-glossary").innerHTML = items.map((item) => `
    <article class="term-card"><header><span>${esc(item.source_term)}</span><span>${item.protected ? "protected" : "translated"}</span></header><p>${esc(item.target_term || "Preserve source form")}</p></article>
  `).join("");
}

async function decideTerm(labelId, decision) {
  try {
    await api(`/v1/admin/translations/${labelId}/${decision}`, {
      method: "POST",
      headers: terminologyHeaders(),
      body: JSON.stringify({ decided_by: "explorer-reviewer", note: "Reviewed in Atlas Explorer" }),
    });
    toast(`Term ${decision}`);
    await loadTerminology();
  } catch (error) { toast(error.message); }
}

async function editTerm(labelId) {
  try {
    await api(`/v1/admin/translations/${labelId}`, {
      method: "PATCH",
      headers: terminologyHeaders(),
      body: JSON.stringify({
        label: $(`[data-term-label="${labelId}"]`).value.trim(),
        definition: $(`[data-term-definition="${labelId}"]`).value.trim() || null,
      }),
    });
    toast("Draft updated");
    await loadTerminology();
  } catch (error) { toast(error.message); }
}

async function createTranslationJob() {
  try {
    const result = await api("/v1/admin/translation-jobs", {
      method: "POST",
      headers: terminologyHeaders(),
      body: JSON.stringify({
        target_language: $("#terminology-language").value,
        requested_by: "explorer-reviewer",
        only_missing: true,
        batch_size: 50,
        execution_mode: "responses",
      }),
    });
    toast(`${result.batch_count} OpenAI groups completed · ${result.requested_count} concepts`);
    await loadTerminology();
  } catch (error) { toast(error.message); }
}

async function syncTranslationJob(jobId) {
  try {
    const result = await api(`/v1/admin/translation-jobs/${jobId}/sync`, { method: "POST", headers: terminologyHeaders() });
    toast(`Batch status: ${result.status}`);
    await loadTerminology();
  } catch (error) { toast(error.message); }
}

async function saveGlossary(event) {
  event.preventDefault();
  try {
    await api("/v1/admin/translation-glossary", {
      method: "POST",
      headers: terminologyHeaders(),
      body: JSON.stringify({
        source_term: $("#glossary-source").value.trim(),
        target_language: $("#terminology-language").value,
        target_term: $("#glossary-target").value.trim() || null,
        protected: $("#glossary-protected").checked,
        domain: "environmental",
        version: "1.0.0",
      }),
    });
    event.target.reset();
    await loadTerminology();
  } catch (error) { toast(error.message); }
}

function currentInput() {
  return {
    query: $("#search-query").value.trim(),
    quantity: Number($("#search-quantity").value),
    unit: $("#search-unit").value,
    scope3Category: isScope3Profile() ? state.scope3Category : null,
    scope3Qualifiers: isScope3Profile() ? scope3Qualifiers() : {},
  };
}

function updateContextSummary() {
  $("#request-geography").textContent = countryCode();
  $("#request-context").textContent = titleCase(state.context);
  $("#request-year").textContent = $("#year").value;
  $("#request-scope3-row").classList.toggle("is-hidden", !isScope3Profile());
  const category = scope3CategoryDefinition();
  $("#request-scope3-category").textContent = category
    ? `${category.code} · ${category.name}`
    : "Required";
}

function emptyState(title, copy, variant = "") {
  return `<div class="empty-state ${variant}">
    <div class="empty-glyph" aria-hidden="true"><i></i><i></i><i></i></div>
    <h3>${esc(title)}</h3>
    <p>${esc(copy)}</p>
  </div>`;
}

function loadingState() {
  return `<div class="loading-state">
    <span class="scanner"></span>
    <p>Atlas is resolving concept, context and geography…</p>
    <i></i><i></i><i></i>
  </div>`;
}

function visibleItems() {
  if (state.debug) return state.items;
  return state.items.filter((item) => item.eligibility?.calculation_eligible !== false);
}

function conversionOptions() {
  const compatibility = state.compatibility || {};
  const direct = (compatibility.direct || []).map((unit) => ({ unit, mode: "direct", parameter: null }));
  const parameterized = (compatibility.parameterized || []).map((entry) => ({ ...entry, mode: "parameterized" }));
  return [...direct, ...parameterized].sort((left, right) => {
    if (left.unit === compatibility.native_activity_unit) return -1;
    if (right.unit === compatibility.native_activity_unit) return 1;
    if (left.mode !== right.mode) return left.mode === "direct" ? -1 : 1;
    return left.unit.localeCompare(right.unit);
  });
}

function selectedConversion() {
  return conversionOptions().find((entry) => entry.unit === state.conversionUnit) || null;
}

function conversionParameters() {
  const conversion = selectedConversion();
  const value = Number(state.conversionParameterValue);
  const unit = state.conversionParameterUnit.trim()
    || `${state.selected?.factor?.activity_unit}/${state.conversionUnit}`;
  if (conversion?.mode !== "parameterized" || !(value > 0) || !unit) return [];
  return [{
    name: conversion.parameter,
    value,
    unit,
    source: "manual",
  }];
}

function renderResults() {
  const container = $("#results-list");
  const items = visibleItems();
  const eligibleCount = items.filter((item) => item.eligibility?.calculation_eligible !== false).length;
  $("#result-count").textContent = state.loading
    ? "…"
    : state.searched
      ? state.debug ? `${eligibleCount}/${items.length}` : String(items.length).padStart(2, "0")
      : "—";
  $("#result-count").title = state.debug ? `${eligibleCount} eligible · ${items.length - eligibleCount} rejected` : `${items.length} eligible`;

  if (state.loading) {
    container.innerHTML = loadingState();
    return;
  }
  if (!state.searched) {
    container.innerHTML = emptyState("Awaiting a search", "Your ranked, context-eligible factors will appear here.");
    return;
  }
  if (!items.length) {
    container.innerHTML = emptyState(
      "No eligible factor",
      `No factor matched ${titleCase(state.context)} / ${activeProfile().replaceAll(".", " · ")} for ${countryCode()}.`,
      "warning",
    );
    return;
  }

  container.innerHTML = items.map((item, index) => {
    const factor = item.factor || {};
    const eligibility = item.eligibility || {};
    const coverage = item.geographic_coverage || {};
    const selected = state.selected?.factor?.factor_id === factor.factor_id;
    const rejected = eligibility.calculation_eligible === false;
    const parameterRequired = (item.reason_codes || []).includes("unit_parameter_required");
    const geoLabel = coverage.fallback_used
      ? `${coverage.factor_geography || factorGeo(factor)} · fallback`
      : `${coverage.factor_geography || factorGeo(factor)} · exact`;
    return `<button class="result-item ${selected ? "selected" : ""} ${rejected ? "rejected" : ""}"
      type="button" data-result-index="${index}">
      <span class="result-rank">${String(index + 1).padStart(2, "0")}</span>
      <span class="result-main">
        <span class="result-source">${esc(sourceName(factor))} · ${esc(factorYear(factor))}</span>
        <strong>${esc(factor.name)}</strong>
        <span class="result-meta">${esc(geoLabel)} · ${esc(factor.sector?.sector_code || "unclassified")} · ${esc(factorUnit(factor))}</span>
        ${state.debug ? `<code>${esc(factor.factor_id)}</code>` : ""}
      </span>
      <span class="result-score">${esc(item.rank?.grade || "—")}<small>${esc(item.rank?.tier || "")}</small></span>
      <span class="result-arrow" aria-hidden="true">→</span>
      ${parameterRequired ? `<span class="requirement-label">Convertible · parameter required after selection</span>` : ""}
      ${rejected ? `<span class="rejected-label">${esc((eligibility.reason_codes || ["ineligible"]).join(" · "))}</span>` : ""}
    </button>`;
  }).join("");

  $$("[data-result-index]", container).forEach((button) => {
    button.addEventListener("click", () => selectResult(items[Number(button.dataset.resultIndex)]));
  });
}

function scoreRow(label, value, status = "pass") {
  return `<div class="decision-row">
    <span class="status-dot ${status}"></span>
    <div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>
  </div>`;
}

function renderFactorDetail() {
  const pane = $("#factor-detail");
  if (!state.selected) {
    pane.innerHTML = `<div class="pane-heading"><p class="section-index">03 / Selection</p><h2 id="detail-title">Factor detail</h2></div>
      ${emptyState("Select a result", "Choose a factor from the result list to inspect its value, source and methodology.")}`;
    return;
  }

  const item = state.selected;
  const factor = item.factor || {};
  const methodology = factor.methodology || {};
  const coverage = item.geographic_coverage || {};
  const eligible = item.eligibility?.calculation_eligible !== false;
  const parameterRequired = (item.reason_codes || []).includes("unit_parameter_required");
  pane.innerHTML = `
    <div class="pane-heading">
      <p class="section-index">03 / Selection</p>
      <span class="eligibility-badge ${parameterRequired ? "parameter" : eligible ? "" : "rejected"}">${parameterRequired ? "Convertible · parameter required" : eligible ? "Calculation eligible" : "Debug · rejected candidate"}</span>
    </div>
    <p class="factor-source-line">${esc(sourceName(factor))} · ${esc(factorYear(factor))}</p>
    <h2 id="detail-title">${esc(factor.name)}</h2>
    <div class="factor-value">
      <strong>${compactNumber(factor.factor_value, 8)}</strong>
      <span>${esc(factorUnit(factor))}</span>
    </div>
    <dl class="detail-list">
      <div><dt>Geography</dt><dd>${esc(factor.origin_geography?.name || factorGeo(factor))} · ${esc(coverage.geographic_fit || factor.geographic_fit_type)}</dd></div>
      <div><dt>Activity</dt><dd>${esc(factor.activity_type)} · ${esc(factor.activity_unit)}</dd></div>
      <div><dt>Sector</dt><dd>${esc(factor.sector?.sector_code || "Not classified")} · ${esc(factor.sector?.category_code || "No category")}</dd></div>
      <div><dt>Scope</dt><dd>${esc(methodology.scope || (methodology.system_boundary === "national_inventory_implied_factor" ? "Scope 1 · inferred from national inventory" : "Not declared"))}</dd></div>
      <div><dt>Boundary</dt><dd>${esc(methodology.system_boundary || "Not declared")}</dd></div>
      <div><dt>Methodology</dt><dd>${esc(methodology.methodology || "Not declared")}</dd></div>
      ${methodology.details?.original_source ? `<div><dt>Original source</dt><dd>${esc(methodology.details.original_source)}</dd></div>` : ""}
      <div><dt>Value kind</dt><dd>${esc(factor.factor_value_kind)}</dd></div>
    </dl>
    <div class="debug-block">
      <span>Factor ID</span><code>${esc(factor.factor_id)}</code>
      <span>Dataset version</span><code>${esc(factor.dataset_version_id)}</code>
      <span>Taxonomy</span><code>${esc(factor.taxonomy_code)}</code>
    </div>`;
}

function conversionLabel(calculation) {
  const conversion = calculation?.conversion || {};
  if (conversion.status === "exact_conversion") return "Exact unit";
  if (conversion.status === "direct_conversion") return "Direct conversion";
  if (calculation?.status === "conversion_parameter_required") return "Parameter required";
  return titleCase(conversion.status || calculation?.status || "Not evaluated");
}

function renderCalculation() {
  if (state.detailError) {
    return `<div class="calculation-card error"><span>Calculation unavailable</span><p>${esc(state.detailError)}</p></div>`;
  }
  if (!state.calculation) {
    return `<div class="calculation-card pending"><span>Calculation preview</span><p>Select a factor to evaluate the entered quantity and unit.</p></div>`;
  }

  const calculation = state.calculation;
  const activity = calculation.activity || {};
  const result = calculation.result;
  if (calculation.status === "conversion_parameter_required") {
    return `<div class="calculation-card warning">
      <span>Additional parameter required</span>
      <h3>${esc((calculation.required_parameters || []).join(", ") || "Conversion parameter")}</h3>
      <p>Atlas stopped the calculation because this conversion cannot continue safely without the parameter.</p>
    </div>`;
  }
  if (calculation.conversion_only && activity.normalized_value != null) {
    return `<div class="calculation-card converted">
      <span>Conversion preview</span>
      <div class="calculation-flow">
        <b>${compactNumber(activity.original_value)} ${esc(activity.original_unit)}</b>
        <i>→</i>
        <b>${compactNumber(activity.normalized_value, 8)} ${esc(activity.normalized_unit)}</b>
      </div>
      <p>Unit conversion is valid. Emission calculation remains blocked because this debug candidate is not eligible for the active profile.</p>
    </div>`;
  }
  if (!result) {
    return `<div class="calculation-card error"><span>Incompatible units</span><h3>${esc(activity.original_unit)} → ${esc(activity.normalized_unit)}</h3><p>No valid conversion path exists.</p></div>`;
  }

  return `<div class="calculation-card success">
    <span>Calculation preview</span>
    <div class="calculation-flow">
      <b>${compactNumber(activity.original_value)} ${esc(activity.original_unit)}</b>
      <i>→</i>
      <b>${compactNumber(activity.normalized_value, 8)} ${esc(activity.normalized_unit)}</b>
    </div>
    <strong class="calculation-result">${compactNumber(result.value, 8)} <small>${esc(result.unit)}</small></strong>
    <p>${esc(conversionLabel(calculation))}</p>
  </div>`;
}

function renderDecisionDetail() {
  const pane = $("#decision-detail");
  if (!state.selected) {
    pane.innerHTML = `<div class="pane-heading"><p class="section-index">04 / Decision</p><h2>Compatibility</h2></div>
      ${emptyState("No decision yet", "Atlas will explain geography, eligibility, unit conversion and calculation here.")}`;
    return;
  }

  const item = state.selected;
  const factor = item.factor || {};
  const eligibility = item.eligibility || {};
  const coverage = item.geographic_coverage || {};
  const compatibility = state.compatibility || {};
  const input = currentInput();
  const eligible = eligibility.calculation_eligible !== false;
  const options = conversionOptions();
  const conversion = selectedConversion();
  const unitStatus = state.calculation?.conversion?.status
    || (conversion?.mode === "parameterized" ? "conditional_conversion" : item.unit_conversion_status)
    || "not evaluated";
  const parameterUnit = state.conversionParameterUnit
    || conversion?.parameter_unit
    || `${factor.activity_unit}/${state.conversionUnit || input.unit}`;
  pane.innerHTML = `
    <div class="pane-heading"><p class="section-index">04 / Decision</p><h2>Compatibility</h2></div>
    ${renderCalculation()}
    <div class="conversion-control">
      <div class="conversion-heading">
        <div><span>Convert activity</span><strong>${compactNumber(input.quantity)} → ${esc(factor.activity_unit)}</strong></div>
        <span class="conversion-mode ${conversion?.mode || ""}">${esc(conversion?.mode || "loading")}</span>
      </div>
      <label class="field">
        <span>Activity unit · updates search input</span>
        <select id="conversion-unit" ${options.length ? "" : "disabled"}>
          ${options.map((entry) => `<option value="${esc(entry.unit)}" ${entry.unit === state.conversionUnit ? "selected" : ""}>${esc(entry.unit)} · ${entry.mode === "direct" ? "direct" : `requires ${entry.parameter}`}</option>`).join("")}
        </select>
      </label>
      ${conversion?.mode === "parameterized" ? `<div class="parameter-entry">
        <div class="parameter-callout"><span>Required parameter</span><strong>${esc(conversion.parameter)}</strong></div>
        <label class="field"><span>Value</span><input id="conversion-parameter-value" type="number" min="0" step="any" value="${esc(state.conversionParameterValue)}" placeholder="0.0375" /></label>
        <label class="field"><span>Parameter unit</span><input id="conversion-parameter-unit" type="text" value="${esc(parameterUnit)}" placeholder="${esc(`${factor.activity_unit}/${state.conversionUnit || input.unit}`)}" /></label>
        <small>Manual value · no default is assumed</small>
      </div>` : ""}
      <button id="convert-button" class="convert-button" type="button" ${options.length ? "" : "disabled"}>
        <span>${eligible ? "Convert & calculate" : "Preview conversion"}</span><b>→</b>
      </button>
    </div>
    <div class="decision-stack">
      ${scoreRow("Context", eligible ? activeProfile().replaceAll(".", " · ") : (eligibility.reason_codes || ["ineligible"]).join(" · "), eligible ? "pass" : "fail")}
      ${scoreRow("Geography", coverage.fallback_used ? `${coverage.factor_geography} fallback` : `${countryCode()} exact`, coverage.fallback_used ? "warning" : "pass")}
      ${scoreRow("Unit", `${state.conversionUnit || input.unit} → ${factor.activity_unit} · ${titleCase(unitStatus)}`, unitStatus === "incompatible" ? "fail" : unitStatus === "conditional_conversion" ? "warning" : "pass")}
      ${scoreRow("Ranking", `${item.rank?.grade || "—"} · ${titleCase(item.rank?.tier || "unranked")}`, "pass")}
    </div>
    <div class="debug-block">
      <span>Reason codes</span><code>${esc((item.reason_codes || []).join(", ") || "eligible")}</code>
      <span>Policy</span><code>${esc(state.policyVersion)}</code>
      <span>Resolved concept</span><code>${esc((item.concept_codes || []).join(", "))}</code>
    </div>`;
  bindDecisionControls();
}

function bindDecisionControls() {
  const unitSelect = $("#conversion-unit");
  if (!unitSelect) return;
  unitSelect.addEventListener("change", () => {
    state.conversionUnit = unitSelect.value;
    const searchUnit = $("#search-unit");
    if (![...searchUnit.options].some((option) => option.value === unitSelect.value)) {
      searchUnit.add(new Option(unitSelect.value, unitSelect.value));
    }
    searchUnit.disabled = false;
    searchUnit.value = unitSelect.value;
    state.conversionParameterValue = "";
    state.conversionParameterUnit = "";
    state.calculation = null;
    state.detailError = null;
    renderDecisionDetail();
  });
  $("#conversion-parameter-value")?.addEventListener("input", (event) => {
    state.conversionParameterValue = event.target.value;
  });
  $("#conversion-parameter-unit")?.addEventListener("input", (event) => {
    state.conversionParameterUnit = event.target.value;
  });
  $("#convert-button")?.addEventListener("click", calculateSelection);
}

function render() {
  document.body.classList.toggle("debug", state.debug);
  updateContextSummary();
  renderResults();
  renderFactorDetail();
  renderDecisionDetail();
}

async function runSearch(event) {
  event?.preventDefault();
  const input = currentInput();
  if (!input.query) return;
  if (isScope3Profile() && !input.scope3Category) {
    state.searched = false;
    state.items = [];
    state.selected = null;
    state.queryMeta = null;
    render();
    if (event) toast("Select a GHG Protocol Scope 3 category.");
    return;
  }
  const missingScope3Detail = (
    input.scope3Category === 6 && !input.scope3Qualifiers.haul
  ) || (
    [5, 12].includes(input.scope3Category)
    && (!input.scope3Qualifiers.material || !input.scope3Qualifiers.treatment)
  );
  if (missingScope3Detail) {
    state.searched = false;
    state.items = [];
    state.selected = null;
    state.queryMeta = null;
    render();
    if (event) toast("Complete the required Scope 3 activity details.");
    return;
  }
  state.loading = true;
  state.searched = true;
  state.items = [];
  state.selected = null;
  state.compatibility = null;
  state.calculation = null;
  state.conversionUnit = null;
  state.conversionParameterValue = "";
  state.conversionParameterUnit = "";
  state.detailError = null;
  render();

  const body = {
    mode: "suggest",
    context: state.context,
    calculation_profile: activeProfile(),
    year: Number($("#year").value),
    limit: 30,
    facility_context: {
      facility_id: state.facilityId,
      country: countryCode(),
      region: facility().region,
    },
    activity: {
      text: input.query,
      quantity: input.quantity,
      unit: input.unit,
      scope3_category: input.scope3Category || undefined,
      qualifiers: input.scope3Qualifiers,
    },
  };
  try {
    const data = await api("/v1/recommendations", { method: "POST", body: JSON.stringify(body) });
    const candidates = [data.recommended, ...(data.alternatives || [])].filter(Boolean);
    state.items = candidates.map((item) => ({
      ...item,
      geographic_coverage: item.geography,
      eligibility: { calculation_eligible: true, reason_codes: [] },
      unit_conversion_status: item.conversion?.status,
    }));
    state.queryMeta = data;
    state.policyVersion = data.policy_version || state.policyVersion;
    state.loading = false;
    render();
    const first = visibleItems().find((item) => item.eligibility?.calculation_eligible !== false);
    if (first) await selectResult(first, false);
  } catch (error) {
    toast(error.message);
    state.items = [];
  } finally {
    state.loading = false;
    render();
  }
}

async function calculateSelection() {
  if (!state.selected) return;
  const input = currentInput();
  const factor = state.selected.factor;
  const eligible = state.selected.eligibility?.calculation_eligible !== false;
  const fromUnit = state.conversionUnit || input.unit;
  const parameters = conversionParameters();
  state.calculation = null;
  state.detailError = null;
  if (!(input.quantity > 0)) {
    renderDecisionDetail();
    return;
  }
  try {
    if (eligible) {
      state.calculation = await api("/v1/explorer/calculate", {
        method: "POST",
        body: JSON.stringify({
          factor_id: factor.factor_id,
          quantity: input.quantity,
          unit: fromUnit,
          country: countryCode(),
          context: state.context,
          calculation_profile: activeProfile(),
          year: Number($("#year").value),
          conversion_parameters: parameters,
        }),
      });
    } else {
      const conversion = await api("/v1/convert", {
        method: "POST",
        body: JSON.stringify({
          mode: "activity",
          value: input.quantity,
          from_unit: fromUnit,
          to_unit: factor.activity_unit,
          parameters,
        }),
      });
      state.calculation = {
        status: conversion.output_value != null
          ? "converted_only"
          : conversion.required_parameters?.length ? "conversion_parameter_required" : "incompatible",
        activity: {
          original_value: input.quantity,
          original_unit: fromUnit,
          normalized_value: conversion.output_value,
          normalized_unit: factor.activity_unit,
        },
        conversion,
        required_parameters: conversion.required_parameters || [],
        result: null,
        conversion_only: conversion.output_value != null,
      };
    }
  } catch (error) {
    state.detailError = error.message;
  }
  renderDecisionDetail();
}

async function selectResult(item, rerender = true) {
  state.selected = item;
  state.compatibility = null;
  state.calculation = null;
  state.detailError = null;
  if (rerender) render();
  try {
    state.compatibility = await api("/v1/explorer/compatibility", {
      method: "POST",
      body: JSON.stringify({ factor_id: item.factor.factor_id }),
    });
    const inputUnit = currentInput().unit;
    const supported = conversionOptions();
    state.conversionUnit = supported.some((entry) => entry.unit === inputUnit)
      ? inputUnit
      : state.compatibility.native_activity_unit;
  } catch (error) {
    state.detailError = error.message;
  }
  await calculateSelection();
  render();
}

async function loadProfiles() {
  const data = await api(`/v1/contexts/${encodeURIComponent(state.context)}/profiles`);
  state.profiles = data.items || [];
  state.policyVersion = data.policy_version || "—";
  if (!state.profiles.some((item) => item.code === state.profile)) {
    state.profile = state.profiles[0]?.code || "";
  }
  $("#profile").innerHTML = state.profiles.map((item) =>
    `<option value="${esc(item.code)}">${esc(item.code.replaceAll(".", " · ").replaceAll("_", " "))}</option>`
  ).join("");
  $("#profile").value = state.profile;
  $("#policy-version").textContent = `Policy · ${state.policyVersion}`;
  syncScope3Category();
}

function loadScope3Categories(data) {
  state.scope3Categories = data.items || [];
  $("#scope3-category").innerHTML = [
    '<option value="">Select GHG Protocol category…</option>',
    ...state.scope3Categories.map((item) =>
      `<option value="${item.code}">${String(item.code).padStart(2, "0")} · ${esc(item.name)} · ${esc(item.availability)}</option>`
    ),
  ].join("");
  syncScope3Category();
}

function syncScope3Category() {
  const active = isScope3Profile();
  $("#scope3-category-field").classList.toggle("is-hidden", !active);
  $("#scope3-category").required = active;
  if (!active) state.scope3Category = null;
  $("#scope3-category").value = state.scope3Category == null
    ? ""
    : String(state.scope3Category);
  const category = scope3CategoryDefinition();
  const needsHaul = active && state.scope3Category === 6;
  const needsWaste = active && [5, 12].includes(state.scope3Category);
  $("#scope3-haul-field").classList.toggle("is-hidden", !needsHaul);
  $("#scope3-haul").required = needsHaul;
  $("#scope3-haul").value = state.scope3Haul;
  $("#scope3-waste-fields").classList.toggle("is-hidden", !needsWaste);
  $("#scope3-waste-material").required = needsWaste;
  $("#scope3-waste-treatment").required = needsWaste;
  $("#scope3-waste-material").value = state.scope3WasteMaterial;
  $("#scope3-waste-treatment").value = state.scope3WasteTreatment;
  $("#scope3-category-meta").textContent = category
    ? `${titleCase(category.direction)} · ${titleCase(category.availability)} · ${category.note}`
    : "Category is required for Scope 3 decisions.";
  updateContextSummary();
}

function loadInputUnits(data) {
  const select = $("#search-unit");
  state.inputUnits = data.items || [];
  if (!state.inputUnits.length) {
    select.innerHTML = `<option value="">Unit registry unavailable</option>`;
    select.disabled = true;
    return;
  }

  const grouped = new Map();
  state.inputUnits.forEach((item) => {
    if (!grouped.has(item.dimension)) grouped.set(item.dimension, []);
    grouped.get(item.dimension).push(item);
  });
  const dimensions = [...grouped.keys()].sort((left, right) => {
    const leftRank = UNIT_GROUP_ORDER.indexOf(left);
    const rightRank = UNIT_GROUP_ORDER.indexOf(right);
    if (leftRank === -1 && rightRank === -1) return left.localeCompare(right);
    if (leftRank === -1) return 1;
    if (rightRank === -1) return -1;
    return leftRank - rightRank;
  });

  select.disabled = false;
  select.innerHTML = dimensions.map((dimension) => {
    const options = grouped.get(dimension)
      .sort((left, right) => left.code.localeCompare(right.code))
      .map((item) => `<option value="${esc(item.code)}">${esc(item.code)}</option>`)
      .join("");
    return `<optgroup label="${esc(titleCase(dimension))}">${options}</optgroup>`;
  }).join("");
  select.value = state.inputUnits.some((item) => item.code === "kWh")
    ? "kWh"
    : state.inputUnits[0].code;
}

async function resetAndSearch() {
  state.items = [];
  state.selected = null;
  state.compatibility = null;
  state.calculation = null;
  state.conversionUnit = null;
  state.conversionParameterValue = "";
  state.conversionParameterUnit = "";
  state.searched = false;
  render();
  if ($("#search-query").value.trim()) await runSearch();
}

function updateFacilityContext() {
  const current = facility();
  $("#country").value = current.code;
  $("#country-code").textContent = `ISO · ${current.code}`;
  const connection = current.electricity_connection_level
    ? `${titleCase(current.electricity_connection_level)} connection`
    : "Connection level not set";
  $("#facility-meta").textContent = `${current.region || "Region not set"} · ${connection} · ${current.registry_version}`;
}

function bindEvents() {
  $("#search-form").addEventListener("submit", runSearch);
  $("#test-lab-open").addEventListener("click", openTestLab);
  $$('[data-lab-tab]').forEach((button) => button.addEventListener("click", () => selectLabTab(button.dataset.labTab)));
  $("#lab-run-current").addEventListener("click", runLabCurrent);
  $("#lab-run-suite").addEventListener("click", runLabSuite);
  $("#lab-run-languages").addEventListener("click", runLanguageMatrix);
  $("#lab-load-coverage").addEventListener("click", loadLabCoverage);
  $("#lab-open-terminology").addEventListener("click", async () => {
    $("#test-lab-dialog").close();
    $("#terminology-admin-key").value = $("#lab-admin-key").value;
    $("#terminology-dialog").showModal();
    await loadTerminology();
  });
  $("#debug-toggle").addEventListener("change", async (event) => {
    state.debug = event.target.checked;
    await resetAndSearch();
  });
  $("#facility").addEventListener("change", async (event) => {
    state.facilityId = event.target.value;
    state.countryOverride = null;
    updateFacilityContext();
    await resetAndSearch();
  });
  $("#country").addEventListener("change", async (event) => {
    state.countryOverride = event.target.value === facility().code ? null : event.target.value;
    $("#country-code").textContent = state.countryOverride
      ? `FACILITY OVERRIDE · ${event.target.value}`
      : `ISO · ${event.target.value}`;
    await resetAndSearch();
  });
  $("#year").addEventListener("change", resetAndSearch);
  $("#context").addEventListener("change", async (event) => {
    state.context = event.target.value;
    await loadProfiles();
    await resetAndSearch();
  });
  $("#profile").addEventListener("change", async (event) => {
    state.profile = event.target.value;
    syncScope3Category();
    await resetAndSearch();
  });
  $("#scope3-category").addEventListener("change", async (event) => {
    state.scope3Category = event.target.value ? Number(event.target.value) : null;
    syncScope3Category();
    await resetAndSearch();
  });
  $("#scope3-haul").addEventListener("change", async (event) => {
    state.scope3Haul = event.target.value;
    await resetAndSearch();
  });
  $("#scope3-waste-material").addEventListener("change", async (event) => {
    state.scope3WasteMaterial = event.target.value.trim();
    await resetAndSearch();
  });
  $("#scope3-waste-treatment").addEventListener("change", async (event) => {
    state.scope3WasteTreatment = event.target.value;
    await resetAndSearch();
  });
  $("#search-unit").addEventListener("change", resetAndSearch);
  $("#search-quantity").addEventListener("change", calculateSelection);
  $("#terminology-open").addEventListener("click", async () => {
    $("#terminology-admin-key").value = sessionStorage.getItem("atlas-admin-key") || "";
    $("#terminology-dialog").showModal();
    await loadTerminology();
  });
  $("#terminology-load").addEventListener("click", loadTerminology);
  $("#terminology-language").addEventListener("change", loadTerminology);
  $("#terminology-create-job").addEventListener("click", createTranslationJob);
  $("#glossary-form").addEventListener("submit", saveGlossary);
}

async function checkHealth() {
  const node = $(".system-health");
  try {
    await api("/health");
    node.classList.add("ready");
    $("#health-label").textContent = "Connected";
  } catch {
    node.classList.add("failed");
    $("#health-label").textContent = "Unavailable";
  }
}

async function bootstrap() {
  bindEvents();
  render();
  checkHealth();
  try {
    const [contexts, countriesResponse, units, facilitiesResponse, scope3Categories] = await Promise.all([
      api("/v1/contexts"),
      api("/v1/countries?language=en"),
      api("/v1/units"),
      api("/v1/facilities"),
      api("/v1/scope3/categories"),
    ]);
    FACILITIES = Object.fromEntries((facilitiesResponse.items || []).map((item) => [
      item.code,
      { ...item, code: item.country_code },
    ]));
    if (!FACILITIES[state.facilityId]) state.facilityId = Object.keys(FACILITIES)[0];
    $("#facility").innerHTML = Object.entries(FACILITIES).map(([id, item]) =>
      `<option value="${id}">${esc(item.name)} · ${esc(item.code)}</option>`
    ).join("");
    $("#facility").value = state.facilityId;
    const countries = (countriesResponse.items || [])
      .sort((left, right) => left.name.localeCompare(right.name));
    $("#country").innerHTML = countries.map((item) =>
      `<option value="${esc(item.code)}">${esc(item.name)} · ${esc(item.code)}</option>`
    ).join("");
    $("#country").value = countryCode();
    $("#context").innerHTML = (contexts.items || []).map((item) =>
      `<option value="${esc(item.context)}">${esc(titleCase(item.context))}</option>`
    ).join("");
    $("#context").value = state.context;
    updateFacilityContext();
    loadInputUnits(units);
    loadScope3Categories(scope3Categories);
    await loadProfiles();
    await runSearch();
  } catch (error) {
    toast(`Registry unavailable: ${error.message}`);
    render();
  }
}

bootstrap();
