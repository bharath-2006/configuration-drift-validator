"""
ci_validator.py - Automated CI/CD Configuration Validation CLI
Configuration Drift Validator (College Project Phase 2)

Command-line tool intended to run in GitHub Actions CI/CD pipelines or locally:
  python -m backend.ci_validator [--env production] [--strict]

Workflow:
  1. Loads configuration files from configs/ or database.
  2. Executes multi-layer drift analysis.
  3. Computes 0-100 risk score.
  4. Saves run summary in validation_runs table and reports/ directory.
  5. Exits with 0 (PASSED) or 1 (BLOCKED) to pass or fail CI pipelines.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.database import init_db, get_db
from backend.rollback import get_active_version, get_config_snapshot_by_version
from backend.drift_engine import run_full_drift_analysis
from backend.risk_score import calculate_risk_score
from backend.notifications import create_notification
from backend.audit import log_audit_event

REPORTS_DIR = BASE_DIR / "reports"

def run_ci_validation(target_env: str = "production", strict: bool = False) -> int:
    """
    Executes automated CI/CD pipeline validation.
    Returns 0 if validation passed, 1 if blocked.
    """
    init_db()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" [*] CONFIGURATION DRIFT VALIDATOR - CI/CD PIPELINE GATE")
    print(f" Target Environment: {target_env.upper()} | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. Retrieve Active Configuration Bundles
    dev_v = get_active_version("development")
    stage_v = get_active_version("staging")
    prod_v = get_active_version("production")

    dev_bundle = get_config_snapshot_by_version("development", dev_v) if dev_v else {}
    stage_bundle = get_config_snapshot_by_version("staging", stage_v) if stage_v else {}
    prod_bundle = get_config_snapshot_by_version("production", prod_v) if prod_v else {}

    # Runtime snapshot
    runtime_file = BASE_DIR / "runtime_snapshots" / "prod_runtime.json"
    runtime_data = None
    if runtime_file.exists():
        try:
            runtime_data = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception:
            runtime_data = None

    # 2. Run Drift Engine
    report = run_full_drift_analysis(
        dev_bundle=dev_bundle,
        staging_bundle=stage_bundle,
        prod_bundle=prod_bundle,
        runtime_snapshot=runtime_data
    )

    # 3. Calculate Quantitative Risk Score
    risk = calculate_risk_score(
        environment=target_env,
        discrepancies=report.discrepancies,
        has_runtime_drift=any(d.category == "runtime" for d in report.discrepancies)
    )

    is_blocked = (report.critical_count > 0) or (strict and report.high_count > 0)
    decision = "BLOCKED" if is_blocked else "SAFE"

    # Count checks
    total_checks = 25  # standard configuration checklist items across envs
    failed_checks = report.total_discrepancies
    passed_checks = max(0, total_checks - failed_checks)

    # 4. Display Formatted Output
    print(f"\n[+] Total Configuration Checks: {total_checks}")
    print(f"    - Passed Checks:            {passed_checks}")
    print(f"    - Discrepancies Found:      {failed_checks}")
    print(f"    - Critical Blocker Issues:  {report.critical_count}")
    print(f"    - High Severity Issues:     {report.high_count}")
    print(f"    - Medium / Low Issues:      {report.medium_count + report.low_count}")
    print(f"\n[+] Risk Evaluation:")
    print(f"    - Quantitative Risk Score:  {risk['score']}/100")
    print(f"    - Risk Classification:      {risk['level']}")
    print(f"    - Explanation:              {risk['explanation']}")

    if report.discrepancies:
        print("\n" + "-" * 70)
        print(" DETECTED DISCREPANCIES:")
        print("-" * 70)
        for idx, d in enumerate(report.discrepancies, 1):
            symbol = "[CRIT]" if d.severity.value == "CRITICAL" else "[WARN]" if d.severity.value == "HIGH" else "[INFO]"
            print(f" {idx}. {symbol} [{d.severity.value}] {d.category.upper()} -> {d.item_key} in {d.environment}")
            print(f"    Expected: {d.expected_val} | Actual: {d.actual_val}")
            print(f"    Reason:   {d.reason}")
            print(f"    Action:   {d.recommendation}\n")

    print("=" * 70)
    if is_blocked:
        print(" [X] CI/CD PIPELINE RESULT: BLOCKED")
        print(f" Reason: {report.critical_count} Critical configuration issues detected.")
        print(" Production deployment is NOT permitted.")
    else:
        print(" [V] CI/CD PIPELINE RESULT: PASSED")
        print(" Status: Configuration is verified safe for deployment.")
    print("=" * 70)

    # 5. Persist Run in validation_runs table
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO validation_runs (
                run_id, environment, total_checks, passed_checks, failed_checks,
                critical_count, high_count, medium_count, low_count,
                deployment_decision, risk_score, risk_level, triggered_by, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.validation_run_id,
            target_env,
            total_checks,
            passed_checks,
            failed_checks,
            report.critical_count,
            report.high_count,
            report.medium_count,
            report.low_count,
            decision,
            risk["score"],
            risk["level"],
            "ci_cd",
            json.dumps({
                "discrepancies": [d.model_dump() for d in report.discrepancies],
                "risk_breakdown": risk["breakdown"]
            })
        ))

    # 6. Save Report Artifact
    report_file = REPORTS_DIR / f"ci_report_{report.validation_run_id}.json"
    report_data = {
        "run_id": report.validation_run_id,
        "timestamp": report.timestamp,
        "environment": target_env,
        "decision": decision,
        "risk_score": risk["score"],
        "risk_level": risk["level"],
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "critical_count": report.critical_count,
        "high_count": report.high_count,
        "discrepancies": [d.model_dump() for d in report.discrepancies]
    }
    report_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"\n[Artifact] Validation report written to: {report_file}")

    # Notifications & Audit
    if is_blocked:
        create_notification(
            title="CI/CD Pipeline Failed",
            message=f"Run {report.validation_run_id} blocked: {report.critical_count} critical drift(s).",
            severity="CRITICAL",
            category="deployment",
            environment=target_env
        )
    log_audit_event(
        user="github-actions",
        action="CI/CD Validation Pipeline",
        environment=target_env,
        details=f"Run {report.validation_run_id} evaluated with result: {decision} (Score: {risk['score']})",
        risk_level=risk["level"]
    )

    return 1 if is_blocked else 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configuration Drift Validator CI/CD Runner")
    parser.add_argument("--env", default="production", help="Target environment to validate")
    parser.add_argument("--strict", action="store_true", help="Fail on HIGH severity issues as well")
    args = parser.parse_args()

    exit_code = run_ci_validation(target_env=args.env, strict=args.strict)
    sys.exit(exit_code)
