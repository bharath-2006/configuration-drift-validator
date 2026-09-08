"""
risk_engine.py - Severity and Risk Analyzer
Evaluates configuration discrepancies and assigns severity (CRITICAL, HIGH, MEDIUM, LOW).
Provides clear human-readable rationale and actionable recommendations.
"""

from typing import Dict, Any, Optional
from backend.schemas import SeverityEnum, DriftDiscrepancy
from backend.normalizer import normalize_value

def classify_discrepancy(
    environment: str,
    category: str,
    key: str,
    expected_val: Any,
    actual_val: Any,
    extra_context: Optional[Dict[str, Any]] = None
) -> DriftDiscrepancy:
    """
    Evaluates an anomaly or drift condition and classifies its risk level.
    """
    env_lower = environment.lower()
    key_upper = key.upper()
    is_prod = env_lower == "production"

    norm_actual, actual_type = normalize_value(actual_val)
    norm_expected, expected_type = normalize_value(expected_val)

    # -------------------------------------------------------------
    # 1. CRITICAL SEVERITY CHECKS (Production Breakers)
    # -------------------------------------------------------------

    # Case A: Production DEBUG enabled
    if is_prod and key_upper == "DEBUG" and norm_actual is True:
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val="false",
            actual_val=str(actual_val),
            severity=SeverityEnum.CRITICAL,
            reason="Debug mode is enabled in production. This exposes internal stack traces, database schema details, and sensitive system state to potential attackers.",
            recommendation="Immediately set DEBUG=false in production configuration before deploying."
        )

    # Case B: Production database pointing to Dev or Staging database
    if is_prod and "DATABASE" in key_upper and any(bad in str(actual_val).lower() for bad in ["dev-db", "localhost", "127.0.0.1", "staging-db"]):
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=str(expected_val) if expected_val else "prod-db",
            actual_val=str(actual_val),
            severity=SeverityEnum.CRITICAL,
            reason=f"Production {key} points to non-production database ('{actual_val}'). This will cause production data corruption or data loss in testing environments.",
            recommendation=f"Update {key} to point to the secure production database cluster ('prod-db')."
        )

    # Case C: Production API pointing to Dev or Staging endpoint
    if is_prod and "API" in key_upper and any(bad in str(actual_val).lower() for bad in ["dev-api", "staging-api", "localhost"]):
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=str(expected_val) if expected_val else "https://api",
            actual_val=str(actual_val),
            severity=SeverityEnum.CRITICAL,
            reason=f"Production is configured with non-production API endpoint '{actual_val}'. Live transactions will hit test servers.",
            recommendation="Switch the API endpoint to the verified production API gateway."
        )

    # Case D: Missing production secret
    if is_prod and category == "secret":
        if actual_val is False or norm_actual is False:
            return DriftDiscrepancy(
                environment=environment,
                category=category,
                item_key=key,
                expected_val="exists: true",
                actual_val="exists: false (missing)",
                severity=SeverityEnum.CRITICAL,
                reason=f"Required secret '{key}' is missing in production secret store. Application will crash during boot or authentication failure.",
                recommendation=f"Provision secret '{key}' in production Secrets Manager before deployment."
            )

    # -------------------------------------------------------------
    # 2. HIGH SEVERITY CHECKS
    # -------------------------------------------------------------

    # Case E: Missing required production environment variable
    if is_prod and (actual_val is None or actual_val == "") and expected_val is not None:
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=str(expected_val),
            actual_val="MISSING",
            severity=SeverityEnum.HIGH,
            reason=f"Mandatory environment variable '{key}' is missing in {environment}.",
            recommendation=f"Define '{key}' in the {environment} configuration file."
        )

    # Case F: Runtime drift (Running container differs from approved config)
    if category == "runtime":
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=str(expected_val),
            actual_val=str(actual_val),
            severity=SeverityEnum.HIGH,
            reason=f"Runtime container state for '{key}' differs from approved configuration. The active container might have been modified out-of-band.",
            recommendation="Restart or redeploy container using the approved configuration baseline."
        )

    # Case G: Production health check disabled or missing
    if is_prod and key.lower() == "health_check" and norm_actual is False:
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val="true",
            actual_val=str(actual_val),
            severity=SeverityEnum.HIGH,
            reason="Health checks are disabled in production infrastructure. Load balancers cannot detect unresponsive instances.",
            recommendation="Enable health_check: true in production infrastructure definitions."
        )

    # -------------------------------------------------------------
    # 3. MEDIUM SEVERITY CHECKS
    # -------------------------------------------------------------

    # Case H: Staging or Dev pointing to unusual endpoint or log level mismatch
    if key_upper == "LOG_LEVEL" and norm_actual != norm_expected:
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=str(expected_val),
            actual_val=str(actual_val),
            severity=SeverityEnum.MEDIUM,
            reason=f"Log level '{actual_val}' deviates from standard '{expected_val}'. Could cause excessive disk writes or insufficient log visibility.",
            recommendation=f"Align LOG_LEVEL with environment policy ({expected_val})."
        )

    # Case I: Secret rotation age warning
    if category == "secret" and extra_context and extra_context.get("age_days", 0) > 90:
        age = extra_context.get("age_days")
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val="rotation < 90 days",
            actual_val=f"{age} days old",
            severity=SeverityEnum.MEDIUM,
            reason=f"Secret '{key}' has not been rotated in {age} days. Security compliance requires rotation within 90 days.",
            recommendation=f"Rotate '{key}' in Secrets Manager and update rotation timestamp."
        )

    # Case J: Feature flag divergence between Staging and Production
    if "FEATURE" in key_upper and norm_actual != norm_expected:
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=str(expected_val),
            actual_val=str(actual_val),
            severity=SeverityEnum.MEDIUM,
            reason=f"Feature flag '{key}' is '{actual_val}' in {environment} while expected is '{expected_val}'. User experience will differ across environments.",
            recommendation=f"Verify if feature flag '{key}' is intentionally staged for rollout."
        )

    # Case K: Infrastructure replica count deviation
    if key.lower() == "replicas" and is_prod and int(norm_actual or 1) < 2:
        return DriftDiscrepancy(
            environment=environment,
            category=category,
            item_key=key,
            expected_val=">= 2",
            actual_val=str(actual_val),
            severity=SeverityEnum.MEDIUM,
            reason="Production replica count is less than 2, leaving no redundancy during pod failovers.",
            recommendation="Increase production replicas to at least 2."
        )

    # -------------------------------------------------------------
    # 4. LOW SEVERITY (Default for other mismatches)
    # -------------------------------------------------------------
    return DriftDiscrepancy(
        environment=environment,
        category=category,
        item_key=key,
        expected_val=str(expected_val),
        actual_val=str(actual_val),
        severity=SeverityEnum.LOW,
        reason=f"Minor configuration difference detected for {key} in {environment}.",
        recommendation="Review the value to confirm it complies with environment standards."
    )
