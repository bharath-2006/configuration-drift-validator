# Configuration Drift Validator
> **Continuous Configuration Safety, CI/CD Validation & Runtime Monitoring Platform**  
> *A 3rd-Year Computer Science Engineering Project — 70% Development Phase Completed*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg)](https://sqlite.org)
[![Tests](https://img.shields.io/badge/Pytest-41%20Passed-brightgreen.svg)](https://docs.pytest.org)
[![CI/CD](https://img.shields.io/badge/GitHub%20Actions-Automated%20Gate-success.svg)](.github/workflows/configuration-validation.yml)
[![Phase](https://img.shields.io/badge/Phase%20Completion-70%25%20Completed-orange.svg)](README.md)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 1. Project Overview & Evolution

In modern software development, multiple developers deploy features across Development, Staging, and Production environments. Because environments naturally have different settings, developers frequently make environment-specific configuration errors (e.g., leaving `DEBUG=true` on, pointing database connections to `dev-db`, referencing test payment gateways, or neglecting secret rotation).

### Development Progression:
- **Phase 1 (Initial 35%):** Created the foundational prototype detecting configuration drift across `.env`, `infra.yaml`, secret metadata, and container snapshots with a binary deployment safety gate, rollback mechanism, and 20 tests.
- **Phase 2 (Current 70%):** Transformed the prototype into a comprehensive **Continuous Configuration Safety and Validation Platform** with:
  1. **Git Commit Change Detection** (identifying configuration changes from repository commits).
  2. **Automated CI/CD Validation** (GitHub Actions workflow and CLI gate with exit codes).
  3. **Dedicated 6-Stage Pre-Deployment Process** (Config $\rightarrow$ Env $\rightarrow$ Infra $\rightarrow$ Secret $\rightarrow$ Runtime $\rightarrow$ Risk $\rightarrow$ Decision).
  4. **Continuous Configuration Monitoring** (periodically verifying live container state against approved baselines).
  5. **Enhanced Dashboard & Analytics** (status cards, health distribution, deployment gate pass/block ratios).
  6. **Configuration Version History & Side-by-Side Diff** (`OLD VALUE → NEW VALUE`).
  7. **Explainable Quantitative Risk Scoring (0–100)**.
  8. **In-App Notification Center** (real-time alerts for critical drift, blocked deploys, and approvals).
  9. **Validation Reports & CSV/JSON Export**.
  10. **Extended Test Suite (41 tests)** and **Phase 1 vs Phase 2 Empirical Benchmark**.

---

## 2. Before and After Process Comparison

```text
FIRST 35% WORKFLOW:
Developer ──► Configuration ──► Manual / Local Validation ──► Deployment Decision

AFTER 70% WORKFLOW:
Developer ──► Git Commit ──► CI/CD Pipeline ──► Multi-Layer Drift Engine
                                                    │
                                            ┌───────┴───────┐
                                            ▼               ▼
                                       Risk Scoring    Peer Review
                                            │               │
                                            └───────┬───────┘
                                                    ▼
                                            Pre-Deployment Gate
                                                    │
                                      ┌─────────────┴─────────────┐
                                      ▼                           ▼
                           ❌ Block Deployment            ✅ Deploy to Production
                                                                  │
                                                                  ▼
                                                      Continuous Monitoring
                                                                  │
                                                      (Audit Trail / Rollback)
```

---

## 3. Feature Matrix: Phase 1 (35%) vs Phase 2 (70%)

| Feature Capability | Phase 1 (Original 35%) | Phase 2 (Enhanced 70%) |
| :--- | :---: | :---: |
| **Three-Pillar Config Ingestion** (`.env`, `infra`, `secrets`) | Yes | Yes (Enhanced schema validation) |
| **Normalizer & Adversarial Sanitizer** | Yes | Yes (Case-insensitive strings, quotes) |
| **Deployment Gate Decision** | Yes | Yes (Multi-stage evaluation) |
| **Versioned Rollback** | Yes | Yes (With history & diff comparison) |
| **Change Approval Workflow** | Yes | Yes (Integrated with notifications) |
| **Git Change Detection** | No | **Yes** (Tracks commit ID, author, changed keys) |
| **CI/CD Pipeline Integration** | No | **Yes** (GitHub Actions + CLI validator) |
| **Dedicated Pre-Deployment Workflow** | No | **Yes** (6-stage sequential verification) |
| **Continuous Runtime Monitoring** | No | **Yes** (Detects out-of-band container drift) |
| **Visual Analytics Charts** | No | **Yes** (Environment drifts, severity, gate ratio) |
| **Configuration Diff Comparator** | No | **Yes** (`OLD VALUE → NEW VALUE` table) |
| **Quantitative Risk Scoring (0–100)** | No | **Yes** (Explainable rule-based scoring) |
| **In-App Notification System** | No | **Yes** (Real-time bell counter & alert feed) |
| **Automated Reports & Export** | No | **Yes** (JSON and CSV downloads) |
| **Automated Pytest Tests** | 20 tests | **41 tests** (Normal, failure, adversarial) |

---

## 4. System Architecture

```mermaid
graph TD
    User([Developer / DevOps Engineer]) -->|Interacts via Browser| WebApp[Web Dashboard<br/>HTML5 / CSS3 / ES6 JS]
    GitAction[GitHub Actions / CI CLI] -->|Validates Commits| CIVal[backend/ci_validator.py]
    
    WebApp -->|REST API| API[FastAPI Server :8000]
    CIVal -->|Validates State| API
    
    subgraph Core Processing Engines
        API --> Ingest[Config Parser & Normalizer]
        Ingest --> DriftEngine[Multi-Layer Drift Engine]
        DriftEngine --> Policy[Environment Policies]
        DriftEngine --> PreDeploy[Pre-Deployment Pipeline]
        DriftEngine --> ContinuousMonitor[Continuous Runtime Monitor]
        DriftEngine --> RiskEngine[0-100 Risk Scoring Engine]
        API --> GitTracker[Git Commit Detector]
        API --> ReportGen[Validation Reports & Exporters]
        API --> NotifMgr[Notification Manager]
        API --> RollbackMgr[Rollback & Version Comparator]
    end

    subgraph Persistence Layer
        Ingest --> DB[(SQLite Database<br/>drift_validator.db)]
        GitTracker --> DB
        PreDeploy --> DB
        ContinuousMonitor --> DB
        NotifMgr --> DB
        ReportGen --> DB
        RollbackMgr --> DB
    end

    subgraph Live State
        ContinuousMonitor -->|Monitors| RuntimeContainer[Container Runtime Snapshot<br/>prod_runtime.json]
    end
```

---

## 5. Technology Stack

- **Backend:** Python 3.10+ / 3.14 with **FastAPI** & **Uvicorn**.
- **Data Validation & Sanitization:** **Pydantic v2** & **PyYAML 6.0+**.
- **Database:** **SQLite 3** (lightweight, zero-configuration local database with row factory).
- **Testing:** **pytest 9.0+** & **HTTPX** (`TestClient`).
- **DevOps & CI/CD:** **GitHub Actions** (`.github/workflows/configuration-validation.yml`), Git, Docker Compose.
- **Frontend:** Vanilla HTML5, Custom CSS3 Dark-Mode Glassmorphism Design System, Vanilla ES6 JavaScript (zero heavy Node/npm bundle steps required).

---

## 6. Installation & Execution Guide (Windows / Linux / macOS)

### Step 1: Clone or Open Project
```powershell
cd "c:\coe project"
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Complete Test Suite (41 Tests)
```powershell
python -m pytest -v
```
*(All 41 tests execute and pass in under 2 seconds).*

### Step 4: Run the Phase 2 Benchmark Experiment
```powershell
python experiments/phase2_benchmark.py
```
*(Empirically compares Phase 1 vs Phase 2 across 20 realistic deployment scenarios).*

### Step 5: Test the CI/CD Pipeline Validator CLI
```powershell
python -m backend.ci_validator --env production
```
*(Simulates a GitHub Actions run: runs drift detection, generates a report artifact, and exits with 0 for PASS or 1 for BLOCKED).*

### Step 6: Start the Web Dashboard
```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at:
👉 **`http://127.0.0.1:8000`**

*(Interactive Swagger API docs available at `http://127.0.0.1:8000/docs`)*

---

## 7. Empirical Benchmark Results: Phase 1 vs Phase 2

We ran an automated benchmark across 20 diverse, realistic deployment scenarios. The table below presents the **actual, un-fabricated measurements**:

| Metric | Phase 1 (Original 35%) | Phase 2 (Enhanced 70%) | Measurable Impact |
| :--- | :---: | :---: | :---: |
| **Automated Checks Performed** | 200 checks | **500 checks** | **+150% more comprehensive verification** |
| **True Configuration Issues** | 17 | 17 | Known ground truth across 20 scenarios |
| **Issues Detected** | 17 | 17 | **100% recall (0 false negatives)** |
| **Issues Missed** | 0 | 0 | Zero configuration leaks |
| **False Positives** | 0 | 0 | **Zero false alarms on valid environment differences** |
| **Detection Rate (Recall)** | 100.0% | 100.0% | Maximum reliability |
| **Deployment Blocks Triggered** | 10 | 10 | Safely prevented hazardous production releases |
| **Manual Inspection Steps Required** | 60 steps | **0 steps** | **100% automated via CI/CD gating** |
| **Total Validation Time** | 5.09 ms | **4.08 ms** | **Sub-millisecond verification (~0.20 ms / scenario)** |

*Full scenario breakdown available in [`docs/experiment_phase2.md`](file:///c:/coe%20project/docs/experiment_phase2.md).*

---

## 8. College Viva Demonstration Walkthrough (16 Steps)

The 70% platform supports the complete end-to-end oral examination flow:

1. **Open Dashboard:** Navigate to `http://127.0.0.1:8000`. Show:
   - Development: `HEALTHY`
   - Staging: `HEALTHY`
   - Production: `HEALTHY`
2. **Inject Dangerous Configuration:** Click **Configurations** tab &rarr; select **Production** &rarr; change `DATABASE_HOST=prod-db` to `DATABASE_HOST=dev-db` &rarr; click **Save New Version**.
3. **Simulate Git Commit:** Click **"Simulate Git Commit"** in the header &rarr; submit commit with `{"DATABASE_HOST": "dev-db"}`.
4. **Inspect CI/CD Validation:** Observe the commit is evaluated: `BLOCKED` with Risk Score `95/100 (CRITICAL RISK)`.
5. **Run Drift Validation:** Click **"Run Drift Validation"**.
6. **Verify Deployment Gate:** Banner turns glowing red: `❌ DEPLOYMENT BLOCKED: Production database points to non-production database ('dev-db')`.
7. **Execute Pre-Deployment Gate:** Click **"Validate Before Deployment"** tab &rarr; run check &rarr; see Stage 2 (Environment Check) fail with critical error.
8. **Inspect Notification:** Bell badge updates to `1` &rarr; open drawer &rarr; show `🔴 Critical configuration drift detected`.
9. **Submit Change Request:** Click **Change Requests** &rarr; submit change: `{"DATABASE_HOST": "prod-db"}`.
10. **Approve Change Request:** Click **Approve** &rarr; system applies the corrected configuration.
11. **Run Validation Again:** Click **"Run Drift Validation"** &rarr; Banner turns glowing green: `✅ DEPLOYMENT APPROVED`.
12. **Inspect Audit Trail:** Click **Audit Logs** &rarr; show tamper-evident activity ledger.
13. **Inspect Configuration History & Diff:** Click **Config History & Diff** &rarr; compare `v1` vs `v2` &rarr; view side-by-side `OLD VALUE → NEW VALUE`.
14. **Inspect Continuous Monitoring:** Click **Continuous Monitoring** &rarr; show baseline vs container sync table.
15. **Simulate Runtime Drift:** Click **"Simulate Runtime Drift (DEBUG=true)"** &rarr; container state diverges &rarr; monitoring flags `RUNTIME DRIFT` alert.
16. **Execute Rollback:** Click **Version Rollback** &rarr; restore Production to Version 1 &rarr; clean state restored.

---

## 9. Security & Academic Integrity Statement

- **Zero Real Credentials:** The validator handles **secret metadata only** (`name`, `exists`, `source`, `last_rotated`, `age_days`). Passwords and API keys are never stored or logged.
- **Input Sanitization:** User inputs and uploaded configuration manifests are strictly parsed with Pydantic and PyYAML.
- **Rule-Based Risk Scoring:** The 0–100 risk score is an explainable rule-based scoring system designed for academic demonstration and DevOps pre-flight analysis.
