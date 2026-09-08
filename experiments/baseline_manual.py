"""
baseline_manual.py - Simulates Manual / Naive Developer Review Baseline
Models typical human checklist inspection or basic git diff comparison:
- Superficial checks (looks for obvious keywords like DEBUG=true)
- Flags legitimate environment differences as false alarms (e.g. dev-db vs prod-db)
- Misses subtle issues (disguised connection string hostnames, secret rotation ages, live container drift)
- Has human/checklist latency overhead
"""

import time
from typing import Dict, Any, List

class ManualBaselineReviewer:
    """Simulates a developer conducting manual config verification."""

    def review_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.perf_counter()
        detected_issues = []
        false_alarms = []

        dev_vars = scenario.get("dev_vars", {})
        staging_vars = scenario.get("staging_vars", {})
        prod_vars = scenario.get("prod_vars", {})
        staging_infra = scenario.get("staging_infra", {})
        prod_infra = scenario.get("prod_infra", {})
        prod_secrets = scenario.get("prod_secrets", [])
        runtime_snapshot = scenario.get("runtime_snapshot")

        # 1. Obvious DEBUG check: Human spots "true" or "TRUE"
        prod_debug = str(prod_vars.get("DEBUG", "")).lower()
        if prod_debug in ("true", "1"):
            detected_issues.append("DEBUG enabled in production")

        # 2. Obvious database host check (exact match on 'dev-db' only)
        prod_db = str(prod_vars.get("DATABASE_HOST", ""))
        if prod_db == "dev-db":
            detected_issues.append("DATABASE_HOST points to dev-db")
        elif "staging-db" in prod_db:
            detected_issues.append("DATABASE_HOST points to staging-db")

        # 3. Naive text diff between Staging and Production:
        # A manual reviewer comparing staging vs prod files often flags legitimate differences as errors!
        if prod_vars.get("DATABASE_HOST") != staging_vars.get("DATABASE_HOST"):
            # If prod is prod-db and staging is staging-db, naive reviewer questions it or marks as diff
            if prod_vars.get("DATABASE_HOST") == "prod-db":
                false_alarms.append("Flagged expected database host difference (staging-db vs prod-db)")

        if prod_infra.get("replicas") != staging_infra.get("replicas"):
            false_alarms.append("Flagged replica scaling difference as drift")

        # 4. Naive whitespace check:
        # " prod-db " vs "prod-db" triggers a false diff alarm in git diff
        if " " in prod_vars.get("DATABASE_HOST", ""):
            false_alarms.append("Flagged whitespace in DATABASE_HOST as syntax error")

        # 5. Missing required keys
        if "DATABASE_PORT" not in prod_vars:
            detected_issues.append("Missing DATABASE_PORT")

        # 6. Infrastructure checks
        if prod_infra.get("health_check") is False:
            detected_issues.append("Health check disabled in production")

        if prod_infra.get("port") and staging_infra.get("port") and prod_infra.get("port") != staging_infra.get("port"):
            detected_issues.append("Port mismatch")

        # 7. Obvious missing secret check
        for sec in prod_secrets:
            if sec.get("exists") is False:
                detected_issues.append(f"Missing secret {sec.get('name')}")

        # LIMITATIONS OF MANUAL REVIEW:
        # - Misses hidden hostnames in connection URLs like postgresql://user:pass@dev-db.corp...
        # - Misses secret rotation age (> 90 days) because manual review doesn't compute day deltas
        # - Misses runtime container drift (developer only reviews repo files, not running container)

        elapsed = time.perf_counter() - start_time
        # Simulate small baseline review latency (minimum 0.05s)
        time.sleep(0.005)

        return {
            "scenario_id": scenario["id"],
            "name": scenario["name"],
            "detected_count": len(detected_issues),
            "false_positive_count": len(false_alarms),
            "detected_issues": detected_issues,
            "false_alarms": false_alarms,
            "time_seconds": elapsed + 0.005
        }
