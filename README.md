# Configuration Drift Validator
> **Continuous Configuration Safety, CI/CD Validation & Runtime Monitoring Platform**  
> *A 3rd-Year Computer Science Engineering Project — 100% Phase 3 Completed*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg)](https://sqlite.org)
[![Tests](https://img.shields.io/badge/Pytest-70%20Passed-brightgreen.svg)](https://docs.pytest.org)
[![Coverage](https://img.shields.io/badge/Coverage-77%25-brightgreen.svg)](docs/testing.md)
[![CI/CD](https://img.shields.io/badge/GitHub%20Actions-Automated%20Gate-success.svg)](.github/workflows/configuration-validation.yml)
[![Phase](https://img.shields.io/badge/Phase%20Completion-100%25%20Completed-brightgreen.svg)](README.md)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents
1. [Project Overview & Evolution](#1-project-overview--evolution)
2. [Problem Statement & Process Comparison](#2-problem-statement--process-comparison)
3. [Main Features & Architecture](#3-main-features--architecture)
4. [Technology Stack](#4-technology-stack)
5. [Installation & Setup on Windows](#5-installation--setup-on-windows)
6. [How to Run the Application](#6-how-to-run-the-application)
7. [Automated Testing & Coverage](#7-automated-testing--coverage)
8. [Error Boundaries & Robustness](#8-error-boundaries--robustness)
9. [REST API Endpoint Summary](#9-rest-api-endpoint-summary)
10. [Database Schema Summary](#10-database-schema-summary)
11. [Configuration Parsers & Formats](#11-configuration-parsers--formats)
12. [CI/CD Validation & Pre-Deployment Gate](#12-cicd-validation--pre-deployment-gate)
13. [Continuous Monitoring & Runtime Drift](#13-continuous-monitoring--runtime-drift)
14. [College Viva Demonstration Walkthrough](#14-college-viva-demonstration-walkthrough)
15. [Empirical Benchmark Results](#15-empirical-benchmark-results)
16. [Troubleshooting](#16-troubleshooting)
17. [Known Limitations](#17-known-limitations)
18. [Documentation Links](#18-documentation-links)

---

## 1. Project Overview & Evolution

In modern software development, multiple developers deploy features across Development, Staging, and Production environments. Because environments naturally have different settings, developers frequently make environment-specific configuration errors (e.g., leaving `DEBUG=true` on, pointing database connections to `dev-db`, referencing test payment gateways, or neglecting secret rotation).

### Development Progression:
- **Phase 1 (Initial 35%):** Foundational prototype detecting configuration drift across `.env`, `infra.yaml`, secret metadata, and container snapshots with a binary deployment safety gate, rollback mechanism, and 20 tests.
- **Phase 2 (70%):** Transformed into a comprehensive Continuous Configuration Safety platform with Git commit change detection, automated CI/CD validation CLI, 6-stage pre-deployment pipeline, runtime container monitoring, risk scoring (0-100), notifications, and 41 tests.
- **Phase 3 (Final 100% Review Readiness):**
  1. **Granular Unit Testing Documentation (`docs/testing.md`)**: Full documentation across all 70 tests and 9 test modules.
  2. **Error Boundaries & Robustness (`docs/error-handling.md`)**: Documented all system error boundaries, security sanitizers, circular reference safeguards, malformed syntax handlers, and secret redaction.
  3. **Complete REST API Reference (`docs/api-reference.md`)**: Documented all 31 active FastAPI endpoints with sample payloads and status codes.
  4. **Database Schema & ER Documentation (`docs/database-schema.md`)**: Documented all 15 SQLite tables with column constraints and a Mermaid ER diagram.
  5. **Security Hardening (`backend/security.py`)**: Input validation (environment whitelisting), path traversal stripping, upload payload size limits, and sensitive key masking.
  6. **Safe Rollback Verification**: End-to-end verification that rolling back restored configuration values (e.g. `DATABASE_HOST=dev-db` -> `prod-db`) and successfully eliminates critical drift.
  7. **Expanded Test Suite (70 tests)** with **77% statement coverage**.

---

## 2. Problem Statement & Process Comparison

```text
BEFORE AUTOMATED GATE:
Developer ──► Configuration ──► Manual Inspection ──► Accidental Leak to Production ──► Outage / Leak

WITH CONFIGURATION DRIFT VALIDATOR:
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

## 3. Main Features & Architecture

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

For full architectural details, see [System Architecture](docs/architecture.md).

---

## 4. Technology Stack

- **Backend:** Python 3.10+ (tested on Python 3.14) with **FastAPI** & **Uvicorn**.
- **Data Validation & Sanitization:** **Pydantic v2**, **PyYAML 6.0+**, and **jsonschema** (Draft-07).
- **Database:** **SQLite 3** (`PRAGMA foreign_keys = ON`, 15 tables).
- **Testing:** **pytest 9.0+**, **pytest-cov**, and **HTTPX** (`TestClient`).
- **DevOps & CI/CD:** **GitHub Actions**, Git, Docker Compose.
- **Frontend:** Responsive HTML5/CSS3 Dark-Mode Glassmorphism Design System, ES6 JavaScript.

---

## 5. Installation & Setup on Windows

### Step 1: Open Terminal & Navigate to Project
```powershell
cd C:\Users\bhara\.gemini\antigravity\scratch\configuration-drift-validator
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
pip install pytest-cov jsonschema
```

---

## 6. How to Run the Application

### Start the Web Dashboard
```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at:
- **Web Dashboard**: **`http://127.0.0.1:8000`**
- **Interactive Swagger API Docs**: **`http://127.0.0.1:8000/docs`**
- **ReDoc API Docs**: **`http://127.0.0.1:8000/redoc`**

---

## 7. Automated Testing & Coverage

The repository contains an automated test suite with **70 passing tests** across 9 test modules.

### Run Tests via Windows PowerShell
```powershell
# Run all tests in verbose mode:
python -m pytest -v

# Run with statement coverage report:
python -m pytest --cov=backend --cov-report=term-missing
```

### Test Suite Execution Output
```
======================= 70 passed in 1.75s ========================
```
- **Overall Statement Coverage**: **77%**
- **100% Coverage**: `backend/risk_engine.py`, `backend/schemas.py`, `backend/audit.py`
- **90%+ Coverage**: `backend/drift_engine.py` (99%), `backend/pre_deployment.py` (97%), `backend/database.py` (96%), `backend/validation_policy.py` (93%), `backend/security.py` (92%), `backend/rollback.py` (90%)
- **80%+ Coverage**: `backend/schema_validator.py` (88%), `backend/monitoring.py` (85%), `backend/normalizer.py` (82%)

For full test scenarios and documentation, see [Detailed Unit Testing Documentation](docs/testing.md).

---

## 8. Error Boundaries & Robustness

The system implements strict error boundaries and security controls:
- **Security Validation & Sanitization**: Validates environment names against strict whitelists, strips directory traversal (`../`) from filenames, limits upload payload sizes to prevent DoS, and detects/masks sensitive secret keys.
- **Artifact Parser Guard**: Gracefully handles malformed YAML, missing delimiters in `.env`, and unclosed quotes with HTTP 400.
- **JSON Schema Validation Guard**: Rejects invalid schemas, unexpected keys, and type mismatches.
- **Circular Reference Guard**: Detects recursive variable interpolations (`A -> ${B}`, `B -> ${A}`) to prevent stack overflows.
- **Safe Rollback Guard**: Verifies target version existence, atomically restores configuration files and active pointers, and clears post-rollback drift without corrupting state.
- **Secret Redaction**: Strictly manages secret **metadata** without ever storing, accepting, or exposing plaintext secrets.

For full error boundary mappings, see [Error Boundaries and Handling](docs/error-handling.md).

---

## 9. REST API Endpoint Summary

The application exposes 31 REST endpoints under `/api/*`:
- `GET /api/health` — Verifies system health and database connectivity.
- `GET /api/environments` — Lists all registered environments.
- `GET /api/configs/{environment}` — Retrieves active configuration parameters.
- `GET /api/configs/{environment}/history` — Retrieves configuration version history.
- `POST /api/configs/parse-artifact` — Parses `.env`, Docker Compose, or K8s ConfigMap.
- `POST /api/configs/{environment}/update` — Updates configuration with version increment.
- `POST /api/validate` — Executes 5-tier drift validation engine.
- `GET /api/deployment-gate` — Returns production release gate decision (`APPROVED` vs `BLOCKED`).
- `POST /api/pre-deployment-check` — Evaluates 6-stage pre-deployment pipeline.
- `GET /api/change-requests` & `POST /api/change-requests` — Manages change review workflow.
- `POST /api/change-requests/{id}/review` — Authorizes or rejects change requests.
- `POST /api/rollback` — Reverts a configuration key to its previous version.
- `GET /api/rollbacks` — Lists historical rollback records.
- `GET /api/audit-logs` — Retrieves chronological audit logs.
- `POST /api/reset-demo` — Resets database to standard reproducible state.
- `GET /api/monitoring/status` & `POST /api/monitoring/scan` — Background drift monitoring.
- `GET /api/notifications` — In-app alerts feed.
- `GET /api/reports/validation-runs` — Lists validation run reports with JSON/CSV export.
- `GET /api/dashboard/summary` — Aggregates summary analytics and metrics.

For full schemas and examples, see [REST API Reference](docs/api-reference.md).

---

## 10. Database Schema Summary

The database uses SQLite 3 with foreign key enforcement (`PRAGMA foreign_keys = ON`) across **15 normalized tables**:
1. `environments`: Tracks deployment stages and health status.
2. `configuration_versions`: Stores versioned key-value parameters with active flags.
3. `environment_variables`: Tracks OS-level environment variables.
4. `infrastructure_definitions`: Retains YAML infrastructure definitions as JSON.
5. `secret_metadata`: Stores metadata (existence flag, rotation age) without raw secrets.
6. `runtime_snapshots`: Point-in-time snapshots of running processes.
7. `validation_runs`: Summarizes validation runs with release gate decisions.
8. `drift_results`: Output records of every detected discrepancy.
9. `change_requests`: Proposed modifications awaiting authorization.
10. `rollback_records`: Immutable records of rollback operations.
11. `audit_logs`: Immutable chronological log of all platform operations.
12. `git_commits`: Simulated git commit log for pre-deployment CI hooks.
13. `notifications`: In-app notification alerts for drift and gate status.
14. `deployment_checks`: Historic log of automated deployment gate decisions.
15. `monitoring_events`: Background drift scanner event log.

For complete ER diagrams, see [Database Schema Documentation](docs/database-schema.md).

---

## 11. Configuration Parsers & Formats

The configuration parsing subsystem (`backend/artifact_parser.py`) supports:
- **Application YAML/JSON Configs**: Flattens nested keys into dot-notation paths (`database.host`, `logging.level`).
- **Docker Compose (v2/v3)**: Extracts services, container images, port bindings, and environment variables into `compose.<service>.*`.
- **Kubernetes ConfigMaps**: Parses standard Kubernetes ConfigMap manifests into `k8s.<name>.*`.
- **Environment Files (`.env`)**: Parses standard `KEY=VALUE` pairs with comment support.

---

## 12. CI/CD Validation & Pre-Deployment Gate

The CLI validator simulates a CI/CD pre-deployment pipeline:
```powershell
python -m backend.ci_validator --env production
```
- Returns exit code `0` if configuration is safe (`PASS`).
- Returns exit code `1` if Critical/High drift is detected (`BLOCKED`).
- Generates a timestamped JSON audit artifact under `reports/`.

---

## 13. Continuous Monitoring & Runtime Drift

The continuous monitoring subsystem (`backend/monitoring.py`) periodically compares declared database baselines against active container memory snapshots (`runtime_snapshots/prod_runtime.json`). If out-of-band modifications occur (e.g., container hot-patched with `DEBUG=true`), the scanner raises a `RUNTIME DRIFT` alert and notifies the dashboard.

---

## 14. College Viva Demonstration Walkthrough

The platform supports a complete 16-step demonstration scenario:
1. **Open Dashboard:** Navigate to `http://127.0.0.1:8000` (all stages `HEALTHY`).
2. **Inject Error:** In Configurations tab, edit Production `DATABASE_HOST=prod-db` to `dev-db` and save.
3. **Simulate Git Commit:** Submit a commit with `{"DATABASE_HOST": "dev-db"}`.
4. **Inspect CI/CD Validation:** Observe commit evaluated as `BLOCKED` with Risk Score `95/100 (CRITICAL RISK)`.
5. **Run Drift Validation:** Click **Run Drift Validation**.
6. **Verify Deployment Gate:** Banner turns red: `❌ DEPLOYMENT BLOCKED`.
7. **Execute Pre-Deployment Gate:** Validate Before Deployment tab shows Stage 2 (Environment Check) failed.
8. **Inspect Notification:** Bell badge updates with critical alert.
9. **Submit Change Request:** Propose restoring `{"DATABASE_HOST": "prod-db"}`.
10. **Approve Change Request:** Authorize request to apply corrected configuration.
11. **Run Validation Again:** Click **Run Drift Validation** &rarr; Banner turns green: `✅ DEPLOYMENT APPROVED`.
12. **Inspect Audit Trail:** View tamper-evident activity ledger.
13. **Inspect Configuration History & Diff:** View side-by-side `OLD VALUE → NEW VALUE`.
14. **Inspect Continuous Monitoring:** View container synchronization status.
15. **Simulate Runtime Drift:** Inject `DEBUG=true` into container &rarr; monitor detects out-of-band divergence.
16. **Execute Rollback:** Click **Version Rollback** &rarr; restore to prior version with one click.

For full guide, see [User Guide](docs/user-guide.md) and [Viva Prep Guide](docs/viva-prep.md).

---

## 15. Empirical Benchmark Results

Evaluated across 20 realistic deployment scenarios:

| Metric | Phase 1 (Original 35%) | Phase 2 & 3 (100%) | Measurable Impact |
| :--- | :---: | :---: | :---: |
| **Automated Checks Performed** | 200 checks | **500 checks** | **+150% more comprehensive verification** |
| **True Configuration Issues** | 17 | 17 | Ground truth across 20 scenarios |
| **Issues Detected** | 17 | 17 | **100% recall (0 false negatives)** |
| **Issues Missed** | 0 | 0 | Zero configuration leaks |
| **False Positives** | 0 | 0 | **Zero false alarms on valid environment differences** |
| **Detection Rate (Recall)** | 100.0% | 100.0% | Maximum reliability |
| **Deployment Blocks Triggered** | 10 | 10 | Safely prevented hazardous production releases |
| **Manual Inspection Steps Required** | 60 steps | **0 steps** | **100% automated via CI/CD gating** |
| **Total Validation Time** | 5.09 ms | **4.08 ms** | **Sub-millisecond verification (~0.20 ms / scenario)** |

Run benchmark anytime:
```powershell
python experiments/phase2_benchmark.py
```

For full details, see [Empirical Experiment Report](docs/experiment.md).

---

## 16. Troubleshooting

- **Port 8000 in use**:
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
  Stop-Process -Id <PID> -Force
  ```
- **Reset database to clean demo state**:
  Click **Reset Demo** in the dashboard header or call `POST /api/reset-demo`.

---

## 17. Known Limitations

1. **Simulated Runtime Snapshots**: Telemetry uses periodic JSON fixtures rather than live Kubernetes daemon hooks.
2. **Local SQLite Persistence**: Uses a self-contained local SQLite file for laptop reproducibility rather than distributed multi-cloud PostgreSQL.
3. **Role Header Authentication**: User identity is provided via request parameters for demonstration simplicity rather than cryptographic OAuth2/JWT verification.

---

## 18. Documentation Links

- 📖 [Detailed Unit Testing Documentation](docs/testing.md)
- 🛡️ [Error Boundaries and Error Handling](docs/error-handling.md)
- 🔌 [REST API Reference](docs/api-reference.md)
- 🗄️ [Database Schema & ER Diagram](docs/database-schema.md)
- 🏛️ [System Architecture](docs/architecture.md)
- 📊 [Empirical Experiment Report](docs/experiment.md)
- 🎯 [User Guide & Viva Demonstration](docs/user-guide.md)
- ⚠️ [Risk Register & Mitigation Matrix](docs/risk-register.md)
- 🎓 [College Viva Questions & Answers](docs/viva-prep.md)
- 📑 [Full College Project Dissertation Report](docs/college-project-report.md)
