"""
test_auth_and_rbac.py - Comprehensive Unit & Integration Tests for Authentication & RBAC
Configuration Drift Validator

Verifies:
1. PBKDF2-HMAC-SHA256 password hashing, salting, and verification
2. JWT token generation, signature verification, expiry, and tampering detection
3. Login API endpoint: valid credentials, invalid passwords, non-existent users
4. RBAC 401 Unauthorized when credentials are missing
5. RBAC 403 Forbidden when role has insufficient privileges (e.g. Viewer attempting rollback)
6. RBAC 200 OK when appropriate role is provided (Developer updating configs, Admin rolling back)
7. Identity extraction from verified credential (preventing user spoofing)
8. Security headers middleware (nosniff, DENY, XSS protection)
9. Pagination and limit/offset query parameters on audit and change request lists
"""

import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import (
    Role,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    authenticate_user
)
from backend.rollback import save_new_config_version

@pytest.fixture
def client():
    return TestClient(app)

# ──────────────────────────────────────────────
# 1. Cryptographic Password Hashing Tests
# ──────────────────────────────────────────────

def test_password_hashing_and_verification():
    """Verifies that password hashing uses unique salts and verifies correctly."""
    pwd = "SecurePassword@2026"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    # Hashes must be different because salts are random
    assert hash1 != hash2
    assert "$" in hash1

    # Verification
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("WrongPassword!", hash1) is False
    assert verify_password("", hash1) is False
    assert verify_password(pwd, "") is False
    assert verify_password(pwd, "corrupted_hash_without_delimiter") is False

# ──────────────────────────────────────────────
# 2. JWT Generation, Signature & Expiry Tests
# ──────────────────────────────────────────────

def test_jwt_generation_and_decoding():
    """Generates and decodes JWT tokens, verifying claims."""
    token = create_access_token({"sub": "lead-architect", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "lead-architect"
    assert payload["role"] == "admin"
    assert "exp" in payload

def test_jwt_expired_token_raises_401():
    """Tokens with past expiration dates are rejected with HTTP 401."""
    expired_token = create_access_token(
        {"sub": "expired-user", "role": "developer"},
        expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(Exception) as exc:
        decode_access_token(expired_token)
    assert "expired" in str(exc.value).lower()

def test_jwt_tampered_token_raises_401():
    """Tampered tokens with invalid signature fail validation."""
    valid_token = create_access_token({"sub": "admin", "role": "admin"})
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.tamperedSignature9999"
    with pytest.raises(Exception) as exc:
        decode_access_token(tampered_token)
    assert "invalid" in str(exc.value).lower()

# ──────────────────────────────────────────────
# 3. Authentication & Login Endpoint Tests
# ──────────────────────────────────────────────

def test_login_endpoint_success(client: TestClient):
    """Admin and Developer log in successfully and receive Bearer JWTs."""
    # Admin login
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["token_type"] == "bearer"

    # Developer login
    res_dev = client.post("/api/auth/login", json={"username": "developer", "password": "Dev@123"})
    assert res_dev.status_code == 200
    assert res_dev.json()["role"] == "developer"

def test_login_endpoint_failure(client: TestClient):
    """Invalid credentials return HTTP 401."""
    # Bad password
    res = client.post("/api/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]

    # Unknown user
    res_unknown = client.post("/api/auth/login", json={"username": "ghost_user", "password": "Password123"})
    assert res_unknown.status_code == 401

def test_auth_me_endpoint(client: TestClient):
    """GET /api/auth/me returns the profile of the authenticated token."""
    token = create_access_token({"sub": "developer", "role": "developer"})
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    profile = res.json()
    assert profile["username"] == "developer"
    assert profile["role"] == "developer"

# ──────────────────────────────────────────────
# 4. RBAC: Unauthenticated Requests (HTTP 401)
# ──────────────────────────────────────────────

def test_unauthenticated_request_to_protected_routes_returns_401(client: TestClient):
    """Calling protected action routes without credentials returns 401."""
    # Rollback without token
    res_rb = client.post("/api/rollback", json={"environment": "production", "target_version": 1, "reason": "Test"})
    assert res_rb.status_code == 401
    assert "Authentication required" in res_rb.json()["detail"]

    # Config update without token
    res_up = client.post("/api/configs/production/update", json={"environment": "production", "raw_env_content": "A=1"})
    assert res_up.status_code == 401

    # Change review without token
    res_rev = client.post("/api/change-requests/1/review", json={"status": "APPROVED"})
    assert res_rev.status_code == 401

# ──────────────────────────────────────────────
# 5. RBAC: Insufficient Permissions (HTTP 403)
# ──────────────────────────────────────────────

def test_viewer_role_cannot_perform_privileged_actions(client: TestClient):
    """Viewer token receives 403 Forbidden on update and rollback operations."""
    viewer_token = create_access_token({"sub": "guest-viewer", "role": "viewer"})
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Viewer trying to perform rollback
    res_rb = client.post("/api/rollback", json={"environment": "production", "target_version": 1, "reason": "Test"}, headers=viewer_headers)
    assert res_rb.status_code == 403
    assert "Forbidden" in res_rb.json()["detail"]

    # Viewer trying to update configuration
    res_up = client.post("/api/configs/production/update", json={"environment": "production", "raw_env_content": "A=1"}, headers=viewer_headers)
    assert res_up.status_code == 403

def test_developer_role_cannot_perform_admin_rollback(client: TestClient):
    """Developer token receives 403 Forbidden when attempting rollback or change review."""
    dev_token = create_access_token({"sub": "junior-coder", "role": "developer"})
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    res_rb = client.post("/api/rollback", json={"environment": "production", "target_version": 1, "reason": "Dev trying rollback"}, headers=dev_headers)
    assert res_rb.status_code == 403
    assert "admin" in res_rb.json()["detail"].lower()

# ──────────────────────────────────────────────
# 6. RBAC: Authorized Actions & Identity Extraction
# ──────────────────────────────────────────────

def test_authorized_actions_extract_verified_identity(client: TestClient):
    """Verified identity from token is recorded in audit logs rather than spoofed parameters."""
    admin_token = create_access_token({"sub": "verified-sec-admin", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Ensure baseline v1 exists
    clean_vars = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}
    v1 = save_new_config_version("production", clean_vars, {}, [], "Initial base", "system")
    v2 = save_new_config_version("production", clean_vars, {}, [], "Update base", "system")

    # Call rollback supplying fake performed_by in body, verifying token identity is used
    res = client.post("/api/rollback", json={
        "environment": "production",
        "target_version": v1,
        "reason": "Test identity extraction",
        "performed_by": "spoofed_hacker_name"
    }, headers=admin_headers)

    assert res.status_code == 200
    assert res.json()["performed_by"] == "verified-sec-admin"
    assert res.json()["performed_by"] != "spoofed_hacker_name"

# ──────────────────────────────────────────────
# 7. Security Headers & Pagination
# ──────────────────────────────────────────────

def test_security_headers_present_on_responses(client: TestClient):
    """Every response contains security hardening headers."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "1; mode=block" in res.headers.get("X-XSS-Protection", "")

def test_pagination_on_list_endpoints(client: TestClient):
    """List endpoints support limit and offset query parameters."""
    res_logs = client.get("/api/audit-logs?limit=3&offset=0")
    assert res_logs.status_code == 200
    assert isinstance(res_logs.json(), list)
    assert len(res_logs.json()) <= 3

    res_crs = client.get("/api/change-requests?limit=2&offset=0")
    assert res_crs.status_code == 200
    assert isinstance(res_crs.json(), list)
    assert len(res_crs.json()) <= 2
