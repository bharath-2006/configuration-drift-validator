# REST API Reference — Configuration Drift Validator

This document provides complete, verified documentation for all active REST endpoints implemented in `backend/main.py`.

The interactive Swagger/OpenAPI documentation is available locally when the application is running at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Endpoint Summary Table

| Category | HTTP Method | URL Path | State Change? | Role Required | Description |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Auth** | `POST` | `/api/auth/token` | No | None (Public) | Authenticates user with username & password; returns Bearer JWT. |
| **Auth** | `POST` | `/api/auth/login` | No | None (Public) | JSON alias for authentication token generation. |
| **Auth** | `GET` | `/api/auth/me` | No | Any Authenticated | Returns authenticated user profile and verified role claims. |
| **Auth** | `GET` | `/api/auth/users` | No | `admin` | Lists system users and assigned roles. |
| **System** | `GET` | `/` | No | None | Serves the frontend single-page dashboard. |
| **System** | `GET` | `/api/health` | No | None | Returns system health and database connectivity status. |
| **Environments** | `GET` | `/api/environments` | No | `viewer` | Lists all registered environments with health status. |
| **Configuration** | `GET` | `/api/configs/{environment}` | No | `viewer` | Retrieves active configuration parameters for an environment. |
| **Configuration** | `GET` | `/api/configs/{environment}/history` | No | `viewer` | Retrieves complete version history of configuration parameters. |
| **Configuration** | `POST` | `/api/configs/parse-artifact` | No | `developer` | Parses `.env`, Docker Compose, or K8s ConfigMap artifacts. |
| **Configuration** | `POST` | `/api/configs/{environment}/update` | Yes | `developer` | Updates a configuration parameter with version increment and audit. |
| **Configuration** | `GET` | `/api/configs/{environment}/compare` | No | `viewer` | Compares configuration between two environments. |
| **Runtime** | `GET` | `/api/runtime/{environment}` | No | `viewer` | Retrieves runtime process snapshots for an environment. |
| **Runtime** | `POST` | `/api/runtime/{environment}` | Yes | `developer` | Records a new runtime process snapshot. |
| **Validation** | `POST` | `/api/validate` | Yes | `developer` / `viewer` | Executes 5-tier drift engine and updates environment status. |
| **Deployment Gate**| `GET` | `/api/deployment-gate` | No | `viewer` | Evaluates deployment gate status for production. |
| **Pre-Deploy** | `POST` | `/api/pre-deployment-check` | Yes | `developer` | Pre-deployment pipeline gate evaluation with CI report generation. |
| **Change Review** | `GET` | `/api/change-requests` | No | `viewer` | Lists change requests with optional status filter and pagination. |
| **Change Review** | `POST` | `/api/change-requests` | Yes | `developer` | Submits a proposed configuration change (user taken from token). |
| **Change Review** | `POST` | `/api/change-requests/{request_id}/review` | Yes | `admin` | Approves or rejects a change request; applies fix if approved. |
| **Rollback** | `GET` | `/api/rollbacks` | No | `viewer` | Retrieves the history of rollbacks performed. |
| **Rollback** | `POST` | `/api/rollback` | Yes | `admin` | Atomically reverts configuration to a target version. |
| **Rollback** | `POST` | `/api/configs/rollback` | Yes | `admin` | Alias for rollback execution. |
| **Audit Trail** | `GET` | `/api/audit-logs` | No | `viewer` | Retrieves chronological audit log records (supports limit/offset). |
| **Demo Setup** | `POST` | `/api/reset-demo` | Yes | `admin` | Resets database to standard reproducible demo state. |
| **Git Simulation** | `GET` | `/api/git/commits` | No | `viewer` | Lists simulated Git commit log entries (supports limit/offset). |
| **Git Simulation** | `POST` | `/api/git/simulate-commit` | Yes | `developer` | Simulates a Git commit with configuration changes. |
| **Monitoring** | `GET` | `/api/monitoring/status` | No | `viewer` | Returns background configuration drift scanner status. |
| **Monitoring** | `POST` | `/api/monitoring/scan` | Yes | `developer` | Triggers a real-time monitoring scan. |
| **Notifications** | `GET` | `/api/notifications` | No | `viewer` | Lists real-time in-app alerts and notifications. |
| **Notifications** | `POST` | `/api/notifications/{id}/read` | Yes | `developer` | Marks a notification as read. |
| **Notifications** | `POST` | `/api/notifications/read-all` | Yes | `developer` | Marks all notifications as read. |
| **Reports** | `GET` | `/api/reports/validation-runs` | No | `viewer` | Lists historical validation run reports. |
| **Reports** | `GET` | `/api/reports/validation-runs/{run_id}` | No | `viewer` | Retrieves full details of a specific validation run. |
| **Reports** | `GET` | `/api/reports/validation-runs/{run_id}/export/json` | No | `viewer` | Exports validation run details as formatted JSON. |
| **Reports** | `GET` | `/api/reports/validation-runs/{run_id}/export/csv` | No | `viewer` | Exports validation run details as CSV. |
| **Dashboard** | `GET` | `/api/dashboard/summary` | No | `viewer` | Aggregates summary statistics, counts, and gate indicators. |

---

## Detailed Endpoint Documentation

### 1. `GET /api/health`
- **Purpose**: Verifies that the FastAPI application and SQLite database connection are operational.
- **Request Parameters**: None.
- **Successful Response (200 OK)**:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-10-28T14:00:00.000000"
}
```

---

### 2. `POST /api/validate`
- **Purpose**: Runs full multi-tier drift detection comparing Staging and Production configurations, environment variables, secret metadata, and runtime snapshots.
- **Request Parameters / Body**: None.
- **Successful Response (200 OK)**:
```json
{
  "run_id": "VAL-56CFBDA7",
  "timestamp": "2026-10-28T14:30:00.123456",
  "total_issues": 1,
  "critical_count": 0,
  "high_count": 1,
  "medium_count": 0,
  "low_count": 0,
  "expected_differences": 2,
  "deployment_allowed": true,
  "issues": [
    {
      "environment": "production",
      "category": "infrastructure",
      "config_key": "payment-api.replicas",
      "expected_value": ">= 2",
      "actual_value": "1",
      "severity": "HIGH",
      "reason": "Production service 'payment-api' has only 1 replica(s), minimum is 2",
      "recommended_action": "Increase replicas to at least 2 for high availability",
      "is_expected_difference": false
    }
  ]
}
```

---

### 3. `GET /api/deployment-gate`
- **Purpose**: Returns the release gating decision for production.
- **Successful Response (200 OK)**:
```json
{
  "environment": "production",
  "gate_status": "APPROVED",
  "deployment_allowed": true,
  "message": "Deployment allowed. No critical blocking issues.",
  "critical_issues": 0,
  "high_issues": 0,
  "total_blocking_issues": 0,
  "last_validation_run": "VAL-56CFBDA7"
}
```

---

### 4. `POST /api/change-requests`
- **Purpose**: Submits a proposed configuration change for review.
- **Request Body**:
```json
{
  "environment": "staging",
  "config_key": "logging.level",
  "new_value": "DEBUG",
  "requested_by": "junior-dev",
  "justification": "Debugging staging payment flow"
}
```
- **Successful Response (200 OK)**:
```json
{
  "message": "Change request created",
  "request_id": 1,
  "status": "pending"
}
```

---

### 5. `POST /api/change-requests/{request_id}/review`
- **Purpose**: Authorizes or rejects a change request.
- **Path Parameters**: `request_id` (int).
- **Request Body**:
```json
{
  "decision": "approved",
  "reviewer": "senior-engineer",
  "comments": "Approved for debugging session."
}
```
- **Successful Response (200 OK)**:
```json
{
  "message": "Review submitted successfully",
  "request_id": 1,
  "status": "approved"
}
```

---

### 6. `POST /api/rollback`
- **Purpose**: Reverts a specific configuration key to its previous version.
- **Request Body**:
```json
{
  "environment": "staging",
  "config_key": "app.debug",
  "rolled_back_by": "lead-dev"
}
```
- **Successful Response (200 OK)**:
```json
{
  "message": "Rollback successful",
  "environment": "staging",
  "config_key": "app.debug",
  "restored_version": 3
}
```
- **Error Responses**: `400 Bad Request` if no prior version exists.

---

### 7. `GET /api/audit-logs`
- **Purpose**: Retrieves chronological audit logs.
- **Query Parameters**:
  - `limit` (int, default: 100)
  - `environment` (str, optional)
- **Successful Response (200 OK)**:
```json
[
  {
    "id": 1,
    "timestamp": "2026-10-28 14:40:00",
    "user": "lead-dev",
    "action": "ROLLBACK",
    "environment": "staging",
    "details": "Rolled back app.debug from v2 to v1",
    "result": "SUCCESS",
    "risk_level": "medium"
  }
]
```

---

### 8. `POST /api/configs/parse-artifact`
- **Purpose**: Parses `.env`, Docker Compose, or Kubernetes ConfigMap content without altering database state.
- **Request Body**:
```json
{
  "artifact_type": "docker-compose",
  "content": "version: '3'\nservices:\n  web:\n    image: nginx\n    ports:\n      - '80:80'"
}
```
- **Successful Response (200 OK)**:
```json
{
  "artifact_type": "docker-compose",
  "is_valid": true,
  "keys_found": 2,
  "parsed_config": {
    "compose.web.image": "nginx",
    "compose.web.ports": "80:80"
  }
}
```
