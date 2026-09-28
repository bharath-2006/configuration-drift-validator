# Explicit JSON/YAML Schema Specifications

## 1. Overview
The **Configuration Drift Validator** enforces explicit JSON/YAML Schemas to guarantee that all configuration inputs, policy rules, and runtime snapshots adhere to strict data types, required keys, and valid environment enumerations before entering the drift engine.

The schema files are stored in the root [`schemas/`](file:///c:/coe%20project/schemas/) directory:
- [`schemas/environment.schema.json`](file:///c:/coe%20project/schemas/environment.schema.json): Validates environment configuration bundles (Development, Staging, Production).
- [`schemas/drift-rule.schema.json`](file:///c:/coe%20project/schemas/drift-rule.schema.json): Validates deterministic drift detection policies.
- [`schemas/runtime-snapshot.schema.json`](file:///c:/coe%20project/schemas/runtime-snapshot.schema.json): Validates live container runtime snapshots.

---

## 2. Schema Breakdown

### 2.1 Environment Configuration Schema (`environment.schema.json`)
Defines the structure of an environment bundle.
- **Required Fields:** `environment`, `variables`.
- **Environment Names:** `"development"`, `"staging"`, `"production"`.
- **Variables:** Mapping of string identifiers to strings, numbers, booleans, or null.
- **Infrastructure:**
  - `service_name` (string)
  - `replicas` (integer $\ge 1$)
  - `port` (integer between 1 and 65535)
  - `health_check` (boolean)
- **Secrets Metadata:** Array of secret descriptors (`name`, `exists`, `source`, `last_rotated`, `age_days`). Real credentials are never stored.

**Example Valid Input:**
```json
{
  "environment": "production",
  "version": 1,
  "description": "Production baseline configuration",
  "author": "bharath",
  "variables": {
    "APP_ENV": "production",
    "DEBUG": "false",
    "DATABASE_HOST": "prod-db",
    "PORT": "8080"
  },
  "infrastructure": {
    "service_name": "payment-api",
    "replicas": 3,
    "port": 8080,
    "health_check": true
  },
  "secrets": [
    {
      "name": "DATABASE_PASSWORD",
      "environment": "production",
      "exists": true,
      "age_days": 15
    }
  ]
}
```

---

### 2.2 Drift Rule Schema (`drift-rule.schema.json`)
Defines policy rules evaluated across environments.
- **Required Fields:** `rule_id`, `target_environment`, `category`, `item_key`, `severity`, `reason`, `recommendation`.
- **Categories:** `env_var`, `infrastructure`, `secret`, `runtime`.
- **Severities:** `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- **Target Environments:** `production`, `staging`, `development`, `all`.

**Example Drift Rule:**
```json
{
  "rule_id": "RULE-PROD-DEBUG",
  "name": "Production Debug Mode Ban",
  "target_environment": "production",
  "category": "env_var",
  "item_key": "DEBUG",
  "severity": "CRITICAL",
  "rule_type": "boolean_check",
  "expected_value": false,
  "reason": "Debug mode enabled in production exposes internal stack traces and secrets.",
  "recommendation": "Set DEBUG=false in production configuration before deploying."
}
```

---

### 2.3 Runtime Snapshot Schema (`runtime-snapshot.schema.json`)
Defines live container configuration state reported by runtime agents.
- **Required Fields:** `environment`, `snapshot_data`.
- **Fields:**
  - `environment` (enum)
  - `app_version` (string)
  - `timestamp` (ISO timestamp)
  - `snapshot_data` (object containing live environment variables)

**Example Snapshot:**
```json
{
  "environment": "production",
  "app_version": "1.0.0",
  "timestamp": "2026-09-28T20:00:00Z",
  "snapshot_data": {
    "database_host": "prod-db",
    "log_level": "INFO",
    "debug": "false"
  }
}
```

---

## 3. How to Validate Payloads in Code

The system provides the [`backend/schema_validator.py`](file:///c:/coe%20project/backend/schema_validator.py) module:

```python
from backend.schema_validator import (
    validate_environment_config,
    validate_drift_rule,
    validate_runtime_snapshot_data
)

# 1. Validate an environment bundle
is_valid, error = validate_environment_config(payload)
if not is_valid:
    print(f"Rejected invalid configuration: {error}")

# 2. Validate a drift rule
is_valid, error = validate_drift_rule(rule_dict)
```

---

## 4. How to Add a New Drift Rule

Follow these simple steps to add a new drift rule:

### Step 1: Define Rule in Schema Format
For example, to enforce that Production must have at least 2 replicas:
```json
{
  "rule_id": "RULE-PROD-MIN-REPLICAS",
  "name": "Production Minimum Replica Count",
  "target_environment": "production",
  "category": "infrastructure",
  "item_key": "replicas",
  "severity": "MEDIUM",
  "rule_type": "threshold_check",
  "expected_value": 2,
  "reason": "Production replica count less than 2 removes redundancy during container failovers.",
  "recommendation": "Increase replicas to at least 2 in production infra.yaml."
}
```

### Step 2: Validate Against Schema
```python
from backend.schema_validator import validate_drift_rule

rule = { ... }
is_valid, err = validate_drift_rule(rule)
assert is_valid, f"Rule schema violation: {err}"
```

### Step 3: Connect Rule into `validation_policy.py` or `risk_engine.py`
In [`backend/risk_engine.py`](file:///c:/coe%20project/backend/risk_engine.py), add the evaluation logic matching the `rule_id` or `item_key`:
```python
if is_prod and key.lower() == "replicas" and int(norm_actual or 1) < 2:
    return DriftDiscrepancy(
        environment=environment,
        category="infrastructure",
        item_key="replicas",
        expected_val=">= 2",
        actual_val=str(actual_val),
        severity=SeverityEnum.MEDIUM,
        reason="Production replica count is less than 2, leaving no redundancy during pod failovers.",
        recommendation="Increase production replicas to at least 2."
    )
```
The new rule is now automatically picked up by the drift engine, CI/CD validator, pre-deployment gate, and risk score calculator!
