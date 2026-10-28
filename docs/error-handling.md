# Error Boundaries and Error Handling Architecture

## 1. Overview of Error Boundaries

An **Error Boundary** in the Configuration Drift Validator is a defined perimeter separating system subsystems where untrusted input, external files, network requests, or database interactions are intercepted, validated, sanitized, and safely handled before they can destabilize core application state.

```
 [Client / CI/CD] 
       │
       ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 1: API Request & Payload Validation (400/422) │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 2: Artifact Parsing (.env, Compose, K8s)      │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 3: JSON Schema Validation (Draft-07)          │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 4: Circular Reference & Normalization Guards  │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 5: Drift Detection & Contamination Rules      │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 6: Change Review & Rollback Guards (400/404)  │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 7: Database Persistence & Transaction Safety   │
 └───────────────────────┬────────────────────────────────┘
                         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Boundary 8: Secret Redaction & Audit Integrity         │
 └────────────────────────────────────────────────────────┘
```

---

## 2. Granular Boundary Specifications

### Boundary 1: API Request & Payload Validation
- **Possible Error**: Uploading unsupported file extensions, missing required fields in JSON payloads, invalid decision strings.
- **Detection Mechanism**: Pydantic schema validation models in `backend/schemas.py` and file extension verification in `backend/main.py`.
- **Handling Strategy**:
  - Missing or malformed Pydantic fields automatically trigger HTTP 422 Unprocessable Entity.
  - Unsupported format triggers `HTTPException(status_code=400, detail="Unsupported artifact format...")`.
- **User Response**: Structured JSON: `{"detail": "<specific reason>"}`.
- **State Impact**: Request terminated; no database records altered.
- **Audit Logging**: Rejected attempts do not alter configuration state.

### Boundary 2: Artifact Parsing & Syntax Failures
- **Possible Error**: Malformed YAML, missing `=` delimiter in `.env` files, unclosed quotes, duplicate keys.
- **Detection Mechanism**: `backend/artifact_parser.py` wraps parser invocations with `try...except ArtifactParseError`.
- **Handling Strategy**: Catches parser exceptions and returns clean HTTP 400 error responses with line numbers and diagnostic context.
- **User Response**: Clean error message without raw Python tracebacks or internal disk paths.
- **State Impact**: Parsing terminates safely.
- **Audit Logging**: Recorded in application log.

### Boundary 3: JSON Schema Validation (Draft-07)
- **Possible Error**: Missing mandatory keys (`DATABASE_HOST`), unexpected undeclared keys, or wrong data types (e.g. integer instead of string).
- **Detection Mechanism**: `backend/schema_validator.py` validates inputs against formal schemas (`schemas/environment.schema.json`, `schemas/drift-rule.schema.json`, `schemas/runtime-snapshot.schema.json`).
- **Handling Strategy**: Gathers schema errors and returns `is_valid: False` with descriptive error lists.
- **User Response**: Detailed array of schema violations.
- **State Impact**: Halts configuration ingestion before persistence.

### Boundary 4: Circular Reference & Type Coercion
- **Possible Error**: Self-referencing variable interpolation (`A -> ${B}`, `B -> ${A}`) causing infinite recursion.
- **Detection Mechanism**: `detect_circular_references()` in `backend/artifact_parser.py` constructs a dependency graph and detects cycles via depth-first search.
- **Handling Strategy**: Detects circular loops and raises `ArtifactParseError("Circular reference detected: ...")`.
- **User Response**: Clear error naming the cyclic keys.
- **State Impact**: Recursion loop prevented.

### Boundary 5: Drift Detection & Contamination Rules
- **Possible Error**: Production configuration referencing development endpoints (`dev-db`, `localhost`, `staging-api`).
- **Detection Mechanism**: `backend/drift_engine.py` evaluates keys against `backend/validation_policy.py`.
- **Handling Strategy**: Flags discrepancy with `severity: "CRITICAL"`, increments blocking count, and updates deployment gate status to `BLOCKED`.
- **User Response**: Prominent Critical alert banner on dashboard.
- **State Impact**: Recorded in `drift_results` and `deployment_checks`.

### Boundary 6: Resource Existence & 404 Guards
- **Possible Error**: Requesting an environment, configuration version, or change request ID that does not exist.
- **Detection Mechanism**: SQLite `fetchone()` existence checks.
- **Handling Strategy**: Raises `HTTPException(status_code=404, detail="Resource not found")`.
- **User Response**: HTTP 404 with clean resource error detail.
- **State Impact**: Execution terminates safely; no partial writes.

### Boundary 7: Rollback Execution & Guardrails
- **Possible Error**: Rollback requested on non-existent environment, missing key, or version 1 with no prior version.
- **Detection Mechanism**: `execute_rollback()` in `backend/rollback.py` checks active version and finds previous versions `< current_version`.
- **Handling Strategy**:
  - If no prior version exists: Raises `RollbackError("No previous version found to rollback to.")`.
  - Catches error in API and returns HTTP 400.
  - Transaction is only committed after the restored version is successfully written.
- **User Response**: Clean HTTP 400 error message.
- **State Impact**: State is NOT modified. It never reports success unless the rollback actually succeeded.
- **Audit Logging**: Successful rollbacks create a `ROLLBACK` audit entry; failed attempts do not generate bogus records.

### Boundary 8: Database Persistence & Transaction Safety
- **Possible Error**: SQLite lock contention, malformed query syntax, connection leaks.
- **Detection Mechanism**: `try...finally` blocks wrapping every database interaction in `backend/database.py` with `conn.close()`.
- **Handling Strategy**: Ensures database connections are reliably closed and foreign keys are strictly enforced (`PRAGMA foreign_keys = ON`).
- **User Response**: HTTP 500 without leaking file paths or credentials.
- **State Impact**: Uncommitted transactions are automatically rolled back by SQLite.

### Boundary 9: Secret Redaction & Information Leakage Prevention
- **Possible Error**: Plaintext database passwords, API tokens, or server file paths leaking in error responses, audit logs, or API payloads.
- **Detection Mechanism**: Secrets are modeled strictly as **metadata** in `backend/schemas.py:SecretMetadata` (fields: `id`, `name`, `exists_flag`, `source`, `last_rotated`, `rotation_policy_days`).
- **Handling Strategy**: The API never accepts or returns raw secret values.
- **User Response**: Users view compliance indicators without ever seeing raw secrets.
- **State Impact**: Secure by design.

---

## 3. Summary of HTTP Status Code Conventions

| Status Code | Meaning in Drift Validator | Examples |
| :---: | :--- | :--- |
| **`200 OK`** | Request succeeded. | Retrieved environments, configs, audit logs, or ran validation. |
| **`201 Created`** | New entity created. | Change request or config item created. |
| **`400 Bad Request`** | Input format error or invalid domain operation. | Unsupported file upload extension, malformed YAML/JSON syntax, or invalid rollback. |
| **`404 Not Found`** | Requested resource does not exist. | Non-existent environment name, config key, or change request ID. |
| **`422 Unprocessable`**| Malformed JSON schema or missing Pydantic fields. | Body payload missing required fields. |
| **`500 Internal Error`**| Unexpected server failure. | Diagnostic details kept in server logs; clean message to user. |
