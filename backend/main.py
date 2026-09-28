"""
main.py - FastAPI Application for Configuration Drift Validator
Exposes REST endpoints for configuration management, drift detection,
deployment gating, change approval workflows, rollbacks, and audit trails.
Serves the web dashboard directly from /frontend.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db, get_db
from backend.schemas import (
    ValidationSummary,
    ChangeRequestCreate,
    ChangeRequestReview,
    RollbackRequest,
    ConfigUploadRequest,
    RuntimeSnapshotPayload,
    GitCommitSimulateRequest,
    PreDeploymentCheckRequest,
    MonitoringScanRequest
)
from backend.normalizer import parse_env_file_content, parse_yaml_or_json
from backend.drift_engine import run_full_drift_analysis
from backend.rollback import (
    get_active_version,
    get_config_snapshot_by_version,
    save_new_config_version,
    perform_rollback,
    get_version_history,
    get_all_rollback_records,
    compare_config_versions
)
from backend.audit import log_audit_event, get_recent_audit_logs
from backend.git_detector import (
    get_recent_commits,
    record_and_validate_commit,
    seed_sample_git_history_if_needed
)
from backend.pre_deployment import run_pre_deployment_pipeline
from backend.monitoring import (
    run_monitoring_scan,
    get_monitoring_dashboard_status
)
from backend.notifications import (
    get_notifications,
    create_notification,
    mark_notification_read,
    mark_all_notifications_read
)
from backend.reports_generator import (
    get_all_validation_runs,
    get_validation_run_details,
    export_run_to_csv
)
from backend.risk_score import calculate_risk_score

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
CONFIGS_DIR = BASE_DIR / "configs"
RUNTIME_DIR = BASE_DIR / "runtime_snapshots"

from contextlib import asynccontextmanager

def seed_sample_configs_if_needed():
    """Seeds the initial configurations from file system if database is empty."""
    init_db()
    for env in ["development", "staging", "production"]:
        active_v = get_active_version(env)
        if active_v is None:
            # Read files
            env_file = CONFIGS_DIR / env / "app.env"
            infra_file = CONFIGS_DIR / env / "infra.yaml"
            secrets_file = CONFIGS_DIR / env / "secrets.json"

            env_vars = {}
            infra = {}
            secrets = []

            if env_file.exists():
                env_vars = parse_env_file_content(env_file.read_text(encoding="utf-8"))
            if infra_file.exists():
                infra = parse_yaml_or_json(infra_file.read_text(encoding="utf-8"))
            if secrets_file.exists():
                try:
                    secrets = json.loads(secrets_file.read_text(encoding="utf-8"))
                except Exception:
                    secrets = []

            save_new_config_version(
                environment=env,
                variables=env_vars,
                infra=infra,
                secrets=secrets,
                description=f"Initial seed configuration for {env}",
                author="system-installer"
            )
    seed_sample_git_history_if_needed()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    seed_sample_configs_if_needed()
    yield
    # Shutdown logic

app = FastAPI(
    title="Configuration Drift Validator",
    description="Student-Friendly Configuration Drift Validator for Preventing Environment-Specific Mistakes from Reaching Production",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- System & Health Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Configuration Drift Validator", "version": "1.0.0"}

@app.get("/api/environments")
def get_environments():
    """Lists all environments, active version, and metadata."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, display_name, description, is_production FROM environments")
        envs = [dict(row) for row in cursor.fetchall()]
        for env in envs:
            env["active_version"] = get_active_version(env["id"])
        return envs

# --- Configuration Endpoints ---

@app.get("/api/configs/{environment}")
def get_environment_config(environment: str, version: Optional[int] = None):
    """Retrieves the active configuration bundle or a specified version."""
    env_lower = environment.lower()
    target_v = version if version is not None else get_active_version(env_lower)
    if target_v is None:
        raise HTTPException(status_code=404, detail=f"No configuration found for environment '{environment}'")
    
    snapshot = get_config_snapshot_by_version(env_lower, target_v)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Version {target_v} not found for '{environment}'")
    return snapshot

@app.get("/api/configs/{environment}/history")
def get_config_history(environment: str):
    """Returns version history for a given environment."""
    return get_version_history(environment.lower())

@app.post("/api/configs/{environment}/update")
def update_environment_config(environment: str, payload: ConfigUploadRequest):
    """
    Updates configuration for an environment by parsing provided raw text/files
    and creating a new immutable configuration version.
    """
    env_lower = environment.lower()
    current_active_v = get_active_version(env_lower)
    existing_bundle = get_config_snapshot_by_version(env_lower, current_active_v) if current_active_v else None

    # Parse provided env vars or keep existing
    if payload.raw_env_content is not None and payload.raw_env_content.strip():
        new_vars = parse_env_file_content(payload.raw_env_content)
    elif existing_bundle:
        new_vars = existing_bundle.get("variables", {})
    else:
        new_vars = {}

    # Parse provided infra or keep existing
    if payload.raw_infra_content is not None and payload.raw_infra_content.strip():
        new_infra = parse_yaml_or_json(payload.raw_infra_content)
    elif existing_bundle:
        new_infra = existing_bundle.get("infrastructure", {})
    else:
        new_infra = {}

    # Parse secrets or keep existing
    if payload.raw_secrets_content is not None and payload.raw_secrets_content.strip():
        try:
            new_secrets = json.loads(payload.raw_secrets_content)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON format for secret metadata.")
    elif existing_bundle:
        new_secrets = existing_bundle.get("secrets", [])
    else:
        new_secrets = []

    new_version = save_new_config_version(
        environment=env_lower,
        variables=new_vars,
        infra=new_infra,
        secrets=new_secrets,
        description=payload.description or "Configuration updated",
        author=payload.author or "developer"
    )

    return {
        "status": "success",
        "environment": env_lower,
        "new_version": new_version,
        "message": f"Successfully created Version {new_version} for {environment}"
    }

# --- Runtime Snapshots ---

@app.get("/api/runtime/{environment}")
def get_runtime_snapshot(environment: str):
    """Fetches the latest runtime snapshot for an environment."""
    env_lower = environment.lower()
    snapshot_file = RUNTIME_DIR / f"{'prod' if env_lower == 'production' else 'dev' if env_lower == 'development' else 'staging'}_runtime.json"
    if snapshot_file.exists():
        try:
            return json.loads(snapshot_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"environment": environment, "status": "No active container snapshot"}

@app.post("/api/runtime/{environment}")
def update_runtime_snapshot(environment: str, payload: RuntimeSnapshotPayload):
    """Updates runtime snapshot for simulation."""
    env_lower = environment.lower()
    prefix = 'prod' if env_lower == 'production' else 'dev' if env_lower == 'development' else 'staging'
    snapshot_file = RUNTIME_DIR / f"{prefix}_runtime.json"
    data = payload.snapshot_data
    data["environment"] = environment
    data["app_version"] = payload.app_version
    snapshot_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    log_audit_event(
        user="runtime-agent",
        action="Runtime Snapshot Received",
        environment=environment,
        details=f"Received runtime snapshot for {environment} (version: {payload.app_version})",
        risk_level="INFO"
    )
    return {"status": "success", "message": "Runtime snapshot saved"}

# --- Drift Detection & Deployment Gate ---

# In-memory cache of latest validation summary for quick retrieval
latest_validation_report: Optional[ValidationSummary] = None

@app.post("/api/validate", response_model=ValidationSummary)
def validate_configurations():
    """
    Executes drift detection across all environments and runtime snapshot.
    Persists discrepancies and logs the audit event.
    """
    global latest_validation_report

    # Retrieve active bundles
    dev_v = get_active_version("development")
    stage_v = get_active_version("staging")
    prod_v = get_active_version("production")

    dev_bundle = get_config_snapshot_by_version("development", dev_v) if dev_v else {}
    stage_bundle = get_config_snapshot_by_version("staging", stage_v) if stage_v else {}
    prod_bundle = get_config_snapshot_by_version("production", prod_v) if prod_v else {}

    # Load runtime snapshot for production
    runtime_file = RUNTIME_DIR / "prod_runtime.json"
    runtime_data = None
    if runtime_file.exists():
        try:
            runtime_data = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception:
            runtime_data = None

    report = run_full_drift_analysis(
        dev_bundle=dev_bundle,
        staging_bundle=stage_bundle,
        prod_bundle=prod_bundle,
        runtime_snapshot=runtime_data
    )

    # Persist in drift_results database table
    with get_db() as conn:
        cursor = conn.cursor()
        for d in report.discrepancies:
            cursor.execute("""
                INSERT INTO drift_results (
                    validation_run_id, environment, category, item_key,
                    expected_val, actual_val, severity, reason, recommendation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.validation_run_id,
                d.environment,
                d.category,
                d.item_key,
                d.expected_val,
                d.actual_val,
                d.severity.value,
                d.reason,
                d.recommendation
            ))

    latest_validation_report = report

    # Audit log entry
    risk = "CRITICAL" if report.critical_count > 0 else "HIGH" if report.high_count > 0 else "INFO"
    log_audit_event(
        user="validator-engine",
        action="Configuration Validation",
        environment="all",
        details=f"Run {report.validation_run_id}: {report.total_discrepancies} issues found ({report.critical_count} Critical, {report.high_count} High). Deployment allowed: {report.production_deployment_allowed}",
        risk_level=risk
    )

    return report

@app.get("/api/deployment-gate")
def get_deployment_gate():
    """Evaluates whether production deployment is allowed or blocked."""
    global latest_validation_report
    if latest_validation_report is None:
        # Run validation on the fly
        latest_validation_report = validate_configurations()

    return {
        "production_deployment_allowed": latest_validation_report.production_deployment_allowed,
        "deployment_message": latest_validation_report.deployment_message,
        "critical_count": latest_validation_report.critical_count,
        "high_count": latest_validation_report.high_count,
        "validation_run_id": latest_validation_report.validation_run_id,
        "timestamp": latest_validation_report.timestamp,
        "blocking_issues": [d for d in latest_validation_report.discrepancies if d.severity.value == "CRITICAL"]
    }

# --- Change Request & Approval Workflow ---

@app.get("/api/change-requests")
def get_change_requests():
    """Lists all change requests."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, environment, title, description, proposed_changes_json,
                   risk_level, status, requested_by, reviewed_by, review_notes,
                   created_at, reviewed_at
            FROM change_requests
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

@app.post("/api/change-requests")
def create_change_request(payload: ChangeRequestCreate):
    """Submits a configuration change request with risk assessment."""
    changes_str = payload.proposed_changes_json.lower()
    
    # Assess risk level
    if "database_host" in changes_str or "secret" in changes_str or "debug" in changes_str or payload.environment.lower() == "production":
        risk_level = "HIGH"
    else:
        risk_level = "MEDIUM"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO change_requests (
                environment, title, description, proposed_changes_json, risk_level, requested_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            payload.environment,
            payload.title,
            payload.description,
            payload.proposed_changes_json,
            risk_level,
            payload.requested_by
        ))
        cr_id = cursor.lastrowid

    log_audit_event(
        user=payload.requested_by,
        action="Change Requested",
        environment=payload.environment,
        details=f"Change Request #{cr_id} '{payload.title}' submitted (Risk: {risk_level})",
        risk_level=risk_level
    )

    return {"status": "success", "id": cr_id, "risk_level": risk_level, "message": "Change request submitted for review"}

@app.post("/api/change-requests/{request_id}/review")
def review_change_request(request_id: int, review: ChangeRequestReview):
    """Approves or rejects a change request. If approved, automatically applies it."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM change_requests WHERE id = ?", (request_id,))
        cr = cursor.fetchone()
        if not cr:
            raise HTTPException(status_code=404, detail="Change request not found")

        cursor.execute("""
            UPDATE change_requests
            SET status = ?, reviewed_by = ?, review_notes = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (review.status.value, review.reviewed_by, review.review_notes, request_id))

    action = f"Change {review.status.value.title()}"
    log_audit_event(
        user=review.reviewed_by,
        action=action,
        environment=cr["environment"],
        details=f"Change Request #{request_id} was {review.status.value} by {review.reviewed_by}. Notes: {review.review_notes}",
        risk_level="MEDIUM" if review.status.value == "APPROVED" else "LOW"
    )

    # If approved, apply proposed changes into active configuration!
    if review.status.value == "APPROVED":
        try:
            changes = json.loads(cr["proposed_changes_json"])
            env = cr["environment"]
            current_v = get_active_version(env)
            existing = get_config_snapshot_by_version(env, current_v) if current_v else {}

            merged_vars = existing.get("variables", {}).copy()
            if "variables" in changes:
                merged_vars.update(changes["variables"])
            elif isinstance(changes, dict):
                # Flat env vars
                for k, v in changes.items():
                    if k not in ("infrastructure", "secrets"):
                        merged_vars[k] = v

            merged_infra = existing.get("infrastructure", {}).copy()
            if "infrastructure" in changes:
                merged_infra.update(changes["infrastructure"])

            merged_secrets = existing.get("secrets", []).copy()
            if "secrets" in changes:
                merged_secrets = changes["secrets"]

            new_v = save_new_config_version(
                environment=env,
                variables=merged_vars,
                infra=merged_infra,
                secrets=merged_secrets,
                description=f"Applied via Change Request #{request_id}: {cr['title']}",
                author=review.reviewed_by
            )
            return {"status": "success", "message": f"Change request approved and applied as Version {new_v}"}
        except Exception as e:
            return {"status": "warning", "message": f"Approved, but error applying: {str(e)}"}

    return {"status": "success", "message": f"Change request {review.status.value}"}

# --- Rollback Endpoints ---

@app.get("/api/rollbacks")
def get_rollbacks():
    """Fetches rollback records."""
    return get_all_rollback_records()

@app.post("/api/rollback")
def execute_rollback(payload: RollbackRequest):
    """Rolls back an environment to a previous version."""
    try:
        result = perform_rollback(
            environment=payload.environment,
            target_version=payload.target_version,
            reason=payload.reason,
            performed_by=payload.performed_by
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Audit Trail Endpoints ---

@app.get("/api/audit-logs")
def get_audit_logs():
    """Fetches recent audit logs."""
    return get_recent_audit_logs(limit=100)

# --- Reset / Seed Helper ---

@app.post("/api/reset-demo")
def reset_demo():
    """Resets the demo data to pristine healthy state."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM configuration_versions;")
        cursor.execute("DELETE FROM environment_variables;")
        cursor.execute("DELETE FROM infrastructure_definitions;")
        cursor.execute("DELETE FROM secret_metadata;")
        cursor.execute("DELETE FROM drift_results;")
        cursor.execute("DELETE FROM change_requests;")
        cursor.execute("DELETE FROM rollback_records;")
        cursor.execute("DELETE FROM audit_logs;")
        cursor.execute("DELETE FROM git_commits;")
        cursor.execute("DELETE FROM validation_runs;")
        cursor.execute("DELETE FROM notifications;")
        cursor.execute("DELETE FROM deployment_checks;")
        cursor.execute("DELETE FROM monitoring_events;")

    # Reset runtime snapshot to clean baseline
    runtime_file = RUNTIME_DIR / "prod_runtime.json"
    try:
        runtime_file.write_text(json.dumps({
            "database_host": "prod-db",
            "log_level": "INFO",
            "environment": "production",
            "app_version": "1.0.0"
        }, indent=2), encoding="utf-8")
    except Exception:
        pass

    seed_sample_configs_if_needed()
    global latest_validation_report
    latest_validation_report = None
    log_audit_event(
        user="demo-admin",
        action="System Reset",
        environment="all",
        details="Reset demo state to pristine initial baseline",
        risk_level="INFO"
    )
    return {"status": "success", "message": "Demo data reset successfully"}

# =========================================================================
# --- Phase 2 New Endpoints ---
# =========================================================================

# --- 1. Git Integration Endpoints ---

@app.get("/api/git/commits")
def get_git_commits(limit: int = 20):
    """Retrieves recorded Git commits modifying configurations."""
    return get_recent_commits(limit=limit)

@app.post("/api/git/simulate-commit")
def simulate_git_commit(payload: GitCommitSimulateRequest):
    """
    Simulates a Git commit modifying configuration values.
    Validates the commit, detects drift, calculates risk score, and determines CI status.
    """
    try:
        result = record_and_validate_commit(
            author=payload.author,
            message=payload.message,
            environment=payload.environment,
            changed_configs=payload.changed_configs,
            changed_files=payload.changed_files
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- 2. Pre-Deployment Validation Endpoint ---

@app.post("/api/pre-deployment-check")
def pre_deployment_check(payload: Optional[PreDeploymentCheckRequest] = None):
    """
    Executes dedicated 6-stage pre-deployment verification pipeline:
    Config Check -> Env Check -> Infra Check -> Secret Check -> Runtime Check -> Risk Analysis -> Gate Decision
    """
    target_env = payload.environment if payload else "production"
    try:
        pipeline_result = run_pre_deployment_pipeline(target_env=target_env)
        return pipeline_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pre-deployment check failed: {str(e)}")

# --- 3. Continuous Configuration Monitoring Endpoints ---

@app.get("/api/monitoring/status")
def get_monitoring_status(environment: str = "production"):
    """Fetches continuous monitoring metrics, status, and expected vs runtime comparison."""
    return get_monitoring_dashboard_status(environment=environment)

@app.post("/api/monitoring/scan")
def trigger_monitoring_scan(payload: Optional[MonitoringScanRequest] = None):
    """Manually triggers a continuous configuration monitoring scan."""
    env = payload.environment if payload else "production"
    return run_monitoring_scan(environment=env)

# --- 4. Configuration History & Side-by-Side Comparison ---

@app.get("/api/configs/{environment}/compare")
def compare_versions(environment: str, v_a: int = Query(..., alias="v_a"), v_b: int = Query(..., alias="v_b")):
    """
    Compares two versions of an environment's configuration side-by-side.
    Returns: OLD VALUE (v_a) -> NEW VALUE (v_b) with additions, modifications, and deletions.
    """
    try:
        return compare_config_versions(environment=environment.lower(), version_a=v_a, version_b=v_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 5. In-App Notification System Endpoints ---

@app.get("/api/notifications")
def list_notifications(unread_only: bool = False, limit: int = 50):
    """Retrieves system notifications."""
    return get_notifications(unread_only=unread_only, limit=limit)

@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int):
    """Marks a single notification as read."""
    success = mark_notification_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success", "message": "Notification marked as read"}

@app.post("/api/notifications/read-all")
def read_all_notifications():
    """Marks all notifications as read."""
    count = mark_all_notifications_read()
    return {"status": "success", "count": count, "message": f"{count} notifications marked as read"}

# --- 6. Validation Reports & Export Endpoints ---

@app.get("/api/reports/validation-runs")
def list_validation_runs(limit: int = 30):
    """Lists past validation runs."""
    return get_all_validation_runs(limit=limit)

@app.get("/api/reports/validation-runs/{run_id}")
def get_validation_run(run_id: str):
    """Retrieves full details for a specific validation run."""
    run = get_validation_run_details(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Validation run '{run_id}' not found")
    return run

@app.get("/api/reports/validation-runs/{run_id}/export/json")
def export_run_json(run_id: str):
    """Downloads validation report as JSON."""
    run = get_validation_run_details(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Validation run '{run_id}' not found")
    return JSONResponse(content=run, headers={
        "Content-Disposition": f"attachment; filename=validation_report_{run_id}.json"
    })

@app.get("/api/reports/validation-runs/{run_id}/export/csv")
def export_run_csv(run_id: str):
    """Downloads validation report as CSV."""
    try:
        csv_data = export_run_to_csv(run_id)
        return Response(content=csv_data, media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename=validation_report_{run_id}.csv"
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- 7. Aggregated Dashboard Summary & Metrics ---

@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    """
    Returns aggregated metrics, environment statuses, and chart data for the improved dashboard.
    """
    global latest_validation_report
    if latest_validation_report is None:
        latest_validation_report = validate_configurations()

    with get_db() as conn:
        cursor = conn.cursor()

        # Count total validations
        cursor.execute("SELECT COUNT(*) as cnt FROM validation_runs")
        total_validations = cursor.fetchone()["cnt"]

        # Count blocked deployments
        cursor.execute("SELECT COUNT(*) as cnt FROM validation_runs WHERE deployment_decision = 'BLOCKED'")
        blocked_deployments = cursor.fetchone()["cnt"]

        # Count approved changes
        cursor.execute("SELECT COUNT(*) as cnt FROM change_requests WHERE status = 'APPROVED'")
        approved_changes = cursor.fetchone()["cnt"]

        # Count rollbacks
        cursor.execute("SELECT COUNT(*) as cnt FROM rollback_records")
        rollbacks = cursor.fetchone()["cnt"]

        # Count git commits
        cursor.execute("SELECT COUNT(*) as cnt FROM git_commits")
        git_commits_cnt = cursor.fetchone()["cnt"]

        # Count unread notifications
        cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE is_read = 0")
        unread_notifs = cursor.fetchone()["cnt"]

        # Recent validation runs for charts
        cursor.execute("""
            SELECT run_id, environment, total_checks, passed_checks, failed_checks,
                   critical_count, high_count, deployment_decision, risk_score, created_at
            FROM validation_runs
            ORDER BY id DESC LIMIT 7
        """)
        recent_runs = [dict(r) for r in cursor.fetchall()]

    # Drift counts by environment
    drifts_by_env = {"development": 0, "staging": 0, "production": 0}
    for d in latest_validation_report.discrepancies:
        env_key = d.environment.lower()
        if env_key in drifts_by_env:
            drifts_by_env[env_key] += 1
        else:
            drifts_by_env[env_key] = 1

    # Severity distribution
    issues_by_severity = {
        "CRITICAL": latest_validation_report.critical_count,
        "HIGH": latest_validation_report.high_count,
        "MEDIUM": latest_validation_report.medium_count,
        "LOW": latest_validation_report.low_count
    }

    # Environment statuses
    env_status = dict(latest_validation_report.environment_status)

    # Calculate overall risk score
    risk_summary = calculate_risk_score(
        environment="production",
        discrepancies=latest_validation_report.discrepancies,
        has_runtime_drift=any(d.category == "runtime" for d in latest_validation_report.discrepancies)
    )

    return {
        "environment_status": env_status,
        "active_versions": {
            "development": get_active_version("development") or 1,
            "staging": get_active_version("staging") or 1,
            "production": get_active_version("production") or 1
        },
        "metrics": {
            "total_validations": max(total_validations, 1),
            "configuration_drifts": latest_validation_report.total_discrepancies,
            "critical_issues": latest_validation_report.critical_count,
            "high_issues": latest_validation_report.high_count,
            "blocked_deployments": blocked_deployments,
            "approved_changes": approved_changes,
            "rollbacks_performed": rollbacks,
            "git_commits_recorded": git_commits_cnt,
            "unread_notifications": unread_notifs,
            "risk_score": risk_summary["score"],
            "risk_level": risk_summary["level"]
        },
        "charts": {
            "drifts_by_env": drifts_by_env,
            "issues_by_severity": issues_by_severity,
            "recent_validations": list(reversed(recent_runs)),
            "gate_ratio": {
                "blocked": blocked_deployments,
                "allowed": max(0, total_validations - blocked_deployments)
            }
        },
        "latest_report_id": latest_validation_report.validation_run_id,
        "latest_decision": "ALLOWED" if latest_validation_report.production_deployment_allowed else "BLOCKED"
    }

# --- Static Frontend Mounting ---

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"message": "Configuration Drift Validator API is running. Frontend not yet mounted."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
