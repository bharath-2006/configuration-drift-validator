# Configuration Rollback & Actual State Restoration Guide

This document explains and demonstrates how the **Configuration Drift Validator** performs **actual state restoration** during a rollback operation, rather than merely logging a rollback event.

---

## 1. Current Configuration Architecture

In the Configuration Drift Validator, an environment configuration consists of:
1. **Database Version Records (`configuration_versions`)**: Holds version metadata, author, description, and an `is_active` flag (1 for active, 0 for previous/archived).
2. **Key-Value Variables (`environment_variables`)**: Active key-value pairs associated with the version.
3. **Infrastructure Definitions (`infrastructure_definitions`)**: Replica count, CPU, memory, port, and health check.
4. **Secret Metadata (`secret_metadata`)**: Presence flags and secret rotation age.
5. **Physical Filesystem Configuration (`configs/{env}/app.env`)**: Real configuration files utilized by running containers, services, and local developer processes.

When a rollback is triggered, the engine ensures that **both** the active database pointers and the physical configuration artifacts (`configs/{env}/app.env`) are synchronized back to the exact snapshot of the target version.

---

## 2. Configuration Version History

Version history is tracked immutably. Every update creates a new sequential version number:

| Version | Environment | Author | Description | Active Flag |
| :--- | :--- | :--- | :--- | :--- |
| **v1** | `production` | `system-installer` | Baseline configuration: `DATABASE_HOST=prod-db`, `PORT=8080`, `DEBUG=false` | 0 (Archived) |
| **v2** | `production` | `junior-dev` | Bad update: Accidentally set `DATABASE_HOST=dev-db` and `DEBUG=true` | 1 (Active - Drift!) |

API Endpoint for retrieving history:
```http
GET /api/configs/production/history
```

Response:
```json
[
  {
    "version": 2,
    "description": "Bad update: set dev-db",
    "created_by": "junior-dev",
    "is_active": 1,
    "created_at": "2026-09-28 10:15:00"
  },
  {
    "version": 1,
    "description": "Baseline configuration",
    "created_by": "system-installer",
    "is_active": 0,
    "created_at": "2026-09-28 08:00:00"
  }
]
```

---

## 3. Problematic Configuration (Incident Scenario)

A misconfiguration incident occurs when a developer pushes a configuration intended for development into production:

### Problematic State (Version 2)
```ini
# configs/production/app.env (v2 - INCIDENT)
DATABASE_HOST=dev-db
DATABASE_PORT=5432
APP_ENV=production
DEBUG=true
LOG_LEVEL=DEBUG
```

### Impact on Validation & Deployment Gate
When validation runs (`POST /api/validate`), the drift engine detects:
1. **Critical Drift**: `DATABASE_HOST` is set to `dev-db` (Non-production database in production environment!).
2. **High Severity Drift**: `DEBUG` is set to `true` in production.
3. **Deployment Gate Action**: Status immediately switches to **BLOCKED**. Deployments are prevented:
```json
{
  "production_deployment_allowed": false,
  "deployment_message": "CRITICAL DRIFT: 1 critical discrepancies detected. Production deployment blocked.",
  "critical_count": 1,
  "high_count": 1
}
```

---

## 4. Rollback Action

To remediate the outage risk, the DevOps lead executes a rollback to Version 1 via the UI or REST API:

### Request
```http
POST /api/rollback
Content-Type: application/json

{
  "environment": "production",
  "target_version": 1,
  "reason": "Reverting accidental pointing of production to dev-db in v2",
  "performed_by": "devops-lead"
}
```

### Rollback Execution Pipeline
During the rollback execution (`perform_rollback()` in `backend/rollback.py`):
1. **Database Pointer Switch**:
   - `UPDATE configuration_versions SET is_active = 0 WHERE environment = 'production'`
   - `UPDATE configuration_versions SET is_active = 1 WHERE environment = 'production' AND version = 1`
2. **Filesystem Synchronization**:
   - Reads the snapshot variables for Version 1 (`DATABASE_HOST=prod-db`, `DEBUG=false`, etc.).
   - Overwrites `configs/production/app.env` with the restored variables so containers and tools receive the restored configuration.
3. **Audit Trail Recording**:
   - Inserts record into `rollback_records`.
   - Logs an audit event with severity `HIGH` into `audit_logs`.
4. **Immediate Post-Rollback Validation**:
   - Invokes `validate_configurations()` automatically.
   - Verifies if the drift is resolved and updates the deployment gate to **APPROVED**.

---

## 5. Restored Configuration (Verified State)

Following the rollback action, the active configuration is verified:

### API Response from Rollback
```json
{
  "status": "success",
  "environment": "production",
  "from_version": 2,
  "restored_version": 1,
  "reason": "Reverting accidental pointing of production to dev-db in v2",
  "performed_by": "devops-lead",
  "restored_variables": {
    "DATABASE_HOST": "prod-db",
    "DATABASE_PORT": "5432",
    "APP_ENV": "production",
    "DEBUG": "false",
    "LOG_LEVEL": "INFO"
  },
  "message": "Successfully restored production to Version 1"
}
```

### Physical File State
File: `configs/production/app.env`:
```ini
# Restored to Version 1
DATABASE_HOST=prod-db
DATABASE_PORT=5432
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
```

---

## 6. Validation After Rollback

The rollback endpoint automatically triggers drift validation immediately upon restoring state.

### Re-Validation Result
- `DATABASE_HOST` matches expected production database (`prod-db`).
- `DEBUG` is confirmed as `false`.
- Discrepancy count drops to 0.
- Production deployment gate unlocks:
```json
{
  "production_deployment_allowed": true,
  "deployment_message": "All environments conform to baseline standards. Deployment allowed.",
  "critical_count": 0,
  "high_count": 0
}
```

---

## 7. Audit Record

Every rollback generates an immutable audit record for compliance and post-mortem analysis:

### Table: `rollback_records`
| ID | Environment | From Version | To Version | Reason | Performed By | Timestamp |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `1` | `production` | `2` | `1` | Reverting accidental pointing of production to dev-db in v2 | `devops-lead` | `2026-09-28 10:20:00` |

### Table: `audit_logs`
```json
{
  "id": 42,
  "user": "devops-lead",
  "action": "Configuration Rollback",
  "environment": "production",
  "details": "Rolled back from Version 2 to Version 1. Restored 5 variables. Reason: Reverting accidental pointing of production to dev-db in v2",
  "risk_level": "HIGH",
  "timestamp": "2026-09-28 10:20:00"
}
```

---

## 8. Role-Based Authorization & Security Guarantees

Rollback is a privileged, high-impact operational capability protected by defense-in-depth:
1. **Admin Authorization Only:** Only authenticated users bearing the admin role can trigger /api/rollback or /api/configs/rollback.
2. **Rejection of Unauthorized Invocations:**
   - Unauthenticated requests receive HTTP 401 Unauthorized.
   - Viewer or Developer credentials receive HTTP 403 Forbidden.
3. **Cryptographically Verified Identity:** The performed_by field is extracted directly from the verified JWT sub claim on the server. Client-supplied body strings cannot spoof user identity.
4. **Post-Rollback Immediate Drift Re-Evaluation:** The active configuration is immediately re-evaluated against environment policy, verifying that critical drift is fully eliminated and unlocking the production deployment gate.
5. **Durable Snapshot Preservation:** Historical configuration versions are immutable. Target versions are validated for existence before any atomic pointer or filesystem changes occur.

---

## Summary of Verification Guarantees

1. **State Restoration**: Database active version points to restored version.
2. **Filesystem Sync**: `configs/production/app.env` is physically updated.
3. **Re-validation**: Drift validator automatically executes and confirms zero critical drift.
4. **Audit Integrity**: Complete forensic trail preserved in `rollback_records` and `audit_logs`.
