"""
pre_deployment.py - Dedicated Pre-Deployment Multi-Stage Validation Pipeline
Configuration Drift Validator (College Project Phase 2)

Executes sequential pre-flight safety gates:
  Configuration Check -> Environment Check -> Infrastructure Check ->
  Secret Metadata Check -> Runtime Check -> Risk Analysis -> Deployment Decision
"""

import time
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.database import get_db
from backend.rollback import get_active_version, get_config_snapshot_by_version
from backend.drift_engine import (
    detect_environment_variable_drift,
    detect_infrastructure_drift,
    detect_secret_metadata_drift,
    detect_runtime_drift,
    run_full_drift_analysis
)
from backend.risk_score import calculate_risk_score
from backend.notifications import create_notification
from backend.audit import log_audit_event
from backend.schemas import SeverityEnum

def run_pre_deployment_pipeline(target_env: str = "production") -> Dict[str, Any]:
    """
    Runs the 6-stage pre-deployment verification pipeline.
    Persists stage outcomes into deployment_checks and validation_runs.
    """
    check_run_id = f"PRE-{uuid.uuid4().hex[:8].upper()}"
    stages_results: List[Dict[str, Any]] = []

    # 1. Fetch current active configuration bundles
    dev_v = get_active_version("development")
    stage_v = get_active_version("staging")
    prod_v = get_active_version(target_env)

    dev_bundle = get_config_snapshot_by_version("development", dev_v) if dev_v else {}
    stage_bundle = get_config_snapshot_by_version("staging", stage_v) if stage_v else {}
    target_bundle = get_config_snapshot_by_version(target_env, prod_v) if prod_v else {}

    # Stage 1: Configuration Check (Ingestion & Schema Integrity)
    t0 = time.perf_counter()
    has_vars = bool(target_bundle.get("variables"))
    has_infra = bool(target_bundle.get("infrastructure"))
    has_sec = bool(target_bundle.get("secrets") is not None)
    st1_status = "PASSED" if (has_vars and has_infra) else "FAILED"
    st1_dur = round((time.perf_counter() - t0) * 1000, 2)
    st1_details = f"Loaded {len(target_bundle.get('variables', {}))} environment variables, {len(target_bundle.get('infrastructure', {}))} infra properties, and {len(target_bundle.get('secrets', []))} secret descriptors."
    stages_results.append({
        "stage_id": 1,
        "stage_name": "Configuration Check",
        "status": st1_status,
        "duration_ms": st1_dur,
        "details": st1_details
    })

    # Stage 2: Environment Check (Policy & Hostname Drift)
    t0 = time.perf_counter()
    env_discrepancies = detect_environment_variable_drift(
        dev_bundle.get("variables", {}),
        stage_bundle.get("variables", {}),
        target_bundle.get("variables", {})
    )
    env_crit = [d for d in env_discrepancies if d.severity == SeverityEnum.CRITICAL]
    env_high = [d for d in env_discrepancies if d.severity == SeverityEnum.HIGH]
    st2_status = "FAILED" if env_crit else "WARNING" if env_high else "PASSED"
    st2_dur = round((time.perf_counter() - t0) * 1000, 2)
    st2_details = f"{len(env_discrepancies)} policy discrepancies ({len(env_crit)} Critical, {len(env_high)} High)."
    stages_results.append({
        "stage_id": 2,
        "stage_name": "Environment Check",
        "status": st2_status,
        "duration_ms": st2_dur,
        "details": st2_details,
        "issues": [d.model_dump() for d in env_discrepancies]
    })

    # Stage 3: Infrastructure Check (Replicas, Port, Health check)
    t0 = time.perf_counter()
    infra_discrepancies = detect_infrastructure_drift(
        dev_bundle.get("infrastructure", {}),
        stage_bundle.get("infrastructure", {}),
        target_bundle.get("infrastructure", {})
    )
    infra_crit = [d for d in infra_discrepancies if d.severity == SeverityEnum.CRITICAL]
    infra_high = [d for d in infra_discrepancies if d.severity == SeverityEnum.HIGH]
    st3_status = "FAILED" if infra_crit else "WARNING" if infra_high else "PASSED"
    st3_dur = round((time.perf_counter() - t0) * 1000, 2)
    st3_details = f"Infrastructure manifest verified: {len(infra_discrepancies)} warnings/errors."
    stages_results.append({
        "stage_id": 3,
        "stage_name": "Infrastructure Check",
        "status": st3_status,
        "duration_ms": st3_dur,
        "details": st3_details,
        "issues": [d.model_dump() for d in infra_discrepancies]
    })

    # Stage 4: Secret Metadata Check (Presence & Rotation age)
    t0 = time.perf_counter()
    sec_discrepancies = detect_secret_metadata_drift(
        stage_bundle.get("secrets", []),
        target_bundle.get("secrets", [])
    )
    sec_crit = [d for d in sec_discrepancies if d.severity == SeverityEnum.CRITICAL]
    sec_high = [d for d in sec_discrepancies if d.severity == SeverityEnum.HIGH]
    st4_status = "FAILED" if sec_crit else "WARNING" if sec_high else "PASSED"
    st4_dur = round((time.perf_counter() - t0) * 1000, 2)
    st4_details = f"Secret metadata audit: {len(sec_discrepancies)} issues ({len(sec_crit)} missing secrets)."
    stages_results.append({
        "stage_id": 4,
        "stage_name": "Secret Metadata Check",
        "status": st4_status,
        "duration_ms": st4_dur,
        "details": st4_details,
        "issues": [d.model_dump() for d in sec_discrepancies]
    })

    # Stage 5: Runtime Check (Live container state)
    t0 = time.perf_counter()
    from pathlib import Path
    runtime_file = Path(__file__).resolve().parent.parent / "runtime_snapshots" / "prod_runtime.json"
    runtime_data = None
    if runtime_file.exists():
        try:
            runtime_data = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception:
            runtime_data = None

    runtime_discrepancies = detect_runtime_drift(target_bundle.get("variables", {}), runtime_data)
    runtime_crit = [d for d in runtime_discrepancies if d.severity == SeverityEnum.CRITICAL]
    runtime_high = [d for d in runtime_discrepancies if d.severity == SeverityEnum.HIGH]
    st5_status = "FAILED" if runtime_crit else "WARNING" if runtime_high else "PASSED"
    st5_dur = round((time.perf_counter() - t0) * 1000, 2)
    st5_details = f"Live container state check: {len(runtime_discrepancies)} runtime deviations."
    stages_results.append({
        "stage_id": 5,
        "stage_name": "Runtime Check",
        "status": st5_status,
        "duration_ms": st5_dur,
        "details": st5_details,
        "issues": [d.model_dump() for d in runtime_discrepancies]
    })

    # Stage 6: Risk Analysis (0-100 quantitative rule-based score)
    t0 = time.perf_counter()
    all_discrepancies = env_discrepancies + infra_discrepancies + sec_discrepancies + runtime_discrepancies
    # Deduplicate
    seen = set()
    deduped = []
    for d in all_discrepancies:
        key = (d.environment, d.category, d.item_key, d.severity)
        if key not in seen:
            seen.add(key)
            deduped.append(d)

    risk_info = calculate_risk_score(
        environment=target_env,
        discrepancies=deduped,
        has_runtime_drift=bool(runtime_discrepancies)
    )
    st6_dur = round((time.perf_counter() - t0) * 1000, 2)
    st6_status = "FAILED" if risk_info["is_blocked"] else "WARNING" if risk_info["level"] == "HIGH" else "PASSED"
    stages_results.append({
        "stage_id": 6,
        "stage_name": "Risk Analysis",
        "status": st6_status,
        "duration_ms": st6_dur,
        "details": f"Risk Score: {risk_info['score']}/100 ({risk_info['level']} Risk) - {risk_info['explanation']}"
    })

    # Deployment Decision
    total_critical = sum(1 for d in deduped if d.severity == SeverityEnum.CRITICAL)
    total_high = sum(1 for d in deduped if d.severity == SeverityEnum.HIGH)
    total_medium = sum(1 for d in deduped if d.severity == SeverityEnum.MEDIUM)
    total_low = sum(1 for d in deduped if d.severity == SeverityEnum.LOW)

    is_safe = (total_critical == 0 and not risk_info["is_blocked"])
    decision = "DEPLOYMENT SAFE" if is_safe else "DEPLOYMENT BLOCKED"

    # Save to database
    with get_db() as conn:
        cursor = conn.cursor()
        for s in stages_results:
            cursor.execute("""
                INSERT INTO deployment_checks (check_run_id, environment, stage_name, status, details, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (check_run_id, target_env, s["stage_name"], s["status"], s["details"], s["duration_ms"]))

        cursor.execute("""
            INSERT INTO validation_runs (
                run_id, environment, total_checks, passed_checks, failed_checks,
                critical_count, high_count, medium_count, low_count,
                deployment_decision, risk_score, risk_level, triggered_by, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            check_run_id,
            target_env,
            25,
            max(0, 25 - len(deduped)),
            len(deduped),
            total_critical,
            total_high,
            total_medium,
            total_low,
            "SAFE" if is_safe else "BLOCKED",
            risk_info["score"],
            risk_info["level"],
            "pre_deployment",
            json.dumps({"stages": stages_results, "risk": risk_info})
        ))

    if not is_safe:
        create_notification(
            title="Pre-Deployment Gate BLOCKED",
            message=f"Production pre-deployment blocked with {total_critical} Critical, {total_high} High issues (Risk: {risk_info['score']}/100).",
            severity="CRITICAL",
            category="deployment",
            environment=target_env
        )
    else:
        create_notification(
            title="Pre-Deployment Gate SAFE",
            message=f"Production pre-deployment checks passed cleanly. Ready for deployment.",
            severity="INFO",
            category="deployment",
            environment=target_env
        )

    log_audit_event(
        user="pre-deployment-gate",
        action="Pre-Deployment Validation",
        environment=target_env,
        details=f"Run {check_run_id}: Decision = {decision} (Critical: {total_critical}, High: {total_high}, Score: {risk_info['score']})",
        risk_level=risk_info["level"]
    )

    return {
        "check_run_id": check_run_id,
        "timestamp": datetime.now().isoformat(),
        "environment": target_env,
        "is_safe": is_safe,
        "decision": decision,
        "decision_summary": f"✅ {decision}" if is_safe else f"❌ {decision}: Critical Issues: {total_critical}, High Issues: {total_high}",
        "critical_issues": total_critical,
        "high_issues": total_high,
        "medium_issues": total_medium,
        "low_issues": total_low,
        "total_discrepancies": len(deduped),
        "risk_score": risk_info["score"],
        "risk_level": risk_info["level"],
        "risk_explanation": risk_info["explanation"],
        "stages": stages_results,
        "discrepancies": [d.model_dump() for d in deduped]
    }
