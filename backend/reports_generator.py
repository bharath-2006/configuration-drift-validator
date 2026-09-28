"""
reports_generator.py - Automated Validation Report Generator & Exporter
Configuration Drift Validator (College Project Phase 2)

Generates structured validation reports and supports CSV and JSON exports.
"""

import csv
import io
import json
from typing import Dict, Any, List, Optional
from backend.database import get_db

def get_all_validation_runs(limit: int = 30) -> List[Dict[str, Any]]:
    """Returns historical validation runs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, run_id, environment, total_checks, passed_checks, failed_checks,
                   critical_count, high_count, medium_count, low_count,
                   deployment_decision, risk_score, risk_level, triggered_by, created_at
            FROM validation_runs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def get_validation_run_details(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a single validation run."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, run_id, environment, total_checks, passed_checks, failed_checks,
                   critical_count, high_count, medium_count, low_count,
                   deployment_decision, risk_score, risk_level, triggered_by, summary_json, created_at
            FROM validation_runs
            WHERE run_id = ?
        """, (run_id,))
        row = cursor.fetchone()
        if not row:
            return None

        record = dict(row)
        try:
            record["summary"] = json.loads(record["summary_json"]) if record["summary_json"] else {}
        except Exception:
            record["summary"] = {}

        # Also fetch any matching drift_results
        cursor.execute("""
            SELECT environment, category, item_key, expected_val, actual_val, severity, reason, recommendation
            FROM drift_results
            WHERE validation_run_id = ?
        """, (run_id,))
        record["drift_results"] = [dict(r) for r in cursor.fetchall()]

        return record

def export_run_to_csv(run_id: str) -> str:
    """Generates CSV representation of a validation report."""
    details = get_validation_run_details(run_id)
    if not details:
        raise ValueError(f"Run ID '{run_id}' not found.")

    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header Metadata Section
    writer.writerow(["CONFIGURATION VALIDATION REPORT", run_id])
    writer.writerow(["Environment", details["environment"]])
    writer.writerow(["Timestamp", details["created_at"]])
    writer.writerow(["Triggered By", details["triggered_by"]])
    writer.writerow(["Deployment Decision", details["deployment_decision"]])
    writer.writerow(["Risk Score", f"{details['risk_score']}/100 ({details['risk_level']})"])
    writer.writerow(["Total Checks", details["total_checks"]])
    writer.writerow(["Passed Checks", details["passed_checks"]])
    writer.writerow(["Failed Checks", details["failed_checks"]])
    writer.writerow(["Critical Issues", details["critical_count"]])
    writer.writerow(["High Issues", details["high_count"]])
    writer.writerow(["Medium Issues", details["medium_count"]])
    writer.writerow(["Low Issues", details["low_count"]])
    writer.writerow([])

    # 2. Detailed Discrepancies Table
    writer.writerow([
        "Severity", "Environment", "Category", "Configuration Key",
        "Expected Value", "Actual Value", "Reason", "Recommendation"
    ])

    discrepancies = details.get("drift_results") or (details.get("summary", {}).get("discrepancies", []))
    for d in discrepancies:
        writer.writerow([
            d.get("severity"),
            d.get("environment"),
            d.get("category"),
            d.get("item_key"),
            d.get("expected_val"),
            d.get("actual_val"),
            d.get("reason"),
            d.get("recommendation")
        ])

    return output.getvalue()
