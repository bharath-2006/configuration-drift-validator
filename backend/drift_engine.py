"""
drift_engine.py - Configuration Drift Detection Engine
Orchestrates comparison across Development, Staging, Production, and Runtime Snapshots.
Differentiates expected environment variances from dangerous drift.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.schemas import ValidationSummary, DriftDiscrepancy, SeverityEnum
from backend.normalizer import values_are_equivalent, normalize_value
from backend.validation_policy import (
    ENVIRONMENT_POLICIES,
    FORBIDDEN_PROD_INDICATORS,
    REQUIRED_ENV_VARS,
    REQUIRED_SECRETS,
    is_expected_difference
)
from backend.risk_engine import classify_discrepancy

def detect_environment_variable_drift(
    dev_vars: Dict[str, Any],
    staging_vars: Dict[str, Any],
    prod_vars: Dict[str, Any]
) -> List[DriftDiscrepancy]:
    """
    Compares environment variables across Dev, Staging, and Production.
    Validates required keys, environment-specific policies, and unintended leakage.
    """
    discrepancies: List[DriftDiscrepancy] = []

    # 1. Check for Production-specific policy rules
    # A. DEBUG check in Production
    prod_debug = prod_vars.get("DEBUG")
    if prod_debug is not None:
        norm_val, _ = normalize_value(prod_debug)
        if norm_val is True:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="env_var",
                key="DEBUG",
                expected_val="false",
                actual_val=prod_debug
            ))

    # B. Forbidden hostnames in Production (e.g., dev-db or staging-db in prod)
    for key, val in prod_vars.items():
        val_str = str(val).lower()
        for forbidden in FORBIDDEN_PROD_INDICATORS:
            if forbidden in val_str:
                discrepancies.append(classify_discrepancy(
                    environment="production",
                    category="env_var",
                    key=key,
                    expected_val="prod-db" if "DATABASE" in key.upper() else "https://api",
                    actual_val=val
                ))

    # C. Required keys check
    for req_key in REQUIRED_ENV_VARS:
        for env_name, env_dict in [("development", dev_vars), ("staging", staging_vars), ("production", prod_vars)]:
            if req_key not in env_dict or env_dict[req_key] is None or env_dict[req_key] == "":
                discrepancies.append(classify_discrepancy(
                    environment=env_name,
                    category="env_var",
                    key=req_key,
                    expected_val=f"Defined for {env_name}",
                    actual_val=None
                ))

    # D. Missing keys across environments (keys in staging missing in prod)
    all_keys = set(dev_vars.keys()) | set(staging_vars.keys()) | set(prod_vars.keys())
    for key in all_keys:
        if key not in prod_vars and key in staging_vars:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="env_var",
                key=key,
                expected_val=staging_vars.get(key),
                actual_val=None
            ))

        # Check for unexpected drift between Staging and Production where values should match
        if key in staging_vars and key in prod_vars:
            val_stage = staging_vars[key]
            val_prod = prod_vars[key]

            # If not equivalent AND not an expected difference
            if not values_are_equivalent(val_stage, val_prod):
                if not is_expected_difference(key, "staging", "production", val_stage, val_prod):
                    # Check if production value violates expected policy
                    discrepancies.append(classify_discrepancy(
                        environment="production",
                        category="env_var",
                        key=key,
                        expected_val=val_stage,
                        actual_val=val_prod
                    ))

    return discrepancies

def detect_infrastructure_drift(
    dev_infra: Dict[str, Any],
    staging_infra: Dict[str, Any],
    prod_infra: Dict[str, Any]
) -> List[DriftDiscrepancy]:
    """
    Compares infrastructure definitions (replicas, port, health_check, memory, cpu).
    """
    discrepancies: List[DriftDiscrepancy] = []

    # 1. Production Health Check
    prod_hc = prod_infra.get("health_check")
    if prod_hc is not None:
        norm_hc, _ = normalize_value(prod_hc)
        if norm_hc is False:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="infrastructure",
                key="health_check",
                expected_val="true",
                actual_val=prod_hc
            ))
    elif "service" in prod_infra or "port" in prod_infra:
        # If infra exists but health_check missing
        discrepancies.append(classify_discrepancy(
            environment="production",
            category="infrastructure",
            key="health_check",
            expected_val="true",
            actual_val=False
        ))

    # 2. Port mismatch between staging and production
    stage_port = staging_infra.get("port")
    prod_port = prod_infra.get("port")
    if stage_port and prod_port and not values_are_equivalent(stage_port, prod_port):
        discrepancies.append(classify_discrepancy(
            environment="production",
            category="infrastructure",
            key="port",
            expected_val=str(stage_port),
            actual_val=str(prod_port)
        ))

    # 3. Production Replica Count
    prod_replicas = prod_infra.get("replicas")
    if prod_replicas is not None:
        norm_rep, _ = normalize_value(prod_replicas)
        if int(norm_rep or 1) < 2:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="infrastructure",
                key="replicas",
                expected_val=">= 2",
                actual_val=prod_replicas
            ))

    return discrepancies

def detect_secret_metadata_drift(
    staging_secrets: List[Dict[str, Any]],
    prod_secrets: List[Dict[str, Any]]
) -> List[DriftDiscrepancy]:
    """
    Compares secret metadata without ever inspecting secret values.
    Checks: secret presence, missing secrets in production, rotation age.
    """
    discrepancies: List[DriftDiscrepancy] = []

    stage_sec_map = {s["name"]: s for s in staging_secrets}
    prod_sec_map = {s["name"]: s for s in prod_secrets}

    # 1. Check Required Secrets in Production
    for req_sec in REQUIRED_SECRETS:
        if req_sec not in prod_sec_map:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="secret",
                key=req_sec,
                expected_val="exists: true",
                actual_val=False
            ))
        else:
            sec_item = prod_sec_map[req_sec]
            is_present = sec_item.get("exists") if "exists" in sec_item else sec_item.get("is_present", True)
            norm_pres, _ = normalize_value(is_present)
            if not norm_pres:
                discrepancies.append(classify_discrepancy(
                    environment="production",
                    category="secret",
                    key=req_sec,
                    expected_val="exists: true",
                    actual_val=False
                ))

    # 2. Check for secrets present in staging but absent in prod
    for sec_name, sec_meta in stage_sec_map.items():
        if sec_name not in prod_sec_map:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="secret",
                key=sec_name,
                expected_val="exists: true",
                actual_val=False
            ))

    # 3. Check for expired/stale secret rotations
    for sec_name, sec_meta in prod_sec_map.items():
        age = sec_meta.get("age_days", 0)
        if age > 90:
            discrepancies.append(classify_discrepancy(
                environment="production",
                category="secret",
                key=sec_name,
                expected_val="rotation < 90 days",
                actual_val=f"{age} days",
                extra_context={"age_days": age}
            ))

    return discrepancies

def detect_runtime_drift(
    approved_prod_vars: Dict[str, Any],
    runtime_snapshot: Optional[Dict[str, Any]]
) -> List[DriftDiscrepancy]:
    """
    Compares approved production configuration against live runtime container snapshot.
    """
    discrepancies: List[DriftDiscrepancy] = []
    if not runtime_snapshot:
        return discrepancies

    # Runtime snapshot usually contains runtime keys like log_level, app_version, database_host, etc.
    for key, runtime_val in runtime_snapshot.items():
        key_upper = key.upper()
        if key_upper in approved_prod_vars:
            approved_val = approved_prod_vars[key_upper]
            if not values_are_equivalent(approved_val, runtime_val):
                discrepancies.append(classify_discrepancy(
                    environment="production",
                    category="runtime",
                    key=key_upper,
                    expected_val=str(approved_val),
                    actual_val=str(runtime_val)
                ))

    return discrepancies

def run_full_drift_analysis(
    dev_bundle: Dict[str, Any],
    staging_bundle: Dict[str, Any],
    prod_bundle: Dict[str, Any],
    runtime_snapshot: Optional[Dict[str, Any]] = None
) -> ValidationSummary:
    """
    Runs the comprehensive drift validation engine across all facets.
    Generates summary metrics and deployment gate decision.
    """
    all_discrepancies: List[DriftDiscrepancy] = []

    # 1. Environment variables drift
    all_discrepancies.extend(detect_environment_variable_drift(
        dev_bundle.get("variables", {}),
        staging_bundle.get("variables", {}),
        prod_bundle.get("variables", {})
    ))

    # 2. Infrastructure definitions drift
    all_discrepancies.extend(detect_infrastructure_drift(
        dev_bundle.get("infrastructure", {}),
        staging_bundle.get("infrastructure", {}),
        prod_bundle.get("infrastructure", {})
    ))

    # 3. Secret metadata drift
    all_discrepancies.extend(detect_secret_metadata_drift(
        staging_bundle.get("secrets", []),
        prod_bundle.get("secrets", [])
    ))

    # 4. Runtime snapshot drift
    all_discrepancies.extend(detect_runtime_drift(
        prod_bundle.get("variables", {}),
        runtime_snapshot
    ))

    # Deduplicate discrepancies by (environment, category, item_key, severity)
    unique_map = {}
    for d in all_discrepancies:
        unique_key = (d.environment, d.category, d.item_key, d.severity)
        if unique_key not in unique_map:
            unique_map[unique_key] = d
    final_discrepancies = list(unique_map.values())
    # Deterministic stable sorting by severity rank, environment, category, item_key
    sev_rank = {SeverityEnum.CRITICAL: 0, SeverityEnum.HIGH: 1, SeverityEnum.MEDIUM: 2, SeverityEnum.LOW: 3}
    final_discrepancies.sort(key=lambda d: (sev_rank.get(d.severity, 4), d.environment, d.category, d.item_key))

    # Count severities
    crit_count = sum(1 for d in final_discrepancies if d.severity == SeverityEnum.CRITICAL)
    high_count = sum(1 for d in final_discrepancies if d.severity == SeverityEnum.HIGH)
    med_count = sum(1 for d in final_discrepancies if d.severity == SeverityEnum.MEDIUM)
    low_count = sum(1 for d in final_discrepancies if d.severity == SeverityEnum.LOW)

    # Deployment Gate Decision:
    # ANY Critical issue BLOCKS deployment.
    is_deployment_allowed = (crit_count == 0)
    if not is_deployment_allowed:
        deployment_msg = f"❌ Production deployment BLOCKED: {crit_count} Critical configuration discrepancies detected."
    elif high_count > 0:
        deployment_msg = f"⚠️ Production deployment ALLOWED with warnings ({high_count} High issues require attention)."
    else:
        deployment_msg = "✅ Production deployment APPROVED: No blocking configuration drift detected."

    # Environment Status
    env_status = {
        "development": "Healthy",
        "staging": "Healthy",
        "production": "Healthy"
    }

    if crit_count > 0:
        env_status["production"] = "Critical"
    elif high_count > 0:
        env_status["production"] = "Warning"

    run_id = f"VAL-{uuid.uuid4().hex[:8].upper()}"
    timestamp_str = datetime.now().isoformat()

    return ValidationSummary(
        validation_run_id=run_id,
        timestamp=timestamp_str,
        environment_status=env_status,
        total_discrepancies=len(final_discrepancies),
        critical_count=crit_count,
        high_count=high_count,
        medium_count=med_count,
        low_count=low_count,
        production_deployment_allowed=is_deployment_allowed,
        deployment_message=deployment_msg,
        discrepancies=final_discrepancies
    )
