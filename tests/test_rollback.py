"""
test_rollback.py - Tests for Versioning, Rollbacks, Audit Trail, and Deployment Gate
"""

import pytest
from backend.database import init_db, get_db
from backend.rollback import (
    save_new_config_version,
    get_active_version,
    get_config_snapshot_by_version,
    perform_rollback,
    get_all_rollback_records
)
from backend.audit import log_audit_event, get_recent_audit_logs

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()

def test_config_versioning_and_rollback():
    """Verify version creation, increment, and rollback to previous version."""
    env = "staging"

    # Version 1
    v1 = save_new_config_version(
        environment=env,
        variables={"DATABASE_HOST": "staging-db-v1", "DEBUG": "true"},
        infra={"service": "app", "replicas": 2},
        secrets=[],
        description="Version 1",
        author="tester"
    )
    assert get_active_version(env) == v1

    # Version 2 (change db host)
    v2 = save_new_config_version(
        environment=env,
        variables={"DATABASE_HOST": "staging-db-v2-broken", "DEBUG": "true"},
        infra={"service": "app", "replicas": 2},
        secrets=[],
        description="Version 2 broken",
        author="tester"
    )
    assert get_active_version(env) == v2
    assert v2 > v1

    # Perform Rollback v2 -> v1
    rollback_res = perform_rollback(
        environment=env,
        target_version=v1,
        reason="Testing rollback restoration",
        performed_by="qa-engineer"
    )

    assert rollback_res["status"] == "success"
    assert rollback_res["restored_version"] == v1
    assert get_active_version(env) == v1

    # Verify restored config matches v1
    active_cfg = get_config_snapshot_by_version(env, v1)
    assert active_cfg["variables"]["DATABASE_HOST"] == "staging-db-v1"

def test_audit_logging():
    """Verify audit log creation and retrieval."""
    log_id = log_audit_event(
        user="test-developer",
        action="Test Action",
        environment="production",
        details="Automated test event verification",
        risk_level="HIGH"
    )
    assert log_id > 0

    recent_logs = get_recent_audit_logs(limit=10)
    matching = [l for l in recent_logs if l["id"] == log_id]
    assert len(matching) == 1
    assert matching[0]["user"] == "test-developer"
    assert matching[0]["risk_level"] == "HIGH"
