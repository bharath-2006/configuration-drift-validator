"""
git_detector.py - Git Integration & Configuration Change Detection
Configuration Drift Validator (College Project Phase 2)

Detects configuration changes from Git commits or simulated repository events.
Evaluates commits through drift detection and risk scoring:
Commit -> Changed Configs -> Validator -> Risk Analysis -> Validation Result (PASSED/BLOCKED)
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from backend.database import get_db
from backend.rollback import get_active_version, get_config_snapshot_by_version
from backend.drift_engine import run_full_drift_analysis
from backend.risk_score import calculate_risk_score
from backend.notifications import create_notification
from backend.audit import log_audit_event

def get_recent_commits(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves recorded Git configuration commits."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, commit_id, author, message, changed_files_json,
                   changed_configs_json, environment, validation_result,
                   risk_level, risk_score, created_at
            FROM git_commits
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        commits = []
        for r in rows:
            c = dict(r)
            try:
                c["changed_files"] = json.loads(c["changed_files_json"])
            except Exception:
                c["changed_files"] = []
            try:
                c["changed_configs"] = json.loads(c["changed_configs_json"])
            except Exception:
                c["changed_configs"] = {}
            commits.append(c)
        return commits

def record_and_validate_commit(
    author: str,
    message: str,
    environment: str,
    changed_configs: Dict[str, Any],
    changed_files: Optional[List[str]] = None,
    commit_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simulates / processes a Git commit modifying configuration values.
    Validates the change in the target environment and computes risk.
    """
    env_lower = environment.lower()
    short_sha = commit_id or f"c-{uuid.uuid4().hex[:7]}"
    if not changed_files:
        changed_files = [f"configs/{env_lower}/app.env"]

    # 1. Fetch current active configuration bundles
    dev_v = get_active_version("development")
    stage_v = get_active_version("staging")
    prod_v = get_active_version("production")

    dev_bundle = get_config_snapshot_by_version("development", dev_v) if dev_v else {"variables": {}}
    stage_bundle = get_config_snapshot_by_version("staging", stage_v) if stage_v else {"variables": {}}
    prod_bundle = get_config_snapshot_by_version("production", prod_v) if prod_v else {"variables": {}}

    # 2. Simulate applying commit changes to the target environment bundle
    if env_lower == "production":
        sim_prod = {"variables": dict(prod_bundle.get("variables", {})), "infrastructure": prod_bundle.get("infrastructure", {}), "secrets": prod_bundle.get("secrets", [])}
        sim_prod["variables"].update(changed_configs)
        val_summary = run_full_drift_analysis(dev_bundle, stage_bundle, sim_prod)
    elif env_lower == "staging":
        sim_stage = {"variables": dict(stage_bundle.get("variables", {})), "infrastructure": stage_bundle.get("infrastructure", {}), "secrets": stage_bundle.get("secrets", [])}
        sim_stage["variables"].update(changed_configs)
        val_summary = run_full_drift_analysis(dev_bundle, sim_stage, prod_bundle)
    else:
        sim_dev = {"variables": dict(dev_bundle.get("variables", {})), "infrastructure": dev_bundle.get("infrastructure", {}), "secrets": dev_bundle.get("secrets", [])}
        sim_dev["variables"].update(changed_configs)
        val_summary = run_full_drift_analysis(sim_dev, stage_bundle, prod_bundle)

    # 3. Calculate Risk Score & Risk Level
    risk_info = calculate_risk_score(
        environment=env_lower,
        discrepancies=val_summary.discrepancies,
        changed_keys=changed_configs
    )

    validation_result = "BLOCKED" if (val_summary.critical_count > 0 or risk_info["is_blocked"]) else "PASSED"
    risk_level = risk_info["level"]
    risk_score = risk_info["score"]

    # 4. Persist in git_commits table
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO git_commits (
                commit_id, author, message, changed_files_json,
                changed_configs_json, environment, validation_result,
                risk_level, risk_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            short_sha,
            author,
            message,
            json.dumps(changed_files),
            json.dumps(changed_configs),
            env_lower,
            validation_result,
            risk_level,
            risk_score
        ))

    # 5. Notifications & Audit
    if validation_result == "BLOCKED":
        create_notification(
            title=f"Git Commit {short_sha} Blocked",
            message=f"Commit by {author} blocked in {env_lower}: {risk_info['explanation']}",
            severity="CRITICAL",
            category="deployment",
            environment=env_lower
        )
    else:
        create_notification(
            title=f"Git Commit {short_sha} Validated",
            message=f"Configuration commit by {author} passed CI checks for {env_lower}.",
            severity="INFO",
            category="drift",
            environment=env_lower
        )

    log_audit_event(
        user=author,
        action="Git Commit Validated",
        environment=env_lower,
        details=f"Commit {short_sha} ('{message}') -> {validation_result} (Risk Score: {risk_score}/100, Level: {risk_level})",
        risk_level=risk_level
    )

    return {
        "commit_id": short_sha,
        "author": author,
        "message": message,
        "environment": env_lower,
        "changed_files": changed_files,
        "changed_configs": changed_configs,
        "validation_result": validation_result,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_explanation": risk_info["explanation"],
        "critical_issues": val_summary.critical_count,
        "discrepancies": [d.model_dump() for d in val_summary.discrepancies]
    }

def seed_sample_git_history_if_needed():
    """Seeds sample git commits if table is empty for viva demonstration."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM git_commits")
        if cursor.fetchone()["count"] == 0:
            record_and_validate_commit(
                author="Bharath (Tech Lead)",
                message="chore(config): Initial production baseline configuration",
                environment="production",
                changed_configs={"DATABASE_HOST": "prod-db", "DEBUG": "false", "LOG_LEVEL": "INFO"},
                changed_files=["configs/production/app.env"],
                commit_id="a1b2c3d"
            )
            record_and_validate_commit(
                author="Dev-Alice",
                message="feat(search): Update staging replica pool configuration",
                environment="staging",
                changed_configs={"DATABASE_HOST": "staging-db", "DEBUG": "true"},
                changed_files=["configs/staging/app.env"],
                commit_id="f4e5d6c"
            )
