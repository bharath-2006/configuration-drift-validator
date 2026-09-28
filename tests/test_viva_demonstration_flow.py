"""
test_viva_demonstration_flow.py - Complete 16-Step Viva Demonstration Verification
Configuration Drift Validator (College Project Phase 2 - 70% Version)

Directly exercises the exact viva walkthrough from Section 22:
  Step 1:  Open dashboard -> All environments Healthy
  Step 2:  Change Production DATABASE_HOST from prod-db to dev-db
  Step 3:  Commit change
  Step 4:  Run CI/CD validation
  Step 5:  Validation Failed: Critical Drift Detected (dev-db in prod)
  Step 6:  Deployment gate is BLOCKED
  Step 7:  Create change request
  Step 8:  Approve correction
  Step 9:  Restore DATABASE_HOST=prod-db
  Step 10: Run validation again -> Validation Passed (Gate OPEN)
  Step 11: Audit trail recorded
  Step 12: Configuration history & side-by-side diff
  Step 13: Runtime monitoring status
  Step 14: Create runtime drift (LOG_LEVEL=DEBUG)
  Step 15: Monitoring alert generated
  Step 16: Rollback demonstrated
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_full_16_step_viva_demonstration():
    # Setup: Clean state
    reset_res = client.post("/api/reset-demo")
    assert reset_res.status_code == 200

    # Step 1: Show Environments Healthy
    dash_res = client.get("/api/dashboard/summary")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["environment_status"]["development"] == "Healthy"
    assert dash_data["environment_status"]["production"] == "Healthy"

    # Step 2: Change Production DATABASE_HOST to dev-db
    update_res = client.post("/api/configs/production/update", json={
        "environment": "production",
        "raw_env_content": "APP_ENV=production\nDEBUG=false\nDATABASE_HOST=dev-db\nDATABASE_PORT=5432\nAPI_URL=https://api\nLOG_LEVEL=INFO",
        "description": "Mistakenly pointed Production to dev-db",
        "author": "Junior-Dev"
    })
    assert update_res.status_code == 200

    # Step 3 & 4: Commit & Run CI/CD validation
    commit_res = client.post("/api/git/simulate-commit", json={
        "author": "Junior-Dev",
        "message": "fix: update production database host to dev-db",
        "environment": "production",
        "changed_configs": {"DATABASE_HOST": "dev-db"}
    })
    assert commit_res.status_code == 200
    commit_data = commit_res.json()

    # Step 5: Show Validation Failed & Critical Drift
    assert commit_data["validation_result"] == "BLOCKED"
    assert commit_data["risk_level"] == "CRITICAL"
    assert commit_data["risk_score"] >= 75

    # Step 6: Verify Deployment Gate is BLOCKED
    val_res = client.post("/api/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["production_deployment_allowed"] is False
    assert val_data["critical_count"] >= 1

    gate_res = client.get("/api/deployment-gate")
    assert gate_res.status_code == 200
    gate_data = gate_res.json()
    assert gate_data["production_deployment_allowed"] is False
    assert len(gate_data["blocking_issues"]) >= 1

    # Step 7: Create Change Request
    cr_res = client.post("/api/change-requests", json={
        "environment": "production",
        "title": "Restore DATABASE_HOST to prod-db",
        "description": "Correction to fix critical database pointer",
        "proposed_changes_json": '{"variables": {"DATABASE_HOST": "prod-db"}}',
        "requested_by": "Bharath (Student)"
    })
    assert cr_res.status_code == 200
    cr_id = cr_res.json()["id"]

    # Step 8 & 9: Approve Correction & Restore prod-db
    review_res = client.post(f"/api/change-requests/{cr_id}/review", json={
        "status": "APPROVED",
        "reviewed_by": "Tech-Lead-Reviewer",
        "review_notes": "Correction approved, restoring prod-db cluster pointer"
    })
    assert review_res.status_code == 200

    # Step 10: Run validation again -> Safe
    val2_res = client.post("/api/validate")
    assert val2_res.status_code == 200
    val2_data = val2_res.json()
    assert val2_data["production_deployment_allowed"] is True
    assert val2_data["critical_count"] == 0

    # Step 11: Audit trail has records
    audit_res = client.get("/api/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 5

    # Step 12: Configuration History & Diff
    hist_res = client.get("/api/configs/production/history")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 3

    diff_res = client.get("/api/configs/production/compare?v_a=1&v_b=2")
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert "variable_diffs" in diff_data

    # Step 13: Continuous Monitoring Status
    mon_res = client.get("/api/monitoring/status?environment=production")
    assert mon_res.status_code == 200
    assert "current_environment_status" in mon_res.json()

    # Step 14 & 15: Create Runtime Drift & Alert
    client.post("/api/runtime/production", json={
        "environment": "production",
        "app_version": "1.0.0",
        "snapshot_data": {"database_host": "prod-db", "log_level": "DEBUG"}
    })
    scan_res = client.post("/api/monitoring/scan")
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["drifts_count"] >= 1

    notifs_res = client.get("/api/notifications")
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()
    assert len(notifs) >= 1

    # Step 16: Demonstrate Rollback
    rollback_res = client.post("/api/rollback", json={
        "environment": "production",
        "target_version": 1,
        "reason": "Restoring to pristine initial version 1",
        "performed_by": "lead-admin"
    })
    assert rollback_res.status_code == 200
    assert rollback_res.json()["status"] == "success"
    assert rollback_res.json()["restored_version"] == 1
