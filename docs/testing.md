# Detailed Unit Testing & Test Suite Documentation

## 1. Testing Objectives

The testing suite for the **Configuration Drift Validator** is engineered to provide rigorous, automated verification across all layers of the configuration management and pre-deployment lifecycle:
- Validate value normalization across diverse representations (booleans, casing, numbers, floating points, whitespace, quotes, delimiters).
- Verify environment-aware policy evaluation (preventing false alarms when differences between development, staging, and production are intentional).
- Detect dangerous cross-environment contamination (preventing development endpoints or test credentials from contaminating production).
- Enforce strict security baseline rules (`DEBUG=false`, `auth_enabled=true`, `ssl=true`, `rate_limit_enabled=true`).
- Validate secret metadata hygiene and detect missing or un-rotated secrets (>90 days) without ever exposing plaintext secret strings.
- Detect runtime drift between static declared repository configuration and running in-memory process snapshots.
- Verify deterministic rollback restoration, ensuring version numbers increment monotonically and prior configurations are reliably restored.
- Verify audit trail persistence for all operations, users, and risk tiers.
- Validate multi-format configuration artifact parsing:
  - Standard `.env` files (including comments, missing delimiters, unclosed quotes, duplicate keys).
  - Docker Compose v2/v3 manifests (ports, service environments, replicas, missing services).
  - Kubernetes `ConfigMap` YAML manifests (syntax, kind matching, data mappings).
- Test JSON Schema validation against formal draft-07 schemas (`environment.schema.json`, `drift-rule.schema.json`, `runtime-snapshot.schema.json`).
- Ensure pre-deployment CI gates correctly block deployments with Critical drift and generate reproducible audit reports.

---

## 2. Testing Tools and Dependencies

The test suite uses modern, industry-standard Python testing frameworks:

| Dependency | Purpose |
| :--- | :--- |
| **`pytest` (>=8.3.0)** | Primary test runner, fixture management, and assertion engine. |
| **`pytest-cov` (>=7.1.0)** | Statement and branch coverage analysis across backend modules. |
| **`starlette.testclient.TestClient` / `httpx`** | In-memory HTTP client testing FastAPI REST routes without opening external network sockets. |
| **`jsonschema` (>=4.26.0)** | Formal draft-07 JSON Schema validation against environment and drift models. |
| **`sqlite3` (file-backed & in-memory)** | Relational database fixture with `PRAGMA foreign_keys = ON` enforcement. |

### Running Tests via Windows PowerShell

Run complete test suite in verbose mode:
```powershell
python -m pytest -v
```

Run test suite with statement coverage report:
```powershell
python -m pytest --cov=backend --cov-report=term-missing
```

Run a specific test file:
```powershell
python -m pytest tests/test_parsers_and_edge_cases.py -v
```

---

## 3. Interpreting Test Results

- **`PASSED` (Green)**: The assertion or scenario executed successfully and satisfied all invariant conditions.
- **`FAILED` (Red)**: An assertion error occurred, or an unhandled unexpected exception was raised. The traceback highlights the exact line and failed condition.
- **`SKIPPED` (Yellow)**: The test was deliberately skipped due to environment or conditional triggers.

---

## 4. Test Suite Structure & Coverage Summary

The repository contains **8 automated test modules** comprising **61 passing automated tests**:

```
tests/
├── test_adversarial.py              # Whitespace, casing, numeric representations, subtle URI contamination
├── test_api_gate.py                 # REST API endpoints, change request review cycle, deployment gate
├── test_drift.py                    # 5 Core drift detection cases (DEBUG, DB, secrets, runtime, expected diffs)
├── test_parsers_and_edge_cases.py   # Env parser, Docker Compose, K8s ConfigMap, JSON Schema, cycles, rollback
├── test_phase2_scenarios.py         # 20 Comprehensive Phase 2 test scenarios (normal, failure, adversarial)
├── test_rollback.py                 # Configuration versioning, rollback execution, and audit logging
├── test_validator.py                # Value normalization and host extraction utilities
└── test_viva_demonstration_flow.py  # End-to-end 16-step viva demonstration integration flow
```

### Coverage Metrics
- **Overall Statement Coverage**: **76%**
- **Core Modules Coverage**:
  - `backend/risk_engine.py`: **100%**
  - `backend/schemas.py`: **100%**
  - `backend/audit.py`: **100%**
  - `backend/drift_engine.py`: **99%**
  - `backend/pre_deployment.py`: **97%**
  - `backend/validation_policy.py`: **93%**
  - `backend/database.py`: **89%**
  - `backend/rollback.py`: **89%**
  - `backend/schema_validator.py`: **88%**
  - `backend/monitoring.py`: **85%**
  - `backend/normalizer.py`: **82%**
  - `backend/artifact_parser.py`: **78%**
  - `backend/git_detector.py`: **71%**
  - `backend/main.py`: **70%**

---

## 5. Granular Component Test Documentation

### 5.1 Docker Compose Parser Tests
- **Test File**: `tests/test_parsers_and_edge_cases.py`
- **Functions**: `test_valid_docker_compose_yaml`, `test_docker_compose_list_format_environment`, `test_malformed_docker_compose_yaml`, `test_docker_compose_missing_services`
- **Component Tested**: `backend/artifact_parser.py:parse_docker_compose_content()`
- **Inputs**:
  - Standard v3 Compose YAML with mapping `environment` (`DATABASE_HOST: prod-db`).
  - List format `environment` (`- DATABASE_HOST=prod-db`).
  - Malformed YAML syntax (`services: [unclosed`).
  - Missing `services` key.
- **Expected Results**: Extracts environment variables, ports, image tags, and replica limits. Malformed files raise `ArtifactParseError` with clean descriptions without crashing.
- **Command**:
  ```powershell
  python -m pytest tests/test_parsers_and_edge_cases.py -k "docker_compose" -v
  ```

### 5.2 Kubernetes ConfigMap Parser Tests
- **Test File**: `tests/test_parsers_and_edge_cases.py`
- **Functions**: `test_valid_kubernetes_configmap`, `test_invalid_kubernetes_yaml_not_a_configmap`, `test_invalid_kubernetes_yaml_syntax`
- **Component Tested**: `backend/artifact_parser.py:parse_kubernetes_manifest_content()`
- **Inputs**:
  - `kind: ConfigMap` with `data` map.
  - Manifest with `kind: Deployment` instead of `ConfigMap`.
  - Malformed YAML syntax.
- **Expected Results**: Successfully extracts key-values from valid ConfigMaps; cleanly rejects non-ConfigMap manifests with `ArtifactParseError`.
- **Command**:
  ```powershell
  python -m pytest tests/test_parsers_and_edge_cases.py -k "kubernetes" -v
  ```

### 5.3 Schema Validation Tests
- **Test File**: `tests/test_parsers_and_edge_cases.py`
- **Functions**: `test_missing_required_key_schema_validation`, `test_unexpected_key_schema_validation`, `test_wrong_data_type_schema_validation`, `test_runtime_snapshot_schema_validation`
- **Component Tested**: `backend/schema_validator.py` (`validate_environment_config`, `validate_runtime_snapshot`)
- **Inputs**: Config dictionaries missing required `DATABASE_HOST`, containing invalid types (integer for host), or violating draft-07 JSON schema.
- **Expected Results**: Returns `is_valid: False` with descriptive `errors` list.
- **Command**:
  ```powershell
  python -m pytest tests/test_parsers_and_edge_cases.py -k "schema" -v
  ```

### 5.4 Circular Reference & Type Coercion Tests
- **Test File**: `tests/test_parsers_and_edge_cases.py`
- **Functions**: `test_circular_configuration_references`, `test_type_coercion_true_vs_boolean`
- **Component Tested**: `backend/artifact_parser.py:detect_circular_references()`, `backend/normalizer.py:normalize_value()`
- **Inputs**:
  - Circular variable interpolation: `A -> ${B}`, `B -> ${A}`.
  - Value comparisons: `"true"` vs `True`, `"1"` vs `True`, `"5432"` vs `5432`.
- **Expected Results**: Circular loops detected and flagged cleanly without `RecursionError`. Normalized values evaluated as equivalent.
- **Command**:
  ```powershell
  python -m pytest tests/test_parsers_and_edge_cases.py -k "circular or coercion" -v
  ```

### 5.5 Drift Detection Engine Tests
- **Test File**: `tests/test_drift.py`
- **Functions**: `test_case_1_production_debug_enabled`, `test_case_2_wrong_database`, `test_case_3_missing_production_secret`, `test_case_4_runtime_drift`, `test_case_5_expected_difference`
- **Component Tested**: `backend/drift_engine.py:detect_drift()`
- **Inputs**: Staging vs Production configurations with injected errors.
- **Expected Results**:
  - `DEBUG=true` in prod detected as **CRITICAL**.
  - `dev-db` in prod detected as **CRITICAL** contamination.
  - Missing secret detected as **CRITICAL**.
  - Runtime drift detected as **HIGH**.
  - Legitimate expected differences recognized as safe policy variances.
- **Command**:
  ```powershell
  python -m pytest tests/test_drift.py -v
  ```

### 5.6 Deployment Gate & Change Approval Tests
- **Test File**: `tests/test_api_gate.py`
- **Functions**: `test_api_deployment_gate_approved_on_clean_state`, `test_api_deployment_gate_blocks_on_critical_drift`, `test_change_request_approval_workflow`
- **Component Tested**: `backend/main.py:check_deployment_gate()`, `/api/change-requests`
- **Inputs**: Clean configurations vs configurations with injected critical drift.
- **Expected Results**:
  - Clean state returns `gate_status: "APPROVED"`, `deployment_allowed: True`.
  - Critical drift returns `gate_status: "BLOCKED"`, `deployment_allowed: False`.
  - Change request approval workflow applies fix and updates status to `approved`.
- **Command**:
  ```powershell
  python -m pytest tests/test_api_gate.py -v
  ```

### 5.7 Rollback Restoration Tests
- **Test File**: `tests/test_rollback.py`, `tests/test_parsers_and_edge_cases.py`
- **Functions**: `test_config_versioning_and_rollback`, `test_rollback_actual_state_restoration`
- **Component Tested**: `backend/rollback.py:execute_rollback()`
- **Inputs**: Update config to v2, then trigger rollback to v1.
- **Expected Results**: Increments version to v3, restores v1's exact value, and logs `rollback_records` and `audit_logs`.
- **Command**:
  ```powershell
  python -m pytest tests/test_rollback.py -v
  ```

---

## 6. GitHub Actions Testing Workflow

A continuous integration workflow is configured at `.github/workflows/test.yml`:

```yaml
name: Test Suite & CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest-cov jsonschema
      - name: Run automated test suite with coverage
        run: python -m pytest -v --cov=backend --cov-report=term-missing
      - name: Run empirical experiment benchmark
        run: python -m experiments.run_experiment
```

---

## 7. Known Testing Limitations

1. **Simulated Runtime Snapshots**: Runtime process memory snapshots are ingested via JSON telemetry fixtures rather than live Kubernetes or container daemon hooks.
2. **Local Concurrency**: SQLite transactions are tested with `PRAGMA foreign_keys = ON`, but multi-server distributed transaction locks are not evaluated.
3. **Role Header Authentication**: User identity is provided via request parameters for demonstration simplicity rather than cryptographic OAuth2/JWT verification.
