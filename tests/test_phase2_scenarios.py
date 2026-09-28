"""
test_phase2_scenarios.py - 18+ Comprehensive Real-World, Failure, and Adversarial Test Cases
Configuration Drift Validator (College Project Phase 2)

Covers all required scenarios from Section 12:
- Normal Cases: Correct prod config, expected env differences, secret metadata, runtime snapshot
- Failure Cases: Wrong db, debug enabled, missing env var, wrong API, missing secret, expired secret, runtime drift, infra mismatch, feature flag divergence
- Adversarial Cases: Capitalization, extra whitespace, "true" vs true, "5432" vs 5432, missing/extra key, similar hostname, pre-deployment pipeline
"""

import pytest
from backend.drift_engine import (
    detect_environment_variable_drift,
    detect_infrastructure_drift,
    detect_secret_metadata_drift,
    detect_runtime_drift,
    run_full_drift_analysis
)
from backend.normalizer import (
    normalize_value,
    values_are_equivalent,
    extract_host_from_url_or_endpoint
)
from backend.risk_score import calculate_risk_score
from backend.pre_deployment import run_pre_deployment_pipeline
from backend.git_detector import record_and_validate_commit
from backend.schemas import SeverityEnum

# =========================================================================
# 1. NORMAL CASES
# =========================================================================

def test_normal_correct_production_configuration():
    """Verify that a compliant, standard production configuration has zero critical/high blockers."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    staging = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, staging, prod)
    critical_issues = [d for d in discrepancies if d.severity == SeverityEnum.CRITICAL]
    assert len(critical_issues) == 0

def test_normal_expected_environment_differences():
    """Verify that dev-db, staging-db, and prod-db differences are recognized as expected policy, not errors."""
    dev = {"APP_ENV": "development", "DATABASE_HOST": "dev-db", "DEBUG": "true", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    staging = {"APP_ENV": "staging", "DATABASE_HOST": "staging-db", "DEBUG": "true", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DATABASE_HOST": "prod-db", "DEBUG": "false", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, staging, prod)
    db_discrepancies = [d for d in discrepancies if d.item_key == "DATABASE_HOST"]
    assert len(db_discrepancies) == 0

def test_normal_correct_secret_metadata():
    """Verify compliant secret metadata produces 0 secret drift issues."""
    stage_secrets = [{"name": "DATABASE_PASSWORD", "exists": True, "age_days": 30}]
    prod_secrets = [
        {"name": "DATABASE_PASSWORD", "exists": True, "age_days": 30},
        {"name": "API_SECRET_KEY", "exists": True, "age_days": 15},
        {"name": "PAYMENT_GATEWAY_TOKEN", "exists": True, "age_days": 10}
    ]
    discrepancies = detect_secret_metadata_drift(stage_secrets, prod_secrets)
    assert len(discrepancies) == 0

def test_normal_correct_runtime_snapshot():
    """Verify synchronized runtime snapshot produces 0 runtime drift issues."""
    approved_prod = {"DATABASE_HOST": "prod-db", "LOG_LEVEL": "INFO", "APP_ENV": "production"}
    runtime = {"database_host": "prod-db", "log_level": "INFO", "app_env": "production"}
    discrepancies = detect_runtime_drift(approved_prod, runtime)
    assert len(discrepancies) == 0

# =========================================================================
# 2. FAILURE CASES
# =========================================================================

def test_failure_wrong_database_in_production():
    """Production database accidentally set to staging-db must be CRITICAL."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    crit = [d for d in discrepancies if d.item_key == "DATABASE_HOST" and d.severity == SeverityEnum.CRITICAL]
    assert len(crit) == 1
    assert "non-production database" in crit[0].reason.lower()

def test_failure_debug_mode_enabled_in_production():
    """DEBUG=true in production must trigger CRITICAL severity."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "true", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    crit = [d for d in discrepancies if d.item_key == "DEBUG" and d.severity == SeverityEnum.CRITICAL]
    assert len(crit) == 1

def test_failure_missing_required_environment_variable():
    """Missing mandatory key DATABASE_HOST in production must be flagged as HIGH severity."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    # Production missing DATABASE_HOST
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    missing = [d for d in discrepancies if d.item_key == "DATABASE_HOST" and d.environment == "production"]
    assert len(missing) >= 1
    assert missing[0].severity == SeverityEnum.HIGH

def test_failure_wrong_api_endpoint_dev_in_prod():
    """Production API pointing to dev-api must trigger CRITICAL severity."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    api_issues = [d for d in discrepancies if d.item_key == "API_URL" and d.severity == SeverityEnum.CRITICAL]
    assert len(api_issues) == 1

def test_failure_missing_secret_metadata():
    """Mandatory secret missing in production must be detected as CRITICAL."""
    stage_secrets = [{"name": "DATABASE_PASSWORD", "exists": True, "age_days": 10}]
    prod_secrets = [
        {"name": "API_SECRET_KEY", "exists": True, "age_days": 10},
        {"name": "DATABASE_PASSWORD", "exists": False, "age_days": 10}
    ]
    discrepancies = detect_secret_metadata_drift(stage_secrets, prod_secrets)
    secret_issues = [d for d in discrepancies if d.item_key == "DATABASE_PASSWORD"]
    assert len(secret_issues) == 1
    assert secret_issues[0].severity == SeverityEnum.CRITICAL

def test_failure_expired_secret_metadata_rotation():
    """Secret older than 90 days must trigger rotation MEDIUM warning."""
    stage_secrets = [{"name": "DATABASE_PASSWORD", "exists": True, "age_days": 10}]
    prod_secrets = [
        {"name": "DATABASE_PASSWORD", "exists": True, "age_days": 115},
        {"name": "API_SECRET_KEY", "exists": True, "age_days": 20},
        {"name": "PAYMENT_GATEWAY_TOKEN", "exists": True, "age_days": 20}
    ]
    discrepancies = detect_secret_metadata_drift(stage_secrets, prod_secrets)
    expired = [d for d in discrepancies if "90 days" in d.reason]
    assert len(expired) == 1
    assert expired[0].severity == SeverityEnum.MEDIUM

def test_failure_runtime_drift_out_of_band():
    """Live container running with LOG_LEVEL=DEBUG when approved was INFO must trigger HIGH severity."""
    approved_prod = {"LOG_LEVEL": "INFO", "DATABASE_HOST": "prod-db"}
    runtime = {"log_level": "DEBUG", "database_host": "prod-db"}

    discrepancies = detect_runtime_drift(approved_prod, runtime)
    assert len(discrepancies) == 1
    assert discrepancies[0].severity == SeverityEnum.HIGH
    assert discrepancies[0].category == "runtime"

def test_failure_infrastructure_mismatch_port_and_replicas():
    """Production health check disabled must trigger HIGH; port mismatch between staging and prod triggers error."""
    dev_infra = {"replicas": 1, "port": 8080, "health_check": True}
    staging_infra = {"replicas": 2, "port": 8080, "health_check": True}
    prod_infra = {"replicas": 1, "port": 9090, "health_check": False}

    discrepancies = detect_infrastructure_drift(dev_infra, staging_infra, prod_infra)
    hc_issues = [d for d in discrepancies if d.item_key == "health_check"]
    port_issues = [d for d in discrepancies if d.item_key == "port"]
    replica_issues = [d for d in discrepancies if d.item_key == "replicas"]

    assert len(hc_issues) >= 1
    assert len(port_issues) >= 1
    assert len(replica_issues) >= 1

def test_failure_incorrect_feature_flag_staging_vs_prod():
    """Uncoordinated feature flag divergence is detected as MEDIUM severity."""
    dev = {"APP_ENV": "development", "FEATURE_NEW_CHECKOUT": "true", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "FEATURE_NEW_CHECKOUT": "true", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "FEATURE_NEW_CHECKOUT": "false", "DEBUG": "false", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    flag_issue = [d for d in discrepancies if d.item_key == "FEATURE_NEW_CHECKOUT"]
    assert len(flag_issue) >= 1
    assert flag_issue[0].severity == SeverityEnum.MEDIUM

# =========================================================================
# 3. ADVERSARIAL CASES
# =========================================================================

def test_adversarial_different_capitalization():
    """Equivalence check handles diverse capitalization without false alarm."""
    assert values_are_equivalent("TRUE", "true") is True
    assert values_are_equivalent("Prod-DB", "prod-db") is True
    assert values_are_equivalent("False", "false") is True

def test_adversarial_extra_whitespace_trimming():
    """Padding whitespace and inner quotes do not alter normalized equivalence."""
    assert values_are_equivalent("   prod-db   ", "prod-db") is True
    assert values_are_equivalent('"prod-db"', "prod-db") is True
    assert values_are_equivalent("'8080'", 8080) is True

def test_adversarial_string_vs_primitive_boolean():
    """String 'true' must be equivalent to Boolean True, and '0' must be equivalent to False."""
    assert values_are_equivalent("true", True) is True
    assert values_are_equivalent("false", False) is True
    assert values_are_equivalent("1", True) is True
    assert values_are_equivalent("0", False) is True

def test_adversarial_string_vs_numeric_port():
    """String port '5432' must equal integer 5432."""
    assert values_are_equivalent("5432", 5432) is True
    assert values_are_equivalent("8080", 8080) is True

def test_adversarial_similar_hostname_bypass_attempt():
    """Disguised dev hostname inside URI query string or subdomain must be blocked."""
    dev = {"APP_ENV": "development", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    # Disguised hostname pointing to dev-db via connection URI
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "postgresql://usr:pwd@dev-db.internal.corp:5432/db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    crit = [d for d in discrepancies if d.item_key == "DATABASE_HOST" and d.severity == SeverityEnum.CRITICAL]
    assert len(crit) >= 1

def test_adversarial_missing_key_and_extra_key():
    """Staging has key that is completely missing in Production."""
    dev = {"APP_ENV": "development", "EXTRA_SECRET_CONFIG": "xyz", "DEBUG": "true", "DATABASE_HOST": "dev-db", "DATABASE_PORT": "5432", "API_URL": "http://dev-api", "LOG_LEVEL": "DEBUG"}
    stage = {"APP_ENV": "staging", "EXTRA_SECRET_CONFIG": "xyz", "DEBUG": "true", "DATABASE_HOST": "staging-db", "DATABASE_PORT": "5432", "API_URL": "https://staging-api", "LOG_LEVEL": "INFO"}
    prod = {"APP_ENV": "production", "DEBUG": "false", "DATABASE_HOST": "prod-db", "DATABASE_PORT": "5432", "API_URL": "https://api", "LOG_LEVEL": "INFO"}

    discrepancies = detect_environment_variable_drift(dev, stage, prod)
    missing = [d for d in discrepancies if d.item_key == "EXTRA_SECRET_CONFIG"]
    assert len(missing) >= 1

# =========================================================================
# 4. PHASE 2 WORKFLOW & PIPELINE TESTS
# =========================================================================

def test_phase2_pre_deployment_pipeline_and_git_commit():
    """Verify pre-deployment pipeline executes all stages and Git commit validator blocks dangerous commit."""
    # Test Git commit validator with dangerous change
    commit_res = record_and_validate_commit(
        author="Junior-Dev",
        message="test: quick db hotfix",
        environment="production",
        changed_configs={"DATABASE_HOST": "dev-db"}
    )
    assert commit_res["validation_result"] == "BLOCKED"
    assert commit_res["risk_level"] == "CRITICAL"
    assert commit_res["risk_score"] >= 75

    # Test pre-deployment pipeline
    pipeline = run_pre_deployment_pipeline(target_env="production")
    assert "stages" in pipeline
    assert len(pipeline["stages"]) == 6
    assert pipeline["stages"][0]["stage_name"] == "Configuration Check"
    assert pipeline["stages"][5]["stage_name"] == "Risk Analysis"
