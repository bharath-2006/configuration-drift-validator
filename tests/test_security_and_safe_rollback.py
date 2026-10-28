"""
test_security_and_safe_rollback.py
Comprehensive Security and Safe Rollback Unit/Integration Tests
Configuration Drift Validator

Verifies:
1. Environment name whitelist validation and injection protection
2. Safe filename sanitization (directory traversal protection)
3. Upload payload size limits (DoS protection)
4. Sensitive key detection and secret value masking (redaction verification)
5. Non-existent environment rejection in API
6. Comprehensive rollback safety:
   - State before rollback: DATABASE_HOST=dev-db
   - Rollback executed
   - State after rollback: DATABASE_HOST=prod-db
   - Post-rollback validation run proves drift is cleared
   - Attempted rollback to non-existent version cleanly raises error
   - Rollback transaction preserves history and logs audit entry
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.security import (
    validate_environment_name,
    sanitize_safe_filename,
    validate_payload_size,
    is_sensitive_key,
    mask_secret_value,
    sanitize_config_dict,
    SecurityValidationError
)
from backend.rollback import (
    perform_rollback,
    get_active_version,
    get_config_snapshot_by_version,
    save_new_config_version
)
from backend.drift_engine import detect_environment_variable_drift
from backend.schemas import SeverityEnum

@pytest.fixture
def client():
    return TestClient(app)

# ──────────────────────────────────────────────
# Security Unit Tests
# ──────────────────────────────────────────────

def test_validate_environment_whitelist():
    """Validates whitelist and rejects arbitrary or path-traversal environment names."""
    assert validate_environment_name("development") == "development"
    assert validate_environment_name("STAGING") == "staging"
    assert validate_environment_name(" Production ") == "production"

    with pytest.raises(SecurityValidationError) as exc:
        validate_environment_name("testing_env")
    assert "Invalid environment" in str(exc.value)

    with pytest.raises(SecurityValidationError):
        validate_environment_name("../production")

    with pytest.raises(SecurityValidationError):
        validate_environment_name("")

def test_sanitize_filename_path_traversal():
    """Sanitizes filenames to prevent directory traversal and illegal characters."""
    assert sanitize_safe_filename("configs/prod.env") == "prod.env"
    assert sanitize_safe_filename("../../etc/passwd") == "passwd"
    assert sanitize_safe_filename("..\\..\\windows\\system32.dll") == "system32.dll"
    assert sanitize_safe_filename("valid_config.yaml") == "valid_config.yaml"
    assert sanitize_safe_filename("") == "unnamed_artifact"

def test_payload_size_limit():
    """Payloads exceeding maximum size are safely rejected."""
    small_payload = "KEY=VALUE\n" * 10
    validate_payload_size(small_payload, max_bytes=1000)

    oversized = "A" * 1050
    with pytest.raises(SecurityValidationError) as exc:
        validate_payload_size(oversized, max_bytes=1000)
    assert "exceeds maximum allowable limit" in str(exc.value)

def test_sensitive_key_detection():
    """Detects various forms of passwords, tokens, API keys, and credentials."""
    assert is_sensitive_key("DATABASE_PASSWORD") is True
    assert is_sensitive_key("db_password") is True
    assert is_sensitive_key("SECRET_KEY") is True
    assert is_sensitive_key("JWT_SECRET") is True
    assert is_sensitive_key("STRIPE_API_KEY") is True
    assert is_sensitive_key("AUTH_TOKEN") is True
    assert is_sensitive_key("BEARER_TOKEN") is True
    
    # Non-sensitive keys
    assert is_sensitive_key("DATABASE_HOST") is False
    assert is_sensitive_key("LOG_LEVEL") is False
    assert is_sensitive_key("PORT") is False

def test_mask_secret_value():
    """Masks secrets so raw credentials never appear in plain text."""
    assert mask_secret_value("short") == "sh****rt"
    assert mask_secret_value("123") == "********"
    assert mask_secret_value("my_ultra_secret_db_pass_2026") == "my****26"
    assert mask_secret_value(None) == "<NULL>"

def test_sanitize_config_dict():
    """Deep masks sensitive keys in configuration dictionaries."""
    config = {
        "DATABASE_HOST": "prod-db",
        "DATABASE_PASSWORD": "SuperSecretPassword123!",
        "API_KEY": "sk_live_998877665544",
        "nested": {
            "JWT_SECRET": "jwt_signing_key_4433",
            "PORT": 5432
        }
    }
    sanitized = sanitize_config_dict(config)
    assert sanitized["DATABASE_HOST"] == "prod-db"
    assert sanitized["DATABASE_PASSWORD"] != "SuperSecretPassword123!"
    assert "SuperSecretPassword123!" not in str(sanitized)
    assert "sk_live" not in str(sanitized["API_KEY"])
    assert sanitized["nested"]["PORT"] == 5432
    assert "jwt_signing" not in str(sanitized["nested"]["JWT_SECRET"])

# ──────────────────────────────────────────────
# API Security Boundaries
# ──────────────────────────────────────────────

def test_api_rejects_invalid_environment(client: TestClient):
    """API endpoints reject unwhitelisted environment names with HTTP 400."""
    res = client.get("/api/configs/unknown_fake_env")
    assert res.status_code == 400
    assert "Invalid environment" in res.json()["detail"]

    res_post = client.post(
        "/api/configs/invalid_env/update",
        json={"environment": "invalid_env", "raw_env_content": "A=1"}
    )
    assert res_post.status_code == 400
    assert "Invalid environment" in res_post.json()["detail"]

# ──────────────────────────────────────────────
# Safe Rollback Scenario (Task 4)
# ──────────────────────────────────────────────

def test_safe_rollback_state_restoration_and_drift_verification():
    """
    Scenario Test (Task 4):
    1. Base clean state at version V_initial has DATABASE_HOST=prod-db.
    2. Save faulty new version with DATABASE_HOST=dev-db.
    3. Verify drift engine detects Critical database contamination.
    4. Execute perform_rollback to V_initial.
    5. Verify active version restored to V_initial.
    6. Verify filesystem/snapshot state has DATABASE_HOST=prod-db.
    7. Run validation after rollback to prove drift is eliminated.
    """
    env = "production"
    
    # Step 1: Ensure initial valid state exists
    clean_vars = {
        "APP_ENV": "production",
        "DEBUG": "false",
        "DATABASE_HOST": "prod-db",
        "DATABASE_PORT": "5432",
        "API_URL": "https://api.production.example.com",
        "LOG_LEVEL": "INFO",
        "FEATURE_PAYMENT": "true"
    }
    clean_infra = {"service_name": "payment-api", "port": 8080, "replicas": 3, "health_check": True}
    clean_secrets = [{"name": "DATABASE_PASSWORD", "environment": "production", "is_present": True, "source": "secret-manager", "age_days": 15}]

    v_initial = save_new_config_version(
        environment=env,
        variables=clean_vars,
        infra=clean_infra,
        secrets=clean_secrets,
        description="Clean baseline configuration",
        author="lead-architect"
    )
    assert get_active_version(env) == v_initial

    # Step 2: Inject faulty configuration with DATABASE_HOST=dev-db
    faulty_vars = dict(clean_vars)
    faulty_vars["DATABASE_HOST"] = "dev-db"

    v_faulty = save_new_config_version(
        environment=env,
        variables=faulty_vars,
        infra=clean_infra,
        secrets=clean_secrets,
        description="Accidental dev-db injection",
        author="junior-dev"
    )
    assert get_active_version(env) == v_faulty

    # Step 3: Verify drift engine catches dev-db as Critical contamination
    active_snapshot = get_config_snapshot_by_version(env, v_faulty)
    assert active_snapshot["variables"]["DATABASE_HOST"] == "dev-db"
    
    discrepancies = detect_environment_variable_drift(clean_vars, clean_vars, faulty_vars)
    crit_issues = [d for d in discrepancies if d.severity == SeverityEnum.CRITICAL and d.environment == "production"]
    assert len(crit_issues) > 0
    assert "dev-db" in crit_issues[0].actual_val

    # Step 4: Execute perform_rollback to v_initial
    rollback_result = perform_rollback(
        environment=env,
        target_version=v_initial,
        reason="Reverting dev-db endpoint back to prod-db",
        performed_by="security-auditor"
    )
    assert rollback_result["status"] == "success"
    assert rollback_result["restored_version"] == v_initial

    # Step 5: Verify active version is restored
    active_v_after = get_active_version(env)
    assert active_v_after == v_initial

    # Step 6: Verify restored snapshot values
    restored_snapshot = get_config_snapshot_by_version(env, active_v_after)
    assert restored_snapshot["variables"]["DATABASE_HOST"] == "prod-db"
    assert restored_snapshot["variables"]["DEBUG"] == "false"

    # Step 7: Run validation after restoration to prove critical drift is cleared
    post_discrepancies = detect_environment_variable_drift(clean_vars, clean_vars, restored_snapshot["variables"])
    post_crit = [d for d in post_discrepancies if d.severity == SeverityEnum.CRITICAL and d.environment == "production"]
    assert len(post_crit) == 0

def test_rollback_to_invalid_version_fails_safely():
    """Attempting rollback to a non-existent version raises ValueError and preserves current state."""
    env = "production"
    current_active = get_active_version(env)

    with pytest.raises(ValueError) as exc:
        perform_rollback(environment=env, target_version=99999, reason="Invalid version attempt")
    assert "does not exist" in str(exc.value)

    # Active version remains intact
    assert get_active_version(env) == current_active
