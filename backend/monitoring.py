"""
monitoring.py - Continuous Configuration Monitoring Service
Configuration Drift Validator (College Project Phase 2)

Periodically checks stored approved configurations against simulated runtime container snapshots.
Detects out-of-band drifts (e.g. LOG_LEVEL=DEBUG running when approved was INFO).
Logs events to monitoring_events and notifies operators.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db
from backend.rollback import get_active_version, get_config_snapshot_by_version
from backend.drift_engine import detect_runtime_drift
from backend.notifications import create_notification
from backend.audit import log_audit_event
from backend.schemas import SeverityEnum
from backend.normalizer import values_are_equivalent

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "runtime_snapshots"

def run_monitoring_scan(environment: str = "production") -> Dict[str, Any]:
    """
    Executes a monitoring scan comparing approved configuration to live runtime state.
    """
    env_lower = environment.lower()
    prefix = 'prod' if env_lower == 'production' else 'dev' if env_lower == 'development' else 'staging'
    runtime_file = RUNTIME_DIR / f"{prefix}_runtime.json"

    runtime_data: Dict[str, Any] = {}
    if runtime_file.exists():
        try:
            runtime_data = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception:
            runtime_data = {}

    # Fetch approved configuration
    active_v = get_active_version(env_lower)
    approved_bundle = get_config_snapshot_by_version(env_lower, active_v) if active_v else {"variables": {}}
    approved_vars = approved_bundle.get("variables", {})

    discrepancies = detect_runtime_drift(approved_vars, runtime_data)
    drifts_count = len(discrepancies)

    crit_count = sum(1 for d in discrepancies if d.severity == SeverityEnum.CRITICAL)
    high_count = sum(1 for d in discrepancies if d.severity == SeverityEnum.HIGH)

    now_iso = datetime.now().isoformat()

    if drifts_count > 0:
        status = "CRITICAL" if crit_count > 0 else "WARNING"
        severity = "CRITICAL" if crit_count > 0 else "HIGH" if high_count > 0 else "MEDIUM"
        event_type = "runtime_drift_detected"
        details_list = [f"{d.item_key}: expected '{d.expected_val}', got runtime '{d.actual_val}'" for d in discrepancies]
        details = "; ".join(details_list)

        # In-app notification
        create_notification(
            title=f"Runtime Drift Detected in {environment.title()}",
            message=f"Live container drifted on {drifts_count} key(s): {details}",
            severity=severity,
            category="runtime",
            environment=env_lower
        )
        log_audit_event(
            user="continuous-monitor",
            action="Runtime Drift Alert",
            environment=env_lower,
            details=f"Monitoring detected {drifts_count} discrepancy in {env_lower} ({details})",
            risk_level=severity
        )
    else:
        status = "HEALTHY"
        severity = "INFO"
        event_type = "healthy_scan"
        details = f"Approved configuration (v{active_v}) is perfectly synchronized with live container state."

    # Record monitoring event
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO monitoring_events (environment, event_type, severity, status, drifts_count, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (env_lower, event_type, severity, status, drifts_count, details))

    return {
        "timestamp": now_iso,
        "environment": env_lower,
        "status": status,
        "drifts_count": drifts_count,
        "critical_count": crit_count,
        "high_count": high_count,
        "details": details,
        "discrepancies": [d.model_dump() for d in discrepancies]
    }

def get_monitoring_dashboard_status(environment: str = "production") -> Dict[str, Any]:
    """
    Returns aggregated metrics and state for the Continuous Monitoring view.
    """
    env_lower = environment.lower()

    with get_db() as conn:
        cursor = conn.cursor()

        # Query recent monitoring events
        cursor.execute("""
            SELECT id, environment, event_type, severity, status, drifts_count, details, timestamp
            FROM monitoring_events
            WHERE environment = ?
            ORDER BY id DESC
            LIMIT 15
        """, (env_lower,))
        events = [dict(r) for r in cursor.fetchall()]

        # Query last successful scan
        cursor.execute("""
            SELECT timestamp FROM monitoring_events
            WHERE environment = ? AND status = 'HEALTHY'
            ORDER BY id DESC LIMIT 1
        """, (env_lower,))
        last_success_row = cursor.fetchone()
        last_success = last_success_row["timestamp"] if last_success_row else "None yet"

        # Query last failed/warning scan
        cursor.execute("""
            SELECT timestamp FROM monitoring_events
            WHERE environment = ? AND status != 'HEALTHY'
            ORDER BY id DESC LIMIT 1
        """, (env_lower,))
        last_failed_row = cursor.fetchone()
        last_failed = last_failed_row["timestamp"] if last_failed_row else "None (0 drifts)"

    # Inspect current live comparison
    prefix = 'prod' if env_lower == 'production' else 'dev' if env_lower == 'development' else 'staging'
    runtime_file = RUNTIME_DIR / f"{prefix}_runtime.json"
    runtime_data: Dict[str, Any] = {}
    if runtime_file.exists():
        try:
            runtime_data = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    active_v = get_active_version(env_lower)
    approved_bundle = get_config_snapshot_by_version(env_lower, active_v) if active_v else {"variables": {}}
    approved_vars = approved_bundle.get("variables", {})

    # Build comparison rows for common runtime keys
    comparison_keys = set([k.upper() for k in approved_vars.keys()] + [k.upper() for k in runtime_data.keys()])
    comparison_table = []
    active_drifts = 0
    crit_issues = 0

    for k in sorted(comparison_keys):
        expected = approved_vars.get(k)
        actual = runtime_data.get(k.lower()) if k.lower() in runtime_data else runtime_data.get(k)
        is_synced = values_are_equivalent(expected, actual) if (expected is not None and actual is not None) else False
        if not is_synced and expected is not None and actual is not None:
            active_drifts += 1
            if k == "DATABASE_HOST" and "dev" in str(actual).lower():
                crit_issues += 1
            elif k == "DEBUG" and str(actual).lower() == "true":
                crit_issues += 1

        comparison_table.append({
            "key": k,
            "approved_value": str(expected) if expected is not None else "NOT SET",
            "runtime_value": str(actual) if actual is not None else "NOT REPORTED",
            "is_synced": is_synced
        })

    current_env_status = "CRITICAL" if crit_issues > 0 else "WARNING" if active_drifts > 0 else "HEALTHY"

    return {
        "environment": env_lower,
        "last_validation_time": events[0]["timestamp"] if events else datetime.now().isoformat(),
        "current_environment_status": current_env_status,
        "number_of_detected_drifts": active_drifts,
        "critical_issues": crit_issues,
        "last_successful_validation": last_success,
        "last_failed_validation": last_failed,
        "comparison_table": comparison_table,
        "recent_events": events
    }
