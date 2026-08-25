"""Backend-served workflow UI for the PDF-first MVP."""


APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UDAP Workflow</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">UDAP</p>
        <h1>Document Accessibility Workflow</h1>
      </div>
      <div class="status-pill" id="job-status">No job loaded</div>
    </header>

    <section class="workflow-grid" aria-label="Accessibility workflow">
      <section class="panel upload-panel" aria-labelledby="upload-title">
        <div class="panel-header">
          <h2 id="upload-title">Upload</h2>
          <span class="step-index">1</span>
        </div>
        <form id="upload-form" class="stack">
          <label for="document-file">Document</label>
          <input id="document-file" name="file" type="file" accept=".pdf,.docx" required>
          <button type="submit">Analyse</button>
        </form>
        <form id="load-form" class="stack load-form">
          <label for="job-id">Existing job ID</label>
          <div class="inline-form">
            <input id="job-id" name="job_id" type="text" autocomplete="off">
            <button type="submit">Load</button>
          </div>
        </form>
      </section>

      <section class="panel assessment-panel" aria-labelledby="assessment-title">
        <div class="panel-header">
          <h2 id="assessment-title">Assessment</h2>
          <span class="step-index">2</span>
        </div>
        <div id="summary" class="summary-grid"></div>
        <div id="issues" class="issue-list"></div>
      </section>

      <section class="panel review-panel" aria-labelledby="review-title">
        <div class="panel-header">
          <h2 id="review-title">Review</h2>
          <span class="step-index">3</span>
        </div>
        <form id="review-form" class="stack">
          <div id="suggestions" class="suggestion-list"></div>
          <button type="submit" disabled id="review-submit">Apply Review</button>
        </form>
      </section>

      <section class="panel output-panel" aria-labelledby="outputs-title">
        <div class="panel-header">
          <h2 id="outputs-title">Outputs</h2>
          <span class="step-index">4</span>
        </div>
        <button id="generate-output" type="button" disabled>Generate PDF And Report</button>
        <div id="remediation-summary" class="remediation-summary"></div>
        <div id="outputs" class="output-list"></div>
      </section>
    </section>

    <section class="report-panel" aria-labelledby="report-title">
      <div class="panel-header">
        <h2 id="report-title">Report</h2>
      </div>
      <div id="report-status" class="summary-grid"></div>
      <div id="report-details" class="report-grid"></div>
    </section>

    <section class="event-panel" aria-labelledby="events-title">
      <div class="panel-header">
        <h2 id="events-title">Status</h2>
      </div>
      <div id="message" role="status" aria-live="polite">Ready.</div>
    </section>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
"""


APP_CSS = """
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --ink: #1f2933;
  --muted: #617080;
  --line: #d7dde3;
  --accent: #0f766e;
  --accent-strong: #0b5f59;
  --warn: #9a3412;
  --danger: #b42318;
  --ok: #166534;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.45;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  min-height: 40px;
  border: 0;
  border-radius: 6px;
  padding: 0 14px;
  background: var(--accent);
  color: #ffffff;
  font-weight: 700;
  cursor: pointer;
}

button:hover {
  background: var(--accent-strong);
}

button:disabled {
  background: #a8b4bf;
  cursor: not-allowed;
}

a {
  color: var(--accent-strong);
  font-weight: 700;
}

.shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 0 22px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: 30px;
  line-height: 1.15;
  letter-spacing: 0;
}

h2 {
  margin-bottom: 0;
  font-size: 18px;
  line-height: 1.25;
  letter-spacing: 0;
}

h3 {
  margin-bottom: 6px;
  font-size: 15px;
  line-height: 1.3;
  letter-spacing: 0;
}

.status-pill,
.step-index,
.tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 2px 8px;
  background: #eef3f5;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.workflow-grid {
  display: grid;
  grid-template-columns: minmax(220px, 0.75fr) minmax(300px, 1.15fr);
  gap: 14px;
}

.panel,
.event-panel,
.report-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 16px;
}

.review-panel,
.output-panel {
  min-height: 230px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.stack {
  display: grid;
  gap: 10px;
}

.load-form {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}

.inline-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

label {
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

input[type="file"],
input[type="text"],
select,
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #ffffff;
  color: var(--ink);
}

input[type="file"] {
  min-height: 42px;
  padding: 8px;
}

input[type="text"] {
  min-height: 40px;
  padding: 0 10px;
}

select {
  min-height: 38px;
  padding: 0 8px;
}

textarea {
  min-height: 74px;
  resize: vertical;
  padding: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.metric {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px;
  background: #fbfcfd;
}

.metric-value {
  display: block;
  font-size: 22px;
  font-weight: 800;
}

.metric-label {
  color: var(--muted);
  font-size: 12px;
}

.issue-list,
.suggestion-list,
.output-list,
.remediation-summary {
  display: grid;
  gap: 10px;
}

.item {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  background: #ffffff;
}

.item p {
  margin-bottom: 8px;
  color: var(--muted);
}

.item-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.item-controls {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.output-list,
.remediation-summary {
  margin-top: 12px;
}

.tag.high,
.tag.critical,
.tag.error {
  border-color: #f0b8b0;
  background: #fff1ef;
  color: var(--danger);
}

.tag.medium,
.tag.review {
  border-color: #f3c9a8;
  background: #fff7ed;
  color: var(--warn);
}

.tag.low,
.tag.ok {
  border-color: #b8d8c0;
  background: #f0fdf4;
  color: var(--ok);
}

.event-panel {
  margin-top: 14px;
}

.report-panel {
  margin-top: 14px;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.report-section {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  background: #ffffff;
}

.report-section ul {
  margin: 0;
  padding-left: 18px;
}

.report-section li {
  margin-bottom: 8px;
  color: var(--muted);
}

#message {
  color: var(--muted);
}

.empty {
  color: var(--muted);
  font-style: italic;
}

@media (max-width: 860px) {
  .topbar,
  .item-row {
    align-items: stretch;
    flex-direction: column;
  }

  .workflow-grid,
  .summary-grid,
  .report-grid {
    grid-template-columns: 1fr;
  }
}
"""


APP_JS = """
const state = {
  job: null,
};

const uploadForm = document.querySelector("#upload-form");
const loadForm = document.querySelector("#load-form");
const reviewForm = document.querySelector("#review-form");
const outputButton = document.querySelector("#generate-output");
const reviewSubmit = document.querySelector("#review-submit");
const message = document.querySelector("#message");
const jobStatus = document.querySelector("#job-status");
const summary = document.querySelector("#summary");
const issues = document.querySelector("#issues");
const suggestions = document.querySelector("#suggestions");
const outputs = document.querySelector("#outputs");
const remediationSummary = document.querySelector("#remediation-summary");
const reportStatus = document.querySelector("#report-status");
const reportDetails = document.querySelector("#report-details");

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.querySelector("#document-file").files[0];
  if (!file) return;

  setMessage("Analysing document...");
  const form = new FormData();
  form.append("file", file);

  try {
    const payload = await requestJson("/documents/analyse", {
      method: "POST",
      body: form,
    });
    setJob(payload);
    setMessage("Analysis complete.");
  } catch (error) {
    setMessage(error.message, true);
  }
});

loadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const jobId = document.querySelector("#job-id").value.trim();
  if (!jobId) return;

  setMessage("Loading job...");
  try {
    const payload = await requestJson(`/jobs/${encodeURIComponent(jobId)}`);
    setJob(payload);
    setMessage("Job loaded.");
  } catch (error) {
    setMessage(error.message, true);
  }
});

reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.job) return;

  const decisions = visibleSuggestions().map((suggestion) => {
    const decision = document.querySelector(`[name="decision-${suggestion.id}"]`).value;
    const finalValue = document.querySelector(`[name="value-${suggestion.id}"]`).value.trim();
    return {
      suggestion_id: suggestion.id,
      issue_id: suggestion.issue_id,
      decision,
      final_value: finalValue || null,
    };
  });

  setMessage("Applying review decisions...");
  try {
    const payload = await requestJson(`/jobs/${state.job.job.id}/review`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(decisions),
    });
    setJob(payload);
    setMessage("Review saved.");
  } catch (error) {
    setMessage(error.message, true);
  }
});

outputButton.addEventListener("click", async () => {
  if (!state.job) return;

  setMessage("Generating PDF and report...");
  try {
    const payload = await requestJson(`/jobs/${state.job.job.id}/outputs/pdf`, {
      method: "POST",
    });
    setJob(payload);
    setMessage("Outputs generated.");
  } catch (error) {
    setMessage(error.message, true);
  }
});

async function requestJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail);
  }
  return response.json();
}

function setJob(payload) {
  state.job = payload;
  render();
}

function render() {
  renderStatus();
  renderSummary();
  renderIssues();
  renderSuggestions();
  renderRemediationSummary();
  renderOutputs();
  renderReport();
}

function renderStatus() {
  if (!state.job) {
    jobStatus.textContent = "No job loaded";
    return;
  }
  jobStatus.textContent = `${state.job.job.status.replaceAll("_", " ")} · ${state.job.file}`;
}

function renderSummary() {
  if (!state.job) {
    summary.innerHTML = `<p class="empty">No analysis yet.</p>`;
    return;
  }

  const data = state.job.summary;
  summary.innerHTML = [
    metric(data.initial_issue_count, "Issues"),
    metric(data.suggestion_count, "Suggestions"),
    metric(Object.keys(data.issue_type_counts || {}).length, "Categories"),
  ].join("");
}

function metric(value, label) {
  return `<div class="metric"><span class="metric-value">${escapeHtml(value)}</span><span class="metric-label">${escapeHtml(label)}</span></div>`;
}

function renderIssues() {
  if (!state.job || state.job.issues.length === 0) {
    issues.innerHTML = `<p class="empty">No issues detected.</p>`;
    return;
  }

  issues.innerHTML = state.job.issues.map((issue) => `
    <article class="item">
      <div class="item-row">
        <div>
          <h3>${escapeHtml(issue.issue_type.replaceAll("_", " "))}</h3>
          <p>${escapeHtml(issue.explanation)}</p>
        </div>
        <span class="tag ${escapeHtml(issue.severity)}">${escapeHtml(issue.severity)}</span>
      </div>
      <span class="tag review">${escapeHtml(issue.automation_status.replaceAll("_", " "))}</span>
    </article>
  `).join("");
}

function renderSuggestions() {
  const visible = visibleSuggestions();
  if (!state.job || visible.length === 0) {
    suggestions.innerHTML = `<p class="empty">No suggestions awaiting review.</p>`;
    reviewSubmit.disabled = true;
    outputButton.disabled = !state.job;
    return;
  }

  reviewSubmit.disabled = false;
  outputButton.disabled = false;
  suggestions.innerHTML = visible.map((suggestion) => {
    const issue = issueById(suggestion.issue_id);
    const issueType = issue ? issue.issue_type.replaceAll("_", " ") : "issue";
    const severity = issue ? issue.severity : "review";
    return `
      <article class="item">
        <div class="item-row">
          <div>
            <h3>${escapeHtml(suggestion.action.replaceAll("_", " "))}</h3>
            <p>${escapeHtml(suggestion.explanation)}</p>
          </div>
          <span class="tag ${escapeHtml(severity)}">${escapeHtml(severity)}</span>
        </div>
        <span class="tag review">${escapeHtml(issueType)}</span>
        <div class="item-controls">
          <label for="decision-${suggestion.id}">Decision</label>
          <select id="decision-${suggestion.id}" name="decision-${suggestion.id}">
            <option value="accept">Accept</option>
            <option value="edit">Edit</option>
            <option value="reject">Reject</option>
          </select>
          <label for="value-${suggestion.id}">Final value</label>
          <textarea id="value-${suggestion.id}" name="value-${suggestion.id}">${escapeHtml(suggestion.proposed_value || "")}</textarea>
        </div>
      </article>
    `;
  }).join("");
}

function renderRemediationSummary() {
  const data = findRemediationSummary();
  if (!data) {
    remediationSummary.innerHTML = "";
    return;
  }

  remediationSummary.innerHTML = [
    metric(data.fixed_issue_count, "Fixed"),
    metric(data.remaining_issue_count, "Remaining"),
    metric(data.manual_review_count, "Manual review"),
    metric(data.rejected_issue_count, "Rejected"),
  ].join("");
}

function renderOutputs() {
  if (!state.job || state.job.output_artifacts.length === 0) {
    outputs.innerHTML = `<p class="empty">No outputs generated.</p>`;
    outputButton.disabled = !state.job;
    return;
  }

  outputButton.disabled = false;
  outputs.innerHTML = state.job.output_artifacts.map((artifact) => `
    <article class="item">
      <div class="item-row">
        <div>
          <h3>${escapeHtml(artifactLabel(artifact))}</h3>
          <p>${escapeHtml(artifact.filename)}</p>
        </div>
        <a href="/jobs/${state.job.job.id}/outputs/${artifact.id}">Download</a>
      </div>
    </article>
  `).join("");
}

function renderReport() {
  const report = findValidationReport();
  const remediation = findRemediationSummary();
  if (!report || !remediation) {
    reportStatus.innerHTML = `<p class="empty">Generate outputs to view the report.</p>`;
    reportDetails.innerHTML = "";
    return;
  }

  reportStatus.innerHTML = [
    metric(statusText(report.pdf_ua?.status), "PDF/UA"),
    metric(statusText(report.structure_plan?.status), "Structure"),
    metric(report.summary?.initial_issue_count ?? 0, "Generated issues"),
  ].join("");

  reportDetails.innerHTML = [
    reportSection("Fixed issues", remediation.fixed_issues),
    reportSection("Remaining issues", remediation.remaining_issues),
    reportSection("Manual review", remediation.manual_review_items),
    reportSection("Rejected issues", remediation.rejected_issues),
  ].join("");
}

function visibleSuggestions() {
  if (!state.job) return [];
  return state.job.suggestions.filter((suggestion) => {
    const issue = issueById(suggestion.issue_id);
    return !issue || issue.final_status === "open";
  });
}

function issueById(issueId) {
  if (!state.job) return null;
  return state.job.issues.find((issue) => issue.id === issueId) || null;
}

function findRemediationSummary() {
  const report = findValidationReport();
  return report?.remediation_summary || null;
}

function findValidationReport() {
  if (!state.job) return null;
  for (const artifact of state.job.output_artifacts || []) {
    if (artifact.type === "accessible_pdf" && artifact.validation_report) {
      return artifact.validation_report;
    }
    if (artifact.type === "accessibility_report" && artifact.validation_report?.validation_report) {
      return artifact.validation_report.validation_report;
    }
  }
  return null;
}

function artifactLabel(artifact) {
  if (artifact.type === "accessible_pdf") return "Accessible PDF";
  if (artifact.type === "accessibility_report") return "Remediation Report";
  return artifact.type.replaceAll("_", " ");
}

function reportSection(title, items) {
  const list = items && items.length
    ? `<ul>${items.map((item) => `<li><strong>${escapeHtml(item.issue_type.replaceAll("_", " "))}</strong>: ${escapeHtml(item.explanation)}</li>`).join("")}</ul>`
    : `<p class="empty">None.</p>`;
  return `<section class="report-section"><h3>${escapeHtml(title)}</h3>${list}</section>`;
}

function statusText(value) {
  return value ? value.replaceAll("_", " ") : "not run";
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.className = isError ? "tag error" : "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

render();
"""
