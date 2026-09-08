"""
test_drift.py - Required Core Failure and Edge Cases from Section 13
1. Production DEBUG Enabled -> Critical
2. Wrong Database (Prod pointing to dev-db) -> Critical
3. Missing Production Secret -> Critical/High
4. Runtime Drift -> High
5. Expected Difference (dev-db vs prod-db) -> NOT an error
"""

import pytest
from backend.drift_engine import (
    detect_environment_variable_drift,
    detect_secret_metadata_drift,
    detect_runtime_drift,
    run_full_drift_analysis
)
from backend.schemas import SeverityEnum

def test_case_1_production_debug_enabled():
    """Case 1: Production DEBUG=true must be detected as CRITICAL."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    staging = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "true", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, staging, prod)
    debug_issues = [d for d in discrepancies if d.item_key == "DEBUG" and d.environment == "production"]

    assert len(debug_issues) > 0
    assert debug_issues[0].severity == SeverityEnum.CRITICAL
    assert "debug mode" in debug_issues[0].reason.lower()

def test_case_2_wrong_database():
    """Case 2: Production points to dev-db must be detected as CRITICAL."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    staging = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, staging, prod)
    db_issues = [d for d in discrepancies if d.item_key == "DATABASE_HOST" and d.environment == "production"]

    assert len(db_issues) > 0
    assert db_issues[0].severity == SeverityEnum.CRITICAL
    assert "non-production database" in db_issues[0].reason.lower()

def test_case_3_missing_production_secret():
    """Case 3: Required production secret missing must be detected as CRITICAL."""
    staging_secrets = [
        {"name": "DATABASE_PASSWORD", "environment": "staging", "exists": True},
        {"name": "API_SECRET_KEY", "environment": "staging", "exists": True}
    ]
    # Production is missing DATABASE_PASSWORD
    prod_secrets = [
        {"name": "API_SECRET_KEY", "environment": "production", "exists": True},
        {"name": "DATABASE_PASSWORD", "environment": "production", "exists": False}
    ]

    discrepancies = detect_secret_metadata_drift(staging_secrets, prod_secrets)
    secret_issues = [d for d in discrepancies if d.item_key == "DATABASE_PASSWORD"]

    assert len(secret_issues) > 0
    assert secret_issues[0].severity == SeverityEnum.CRITICAL
    assert "missing" in secret_issues[0].reason.lower()

def test_case_4_runtime_drift():
    """Case 4: Approved config LOG_LEVEL=INFO but runtime snapshot has DEBUG -> HIGH."""
    approved_prod = {"LOG_LEVEL": "INFO", "DATABASE_HOST": "prod-db"}
    runtime_snapshot = {"log_level": "DEBUG", "database_host": "prod-db"}

    discrepancies = detect_runtime_drift(approved_prod, runtime_snapshot)
    runtime_issues = [d for d in discrepancies if d.item_key == "LOG_LEVEL"]

    assert len(runtime_issues) > 0
    assert runtime_issues[0].severity == SeverityEnum.HIGH
    assert runtime_issues[0].category == "runtime"

def test_case_5_expected_difference():
    """Case 5: Development database dev-db vs production prod-db must NOT be classified as dangerous drift."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    staging = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, staging, prod)
    # Filter out any issues flagged for DATABASE_HOST in production
    db_issues = [d for d in discrepancies if d.item_key == "DATABASE_HOST"]
    assert len(db_issues) == 0, "Legitimate database host differences should not be flagged as drift!"
