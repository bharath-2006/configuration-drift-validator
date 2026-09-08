# Configuration Drift Validator
> **Student-Friendly Pre-Production Configuration Safety Gate**  
> *A 3rd-Year College Engineering Project in Computer Science & Information Technology*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg)](https://sqlite.org)
[![Tests](https://img.shields.io/badge/Pytest-20%20Passed-brightgreen.svg)](https://docs.pytest.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 1. Problem Statement & Background

In fast-paced startups, multiple developers share an overloaded staging environment. Because Development, Staging, and Production environments have different infrastructure and settings, developers frequently make environment-specific configuration mistakes (e.g., leaving `DEBUG=true` on, pointing a database connection to `dev-db`, or referencing sandbox API endpoints).

Because staging environments often "work" even with messy configurations, these mistakes slip through staging unnoticed and reach production, leading to catastrophic outages, data corruption, and security vulnerabilities.

### The Solution:
The **Configuration Drift Validator** is an automated pre-production safety gate that cross-validates environment configurations, sanitizes adversarial inputs, verifies secret metadata (without exposing raw credentials), compares live container states, and **blocks production deployment** if any critical configuration drift is detected.

---

## 2. Key Features

- **Multi-Tier Drift Detection:** Ingests and compares Environment Variables (`.env`), Infrastructure manifests (`YAML`), Secret metadata (`JSON`), and live Container Runtime snapshots.
- **Environment-Aware Policies:** Understands that `dev-db` in Dev vs `prod-db` in Prod is an **expected difference**, but `dev-db` in Prod is **CRITICAL**.
- **Adversarial Resilience:** Canonical normalizer cleans whitespace, quotes, numeric strings, and boolean variations to prevent bypasses.
- **Pre-Production Deployment Gate:** Automatically evaluates deployment safety and blocks production release if critical issues are open.
- **Zero-Exposure Secret Metadata:** Tracks secret existence, source, and rotation age without ever handling or displaying raw passwords or tokens.
- **Change Request Review Workflow:** Formal peer review process (Approve/Reject) with risk assessment for high-impact production changes.
- **1-Click Versioned Rollback:** Revert an environment to any previous immutable configuration snapshot with full audit tracking.
- **Tamper-Evident Audit Trail:** Detailed chronological log of every change, validation, approval, and rollback.
- **Modern Web Dashboard:** Responsive single-page interface with real-time gate banners, interactive tables, and 1-click viva demonstration scenarios.

---

## 3. Technology Stack

- **Backend:** Python 3.10+ with **FastAPI** (asynchronous REST API, typed schemas, interactive Swagger UI).
- **Data Parsing & Sanitization:** **Pydantic v2** & **PyYAML**.
- **Database:** **SQLite 3** (local, zero-config, single-file database `drift_validator.db`).
- **Testing:** **pytest** (20 automated unit, integration, adversarial, and gate tests).
- **Frontend:** **Vanilla HTML5 + Custom CSS3 + ES6 JavaScript** (no heavy Node build step required; runs instantly from FastAPI).

---

## 4. System Architecture

```text
                                 ┌─────────────────────────────────┐
                                 │     Developer / DevOps Lead     │
                                 └────────────────┬────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │     Modern Web Dashboard        │
                                 │ (HTML5 / Vanilla CSS / ES6 JS)  │
                                 └────────────────┬────────────────┘
                                                  │ HTTP REST API
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │         FastAPI Backend         │
                                 │           (main.py)             │
                                 └───────┬───────────────┬─────────┘
                                         │               │
                     ┌───────────────────┼───────────────┼──────────────────┐
                     ▼                   ▼               ▼                  ▼
              ┌─────────────┐     ┌─────────────┐ ┌─────────────┐    ┌─────────────┐
              │   Config    │     │    Drift    │ │    Risk     │    │   Change    │
              │  Ingestion  │     │   Engine    │ │  Analyzer   │    │ & Rollback  │
              │ & Normalizer│     │             │ │             │    │   Manager   │
              └──────┬──────┘     └──────┬──────┘ └──────┬──────┘    └──────┬──────┘
                     │                   │               │                  │
                     └───────────────────┼───────────────┴──────────────────┘
                                         ▼
                                 ┌─────────────────────────────────┐
                                 │      SQLite Database Engine     │
                                 │   (sqlite3 / drift_validator.db)│
                                 └───────────────┬─────────────────┘
                                                 │
                                                 ▼
                                 ┌─────────────────────────────────┐
                                 │   Audit Trail & Version Store   │
                                 └─────────────────────────────────┘
```

---

## 5. Quick Installation & Running (Windows / Mac / Linux)

### Step 1: Clone or Navigate to Directory
```powershell
cd "c:\coe project"
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Automated Test Suite
```powershell
python -m pytest -v
```
*(All 20 tests pass in under 1 second).*

### Step 4: Run the Benchmark Experiment
```powershell
python experiments/run_experiment.py
```

### Step 5: Start the Web Dashboard
```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at:
👉 **`http://127.0.0.1:8000`**

*(Swagger API Documentation is available at `http://127.0.0.1:8000/docs`)*

---

## 6. Real Experimental Benchmark Results

We benchmarked the **Configuration Drift Validator** against a standard **Manual Checklist Baseline** across 20 realistic scenarios.

| Metric | Manual Baseline | Proposed Drift Validator | Improvement |
| :--- | :---: | :---: | :---: |
| **Total Scenarios** | 20 | 20 | - |
| **Ground Truth Issues** | 17 | 17 | - |
| **Issues Detected** | 10 | 17 | **+7 issues detected** |
| **Issues Missed (False Negatives)** | 7 | 0 | **0 missed (100% recall)** |
| **False Positives (False Alarms)** | 36 | 0 | **36 false alarms eliminated** |
| **Detection Rate (Recall)** | 58.8% | 100.0% | **+41.2% higher accuracy** |
| **Total Benchmark Runtime** | 100.2 ms | 6.6 ms | **~15x faster** |

*Full scenario breakdown and analysis available in [`docs/experiment.md`](file:///c:/coe%20project/docs/experiment.md).*

---

## 7. Viva Demonstration Walkthrough (12 Steps)

The application includes an interactive **"College Viva Demo Scenarios"** panel supporting this live demonstration:

1. **Clean Initial Baseline:** Click **"Reset Demo"** -> Show Green Banner: *"Production Deployment APPROVED"*.
2. **Inject Mistake:** Click **"Trigger Scenario 1"** (*Production DATABASE_HOST = dev-db*).
3. **Run Validation:** Validator executes instantly.
4. **Inspect Critical Detection:** Banner turns glowing RED: *"Production Deployment BLOCKED: 1 Critical issue"*.
5. **Simulate Deployment Gate:** Click **"🚀 Deploy to Production"** -> Blocked modal appears.
6. **Create Change Request:** Go to **"Change Requests"** -> Submit request to restore `prod-db`.
7. **Review & Approve:** Click **"✓ Approve"** -> Backend automatically applies fix as a new version.
8. **Re-Validate:** System validates updated state -> Banner turns **GREEN**.
9. **Deployment Allowed:** Click **"🚀 Deploy to Production"** -> Deployment Approved.
10. **Audit Trail:** Switch to **"Audit Trail"** tab to view the complete timestamped ledger.
11. **Rollback:** Go to **"Version Rollback"** -> Revert to Version 1 with 1 click.
12. **Edge Cases:** Demonstrate Scenarios 2 (Debug enabled), 3 (Missing secret), 4 (Runtime drift), and 5 (Expected variance).

*Detailed step-by-step presentation script available in [`docs/user-guide.md`](file:///c:/coe%20project/docs/user-guide.md).*

---

## 8. College Project Deliverables Map

- **Source Code:**
  - Backend API: [`backend/main.py`](file:///c:/coe%20project/backend/main.py)
  - Drift Engine: [`backend/drift_engine.py`](file:///c:/coe%20project/backend/drift_engine.py)
  - Validation Policy: [`backend/validation_policy.py`](file:///c:/coe%20project/backend/validation_policy.py)
  - Risk Analyzer: [`backend/risk_engine.py`](file:///c:/coe%20project/backend/risk_engine.py)
  - Version Rollback: [`backend/rollback.py`](file:///c:/coe%20project/backend/rollback.py)
  - Audit Trail: [`backend/audit.py`](file:///c:/coe%20project/backend/audit.py)
  - Web UI: [`frontend/index.html`](file:///c:/coe%20project/frontend/index.html), [`frontend/style.css`](file:///c:/coe%20project/frontend/style.css), [`frontend/app.js`](file:///c:/coe%20project/frontend/app.js)
- **Documentation:**
  - Full 14-Chapter College Report: [`docs/college-project-report.md`](file:///c:/coe%20project/docs/college-project-report.md)
  - 20 Viva Q&As: [`docs/viva-prep.md`](file:///c:/coe%20project/docs/viva-prep.md)
  - System Architecture & Sequence Diagrams: [`docs/architecture.md`](file:///c:/coe%20project/docs/architecture.md)
  - Empirical Experiment & Benchmark: [`docs/experiment.md`](file:///c:/coe%20project/docs/experiment.md)
  - Risk Register: [`docs/risk-register.md`](file:///c:/coe%20project/docs/risk-register.md)
  - User Guide & Walkthrough: [`docs/user-guide.md`](file:///c:/coe%20project/docs/user-guide.md)
- **Automated Tests:**
  - Pytest Suites: [`tests/test_validator.py`](file:///c:/coe%20project/tests/test_validator.py), [`tests/test_drift.py`](file:///c:/coe%20project/tests/test_drift.py), [`tests/test_adversarial.py`](file:///c:/coe%20project/tests/test_adversarial.py), [`tests/test_rollback.py`](file:///c:/coe%20project/tests/test_rollback.py), [`tests/test_api_gate.py`](file:///c:/coe%20project/tests/test_api_gate.py)
- **Configuration & Snapshots:**
  - Environments: `configs/development/`, `configs/staging/`, `configs/production/`
  - Runtime Snapshots: `runtime_snapshots/`
