"""
test_api_gate.py - Integration tests for Deployment Gate and Change Request Lifecycle
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app, seed_sample_configs_if_needed
from backend.rollback import save_new_config_version
from backend.auth import create_access_token

client = TestClient(app)
admin_token = create_access_token({"sub": "admin", "role": "admin"})
client.headers["Authorization"] = f"Bearer {admin_token}"

@pytest.fixture(autouse=True)
def setup_api():
    client.post("/api/reset-demo")

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_api_deployment_gate_approved_on_clean_state():
    # Trigger validation
    val_res = client.post("/api/validate")
    assert val_res.status_code == 200

    gate_res = client.get("/api/deployment-gate")
    assert gate_res.status_code == 200
    data = gate_res.json()
    assert data["production_deployment_allowed"] is True
    assert data["critical_count"] == 0

def test_api_deployment_gate_blocks_on_critical_drift():
    # Inject critical mistake: DEBUG=true in prod
    client.post("/api/configs/production/update", json={
        "environment": "production",
        "raw_env_content": "APP_ENV=production\nDEBUG=true\nDATABASE_HOST=prod-db\nDATABASE_PORT=5432\nAPI_URL=https://api\nLOG_LEVEL=INFO",
        "description": "Mistakenly enabled debug",
        "author": "tester"
    })

    # Validate
    val_res = client.post("/api/validate")
    assert val_res.status_code == 200
    summary = val_res.json()
    assert summary["production_deployment_allowed"] is False
    assert summary["critical_count"] >= 1

    # Check Gate
    gate_res = client.get("/api/deployment-gate")
    data = gate_res.json()
    assert data["production_deployment_allowed"] is False
    assert "BLOCKED" in data["deployment_message"]
    assert len(data["blocking_issues"]) >= 1

def test_change_request_approval_workflow():
    # Submit change request
    create_res = client.post("/api/change-requests", json={
        "environment": "production",
        "title": "Migrate Database Host to prod-db-replica",
        "description": "Production database read replica switch",
        "proposed_changes_json": '{"variables": {"DATABASE_HOST": "prod-db"}}',
        "requested_by": "dev-engineer"
    })
    assert create_res.status_code == 200
    cr_id = create_res.json()["id"]

    # Review & Approve
    review_res = client.post(f"/api/change-requests/{cr_id}/review", json={
        "status": "APPROVED",
        "reviewed_by": "principal-architect",
        "review_notes": "Verified and approved"
    })
    assert review_res.status_code == 200
    assert "approved" in review_res.json()["message"].lower()

    # Verify change request is marked APPROVED
    list_res = client.get("/api/change-requests")
    cr_item = next(c for c in list_res.json() if c["id"] == cr_id)
    assert cr_item["status"] == "APPROVED"
    assert cr_item["reviewed_by"] == "admin"
