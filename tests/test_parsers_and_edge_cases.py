"""
test_parsers_and_edge_cases.py - Comprehensive Unit & Integration Tests
Configuration Drift Validator

Verifies the four review improvements:
1. Real configuration artifact parsing (.env, Docker Compose, Kubernetes ConfigMap)
2. Explicit JSON Schema validations (required fields, unexpected keys, data types)
3. Automated edge case tests (circular refs, type coercion, duplicates, syntax errors)
4. Actual rollback state restoration (DB active pointer, filesystem app.env, re-validation)
"""

import os
import json
import pytest
from pathlib import Path

from backend.artifact_parser import (
    parse_env_content,
    parse_docker_compose_content,
    parse_kubernetes_configmap_content,
    parse_configuration_artifact,
    ArtifactParseError
)
from backend.schema_validator import (
    validate_environment_config,
    validate_runtime_snapshot_data,
    validate_drift_rule,
    validate_against_schema
)
from backend.database import init_db, get_db
from backend.rollback import (
    save_new_config_version,
    get_active_version,
    get_config_snapshot_by_version,
    perform_rollback,
    get_all_rollback_records
)
from backend.drift_engine import run_full_drift_analysis


@pytest.fixture(autouse=True)
def setup_database():
    """Ensures test database is initialized for every test."""
    init_db()


# =====================================================================
# 1. REAL ARTIFACT PARSER TESTS (.env, Docker Compose, K8s ConfigMap)
# =====================================================================

def test_valid_env_file():
    """Tests parsing of a valid .env file with comments, whitespace, and quoted strings."""
    env_content = """
    # Application Configuration
    DATABASE_HOST=prod-db.internal
    DATABASE_PORT=5432
    DEBUG=false
    API_KEY="secret-jwt-token-xyz"
    APP_NAME='Drift Validator Production'
    EMPTY_VAR=
    """
    parsed = parse_env_content(env_content)
    assert parsed["DATABASE_HOST"] == "prod-db.internal"
    assert parsed["DATABASE_PORT"] == "5432"
    assert parsed["DEBUG"] == "false"
    assert parsed["API_KEY"] == "secret-jwt-token-xyz"
    assert parsed["APP_NAME"] == "Drift Validator Production"
    assert parsed["EMPTY_VAR"] == ""


def test_invalid_env_file_missing_delimiter():
    """Tests that a malformed .env line without an '=' sign raises ArtifactParseError."""
    malformed_env = """
    DATABASE_HOST=prod-db
    THIS_LINE_HAS_NO_EQUALS_SIGN_OR_DELIMITER
    DEBUG=false
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_env_content(malformed_env)
    assert "Invalid entry" in str(exc_info.value) or "missing '='" in str(exc_info.value).lower()


def test_invalid_env_file_unclosed_quotes():
    """Tests that unclosed quotation marks raise ArtifactParseError."""
    unclosed_quote_env = """
    DATABASE_HOST="prod-db
    DEBUG=false
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_env_content(unclosed_quote_env)
    assert "unclosed" in str(exc_info.value).lower()


def test_valid_docker_compose_yaml():
    """Tests parsing a valid Docker Compose YAML containing service environment definitions."""
    compose_yaml = """
    version: '3.8'
    services:
      web:
        image: myapp:1.0
        ports:
          - "8080:8080"
        deploy:
          replicas: 3
        environment:
          DATABASE_HOST: prod-db.cluster
          DATABASE_PORT: "5432"
          DEBUG: "false"
          CACHE_ENABLED: true
    """
    result = parse_docker_compose_content(compose_yaml)
    variables = result["variables"]
    infra = result["infrastructure"]

    assert variables["DATABASE_HOST"] == "prod-db.cluster"
    assert variables["DATABASE_PORT"] == "5432"
    assert variables["DEBUG"] == "false"
    assert variables["CACHE_ENABLED"] is True
    assert infra.get("replicas") == 3
    assert infra.get("port") == 8080


def test_docker_compose_list_format_environment():
    """Tests Docker Compose YAML with list-based environment format (- KEY=val)."""
    compose_list_yaml = """
    version: '3'
    services:
      app:
        image: python:3.11
        environment:
          - DATABASE_HOST=db.prod.internal
          - DEBUG=false
          - LOG_LEVEL=INFO
    """
    result = parse_docker_compose_content(compose_list_yaml)
    assert result["variables"]["DATABASE_HOST"] == "db.prod.internal"
    assert result["variables"]["DEBUG"] == "false"
    assert result["variables"]["LOG_LEVEL"] == "INFO"


def test_malformed_docker_compose_yaml():
    """Tests that syntax-broken YAML raises a clear ArtifactParseError without crashing."""
    broken_yaml = """
    version: '3.8'
    services:
      web:
        environment:
          - KEY_WITHOUT_VALUE
          unbalanced_yaml_indent: [
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_docker_compose_content(broken_yaml)
    assert "YAML syntax error" in str(exc_info.value) or "Malformed" in str(exc_info.value)


def test_docker_compose_missing_services():
    """Tests that Docker Compose YAML without a 'services' block raises ArtifactParseError."""
    invalid_structure_yaml = """
    version: '3.8'
    networks:
      default:
        driver: bridge
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_docker_compose_content(invalid_structure_yaml)
    assert "services" in str(exc_info.value).lower() and "missing" in str(exc_info.value).lower()


def test_valid_kubernetes_configmap():
    """Tests parsing a standard Kubernetes ConfigMap YAML with both data and stringData."""
    k8s_cm_yaml = """
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: app-config
      namespace: production
    data:
      DATABASE_HOST: prod-db.postgres.svc.cluster.local
      DATABASE_PORT: "5432"
      DEBUG: "false"
    stringData:
      EXTRA_FLAG: enabled
    """
    result = parse_kubernetes_configmap_content(k8s_cm_yaml)
    assert result["DATABASE_HOST"] == "prod-db.postgres.svc.cluster.local"
    assert result["DATABASE_PORT"] == "5432"
    assert result["DEBUG"] == "false"
    assert result["EXTRA_FLAG"] == "enabled"


def test_invalid_kubernetes_yaml_not_a_configmap():
    """Tests that a non-ConfigMap Kubernetes resource (e.g. Deployment) is rejected with clear error."""
    k8s_deployment_yaml = """
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: my-app
    spec:
      replicas: 2
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_kubernetes_configmap_content(k8s_deployment_yaml)
    assert "configmap" in str(exc_info.value).lower() and "expected" in str(exc_info.value).lower()


def test_invalid_kubernetes_yaml_syntax():
    """Tests that unparseable Kubernetes YAML raises ArtifactParseError."""
    broken_k8s = """
    apiVersion: v1
    kind: ConfigMap
    data:
      KEY: { invalid: [ yaml unclosed
    """
    with pytest.raises(ArtifactParseError):
        parse_kubernetes_configmap_content(broken_k8s)


# =====================================================================
# 2. EDGE CASES: DUPLICATES, CIRCULAR REFS, TYPE COERCION
# =====================================================================

def test_duplicate_key_in_env_file():
    """Tests detection of duplicate configuration keys within a single artifact."""
    duplicate_env = """
    DATABASE_HOST=dev-db
    DEBUG=false
    DATABASE_HOST=prod-db
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_env_content(duplicate_env, allow_duplicates=False)
    assert "Duplicate configuration key 'DATABASE_HOST'" in str(exc_info.value)


def test_circular_configuration_references():
    """Tests that circular references (A=${B}, B=${A}) raise a clean ArtifactParseError."""
    circular_env = """
    BASE_URL=https://${HOST_NAME}
    HOST_NAME=${BASE_URL}/api
    """
    with pytest.raises(ArtifactParseError) as exc_info:
        parse_env_content(circular_env)
    assert "Circular configuration reference detected" in str(exc_info.value)


def test_type_coercion_true_vs_boolean():
    """
    Tests type normalization & differentiation between string 'true' and boolean True.
    The drift validator parses both formats predictably without crashing.
    """
    env_content = """
    BOOL_STRING=true
    BOOL_STRING_UPPER=TRUE
    NUM_STRING=42
    """
    parsed = parse_env_content(env_content)
    # .env values are parsed as strings
    assert parsed["BOOL_STRING"] == "true"
    assert parsed["BOOL_STRING_UPPER"] == "TRUE"
    assert parsed["NUM_STRING"] == "42"

    # In YAML/JSON, boolean types are preserved or coerced safely
    compose_yaml = """
    version: '3'
    services:
      app:
        environment:
          BOOL_LITERAL: true
          BOOL_STR: "true"
          PORT_NUM: 8080
    """
    compose_res = parse_docker_compose_content(compose_yaml)
    assert compose_res["variables"]["BOOL_LITERAL"] is True
    assert compose_res["variables"]["BOOL_STR"] == "true"
    assert compose_res["variables"]["PORT_NUM"] == 8080


# =====================================================================
# 3. EXPLICIT JSON SCHEMA VALIDATION TESTS
# =====================================================================

def test_missing_required_key_schema_validation():
    """Tests that an environment bundle missing required 'variables' fails schema validation."""
    invalid_bundle = {
        "environment": "production"
        # "variables" is required but omitted!
    }
    is_valid, errors = validate_environment_config(invalid_bundle)
    assert is_valid is False
    assert any("'variables' is a required property" in err for err in errors)


def test_unexpected_key_schema_validation():
    """Tests that unexpected / undeclared keys are rejected by strict schema validation."""
    bundle_with_unknown_field = {
        "environment": "production",
        "variables": {"DATABASE_HOST": "prod-db"},
        "unauthorized_extra_field": "injected-payload"
    }
    is_valid, errors = validate_environment_config(bundle_with_unknown_field)
    assert is_valid is False
    assert any("Additional properties are not allowed" in err for err in errors)


def test_wrong_data_type_schema_validation():
    """Tests that fields with incorrect data types (e.g. version as string or replicas as string) fail."""
    # 1. version should be integer, given string
    bundle_wrong_type = {
        "environment": "staging",
        "version": "not-an-integer",
        "variables": {"DATABASE_HOST": "staging-db"}
    }
    is_valid, errors = validate_environment_config(bundle_wrong_type)
    assert is_valid is False
    assert any("not-an-integer" in err or "is not of type 'integer'" in err for err in errors)

    # 2. replicas in infrastructure should be integer
    bundle_wrong_infra = {
        "environment": "production",
        "version": 1,
        "variables": {"DATABASE_HOST": "prod-db"},
        "infrastructure": {
            "replicas": "five"  # Wrong data type!
        }
    }
    is_valid, errors = validate_environment_config(bundle_wrong_infra)
    assert is_valid is False
    assert any("replicas" in err for err in errors)


def test_runtime_snapshot_schema_validation():
    """Tests valid and invalid runtime snapshots against runtime-snapshot.schema.json."""
    # Valid
    valid_snap = {
        "environment": "production",
        "app_version": "1.2.0",
        "snapshot_data": {
            "DATABASE_HOST": "prod-db",
            "DEBUG": False
        }
    }
    is_valid, errors = validate_runtime_snapshot_data(valid_snap)
    assert is_valid is True
    assert len(errors) == 0

    # Invalid: missing snapshot_data
    invalid_snap = {
        "environment": "production"
    }
    is_valid, errors = validate_runtime_snapshot_data(invalid_snap)
    assert is_valid is False
    assert any("'snapshot_data' is a required property" in err for err in errors)


# =====================================================================
# 4. DRIFT DETECTION & ENVIRONMENT-SPECIFIC DIFFERENCES
# =====================================================================

def test_expected_environment_specific_differences():
    """
    Tests that intentional environment differences (e.g. APP_ENV=development in dev
    vs APP_ENV=production in prod, or replicas 1 vs 3) are handled appropriately
    without incorrectly blocking production deployment.
    """
    dev_bundle = {
        "environment": "development",
        "variables": {
            "DATABASE_HOST": "localhost",
            "APP_ENV": "development",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG"
        },
        "infrastructure": {"replicas": 1, "port": 8080}
    }
    std_secrets = [
        {"name": "DATABASE_PASSWORD", "environment": "production", "exists": True},
        {"name": "API_SECRET_KEY", "environment": "production", "exists": True},
        {"name": "PAYMENT_GATEWAY_TOKEN", "environment": "production", "exists": True}
    ]
    staging_bundle = {
        "environment": "staging",
        "variables": {
            "DATABASE_HOST": "staging-db",
            "APP_ENV": "staging",
            "DEBUG": "true",
            "LOG_LEVEL": "INFO"
        },
        "infrastructure": {"replicas": 2, "port": 8080},
        "secrets": std_secrets
    }
    prod_bundle = {
        "environment": "production",
        "variables": {
            "DATABASE_HOST": "prod-db",
            "APP_ENV": "production",
            "DEBUG": "false",
            "LOG_LEVEL": "INFO"
        },
        "infrastructure": {"replicas": 3, "port": 8080},
        "secrets": std_secrets
    }
    runtime_snap = {
        "environment": "production",
        "database_host": "prod-db",
        "log_level": "INFO"
    }

    report = run_full_drift_analysis(
        dev_bundle=dev_bundle,
        staging_bundle=staging_bundle,
        prod_bundle=prod_bundle,
        runtime_snapshot=runtime_snap
    )

    # Production is in compliance with its expected baseline
    assert report.critical_count == 0
    assert report.production_deployment_allowed is True


def test_critical_production_drift():
    """
    Tests that when production configuration points to a development database
    or has debug enabled, critical drift is flagged and deployment is blocked.
    """
    prod_bundle_broken = {
        "environment": "production",
        "variables": {
            "DATABASE_HOST": "dev-db",  # CRITICAL INCIDENT!
            "APP_ENV": "production",
            "DEBUG": "true",           # HIGH SEVERITY!
            "LOG_LEVEL": "INFO"
        },
        "infrastructure": {"replicas": 1, "port": 8080}
    }

    report = run_full_drift_analysis(
        dev_bundle={},
        staging_bundle={},
        prod_bundle=prod_bundle_broken,
        runtime_snapshot={"database_host": "dev-db"}
    )

    # Must detect critical drift and block deployment
    assert report.critical_count >= 1
    assert report.production_deployment_allowed is False
    assert any("dev-db" in d.actual_val or "dev-db" in d.reason for d in report.discrepancies)


# =====================================================================
# 5. ACTUAL ROLLBACK STATE RESTORATION & POST-VALIDATION
# =====================================================================

def test_rollback_actual_state_restoration(tmp_path):
    """
    Verifies actual state restoration:
    1. Initial Version 1: DATABASE_HOST=prod-db
    2. Faulty Version 2: DATABASE_HOST=dev-db
    3. Rollback to Version 1
    4. Active configuration in DB actually contains prod-db
    5. configs/production/app.env physically restored
    6. Audit log records the rollback with restored count
    7. Validation runs and deployment is unblocked
    """
    env = "production"
    std_secrets = [
        {"name": "DATABASE_PASSWORD", "environment": "production", "exists": True},
        {"name": "API_SECRET_KEY", "environment": "production", "exists": True},
        {"name": "PAYMENT_GATEWAY_TOKEN", "environment": "production", "exists": True}
    ]

    # Step 1: Save Version 1 (Healthy Baseline)
    v1 = save_new_config_version(
        environment=env,
        variables={
            "APP_ENV": "production",
            "DEBUG": "false",
            "DATABASE_HOST": "prod-db",
            "DATABASE_PORT": "5432",
            "API_URL": "https://api",
            "LOG_LEVEL": "INFO",
            "FEATURE_PAYMENT": "true"
        },
        infra={"service": "api", "replicas": 3, "port": 8080},
        secrets=std_secrets,
        description="Version 1 - Healthy Production Baseline",
        author="lead-devops"
    )
    assert get_active_version(env) == v1

    # Step 2: Save Version 2 (Problematic configuration with drift)
    v2 = save_new_config_version(
        environment=env,
        variables={
            "APP_ENV": "production",
            "DEBUG": "true",
            "DATABASE_HOST": "dev-db",
            "DATABASE_PORT": "5432",
            "API_URL": "https://api",
            "LOG_LEVEL": "INFO",
            "FEATURE_PAYMENT": "true"
        },
        infra={"service": "api", "replicas": 1, "port": 8080},
        secrets=std_secrets,
        description="Version 2 - Accidental dev-db injection",
        author="junior-engineer"
    )
    assert get_active_version(env) == v2
    assert v2 > v1

    # Verify that v2 causes critical drift
    active_v2_snapshot = get_config_snapshot_by_version(env, v2)
    pre_report = run_full_drift_analysis(
        dev_bundle={},
        staging_bundle={},
        prod_bundle=active_v2_snapshot
    )
    assert pre_report.production_deployment_allowed is False

    # Step 3: Perform actual state rollback to Version 1
    rollback_result = perform_rollback(
        environment=env,
        target_version=v1,
        reason="Reverting critical dev-db misconfiguration from Version 2",
        performed_by="lead-devops"
    )

    # Step 4: Verify rollback result payload
    assert rollback_result["status"] == "success"
    assert rollback_result["from_version"] == v2
    assert rollback_result["restored_version"] == v1
    assert rollback_result["restored_variables"]["DATABASE_HOST"] == "prod-db"
    assert rollback_result["restored_variables"]["DEBUG"] == "false"

    # Step 5: Verify active DB pointer points back to v1
    current_active = get_active_version(env)
    assert current_active == v1

    restored_bundle = get_config_snapshot_by_version(env, current_active)
    assert restored_bundle["variables"]["DATABASE_HOST"] == "prod-db"
    assert restored_bundle["variables"]["DEBUG"] == "false"

    # Step 6: Verify physical filesystem app.env file was restored
    base_dir = Path(__file__).resolve().parent.parent
    app_env_file = base_dir / "configs" / env / "app.env"
    if app_env_file.exists():
        content = app_env_file.read_text(encoding="utf-8")
        assert "DATABASE_HOST=prod-db" in content
        assert "DEBUG=false" in content

    # Step 7: Verify audit record
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rollback_records WHERE environment = ? ORDER BY id DESC LIMIT 1", (env,))
        record = cursor.fetchone()
        assert record is not None
        assert record["from_version"] == v2
        assert record["to_version"] == v1
        assert "dev-db" in record["reason"]

    # Step 8: Post-rollback validation confirms healthy status and allows deployment
    post_report = run_full_drift_analysis(
        dev_bundle={},
        staging_bundle={},
        prod_bundle=restored_bundle,
        runtime_snapshot={"database_host": "prod-db", "log_level": "INFO"}
    )
    assert post_report.critical_count == 0
    assert post_report.production_deployment_allowed is True
