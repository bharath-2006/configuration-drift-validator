/**
 * app.js - Configuration Drift Validator Frontend Controller
 * Handles real-time API communication, validation triggers, live editor,
 * change reviews, rollbacks, and interactive college demonstration scenarios.
 */

const API_BASE = "";

// State
let currentSelectedEnv = "production";
let cachedDriftItems = [];
let activeFilter = "ALL";

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  await fetchEnvironments();
  await runValidation();
  await loadSelectedConfig();
  await loadChangeRequests();
  await loadAuditLogs();
  await loadVersionOptionsForRollback();
  await loadRollbackHistory();
}

// --- Navigation Tabs ---
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));

  event.currentTarget.classList.add("active");
  const targetPanel = document.getElementById(tabId);
  if (targetPanel) targetPanel.classList.add("active");

  if (tabId === "change-tab") loadChangeRequests();
  if (tabId === "audit-tab") loadAuditLogs();
  if (tabId === "rollback-tab") {
    loadVersionOptionsForRollback();
    loadRollbackHistory();
  }
}

function openConfigTab(env) {
  selectConfigEnv(env);
  const tabBtn = document.querySelectorAll(".tab-btn")[1]; // Config tab
  tabBtn.click();
}

// --- Fetch Environment Summary Cards ---
async function fetchEnvironments() {
  try {
    const res = await fetch(`${API_BASE}/api/environments`);
    const envs = await res.json();
    
    envs.forEach(env => {
      const vElem = document.getElementById(`v-${env.id.substring(0, 4) === 'deve' ? 'dev' : env.id.substring(0, 4) === 'stag' ? 'staging' : 'prod'}`);
      if (vElem) vElem.textContent = `v${env.active_version || 1}`;
    });

    // Also fetch current dev, staging, prod config for summary cards
    for (const envId of ["development", "staging", "production"]) {
      const cfgRes = await fetch(`${API_BASE}/api/configs/${envId}`);
      if (cfgRes.ok) {
        const cfg = await cfgRes.json();
        const prefix = envId === "development" ? "dev" : envId === "staging" ? "staging" : "prod";
        const dbElem = document.getElementById(`db-${prefix}`);
        const debugElem = document.getElementById(`debug-${prefix}`);
        if (dbElem && cfg.variables.DATABASE_HOST) dbElem.textContent = cfg.variables.DATABASE_HOST;
        if (debugElem && cfg.variables.DEBUG !== undefined) debugElem.textContent = cfg.variables.DEBUG;
      }
    }
  } catch (err) {
    console.error("Error fetching environments:", err);
  }
}

// --- Drift Validation Execution ---
async function runValidation() {
  const btn = document.getElementById("btn-validate");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Validating...`;

  try {
    const res = await fetch(`${API_BASE}/api/validate`, { method: "POST" });
    if (!res.ok) throw new Error("Validation request failed");
    const summary = await res.json();

    cachedDriftItems = summary.discrepancies || [];
    renderDeploymentGate(summary);
    renderMetrics(summary);
    renderDriftTable(cachedDriftItems);
    updateEnvironmentCards(summary);

    document.getElementById("last-updated").textContent = `Last scan: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.error("Validation error:", err);
    alert("Validation failed: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
      Run Drift Validation
    `;
  }
}

// --- Render Gate Banner ---
function renderDeploymentGate(summary) {
  const banner = document.getElementById("deployment-gate-banner");
  const title = document.getElementById("gate-title");
  const pill = document.getElementById("gate-pill");
  const desc = document.getElementById("gate-desc");
  const icon = document.getElementById("gate-icon");
  const gateMetric = document.getElementById("metric-gate-status");

  banner.className = "gate-banner";

  if (summary.production_deployment_allowed) {
    banner.classList.add("gate-approved");
    icon.textContent = "🛡️";
    title.textContent = "Production Deployment APPROVED";
    pill.className = "pill pill-neutral";
    pill.style.background = "rgba(16, 185, 129, 0.2)";
    pill.style.color = "#34D399";
    pill.textContent = "SAFE TO DEPLOY";
    desc.textContent = "All configurations adhere to environment policies. No critical drift detected.";
    gateMetric.textContent = "OPEN";
    gateMetric.className = "metric-num text-emerald";
  } else {
    banner.classList.add("gate-blocked");
    icon.textContent = "❌";
    title.textContent = "Production Deployment BLOCKED";
    pill.className = "pill pill-critical";
    pill.textContent = `${summary.critical_count} CRITICAL BLOCKERS`;
    desc.textContent = summary.deployment_message || "Dangerous configuration differences detected before reaching production.";
    gateMetric.textContent = "BLOCKED";
    gateMetric.className = "metric-num text-rose";
  }
}

// --- Render Metrics Ribbon ---
function renderMetrics(summary) {
  document.getElementById("metric-critical").textContent = summary.critical_count;
  document.getElementById("metric-high").textContent = summary.high_count;
  document.getElementById("metric-med").textContent = summary.medium_count + summary.low_count;
  document.getElementById("drift-count-badge").textContent = summary.total_discrepancies;
}

// --- Update Environment Status Badges ---
function updateEnvironmentCards(summary) {
  const statuses = summary.environment_status || {};
  
  ["development", "staging", "production"].forEach(env => {
    const prefix = env === "development" ? "dev" : env === "staging" ? "staging" : "prod";
    const badge = document.getElementById(`badge-${prefix}`);
    const card = document.getElementById(`card-${prefix}`);
    const status = statuses[env] || "Healthy";

    if (badge) {
      badge.textContent = status;
      badge.className = "status-badge";
      if (status === "Critical") badge.classList.add("badge-critical");
      else if (status === "Warning") badge.classList.add("badge-warning");
      else badge.classList.add("badge-healthy");
    }
  });
}

// --- Render Drift Table ---
function renderDriftTable(items) {
  const tbody = document.getElementById("drift-tbody");
  const emptyState = document.getElementById("drift-empty-state");
  const table = document.getElementById("drift-table");

  let filtered = items;
  if (activeFilter !== "ALL") {
    filtered = items.filter(it => it.severity === activeFilter);
  }

  tbody.innerHTML = "";

  if (filtered.length === 0) {
    table.style.display = "none";
    emptyState.style.display = "block";
    return;
  }

  table.style.display = "table";
  emptyState.style.display = "none";

  filtered.forEach(item => {
    const tr = document.createElement("tr");

    let pillClass = "pill-low";
    if (item.severity === "CRITICAL") pillClass = "pill-critical";
    else if (item.severity === "HIGH") pillClass = "pill-high";
    else if (item.severity === "MEDIUM") pillClass = "pill-medium";

    tr.innerHTML = `
      <td><span class="pill ${pillClass}">${item.severity}</span></td>
      <td><span class="env-tag env-tag-${item.environment === 'development' ? 'dev' : item.environment === 'staging' ? 'staging' : 'prod'}">${item.environment.toUpperCase()}</span></td>
      <td><span class="file-tag">${item.category}</span></td>
      <td><strong class="mono">${escapeHtml(item.item_key)}</strong></td>
      <td><code class="mono" style="color: #93C5FD;">${escapeHtml(item.expected_val || "None")}</code></td>
      <td><code class="mono" style="color: #F87171;">${escapeHtml(item.actual_val || "Missing")}</code></td>
      <td>
        <div style="font-size: 0.83rem; color: #E5E7EB; margin-bottom: 4px;">${escapeHtml(item.reason)}</div>
        <div style="font-size: 0.76rem; color: #34D399;"><strong>Fix:</strong> ${escapeHtml(item.recommendation)}</div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterDrift(level) {
  activeFilter = level;
  document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
  event.currentTarget.classList.add("active");
  renderDriftTable(cachedDriftItems);
}

// --- Configuration Manager ---
function selectConfigEnv(env) {
  currentSelectedEnv = env;
  document.querySelectorAll(".env-btn").forEach(b => b.classList.remove("active"));
  const btn = document.getElementById(`btn-env-${env === 'development' ? 'dev' : env === 'staging' ? 'stage' : 'prod'}`);
  if (btn) btn.classList.add("active");
  loadSelectedConfig();
}

async function loadSelectedConfig() {
  try {
    const res = await fetch(`${API_BASE}/api/configs/${currentSelectedEnv}`);
    if (!res.ok) throw new Error("Failed to load config");
    const bundle = await res.json();

    // Convert variables to .env text
    let envLines = [];
    for (const [k, v] of Object.entries(bundle.variables || {})) {
      envLines.push(`${k}=${v}`);
    }
    document.getElementById("editor-env-vars").value = envLines.join("\n");

    // Convert infrastructure to YAML-like text
    let infraLines = [];
    for (const [k, v] of Object.entries(bundle.infrastructure || {})) {
      if (k !== "id" && k !== "version_id") {
        infraLines.push(`${k}: ${v}`);
      }
    }
    document.getElementById("editor-infra").value = infraLines.join("\n");

    // Secrets JSON
    const secretsClean = (bundle.secrets || []).map(s => {
      const { id, version_id, ...rest } = s;
      return rest;
    });
    document.getElementById("editor-secrets").value = JSON.stringify(secretsClean, null, 2);

    document.getElementById("config-change-desc").value = "";
  } catch (err) {
    console.error("Error loading config bundle:", err);
  }
}

async function saveActiveConfig() {
  const desc = document.getElementById("config-change-desc").value.trim() || `Manual update via dashboard for ${currentSelectedEnv}`;
  const envContent = document.getElementById("editor-env-vars").value;
  const infraContent = document.getElementById("editor-infra").value;
  const secretsContent = document.getElementById("editor-secrets").value;

  try {
    const res = await fetch(`${API_BASE}/api/configs/${currentSelectedEnv}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: currentSelectedEnv,
        raw_env_content: envContent,
        raw_infra_content: infraContent,
        raw_secrets_content: secretsContent,
        description: desc,
        author: "developer"
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Save failed");
    }

    const data = await res.json();
    alert(`Success! Created Version ${data.new_version} for ${currentSelectedEnv}.`);
    await fetchEnvironments();
    await runValidation();
    await loadVersionOptionsForRollback();
  } catch (err) {
    alert("Error saving configuration: " + err.message);
  }
}

// --- Change Request & Approval Workflow ---
async function loadChangeRequests() {
  try {
    const res = await fetch(`${API_BASE}/api/change-requests`);
    const requests = await res.json();
    const tbody = document.getElementById("change-requests-tbody");
    document.getElementById("cr-count-badge").textContent = requests.filter(r => r.status === "PENDING").length;

    tbody.innerHTML = "";
    if (requests.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #9CA3AF; padding: 32px;">No change requests submitted yet.</td></tr>`;
      return;
    }

    requests.forEach(cr => {
      const tr = document.createElement("tr");

      let statusPill = "pill-neutral";
      if (cr.status === "APPROVED") statusPill = "badge-healthy";
      else if (cr.status === "REJECTED") statusPill = "badge-critical";
      else statusPill = "badge-warning";

      let actionsHtml = `<span style="color: #6B7280;">Closed</span>`;
      if (cr.status === "PENDING") {
        actionsHtml = `
          <button class="btn btn-outline" style="padding: 4px 10px; font-size: 0.75rem; color: #34D399; margin-right: 6px;" onclick="reviewChange(${cr.id}, 'APPROVED')">✓ Approve</button>
          <button class="btn btn-outline" style="padding: 4px 10px; font-size: 0.75rem; color: #F87171;" onclick="reviewChange(${cr.id}, 'REJECTED')">✕ Reject</button>
        `;
      }

      tr.innerHTML = `
        <td><strong>#${cr.id}</strong></td>
        <td><span class="env-tag env-tag-${cr.environment === 'development' ? 'dev' : cr.environment === 'staging' ? 'staging' : 'prod'}">${cr.environment.toUpperCase()}</span></td>
        <td>
          <strong>${escapeHtml(cr.title)}</strong>
          <div style="font-size: 0.75rem; color: #9CA3AF;">${escapeHtml(cr.description || "")}</div>
        </td>
        <td><span class="pill ${cr.risk_level === 'HIGH' ? 'pill-high' : 'pill-medium'}">${cr.risk_level}</span></td>
        <td><span class="status-badge ${statusPill}">${cr.status}</span></td>
        <td>${escapeHtml(cr.requested_by)}</td>
        <td>${escapeHtml(cr.reviewed_by || "Pending")}</td>
        <td>${actionsHtml}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading change requests:", err);
  }
}

function openNewChangeModal() {
  document.getElementById("modal-change-request").classList.add("open");
}

function closeNewChangeModal() {
  document.getElementById("modal-change-request").classList.remove("open");
}

async function submitChangeRequest() {
  const env = document.getElementById("cr-modal-env").value;
  const title = document.getElementById("cr-modal-title").value.trim();
  const desc = document.getElementById("cr-modal-desc").value.trim();
  const jsonStr = document.getElementById("cr-modal-json").value.trim();
  const author = document.getElementById("cr-modal-author").value.trim() || "developer";

  if (!title || !jsonStr) {
    alert("Please provide both Title and Proposed Changes JSON.");
    return;
  }

  try {
    // Validate JSON format
    JSON.parse(jsonStr);

    const res = await fetch(`${API_BASE}/api/change-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: env,
        title: title,
        description: desc,
        proposed_changes_json: jsonStr,
        requested_by: author
      })
    });

    if (!res.ok) throw new Error("Failed to submit change request");

    closeNewChangeModal();
    await loadChangeRequests();
    alert("Change request submitted successfully!");
  } catch (err) {
    alert("Invalid change request: " + err.message);
  }
}

async function reviewChange(id, decision) {
  const notes = prompt(`Enter review notes for ${decision}:`, `Reviewed and ${decision.toLowerCase()} by tech-lead`);
  if (notes === null) return;

  try {
    const res = await fetch(`${API_BASE}/api/change-requests/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: decision,
        reviewed_by: "tech-lead",
        review_notes: notes
      })
    });

    const data = await res.json();
    alert(data.message);
    await loadChangeRequests();
    await fetchEnvironments();
    await runValidation();
    await loadAuditLogs();
  } catch (err) {
    alert("Review error: " + err.message);
  }
}

// --- Rollback Handling ---
async function loadVersionOptionsForRollback() {
  const env = document.getElementById("rollback-env-select").value;
  const select = document.getElementById("rollback-target-version");
  select.innerHTML = `<option value="">Loading versions...</option>`;

  try {
    const res = await fetch(`${API_BASE}/api/configs/${env}/history`);
    const versions = await res.json();
    select.innerHTML = "";

    if (versions.length === 0) {
      select.innerHTML = `<option value="">No versions found</option>`;
      return;
    }

    versions.forEach(v => {
      const opt = document.createElement("option");
      opt.value = v.version;
      opt.textContent = `Version ${v.version} - ${v.description || 'Snapshot'} (${v.is_active ? 'Currently Active' : 'Inactive'})`;
      if (!v.is_active && !select.value) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading version history:", err);
  }
}

async function loadRollbackHistory() {
  const list = document.getElementById("rollback-history-list");
  try {
    const res = await fetch(`${API_BASE}/api/rollbacks`);
    const records = await res.json();
    list.innerHTML = "";

    if (records.length === 0) {
      list.innerHTML = `<p style="color: #6B7280; font-size: 0.82rem; text-align: center; padding: 24px;">No rollback events recorded yet.</p>`;
      return;
    }

    records.forEach(r => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <div class="history-item-header">
          <span style="color: #F87171;">⏪ ${r.environment.toUpperCase()}: v${r.from_version} &rarr; v${r.to_version}</span>
          <span style="color: #9CA3AF; font-size: 0.75rem;">${new Date(r.timestamp).toLocaleString()}</span>
        </div>
        <div class="history-item-detail">
          <strong>Reason:</strong> ${escapeHtml(r.reason)} | <strong>By:</strong> ${escapeHtml(r.performed_by)}
        </div>
      `;
      list.appendChild(item);
    });
  } catch (err) {
    console.error("Error loading rollback records:", err);
  }
}

async function submitRollback() {
  const env = document.getElementById("rollback-env-select").value;
  const version = parseInt(document.getElementById("rollback-target-version").value);
  const reason = document.getElementById("rollback-reason").value.trim() || "Manual rollback initiated via dashboard";
  const user = document.getElementById("rollback-user").value.trim() || "devops-admin";

  if (!version) {
    alert("Please select a target version to restore.");
    return;
  }

  if (!confirm(`Are you sure you want to rollback ${env.toUpperCase()} to Version ${version}?`)) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: env,
        target_version: version,
        reason: reason,
        performed_by: user
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Rollback failed");
    }

    const data = await res.json();
    alert(`Rollback Complete: ${env.toUpperCase()} restored to Version ${data.restored_version}`);
    await fetchEnvironments();
    await runValidation();
    await loadRollbackHistory();
    await loadVersionOptionsForRollback();
    await loadAuditLogs();
  } catch (err) {
    alert("Rollback failed: " + err.message);
  }
}

// --- Audit Trail ---
async function loadAuditLogs() {
  try {
    const res = await fetch(`${API_BASE}/api/audit-logs`);
    const logs = await res.json();
    const tbody = document.getElementById("audit-tbody");
    tbody.innerHTML = "";

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #6B7280; padding: 24px;">No audit records found.</td></tr>`;
      return;
    }

    logs.forEach(log => {
      const tr = document.createElement("tr");

      let riskPill = "pill-low";
      if (log.risk_level === "CRITICAL") riskPill = "pill-critical";
      else if (log.risk_level === "HIGH") riskPill = "pill-high";
      else if (log.risk_level === "MEDIUM") riskPill = "pill-medium";

      tr.innerHTML = `
        <td class="mono" style="font-size: 0.76rem; color: #9CA3AF;">${new Date(log.timestamp).toLocaleString()}</td>
        <td><span class="mono" style="color: #93C5FD;">${escapeHtml(log.user)}</span></td>
        <td><strong>${escapeHtml(log.action)}</strong></td>
        <td><span class="env-tag env-tag-${log.environment === 'development' ? 'dev' : log.environment === 'staging' ? 'staging' : 'prod'}">${log.environment.toUpperCase()}</span></td>
        <td><span class="pill ${riskPill}">${log.risk_level}</span></td>
        <td style="font-size: 0.8rem; color: #D1D5DB;">${escapeHtml(log.details)}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading audit logs:", err);
  }
}

// --- Interactive Viva Demonstration Scenarios ---
async function injectScenario(scenario) {
  if (scenario === "wrong_db") {
    // Introduce mistake: Production DATABASE_HOST = dev-db
    await fetch(`${API_BASE}/api/configs/production/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: "production",
        raw_env_content: "APP_ENV=production\nDEBUG=false\nDATABASE_HOST=dev-db\nDATABASE_PORT=5432\nAPI_URL=https://api\nLOG_LEVEL=INFO\nFEATURE_PAYMENT=true",
        description: "Viva Demo: Mistakenly pointed Production database to dev-db",
        author: "junior-developer"
      })
    });
    alert("⚠️ Injected Scenario 1: Production DATABASE_HOST is now set to 'dev-db'!\nRunning validator...");
  } 
  else if (scenario === "debug_true") {
    // Introduce mistake: Production DEBUG=true
    await fetch(`${API_BASE}/api/configs/production/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: "production",
        raw_env_content: "APP_ENV=production\nDEBUG=true\nDATABASE_HOST=prod-db\nDATABASE_PORT=5432\nAPI_URL=https://api\nLOG_LEVEL=INFO\nFEATURE_PAYMENT=true",
        description: "Viva Demo: Accidental DEBUG=true in Production",
        author: "junior-developer"
      })
    });
    alert("⚠️ Injected Scenario 2: Production DEBUG=true enabled!\nRunning validator...");
  }
  else if (scenario === "missing_secret") {
    // Introduce missing secret
    const brokenSecrets = [
      { name: "API_SECRET_KEY", environment: "production", exists: true, source: "secret-manager", age_days: 15 },
      { name: "DATABASE_PASSWORD", environment: "production", exists: false, source: "secret-manager", age_days: 15 }
    ];
    await fetch(`${API_BASE}/api/configs/production/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: "production",
        raw_secrets_content: JSON.stringify(brokenSecrets),
        description: "Viva Demo: Production missing DATABASE_PASSWORD secret",
        author: "security-auditor"
      })
    });
    alert("⚠️ Injected Scenario 3: Missing required secret DATABASE_PASSWORD in Production!\nRunning validator...");
  }
  else if (scenario === "runtime_drift") {
    // Update live runtime snapshot
    await fetch(`${API_BASE}/api/runtime/production`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: "production",
        app_version: "1.4.2",
        snapshot_data: {
          database_host: "prod-db",
          log_level: "DEBUG", // Drift! Approved is INFO
          feature_payment: true
        }
      })
    });
    alert("⚠️ Injected Scenario 4: Live container snapshot reports LOG_LEVEL=DEBUG (Differs from approved INFO)!\nRunning validator...");
  }
  else if (scenario === "healthy_expected") {
    await resetDemoState();
    return;
  }

  await fetchEnvironments();
  await runValidation();
  // Switch to results tab
  document.querySelectorAll(".tab-btn")[0].click();
}

async function resetDemoState() {
  if (!confirm("Reset demo data to initial healthy baseline?")) return;
  try {
    const res = await fetch(`${API_BASE}/api/reset-demo`, { method: "POST" });
    const data = await res.json();
    alert(data.message);
    await initDashboard();
  } catch (err) {
    alert("Reset failed: " + err.message);
  }
}

// --- Deployment Gate Simulation ---
async function simulateProductionDeployment() {
  const res = await fetch(`${API_BASE}/api/deployment-gate`);
  const gate = await res.json();

  if (gate.production_deployment_allowed) {
    alert("🚀 PRODUCTION DEPLOYMENT APPROVED!\n\nSafety Gate Result: PASSED\nZero blocking configuration discrepancies detected.\nContainer deployment pipeline proceeding...");
  } else {
    let blockers = gate.blocking_issues.map(b => `• [${b.severity}] ${b.item_key}: ${b.reason}`).join("\n");
    alert(`⛔ DEPLOYMENT BLOCKED BY SAFETY GATE!\n\nReason: ${gate.critical_count} Critical configuration issues detected.\n\nBlocking Issues:\n${blockers}\n\nPlease fix or rollback configurations before proceeding.`);
  }
}

function escapeHtml(str) {
  if (typeof str !== "string") str = String(str);
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
