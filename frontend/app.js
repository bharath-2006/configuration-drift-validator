/**
 * app.js - Configuration Drift Validator Frontend Controller (Phase 2 - 70% Version)
 * Comprehensive controller handling:
 * - Real-time Drift Detection & Deployment Gating
 * - Multi-Stage Pre-Deployment Validation Pipeline
 * - Git Commit Ingestion & Simulation
 * - Continuous Runtime Monitoring & Drift Simulator
 * - Version History & Side-by-Side Diff Comparator
 * - In-App Notification Center
 * - Validation Reports & CSV/JSON Exporters
 * - Configuration Editor, Change Approvals, Rollbacks, and Viva Scenarios
 */

const API_BASE = "";

// State
let currentSelectedEnv = "production";
let cachedDriftItems = [];
let activeFilter = "ALL";
let currentHistEnv = "production";

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  await fetchDashboardSummary();
  await fetchEnvironments();
  await runValidation(false);
  await loadSelectedConfig();
  await loadChangeRequests();
  await loadAuditLogs();
  await loadGitCommits();
  await loadMonitoringStatus();
  await loadValidationReports();
  await loadNotifications();
  await loadVersionOptionsForRollback();
  await loadRollbackHistory();
  await loadHistoryForEnv("production");
}

// --- Navigation Tabs ---
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));

  if (event && event.currentTarget) {
    event.currentTarget.classList.add("active");
  } else {
    // Programmatic activation
    const btn = Array.from(document.querySelectorAll(".tab-btn")).find(b => b.getAttribute("onclick")?.includes(tabId));
    if (btn) btn.classList.add("active");
  }

  const targetPanel = document.getElementById(tabId);
  if (targetPanel) targetPanel.classList.add("active");

  if (tabId === "dashboard-tab") {
    fetchDashboardSummary();
    loadGitCommits();
  } else if (tabId === "change-tab") {
    loadChangeRequests();
  } else if (tabId === "audit-tab") {
    loadAuditLogs();
  } else if (tabId === "history-tab") {
    loadHistoryForEnv(currentHistEnv);
  } else if (tabId === "monitoring-tab") {
    loadMonitoringStatus();
  } else if (tabId === "reports-tab") {
    loadValidationReports();
  } else if (tabId === "rollback-tab") {
    loadVersionOptionsForRollback();
    loadRollbackHistory();
  }
}

function openConfigTab(env) {
  selectConfigEnv(env);
  const tabBtns = document.querySelectorAll(".tab-btn");
  const cfgBtn = Array.from(tabBtns).find(b => b.textContent.includes("Configurations"));
  if (cfgBtn) cfgBtn.click();
}

// --- Dashboard Summary & Charts ---
async function fetchDashboardSummary() {
  try {
    const res = await fetch(`${API_BASE}/api/dashboard/summary`);
    if (!res.ok) return;
    const data = await res.json();

    // Metrics Ribbon
    document.getElementById("metric-total-validations").textContent = data.metrics.total_validations;
    document.getElementById("metric-drifts").textContent = data.metrics.configuration_drifts;
    document.getElementById("metric-critical").textContent = data.metrics.critical_issues;
    document.getElementById("metric-high").textContent = data.metrics.high_issues;
    document.getElementById("metric-blocked-deploys").textContent = data.metrics.blocked_deployments;
    document.getElementById("metric-approved-changes").textContent = data.metrics.approved_changes;
    document.getElementById("metric-rollbacks").textContent = data.metrics.rollbacks_performed;
    document.getElementById("metric-risk-score").textContent = `${data.metrics.risk_score}/100`;

    // Environment Badges
    const devBadge = document.getElementById("badge-dev");
    const stageBadge = document.getElementById("badge-staging");
    const prodBadge = document.getElementById("badge-prod");

    if (devBadge) {
      devBadge.textContent = (data.environment_status.development || "HEALTHY").toUpperCase();
      devBadge.className = `status-badge badge-${data.environment_status.development === 'Critical' ? 'critical' : data.environment_status.development === 'Warning' ? 'warning' : 'healthy'}`;
    }
    if (stageBadge) {
      stageBadge.textContent = (data.environment_status.staging || "HEALTHY").toUpperCase();
      stageBadge.className = `status-badge badge-${data.environment_status.staging === 'Critical' ? 'critical' : data.environment_status.staging === 'Warning' ? 'warning' : 'healthy'}`;
    }
    if (prodBadge) {
      prodBadge.textContent = (data.environment_status.production || "HEALTHY").toUpperCase();
      prodBadge.className = `status-badge badge-${data.environment_status.production === 'Critical' ? 'critical' : data.environment_status.production === 'Warning' ? 'warning' : 'healthy'}`;
    }

    // Chart 1: Drifts by Environment
    const devDrifts = data.charts.drifts_by_env.development || 0;
    const stageDrifts = data.charts.drifts_by_env.staging || 0;
    const prodDrifts = data.charts.drifts_by_env.production || 0;
    const maxDrift = Math.max(devDrifts, stageDrifts, prodDrifts, 1);

    document.getElementById("lbl-dev-drifts").textContent = devDrifts;
    document.getElementById("lbl-stage-drifts").textContent = stageDrifts;
    document.getElementById("lbl-prod-drifts").textContent = prodDrifts;
    document.getElementById("total-env-drifts").textContent = `${devDrifts + stageDrifts + prodDrifts} Total`;

    document.getElementById("bar-dev-drifts").style.width = `${(devDrifts / maxDrift) * 100}%`;
    document.getElementById("bar-stage-drifts").style.width = `${(stageDrifts / maxDrift) * 100}%`;
    document.getElementById("bar-prod-drifts").style.width = `${(prodDrifts / maxDrift) * 100}%`;

    // Chart 2: Issues by Severity
    const crit = data.charts.issues_by_severity.CRITICAL || 0;
    const high = data.charts.issues_by_severity.HIGH || 0;
    const med = data.charts.issues_by_severity.MEDIUM || 0;
    const low = data.charts.issues_by_severity.LOW || 0;
    const maxSev = Math.max(crit, high, med, low, 1);

    document.getElementById("lbl-crit-cnt").textContent = crit;
    document.getElementById("lbl-high-cnt").textContent = high;
    document.getElementById("lbl-med-cnt").textContent = med;
    document.getElementById("lbl-low-cnt").textContent = low;

    document.getElementById("bar-crit-cnt").style.width = `${(crit / maxSev) * 100}%`;
    document.getElementById("bar-high-cnt").style.width = `${(high / maxSev) * 100}%`;
    document.getElementById("bar-med-cnt").style.width = `${(med / maxSev) * 100}%`;
    document.getElementById("bar-low-cnt").style.width = `${(low / maxSev) * 100}%`;

    // Chart 3: Deployment Gate Ratio
    const blocked = data.charts.gate_ratio.blocked || 0;
    const allowed = data.charts.gate_ratio.allowed || 0;
    const totalGate = Math.max(blocked + allowed, 1);

    document.getElementById("lbl-gate-passed").textContent = allowed;
    document.getElementById("lbl-gate-blocked").textContent = blocked;
    document.getElementById("bar-gate-passed").style.width = `${(allowed / totalGate) * 100}%`;
    document.getElementById("bar-gate-blocked").style.width = `${(blocked / totalGate) * 100}%`;

  } catch (err) {
    console.error("Dashboard summary error:", err);
  }
}

// --- Fetch Environment Summary Cards ---
async function fetchEnvironments() {
  try {
    const res = await fetch(`${API_BASE}/api/environments`);
    const envs = await res.json();
    
    envs.forEach(env => {
      const prefix = env.id.substring(0, 4) === 'deve' ? 'dev' : env.id.substring(0, 4) === 'stag' ? 'staging' : 'prod';
      const vElem = document.getElementById(`v-${prefix}`);
      if (vElem) vElem.textContent = `v${env.active_version || 1}`;
    });

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
async function runValidation(showAlert = false) {
  const btn = document.getElementById("btn-validate");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Validating...`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/validate`, { method: "POST" });
    if (!res.ok) throw new Error("Validation request failed");
    const summary = await res.json();

    cachedDriftItems = summary.discrepancies || [];
    renderDeploymentGate(summary);
    renderDriftTable(cachedDriftItems);
    await fetchDashboardSummary();
    await loadNotifications();

    document.getElementById("last-updated").textContent = `Last scan: ${new Date().toLocaleTimeString()}`;
    if (showAlert) alert(`Validation complete: ${summary.deployment_message}`);
  } catch (err) {
    console.error("Validation error:", err);
    if (showAlert) alert("Validation failed: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        Run Drift Validation
      `;
    }
  }
}

// --- Render Gate Banner ---
function renderDeploymentGate(summary) {
  const banner = document.getElementById("deployment-gate-banner");
  const title = document.getElementById("gate-title");
  const pill = document.getElementById("gate-pill");
  const desc = document.getElementById("gate-desc");
  const icon = document.getElementById("gate-icon");
  const deployBtn = document.getElementById("btn-deploy-simulate");

  banner.className = "gate-banner";

  if (summary.production_deployment_allowed) {
    banner.classList.add("gate-approved");
    icon.textContent = "✅";
    title.textContent = "Production Safety Gate: SAFE TO DEPLOY";
    pill.className = "pill pill-approved";
    pill.textContent = "GATE OPEN";
    desc.textContent = summary.deployment_message;
    if (deployBtn) {
      deployBtn.disabled = false;
      deployBtn.className = "btn btn-gate";
      deployBtn.textContent = "🚀 Deploy to Production";
    }
  } else {
    banner.classList.add("gate-critical");
    icon.textContent = "⛔";
    title.textContent = "Production Safety Gate: DEPLOYMENT BLOCKED";
    pill.className = "pill pill-critical";
    pill.textContent = "BLOCKED";
    desc.textContent = summary.deployment_message;
    if (deployBtn) {
      deployBtn.disabled = true;
      deployBtn.className = "btn btn-gate btn-disabled";
      deployBtn.textContent = "⛔ Deployment Blocked";
    }
  }
}

// --- Render Drift Table ---
function renderDriftTable(items) {
  const tbody = document.getElementById("drift-tbody");
  const emptyState = document.getElementById("drift-empty-state");
  const countBadge = document.getElementById("drift-count-badge");
  tbody.innerHTML = "";

  const filtered = activeFilter === "ALL" 
    ? items 
    : items.filter(d => d.severity.toUpperCase() === activeFilter);

  countBadge.textContent = items.length;

  if (filtered.length === 0) {
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";

  filtered.forEach(d => {
    const tr = document.createElement("tr");
    const sevClass = d.severity.toLowerCase();

    tr.innerHTML = `
      <td><span class="severity-pill sev-${sevClass}">${d.severity}</span></td>
      <td><span class="env-tag env-tag-${d.environment.toLowerCase()}">${d.environment.toUpperCase()}</span></td>
      <td><span class="category-tag">${d.category}</span></td>
      <td><strong class="mono text-cyan">${escapeHtml(d.item_key)}</strong></td>
      <td class="mono">${escapeHtml(d.expected_val || "None")}</td>
      <td class="mono ${sevClass === 'critical' ? 'text-rose' : 'text-amber'}">${escapeHtml(d.actual_val || "MISSING")}</td>
      <td>
        <div class="reason-box"><strong>Reason:</strong> ${escapeHtml(d.reason)}</div>
        <div class="rec-box"><strong>Action:</strong> ${escapeHtml(d.recommendation)}</div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterDrift(severity) {
  activeFilter = severity;
  document.querySelectorAll(".filter-chip").forEach(btn => {
    btn.classList.toggle("active", btn.textContent.toUpperCase() === severity || (severity === "ALL" && btn.textContent === "All"));
  });
  renderDriftTable(cachedDriftItems);
}

// --- Pre-Deployment Validation Pipeline ---
async function triggerPreDeploymentValidation() {
  const envSelect = document.getElementById("predeploy-env-select");
  const targetEnv = envSelect ? envSelect.value : "production";

  // Switch to predeploy tab
  switchTab("predeploy-tab");

  const container = document.getElementById("pipeline-steps-container");
  const decisionBanner = document.getElementById("predeploy-decision-banner");
  container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-secondary);">Executing 6-stage pre-deployment verification pipeline...</div>`;
  decisionBanner.style.display = "none";

  try {
    const res = await fetch(`${API_BASE}/api/pre-deployment-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ environment: targetEnv })
    });
    if (!res.ok) throw new Error("Pre-deployment check failed");
    const data = await res.json();

    // Render Pipeline Steps
    container.innerHTML = "";
    data.stages.forEach(st => {
      const card = document.createElement("div");
      card.className = "pipeline-step-card";
      const statusClass = st.status === "PASSED" ? "status-passed" : st.status === "FAILED" ? "status-failed" : "status-warning";
      const icon = st.status === "PASSED" ? "✓" : st.status === "FAILED" ? "✗" : "!";

      card.innerHTML = `
        <div class="pipeline-step-info">
          <div class="pipeline-step-num">${st.stage_id}</div>
          <div>
            <div class="pipeline-step-title">${st.stage_name}</div>
            <div class="pipeline-step-desc">${st.details}</div>
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
          <span style="font-size:0.75rem; color:var(--text-muted);">${st.duration_ms} ms</span>
          <span class="pipeline-step-status ${statusClass}">${icon} ${st.status}</span>
        </div>
      `;
      container.appendChild(card);
    });

    // Render Decision Banner
    decisionBanner.style.display = "flex";
    if (data.is_safe) {
      decisionBanner.className = "decision-card decision-safe";
      document.getElementById("predeploy-decision-title").textContent = "✅ DEPLOYMENT SAFE";
      document.getElementById("predeploy-decision-desc").textContent = "All pre-flight stages passed. Production deployment is permitted.";
    } else {
      decisionBanner.className = "decision-card decision-blocked";
      document.getElementById("predeploy-decision-title").textContent = `❌ DEPLOYMENT BLOCKED (Critical Issues: ${data.critical_issues}, High Issues: ${data.high_issues})`;
      document.getElementById("predeploy-decision-desc").textContent = `Risk Score: ${data.risk_score}/100 (${data.risk_level}) — ${data.risk_explanation}`;
    }

    await fetchDashboardSummary();
    await loadNotifications();
  } catch (err) {
    container.innerHTML = `<div style="color:var(--accent-rose); padding:20px;">Error executing pipeline: ${err.message}</div>`;
  }
}

// --- Git Commit Ingestion & Simulation ---
function openGitCommitModal() {
  document.getElementById("modal-git-commit").classList.add("open");
}
function closeGitCommitModal() {
  document.getElementById("modal-git-commit").classList.remove("open");
}

async function submitGitCommitSimulation() {
  const author = document.getElementById("git-modal-author").value;
  const message = document.getElementById("git-modal-msg").value;
  const env = document.getElementById("git-modal-env").value;
  const jsonStr = document.getElementById("git-modal-json").value;

  let changedConfigs = {};
  try {
    changedConfigs = JSON.parse(jsonStr);
  } catch (err) {
    alert("Invalid JSON format for changed configs");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/git/simulate-commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        author,
        message,
        environment: env,
        changed_configs: changedConfigs
      })
    });
    if (!res.ok) throw new Error("Failed to record Git commit");
    const data = await res.json();

    closeGitCommitModal();
    alert(`Git Commit ${data.commit_id} evaluated: ${data.validation_result} (Risk Score: ${data.risk_score}/100, ${data.risk_level})`);
    await loadGitCommits();
    await fetchDashboardSummary();
    await loadNotifications();
  } catch (err) {
    alert("Commit simulation error: " + err.message);
  }
}

async function loadGitCommits() {
  const tbody = document.getElementById("git-commits-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/git/commits`);
    const commits = await res.json();
    tbody.innerHTML = "";

    if (commits.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No Git configuration commits recorded yet.</td></tr>`;
      return;
    }

    commits.forEach(c => {
      const tr = document.createElement("tr");
      const isBlocked = c.validation_result === "BLOCKED";
      const keys = Object.keys(c.changed_configs || {}).join(", ") || "manifests";

      tr.innerHTML = `
        <td><strong class="mono text-cyan">${c.commit_id}</strong></td>
        <td>${escapeHtml(c.author)}</td>
        <td>${escapeHtml(c.message)}</td>
        <td><span class="env-tag env-tag-${c.environment.toLowerCase()}">${c.environment.toUpperCase()}</span></td>
        <td class="mono">${escapeHtml(keys)}</td>
        <td><span class="severity-pill ${isBlocked ? 'sev-critical' : 'sev-low'}">${c.validation_result}</span></td>
        <td><span class="severity-pill sev-${c.risk_level.toLowerCase()}">${c.risk_level} (${c.risk_score})</span></td>
        <td style="font-size:0.75rem; color:var(--text-muted);">${c.created_at || "Just now"}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading git commits:", err);
  }
}

// --- Continuous Configuration Monitoring ---
async function loadMonitoringStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/monitoring/status?environment=production`);
    if (!res.ok) return;
    const data = await res.json();

    const envStatus = document.getElementById("mon-env-status");
    if (envStatus) {
      envStatus.textContent = data.current_environment_status;
      envStatus.className = `mon-val ${data.current_environment_status === 'HEALTHY' ? 'text-emerald' : 'text-rose'}`;
    }
    document.getElementById("mon-drifts-count").textContent = data.number_of_detected_drifts;
    document.getElementById("mon-critical-count").textContent = data.critical_issues;
    document.getElementById("mon-last-success").textContent = data.last_successful_validation.replace("T", " ").substring(0, 19);
    document.getElementById("mon-last-failed").textContent = data.last_failed_validation.replace("T", " ").substring(0, 19);

    // Render comparison table
    const compTbody = document.getElementById("monitoring-comparison-tbody");
    if (compTbody) {
      compTbody.innerHTML = "";
      data.comparison_table.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong class="mono">${escapeHtml(row.key)}</strong></td>
          <td class="mono">${escapeHtml(row.approved_value)}</td>
          <td class="mono ${row.is_synced ? 'text-emerald' : 'text-rose'}">${escapeHtml(row.runtime_value)}</td>
          <td>
            <span class="pipeline-step-status ${row.is_synced ? 'status-passed' : 'status-failed'}">
              ${row.is_synced ? 'SYNCHRONIZED' : 'RUNTIME DRIFT'}
            </span>
          </td>
        `;
        compTbody.appendChild(tr);
      });
    }

    // Render events table
    const evtTbody = document.getElementById("monitoring-events-tbody");
    if (evtTbody) {
      evtTbody.innerHTML = "";
      data.recent_events.forEach(e => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-size:0.75rem; color:var(--text-muted);">${e.timestamp.replace("T", " ").substring(0, 19)}</td>
          <td><span class="category-tag">${e.event_type}</span></td>
          <td><span class="severity-pill sev-${e.severity.toLowerCase()}">${e.status}</span></td>
          <td><strong>${e.drifts_count}</strong></td>
          <td style="font-size:0.8rem;">${escapeHtml(e.details)}</td>
        `;
        evtTbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error("Monitoring status error:", err);
  }
}

async function triggerMonitoringScan() {
  try {
    const res = await fetch(`${API_BASE}/api/monitoring/scan`, { method: "POST" });
    const data = await res.json();
    alert(`Monitoring scan completed: Environment is ${data.status} (${data.drifts_count} drifts detected).`);
    await loadMonitoringStatus();
    await loadNotifications();
    await fetchDashboardSummary();
  } catch (err) {
    alert("Scan error: " + err.message);
  }
}

async function simulateRuntimeDrift() {
  try {
    // Post out-of-band drift to runtime endpoint
    await fetch(`${API_BASE}/api/runtime/production`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: "production",
        app_version: "1.0.0",
        snapshot_data: {
          database_host: "dev-db",
          log_level: "DEBUG"
        }
      })
    });

    // Run monitoring scan
    await fetch(`${API_BASE}/api/monitoring/scan`, { method: "POST" });
    alert("Runtime drift injected: Container modified out-of-band to DATABASE_HOST=dev-db, LOG_LEVEL=DEBUG!");
    await loadMonitoringStatus();
    await loadNotifications();
    await fetchDashboardSummary();
  } catch (err) {
    alert("Error simulating drift: " + err.message);
  }
}

// --- Configuration History & Side-by-Side Diff ---
async function loadHistoryForEnv(env) {
  currentHistEnv = env;
  document.getElementById("btn-hist-prod")?.classList.toggle("active", env === "production");
  document.getElementById("btn-hist-stage")?.classList.toggle("active", env === "staging");
  document.getElementById("btn-hist-dev")?.classList.toggle("active", env === "development");

  const tbody = document.getElementById("history-tbody");
  const selA = document.getElementById("diff-v-a");
  const selB = document.getElementById("diff-v-b");

  try {
    const res = await fetch(`${API_BASE}/api/configs/${env}/history`);
    const history = await res.json();

    if (tbody) tbody.innerHTML = "";
    if (selA) selA.innerHTML = "";
    if (selB) selB.innerHTML = "";

    if (history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No version history.</td></tr>`;
      return;
    }

    history.forEach((h, idx) => {
      if (selA) {
        const opt = document.createElement("option");
        opt.value = h.version;
        opt.textContent = `v${h.version}`;
        if (idx === 1) opt.selected = true;
        selA.appendChild(opt);
      }
      if (selB) {
        const opt = document.createElement("option");
        opt.value = h.version;
        opt.textContent = `v${h.version}`;
        if (idx === 0) opt.selected = true;
        selB.appendChild(opt);
      }

      if (tbody) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong class="mono text-cyan">v${h.version}</strong> ${h.is_active ? '<span class="pill pill-approved" style="font-size:0.65rem; margin-left:6px;">ACTIVE</span>' : ''}</td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${h.created_at || "Just now"}</td>
          <td>${escapeHtml(h.created_by)}</td>
          <td>${escapeHtml(h.description || "Config snapshot")}</td>
          <td><span class="severity-pill ${h.is_active ? 'sev-low' : 'sev-medium'}">${h.is_active ? 'APPROVED' : 'ARCHIVED'}</span></td>
          <td>
            <button class="btn-text-link" onclick="quickCompareVersion(${h.version})">Compare &rarr;</button>
          </td>
        `;
        tbody.appendChild(tr);
      }
    });
  } catch (err) {
    console.error("Error loading config history:", err);
  }
}

async function quickCompareVersion(v) {
  const selA = document.getElementById("diff-v-a");
  const selB = document.getElementById("diff-v-b");
  if (selA && selB) {
    selA.value = Math.max(1, v - 1);
    selB.value = v;
    executeVersionDiff();
  }
}

async function executeVersionDiff() {
  const vA = document.getElementById("diff-v-a").value;
  const vB = document.getElementById("diff-v-b").value;
  if (!vA || !vB) return;

  const outBox = document.getElementById("diff-output-box");
  const title = document.getElementById("diff-title");
  const badge = document.getElementById("diff-stats-badge");
  const tbody = document.getElementById("diff-tbody");

  try {
    const res = await fetch(`${API_BASE}/api/configs/${currentHistEnv}/compare?v_a=${vA}&v_b=${vB}`);
    if (!res.ok) throw new Error("Could not compare versions");
    const diff = await res.json();

    outBox.style.display = "block";
    title.textContent = `Comparing Version ${vA} (Old) ➔ Version ${vB} (New) [${currentHistEnv.toUpperCase()}]`;
    badge.textContent = `${diff.summary.modified} Modified, ${diff.summary.added} Added, ${diff.summary.removed} Removed`;

    tbody.innerHTML = "";
    diff.variable_diffs.forEach(row => {
      const tr = document.createElement("tr");
      let rowClass = "";
      let statusBadge = "";

      if (row.change_type === "MODIFIED") {
        rowClass = "diff-modified";
        statusBadge = `<span class="severity-pill sev-medium">MODIFIED</span>`;
      } else if (row.change_type === "ADDED") {
        rowClass = "diff-added";
        statusBadge = `<span class="severity-pill sev-low">+ ADDED</span>`;
      } else if (row.change_type === "REMOVED") {
        rowClass = "diff-removed";
        statusBadge = `<span class="severity-pill sev-critical">- REMOVED</span>`;
      } else {
        statusBadge = `<span class="pill pill-neutral">UNCHANGED</span>`;
      }

      tr.className = rowClass;
      tr.innerHTML = `
        <td><strong class="mono">${escapeHtml(row.key)}</strong></td>
        <td><span class="${row.change_type === 'MODIFIED' || row.change_type === 'REMOVED' ? 'diff-val-old' : 'mono'}">${escapeHtml(row.old_value !== null ? row.old_value : "—")}</span></td>
        <td><span class="${row.change_type === 'MODIFIED' || row.change_type === 'ADDED' ? 'diff-val-new' : 'mono'}">${escapeHtml(row.new_value !== null ? row.new_value : "—")}</span></td>
        <td>${statusBadge}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    alert("Comparison error: " + err.message);
  }
}

// --- Notifications Center ---
function toggleNotificationDrawer() {
  const drawer = document.getElementById("notif-drawer");
  drawer.classList.toggle("open");
}

async function loadNotifications() {
  try {
    const res = await fetch(`${API_BASE}/api/notifications?limit=25`);
    if (!res.ok) return;
    const notifs = await res.json();

    const unreadCount = notifs.filter(n => !n.is_read).length;
    const badge = document.getElementById("notif-badge");
    if (badge) {
      badge.textContent = unreadCount;
      badge.style.display = unreadCount > 0 ? "inline-block" : "none";
    }

    const list = document.getElementById("notif-list");
    if (list) {
      list.innerHTML = "";
      if (notifs.length === 0) {
        list.innerHTML = `<div style="text-align:center; padding:16px; color:var(--text-muted); font-size:0.8rem;">No notifications.</div>`;
        return;
      }
      notifs.forEach(n => {
        const item = document.createElement("div");
        const sevClass = n.severity.toLowerCase() === "critical" ? "crit" : n.severity.toLowerCase() === "warning" ? "warn" : "info";
        item.className = `notif-item ${sevClass}`;
        item.innerHTML = `
          <div class="notif-title">${escapeHtml(n.title)}</div>
          <div class="notif-msg">${escapeHtml(n.message)}</div>
          <div class="notif-time">${n.created_at || "Just now"}</div>
        `;
        list.appendChild(item);
      });
    }
  } catch (err) {
    console.error("Notifications error:", err);
  }
}

async function markAllNotificationsRead() {
  try {
    await fetch(`${API_BASE}/api/notifications/read-all`, { method: "POST" });
    await loadNotifications();
  } catch (err) {
    console.error("Mark read error:", err);
  }
}

// --- Validation Reports ---
async function loadValidationReports() {
  const tbody = document.getElementById("reports-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/reports/validation-runs`);
    const runs = await res.json();
    tbody.innerHTML = "";

    if (runs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted);">No validation reports generated yet.</td></tr>`;
      return;
    }

    runs.forEach(r => {
      const tr = document.createElement("tr");
      const isBlocked = r.deployment_decision === "BLOCKED";

      tr.innerHTML = `
        <td><strong class="mono text-cyan">${r.run_id}</strong></td>
        <td style="font-size:0.75rem; color:var(--text-muted);">${r.created_at ? r.created_at.substring(0, 19).replace("T", " ") : "Just now"}</td>
        <td><span class="env-tag env-tag-${r.environment.toLowerCase()}">${r.environment.toUpperCase()}</span></td>
        <td>${r.total_checks}</td>
        <td class="text-emerald font-bold">${r.passed_checks}</td>
        <td class="${r.failed_checks > 0 ? 'text-rose' : 'text-emerald'} font-bold">${r.failed_checks}</td>
        <td class="${r.critical_count > 0 ? 'text-rose font-bold' : ''}">${r.critical_count}</td>
        <td><span class="severity-pill ${isBlocked ? 'sev-critical' : 'sev-low'}">${r.deployment_decision}</span></td>
        <td><span class="severity-pill sev-${r.risk_level.toLowerCase()}">${r.risk_score}/100</span></td>
        <td style="display:flex; gap:6px;">
          <button class="btn btn-outline" style="padding:4px 8px; font-size:0.75rem;" onclick="viewReportDetails('${r.run_id}')">View</button>
          <a class="btn btn-outline" style="padding:4px 8px; font-size:0.75rem;" href="${API_BASE}/api/reports/validation-runs/${r.run_id}/export/csv" download>CSV</a>
          <a class="btn btn-outline" style="padding:4px 8px; font-size:0.75rem;" href="${API_BASE}/api/reports/validation-runs/${r.run_id}/export/json" download>JSON</a>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading validation reports:", err);
  }
}

async function viewReportDetails(runId) {
  try {
    const res = await fetch(`${API_BASE}/api/reports/validation-runs/${runId}`);
    if (!res.ok) throw new Error("Report not found");
    const r = await res.json();

    document.getElementById("report-modal-title").textContent = `Configuration Validation Report: ${r.run_id}`;
    const content = document.getElementById("report-modal-content");

    content.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; font-size:0.85rem; margin-bottom:16px;">
        <div><strong>Environment:</strong> ${r.environment.toUpperCase()}</div>
        <div><strong>Date:</strong> ${r.created_at}</div>
        <div><strong>Triggered By:</strong> ${r.triggered_by}</div>
        <div><strong>Deployment Decision:</strong> <span class="severity-pill ${r.deployment_decision === 'BLOCKED' ? 'sev-critical' : 'sev-low'}">${r.deployment_decision}</span></div>
        <div><strong>Risk Score:</strong> ${r.risk_score}/100 (${r.risk_level})</div>
        <div><strong>Checks Summary:</strong> ${r.passed_checks} Passed / ${r.total_checks} Total (${r.failed_checks} Discrepancies)</div>
      </div>
      <h4>Discrepancies (${(r.drift_results || []).length}):</h4>
      <div style="max-height:220px; overflow-y:auto; font-size:0.8rem;">
        ${(r.drift_results || []).map(d => `
          <div style="border-bottom:1px solid var(--border-subtle); padding:6px 0;">
            <span class="severity-pill sev-${d.severity.toLowerCase()}">${d.severity}</span>
            <strong class="mono" style="margin-left:8px;">${escapeHtml(d.item_key)}</strong>: ${escapeHtml(d.reason)}
          </div>
        `).join('') || '<div style="color:var(--text-muted);">No discrepancies recorded.</div>'}
      </div>
    `;

    document.getElementById("btn-export-json").onclick = () => window.location.href = `${API_BASE}/api/reports/validation-runs/${runId}/export/json`;
    document.getElementById("btn-export-csv").onclick = () => window.location.href = `${API_BASE}/api/reports/validation-runs/${runId}/export/csv`;

    document.getElementById("modal-report-details").classList.add("open");
  } catch (err) {
    alert("Error fetching report: " + err.message);
  }
}

function closeReportModal() {
  document.getElementById("modal-report-details").classList.remove("open");
}

// --- Configuration Manager Tab ---
function selectConfigEnv(env) {
  currentSelectedEnv = env;
  document.querySelectorAll(".env-btn").forEach(btn => btn.classList.remove("active"));
  const btn = document.getElementById(`btn-env-${env === 'development' ? 'dev' : env === 'staging' ? 'stage' : 'prod'}`);
  if (btn) btn.classList.add("active");
  loadSelectedConfig();
}

async function loadSelectedConfig() {
  try {
    const res = await fetch(`${API_BASE}/api/configs/${currentSelectedEnv}`);
    if (!res.ok) throw new Error("Config not found");
    const cfg = await res.json();

    const envLines = Object.entries(cfg.variables || {}).map(([k, v]) => `${k}=${v}`).join("\n");
    document.getElementById("editor-env-vars").value = envLines;

    const infraLines = Object.entries(cfg.infrastructure || {}).map(([k, v]) => `${k}: ${v}`).join("\n");
    document.getElementById("editor-infra").value = infraLines;

    document.getElementById("editor-secrets").value = JSON.stringify(cfg.secrets || [], null, 2);
    document.getElementById("config-change-desc").value = "";
  } catch (err) {
    console.error("Error loading config:", err);
  }
}

async function saveActiveConfig() {
  const desc = document.getElementById("config-change-desc").value || `Manual update for ${currentSelectedEnv}`;
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
        author: "web-operator"
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Update failed");
    }

    const data = await res.json();
    alert(`Success: Created Version ${data.new_version} for ${currentSelectedEnv}`);
    await runValidation(false);
    await fetchEnvironments();
    await fetchDashboardSummary();
  } catch (err) {
    alert("Failed to save config: " + err.message);
  }
}

// --- Change Requests ---
async function loadChangeRequests() {
  try {
    const res = await fetch(`${API_BASE}/api/change-requests`);
    const requests = await res.json();
    const tbody = document.getElementById("change-requests-tbody");
    const badge = document.getElementById("cr-count-badge");
    tbody.innerHTML = "";

    badge.textContent = requests.filter(r => r.status === "PENDING").length;

    if (requests.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No change requests found.</td></tr>`;
      return;
    }

    requests.forEach(cr => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong class="mono text-cyan">#${cr.id}</strong></td>
        <td><span class="env-tag env-tag-${cr.environment.toLowerCase()}">${cr.environment.toUpperCase()}</span></td>
        <td>
          <div style="font-weight:600;">${escapeHtml(cr.title)}</div>
          <div style="font-size:0.8rem; color:var(--text-muted);">${escapeHtml(cr.description || '')}</div>
        </td>
        <td><span class="severity-pill sev-${cr.risk_level.toLowerCase()}">${cr.risk_level}</span></td>
        <td>
          <span class="pill pill-${cr.status === 'APPROVED' ? 'approved' : cr.status === 'REJECTED' ? 'critical' : 'warning'}">
            ${cr.status}
          </span>
        </td>
        <td>${escapeHtml(cr.requested_by)}</td>
        <td>${cr.reviewed_by ? escapeHtml(cr.reviewed_by) : '<span style="color:var(--text-muted);">Unassigned</span>'}</td>
        <td>
          ${cr.status === 'PENDING' ? `
            <div style="display:flex; gap:6px;">
              <button class="btn btn-outline" style="padding:4px 8px; font-size:0.75rem;" onclick="reviewChangeRequest(${cr.id}, 'APPROVED')">Approve</button>
              <button class="btn btn-danger" style="padding:4px 8px; font-size:0.75rem;" onclick="reviewChangeRequest(${cr.id}, 'REJECTED')">Reject</button>
            </div>
          ` : `
            <span style="font-size:0.75rem; color:var(--text-muted);">Completed</span>
          `}
        </td>
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
  const title = document.getElementById("cr-modal-title").value;
  const desc = document.getElementById("cr-modal-desc").value;
  const jsonStr = document.getElementById("cr-modal-json").value;
  const author = document.getElementById("cr-modal-author").value;

  if (!title.trim()) {
    alert("Please provide a title for the change request.");
    return;
  }

  try {
    JSON.parse(jsonStr);
  } catch (e) {
    alert("Invalid JSON format for proposed changes.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/change-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: env,
        title,
        description: desc,
        proposed_changes_json: jsonStr,
        requested_by: author
      })
    });
    if (!res.ok) throw new Error("Submission failed");
    closeNewChangeModal();
    alert("Change request submitted for peer review.");
    await loadChangeRequests();
    await fetchDashboardSummary();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function reviewChangeRequest(id, status) {
  const reviewer = prompt("Enter Reviewer Name:", "Principal-Architect");
  if (!reviewer) return;
  const notes = prompt("Enter Review Notes:", `Verified and ${status}`);

  try {
    const res = await fetch(`${API_BASE}/api/change-requests/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status,
        reviewed_by: reviewer,
        review_notes: notes || ""
      })
    });
    if (!res.ok) throw new Error("Review submission failed");
    const data = await res.json();
    alert(data.message);
    await loadChangeRequests();
    await fetchEnvironments();
    await runValidation(false);
    await fetchDashboardSummary();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

// --- Rollback ---
async function loadVersionOptionsForRollback() {
  const envSelect = document.getElementById("rollback-env-select");
  const targetSelect = document.getElementById("rollback-target-version");
  const env = envSelect.value;

  try {
    const res = await fetch(`${API_BASE}/api/configs/${env}/history`);
    const history = await res.json();
    targetSelect.innerHTML = "";

    history.forEach(h => {
      const opt = document.createElement("option");
      opt.value = h.version;
      opt.textContent = `Version ${h.version} (${h.description || 'Snapshot'}) - By ${h.created_by}`;
      targetSelect.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading versions for rollback:", err);
  }
}

async function submitRollback() {
  const env = document.getElementById("rollback-env-select").value;
  const targetVersion = parseInt(document.getElementById("rollback-target-version").value);
  const reason = document.getElementById("rollback-reason").value || "Operator manual rollback";
  const user = document.getElementById("rollback-user").value || "devops-lead";

  if (!confirm(`Are you sure you want to rollback ${env.toUpperCase()} to Version ${targetVersion}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: env,
        target_version: targetVersion,
        reason,
        performed_by: user
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Rollback failed");
    }

    alert(`Rollback successful! Restored ${env.toUpperCase()} to Version ${targetVersion}.`);
    await fetchEnvironments();
    await runValidation(false);
    await loadRollbackHistory();
    await fetchDashboardSummary();
  } catch (err) {
    alert("Rollback failed: " + err.message);
  }
}

async function loadRollbackHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/rollbacks`);
    const records = await res.json();
    const list = document.getElementById("rollback-history-list");
    list.innerHTML = "";

    if (records.length === 0) {
      list.innerHTML = `<div style="color:var(--text-muted); font-size:0.85rem;">No rollback records yet.</div>`;
      return;
    }

    records.forEach(r => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
          <strong>${r.environment.toUpperCase()}</strong>
          <span style="font-size:0.75rem; color:var(--text-muted);">${r.timestamp}</span>
        </div>
        <div style="font-size:0.85rem;">v${r.from_version} &rarr; <span class="text-cyan font-bold">v${r.to_version}</span></div>
        <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:2px;">Reason: ${escapeHtml(r.reason)} (By ${escapeHtml(r.performed_by)})</div>
      `;
      list.appendChild(item);
    });
  } catch (err) {
    console.error("Error loading rollback records:", err);
  }
}

// --- Audit Trail ---
async function loadAuditLogs() {
  try {
    const res = await fetch(`${API_BASE}/api/audit-logs`);
    const logs = await res.json();
    const tbody = document.getElementById("audit-tbody");
    tbody.innerHTML = "";

    logs.forEach(l => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-size:0.8rem; color:var(--text-muted);">${l.timestamp}</td>
        <td><strong class="mono text-cyan">${escapeHtml(l.user)}</strong></td>
        <td>${escapeHtml(l.action)}</td>
        <td><span class="env-tag env-tag-${l.environment.toLowerCase()}">${l.environment.toUpperCase()}</span></td>
        <td><span class="severity-pill sev-${l.risk_level.toLowerCase()}">${l.risk_level}</span></td>
        <td style="font-size:0.85rem;">${escapeHtml(l.details)}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading audit logs:", err);
  }
}

// --- College Viva Scenarios Injection ---
async function injectScenario(type) {
  let endpoint = "";
  let payload = {};

  if (type === "wrong_db") {
    endpoint = `${API_BASE}/api/configs/production/update`;
    payload = {
      environment: "production",
      raw_env_content: "APP_ENV=production\nDEBUG=false\nDATABASE_HOST=dev-db\nDATABASE_PORT=5432\nAPI_URL=https://api\nLOG_LEVEL=INFO",
      description: "Mistakenly pointed Production to dev-db",
      author: "careless-dev"
    };
  } else if (type === "debug_true") {
    endpoint = `${API_BASE}/api/configs/production/update`;
    payload = {
      environment: "production",
      raw_env_content: "APP_ENV=production\nDEBUG=true\nDATABASE_HOST=prod-db\nDATABASE_PORT=5432\nAPI_URL=https://api\nLOG_LEVEL=INFO",
      description: "Enabled DEBUG=true in Production",
      author: "tester"
    };
  } else if (type === "missing_secret") {
    endpoint = `${API_BASE}/api/configs/production/update`;
    payload = {
      environment: "production",
      raw_secrets_content: JSON.stringify([
        { name: "API_SECRET_KEY", environment: "production", exists: true, age_days: 10 },
        { name: "DATABASE_PASSWORD", environment: "production", exists: false, age_days: 10 }
      ]),
      description: "DATABASE_PASSWORD secret missing in production store",
      author: "ops-engineer"
    };
  } else if (type === "runtime_drift") {
    await fetch(`${API_BASE}/api/runtime/production`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        environment: "production",
        app_version: "1.0.0",
        snapshot_data: { database_host: "prod-db", log_level: "DEBUG" }
      })
    });
    alert("Injected Scenario 4: Live container running LOG_LEVEL=DEBUG while approved config is INFO!");
    await runValidation(false);
    switchTab("drift-tab");
    return;
  } else if (type === "healthy_expected") {
    await resetDemoState();
    alert("Injected Scenario 5: Reset to pristine healthy state with expected variance (dev-db vs prod-db)!");
    switchTab("drift-tab");
    return;
  }

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Scenario injection failed");
    alert(`Scenario Injected: System will now detect the discrepancy!`);
    await fetchEnvironments();
    await runValidation(false);
    switchTab("drift-tab");
  } catch (err) {
    alert("Scenario Error: " + err.message);
  }
}

// --- Simulate Deployment ---
function simulateProductionDeployment() {
  alert("Initiating Production Deployment Pipeline...\nValidating Deployment Safety Gate...");
  runValidation(false).then(() => {
    const isAllowed = document.getElementById("deployment-gate-banner").classList.contains("gate-approved");
    if (isAllowed) {
      alert("✅ DEPLOYMENT PROCEEDED: Configuration verified safe!");
    } else {
      alert("❌ DEPLOYMENT ABORTED: Critical configuration drift detected!");
    }
  });
}

// --- Reset Demo State ---
async function resetDemoState() {
  try {
    await fetch(`${API_BASE}/api/reset-demo`, { method: "POST" });
    await fetchEnvironments();
    await runValidation(false);
    await loadSelectedConfig();
    await loadChangeRequests();
    await loadAuditLogs();
    await loadGitCommits();
    await loadMonitoringStatus();
    await loadValidationReports();
    await loadNotifications();
    await fetchDashboardSummary();
  } catch (err) {
    console.error("Reset demo error:", err);
  }
}

// --- Utilities ---
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
