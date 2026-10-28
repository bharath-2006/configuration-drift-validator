"""
demo_safe_rollback.py - Interactive Rollback Safety Verification
Configuration Drift Validator (Viva Demonstration Script)

Demonstrates:
1. State before rollback (Production has contaminated DATABASE_HOST=dev-db).
2. Drift engine detection (Critical blocker triggered).
3. Safe atomic rollback execution (Reverting to approved baseline version).
4. State after rollback (Restored to DATABASE_HOST=prod-db).
5. Post-rollback validation run showing drift is resolved and deployment is allowed.
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.rollback import (
    save_new_config_version,
    get_active_version,
    get_config_snapshot_by_version,
    perform_rollback
)
from backend.drift_engine import detect_environment_variable_drift
from backend.schemas import SeverityEnum

def print_separator(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def run_demonstration():
    print_separator("VIVA DEMO: SAFE CONFIGURATION ROLLBACK & DRIFT RECOVERY")
    env = "production"

    # Step 1: Baseline valid configuration
    clean_vars = {
        "APP_ENV": "production",
        "DEBUG": "false",
        "DATABASE_HOST": "prod-db",
        "DATABASE_PORT": "5432",
        "API_URL": "https://api.production.example.com",
        "LOG_LEVEL": "INFO",
        "FEATURE_PAYMENT": "true"
    }
    clean_infra = {"service_name": "payment-api", "port": 8080, "replicas": 3, "health_check": True}
    clean_secrets = [{"name": "DATABASE_PASSWORD", "environment": "production", "is_present": True, "source": "secret-manager", "age_days": 15}]

    v_baseline = save_new_config_version(
        environment=env,
        variables=clean_vars,
        infra=clean_infra,
        secrets=clean_secrets,
        description="Clean baseline configuration (Verified)",
        author="lead-architect"
    )
    print(f"[*] Step 1: Created baseline clean version v{v_baseline} for '{env}'.")
    print(f"    - DATABASE_HOST: {clean_vars['DATABASE_HOST']}")
    print(f"    - Active version: {get_active_version(env)}")

    # Step 2: Inject accidental bad configuration
    print_separator("STEP 2: ACCIDENTAL CONTAMINATION INJECTED")
    faulty_vars = dict(clean_vars)
    faulty_vars["DATABASE_HOST"] = "dev-db"

    v_faulty = save_new_config_version(
        environment=env,
        variables=faulty_vars,
        infra=clean_infra,
        secrets=clean_secrets,
        description="Accidental dev-db injection by junior dev",
        author="junior-developer"
    )
    print(f"[!] Contaminated version v{v_faulty} deployed.")
    print(f"    - Current DATABASE_HOST: {faulty_vars['DATABASE_HOST']}")
    print(f"    - Current Active Version: {get_active_version(env)}")

    # Step 3: Run drift engine
    print_separator("STEP 3: MULTI-LAYER DRIFT DETECTION RUN")
    discrepancies = detect_environment_variable_drift(clean_vars, clean_vars, faulty_vars)
    crit_issues = [d for d in discrepancies if d.severity == SeverityEnum.CRITICAL and d.environment == "production"]
    
    print(f"[!] Total Discrepancies Found: {len(discrepancies)}")
    print(f"[!] Critical Blocker Count:   {len(crit_issues)}")
    for issue in crit_issues:
        print(f"    -> [CRITICAL] {issue.item_key}: Actual='{issue.actual_val}', Expected='{issue.expected_val}'")
        print(f"       Reason: {issue.reason}")

    if len(crit_issues) > 0:
        print("\n[BLOCKED] Production deployment safety gate is BLOCKED!")

    # Step 4: Execute Safe Rollback
    print_separator(f"STEP 4: EXECUTING SAFE ROLLBACK TO BASELINE (v{v_baseline})")
    rollback_res = perform_rollback(
        environment=env,
        target_version=v_baseline,
        reason="Emergency recovery: Revert dev-db to prod-db",
        performed_by="security-auditor"
    )
    print(f"[+] Rollback Status:    {rollback_res['status']}")
    print(f"[+] Restored Version:   v{rollback_res['restored_version']}")
    print(f"[+] Active Version Now: v{get_active_version(env)}")

    # Step 5: Post-rollback verification
    print_separator("STEP 5: POST-ROLLBACK STATE & DRIFT VERIFICATION")
    restored_snapshot = get_config_snapshot_by_version(env, get_active_version(env))
    restored_db_host = restored_snapshot["variables"]["DATABASE_HOST"]
    print(f"[+] Restored DATABASE_HOST: {restored_db_host}")
    assert restored_db_host == "prod-db", "DATABASE_HOST was not properly restored!"

    # Re-run drift analysis
    post_discrepancies = detect_environment_variable_drift(clean_vars, clean_vars, restored_snapshot["variables"])
    post_crit = [d for d in post_discrepancies if d.severity == SeverityEnum.CRITICAL and d.environment == "production"]
    print(f"[+] Post-Rollback Critical Discrepancies: {len(post_crit)}")
    
    if len(post_crit) == 0:
        print("\n[PASSED] Drift completely resolved! Production gate is now GREEN (APPROVED).")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_demonstration()
