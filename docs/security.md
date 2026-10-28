# Security Architecture & Threat Mitigation Guide

## 1. Overview

The **Configuration Drift Validator** implements defense-in-depth security engineered for configuration management platforms. The architecture enforces cryptographic authentication, strict Role-Based Access Control (RBAC), input sanitization, directory traversal prevention, sensitive data masking, and tamper-evident audit logging.

```
 [ Client / CI Pipeline ]
           │
           │  Authorization: Bearer <JWT>
           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Layer 1: HTTP Security Headers & Payload Size Guard     │
 │ - X-Content-Type-Options: nosniff                       │
 │ - X-Frame-Options: DENY                                 │
 │ - X-XSS-Protection: 1; mode=block                       │
 │ - Max Payload Limit: 1 MB (DoS Prevention)              │
 └─────────────────────────┬───────────────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Layer 2: Authentication & Identity Verification         │
 │ - OAuth2 Password Bearer Flow                           │
 │ - Cryptographic HMAC-SHA256 JWT (RFC 7519)              │
 │ - PBKDF2-HMAC-SHA256 (100k rounds, 16-byte salt)        │
 │ - Verified Token Claims ('sub', 'role')                 │
 └─────────────────────────┬───────────────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Layer 3: Role-Based Access Control (RBAC)               │
 │ - Admin: Rollbacks, Change Approvals, System Config     │
 │ - Developer: Config Updates, Parsing, Change Requests   │
 │ - Viewer: Read-only Status, Audit Logs, Reports         │
 └─────────────────────────┬───────────────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Layer 4: Input Sanitization & Path Traversal Guards     │
 │ - Environment Whitelist Verification                    │
 │ - Filename Basename Sanitization (stops '../../')       │
 │ - Safe YAML Parsing (yaml.safe_load)                    │
 └─────────────────────────┬───────────────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Layer 5: Secret Masking & Metadata Isolation            │
 │ - Metadata-only modeling (exists, source, age_days)     │
 │ - Recursive secret masking ('pa****wd' / '********')    │
 │ - Sensitive key pattern matching                        │
 └─────────────────────────────────────────────────────────┘
```

---

## 2. Authentication Architecture

### 2.1 Cryptographic Password Storage
Passwords stored in SQLite are hashed using **PBKDF2-HMAC-SHA256** in accordance with OWASP Password Storage Guidelines:
- **Hash Algorithm:** PBKDF2 with SHA-256 digest
- **Iteration Count:** 100,000 iterations
- **Salt Generation:** 16 bytes of cryptographically secure randomness generated via Python's `secrets.token_hex(16)`
- **Storage Format:** `salt_hex$hash_hex`
- **Verification:** Uses `hmac.compare_digest()` to execute constant-time comparisons, preventing timing attacks.

### 2.2 JSON Web Tokens (JWT)
State-modifying API operations authenticate using standard Bearer JWT tokens:
- **Signature Algorithm:** `HS256` (HMAC with SHA-256)
- **Claims Included:**
  - `sub`: Verified username identifier
  - `role`: User role (`admin`, `developer`, `viewer`)
  - `iat`: Issue timestamp
  - `exp`: Expiration timestamp (default: 120 minutes)
- **Signing Key:** Loaded from `JWT_SECRET_KEY` environment variable with safe development fallback.
- **Expiry & Tampering Detection:** Expired or tampered tokens immediately raise `HTTP 401 Unauthorized` with `WWW-Authenticate: Bearer`.

---

## 3. Role-Based Access Control (RBAC)

Operations are partitioned across three hierarchical permission tiers:

| Role | Hierarchy Level | Allowed Operations |
| :--- | :---: | :--- |
| **`viewer`** | 1 | Read environments, view active configurations, inspect drift reports, read audit logs, check deployment gate status, view monitoring events. |
| **`developer`** | 2 | All Viewer permissions, plus: upload configurations, parse artifacts (.env, Compose, K8s), submit change requests, trigger drift validation, submit runtime snapshots. |
| **`admin`** | 3 | All Developer permissions, plus: execute configuration rollbacks, approve or reject deployment change requests, manage system users, reset demo state. |

### Enforcing Verified Identity
The system **never trusts client-supplied user parameters** (such as `author`, `performed_by`, or `reviewed_by` in request bodies). All identity attributes are derived directly from the verified cryptographic claims inside the validated JWT token (`current_user.username`).

---

## 4. Input Validation & Sanitization

### 4.1 Strict Environment Whitelisting
All configuration endpoints validate target environments strictly against a set of permitted environments:
```python
VALID_ENVIRONMENTS = {"development", "staging", "production"}
```
Any invalid name, arbitrary string, or path traversal attempt (e.g., `../production` or `fake_env`) raises a `SecurityValidationError` translated into `HTTP 400 Bad Request`.

### 4.2 Path Traversal Prevention
Uploaded artifact filenames are sanitized to prevent directory traversal attacks:
```python
def sanitize_safe_filename(filename: str) -> str:
    # Extracts only the base name (no directory components)
    base = os.path.basename(filename.replace("\\", "/"))
    clean = re.sub(r"[^A-Za-z0-9_.-]", "_", base)
    return clean or "safe_artifact"
```
Filenames like `../../etc/passwd` or `..\\..\\windows\\system32.dll` are stripped to safe basenames before filesystem interactions.

### 4.3 Payload Size Limits (DoS Mitigation)
To prevent regex backtracking attacks (ReDoS) and memory exhaustion, incoming configuration payloads are checked against a strict size boundary:
- **Maximum Configuration Size:** 1 MB (1,048,576 bytes)
- Payloads exceeding this limit raise `SecurityValidationError` (HTTP 400) before parsing.

### 4.4 Safe YAML & JSON Deserialization
All YAML parsing uses `yaml.safe_load()` rather than `yaml.load()`, preventing arbitrary Python object execution during manifest deserialization.

---

## 5. Secret Hygiene & Data Masking

### 5.1 Metadata-Only Principle
The application adheres strictly to a **metadata-only secret hygiene model**:
- Secrets are never ingested, stored, or returned as plaintext strings.
- Only metadata attributes are persisted:
  ```json
  {
    "name": "DATABASE_PASSWORD",
    "environment": "production",
    "is_present": true,
    "source": "secret-manager",
    "last_rotated": "2026-08-20",
    "age_days": 19
  }
  ```

### 5.2 Deep Secret Redaction
When displaying or logging configurations, keys matching sensitive patterns (`PASSWORD`, `SECRET`, `API_KEY`, `JWT`, `TOKEN`, `CREDENTIAL`) are automatically detected and masked:
- `is_sensitive_key()`: Regular expression pattern matcher.
- `mask_secret_value()`: Masks characters (e.g. `sk_live_998877665544` -> `sk****44`, short strings -> `********`).
- `sanitize_config_dict()`: Recursively traverses dictionaries and lists to sanitize sensitive values before serializing.

---

## 6. HTTP Security Hardening

FastAPI middleware applies standard security headers to every response:
- `X-Content-Type-Options: nosniff`: Prevents MIME-sniffing exploits.
- `X-Frame-Options: DENY`: Blocks clickjacking by preventing embedding in `<iframe>` elements.
- `X-XSS-Protection: 1; mode=block`: Activates cross-site scripting filters in legacy browsers.

---

## 7. Known Limitations & Threat Model Considerations

1. **Local SQLite File:** SQLite database permissions rely on the underlying OS user profile permissions.
2. **Simulated Secret Store:** Secret rotation and presence are monitored through metadata records rather than a live connection to AWS Secrets Manager or HashiCorp Vault.
3. **In-Memory JWT Secret:** In local development, a default key is used. For production deployments, `JWT_SECRET_KEY` must be supplied via a secure environment variable or key management service.
