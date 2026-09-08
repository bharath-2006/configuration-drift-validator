"""
test_adversarial.py - Adversarial and Edge-Case Testing from Section 14
Designed to test resilience against normalization tricks, disguised hostnames, and stale secrets.
"""

import pytest
from backend.normalizer import values_are_equivalent, extract_host_from_url_or_endpoint
from backend.drift_engine import (
    detect_environment_variable_drift,
    detect_secret_metadata_drift,
    detect_runtime_drift
)
from backend.schemas import SeverityEnum

def test_adversarial_whitespace_and_casing():
    """Ensure padding and casing don't fool equivalence checks."""
    assert values_are_equivalent("  prod-db  ", "prod-db") is True
    assert values_are_equivalent("TRUE", True) is True
    assert values_are_equivalent("False", False) is True
    assert values_are_equivalent("  5432  ", 5432) is True

def test_adversarial_boolean_strings_in_prod_debug():
    """Detects DEBUG=true even if written as 'TRUE', '1', or 'True' in quotes."""
    for truthy_val in ["true", "TRUE", "True", " 1 ", '"true"']:
        prod = {
            "APP_ENV": "production",
            "DEBUG": truthy_val,
            "DATABASE_HOST": "prod-db",
            "DATABASE_PORT": "5432",
            "API_URL": "https://api",
            "LOG_LEVEL": "INFO"
        }
        dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
        stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}

        issues = detect_environment_variable_drift(dev, stage, prod)
        debug_issue = [d for d in issues if d.item_key == "DEBUG" and d.environment == "production"]
        assert len(debug_issue) > 0, f"Failed to detect truthy debug value: {truthy_val}"
        assert debug_issue[0].severity == SeverityEnum.CRITICAL

def test_adversarial_hidden_dev_hostname_in_prod():
    """Detects development hostname disguised in production database host."""
    prod = {
        "APP_ENV": "production",
        "DEBUG": "false",
        "DATABASE_HOST": "postgres://admin:secret@dev-db.internal:5432/app",
        "DATABASE_PORT": "5432",
        "API_URL": "https://api",
        "LOG_LEVEL": "INFO"
    }
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}

    issues = detect_environment_variable_drift(dev, stage, prod)
    db_issue = [d for d in issues if d.item_key == "DATABASE_HOST" and d.environment == "production"]
    assert len(db_issue) > 0
    assert db_issue[0].severity == SeverityEnum.CRITICAL

def test_adversarial_expired_secret_rotation():
    """Secret exists but age_days > 90 must trigger rotation warning."""
    staging_secrets = [{"name": "DATABASE_PASSWORD", "environment": "staging", "exists": True, "age_days": 10}]
    prod_secrets = [
        {"name": "DATABASE_PASSWORD", "environment": "production", "exists": True, "age_days": 120},
        {"name": "API_SECRET_KEY", "environment": "production", "exists": True, "age_days": 15},
        {"name": "PAYMENT_GATEWAY_TOKEN", "environment": "production", "exists": True, "age_days": 15}
    ]

    issues = detect_secret_metadata_drift(staging_secrets, prod_secrets)
    expired = [d for d in issues if "90 days" in d.reason]
    assert len(expired) > 0
    assert expired[0].severity == SeverityEnum.MEDIUM
