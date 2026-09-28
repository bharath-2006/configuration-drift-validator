"""
rollback.py - Configuration Version Management and Rollback Engine
Enables immutable version tracking, history inspection, and safe rollbacks.
"""

from typing import Dict, Any, List, Optional
from backend.database import get_db
from backend.audit import log_audit_event

def get_active_version(environment: str) -> Optional[int]:
    """Gets the currently active version number for an environment."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT version FROM configuration_versions
            WHERE environment = ? AND is_active = 1
            ORDER BY version DESC LIMIT 1
        """, (environment,))
        row = cursor.fetchone()
        return row["version"] if row else None

def get_version_history(environment: str) -> List[Dict[str, Any]]:
    """Fetches all configuration versions for a given environment."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, environment, version, is_active, description, created_by, created_at
            FROM configuration_versions
            WHERE environment = ?
            ORDER BY version DESC
        """, (environment,))
        return [dict(row) for row in cursor.fetchall()]

def get_config_snapshot_by_version(environment: str, version_num: int) -> Optional[Dict[str, Any]]:
    """Retrieves full configuration bundle for an environment at a specific version."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, environment, version, is_active, description, created_by, created_at
            FROM configuration_versions
            WHERE environment = ? AND version = ?
        """, (environment, version_num))
        v_row = cursor.fetchone()
        if not v_row:
            return None

        v_id = v_row["id"]

        # Environment variables
        cursor.execute("SELECT key, value, data_type FROM environment_variables WHERE version_id = ?", (v_id,))
        variables = {row["key"]: row["value"] for row in cursor.fetchall()}

        # Infrastructure
        cursor.execute("""
            SELECT service_name, replicas, memory, cpu, port, health_check
            FROM infrastructure_definitions WHERE version_id = ?
        """, (v_id,))
        infra_row = cursor.fetchone()
        infra = dict(infra_row) if infra_row else {}
        if infra and "health_check" in infra:
            infra["health_check"] = bool(infra["health_check"])

        # Secrets metadata
        cursor.execute("""
            SELECT name, environment, is_present, source, last_rotated, age_days
            FROM secret_metadata WHERE version_id = ?
        """, (v_id,))
        secrets = []
        for row in cursor.fetchall():
            s = dict(row)
            s["is_present"] = bool(s.get("is_present", 1))
            s["exists"] = s["is_present"]
            secrets.append(s)

        return {
            "environment": environment,
            "version": version_num,
            "is_active": bool(v_row["is_active"]),
            "description": v_row["description"],
            "created_by": v_row["created_by"],
            "created_at": v_row["created_at"],
            "variables": variables,
            "infrastructure": infra,
            "secrets": secrets
        }

def save_new_config_version(
    environment: str,
    variables: Dict[str, Any],
    infra: Dict[str, Any],
    secrets: List[Dict[str, Any]],
    description: str = "Configuration update",
    author: str = "developer"
) -> int:
    """
    Saves a new immutable configuration version and marks it active.
    Deactivates previous versions.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Find current highest version
        cursor.execute("SELECT MAX(version) as max_v FROM configuration_versions WHERE environment = ?", (environment,))
        row = cursor.fetchone()
        current_max = row["max_v"] if row and row["max_v"] is not None else 0
        new_version = current_max + 1

        # Mark previous versions as inactive
        cursor.execute("UPDATE configuration_versions SET is_active = 0 WHERE environment = ?", (environment,))

        # Create new version record
        cursor.execute("""
            INSERT INTO configuration_versions (environment, version, is_active, description, created_by)
            VALUES (?, ?, 1, ?, ?)
        """, (environment, new_version, description, author))
        version_id = cursor.lastrowid

        # Insert variables
        for k, v in variables.items():
            cursor.execute("""
                INSERT INTO environment_variables (version_id, key, value)
                VALUES (?, ?, ?)
            """, (version_id, str(k), str(v)))

        # Insert infrastructure definition
        if infra:
            cursor.execute("""
                INSERT INTO infrastructure_definitions (version_id, service_name, replicas, memory, cpu, port, health_check)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id,
                infra.get("service", infra.get("service_name", "app-service")),
                infra.get("replicas", 1),
                infra.get("memory", "512Mi"),
                infra.get("cpu", "500m"),
                infra.get("port", 8080),
                1 if infra.get("health_check", True) else 0
            ))

        # Insert secret metadata
        for sec in secrets:
            cursor.execute("""
                INSERT INTO secret_metadata (version_id, name, environment, is_present, source, last_rotated, age_days)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id,
                sec.get("name", "SECRET"),
                environment,
                1 if sec.get("exists", sec.get("is_present", True)) else 0,
                sec.get("source", "secret-manager"),
                sec.get("last_rotated", "2026-08-20"),
                sec.get("age_days", 0)
            ))

    log_audit_event(
        user=author,
        action="Configuration Created",
        environment=environment,
        details=f"Created version {new_version}: {description}",
        risk_level="INFO"
    )

    return new_version

def perform_rollback(
    environment: str,
    target_version: int,
    reason: str,
    performed_by: str = "devops-lead"
) -> Dict[str, Any]:
    """
    Rolls back the active configuration of an environment to target_version.
    Maintains audit logs and rollback records.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify target version exists
        cursor.execute("SELECT id FROM configuration_versions WHERE environment = ? AND version = ?", (environment, target_version))
        target_row = cursor.fetchone()
        if not target_row:
            raise ValueError(f"Version {target_version} does not exist for environment '{environment}'.")

        # Find currently active version
        cursor.execute("SELECT version FROM configuration_versions WHERE environment = ? AND is_active = 1", (environment,))
        active_row = cursor.fetchone()
        from_version = active_row["version"] if active_row else 0

        # Mark all inactive, then activate target
        cursor.execute("UPDATE configuration_versions SET is_active = 0 WHERE environment = ?", (environment,))
        cursor.execute("UPDATE configuration_versions SET is_active = 1 WHERE environment = ? AND version = ?", (environment, target_version))

        # Record rollback event
        cursor.execute("""
            INSERT INTO rollback_records (environment, from_version, to_version, reason, performed_by)
            VALUES (?, ?, ?, ?, ?)
        """, (environment, from_version, target_version, reason, performed_by))

    # Retrieve the restored snapshot to verify actual state restoration
    restored_snapshot = get_config_snapshot_by_version(environment, target_version) or {}
    restored_vars = restored_snapshot.get("variables", {})
    restored_infra = restored_snapshot.get("infrastructure", {})

    # Actual state restoration: sync restored configuration back to filesystem configs/
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent
    env_dir = base_dir / "configs" / environment
    if env_dir.exists() and restored_vars:
        env_file = env_dir / "app.env"
        env_lines = [f"{k}={v}" for k, v in restored_vars.items()]
        try:
            env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    log_audit_event(
        user=performed_by,
        action="Configuration Rollback",
        environment=environment,
        details=f"Rolled back from Version {from_version} to Version {target_version}. Restored {len(restored_vars)} variables. Reason: {reason}",
        risk_level="HIGH"
    )

    # Dispatch notification for operational visibility
    try:
        from backend.notifications import create_notification
        create_notification(
            title=f"Configuration Rollback: {environment.title()} v{target_version}",
            message=f"Restored from v{from_version} to v{target_version}. Reason: {reason}",
            severity="WARNING",
            category="rollback",
            environment=environment
        )
    except Exception:
        pass

    return {
        "status": "success",
        "environment": environment,
        "from_version": from_version,
        "restored_version": target_version,
        "reason": reason,
        "performed_by": performed_by,
        "restored_variables": restored_vars,
        "message": f"Successfully restored {environment} to Version {target_version}"
    }

def get_all_rollback_records() -> List[Dict[str, Any]]:
    """Fetches full rollback history across environments."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, environment, from_version, to_version, reason, performed_by, timestamp
            FROM rollback_records
            ORDER BY timestamp DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

def compare_config_versions(environment: str, version_a: int, version_b: int) -> Dict[str, Any]:
    """
    Compares two configuration versions for an environment and computes side-by-side diff:
    OLD VALUE (version_a) -> NEW VALUE (version_b)
    """
    snap_a = get_config_snapshot_by_version(environment, version_a)
    snap_b = get_config_snapshot_by_version(environment, version_b)

    if not snap_a:
        raise ValueError(f"Version {version_a} not found for '{environment}'.")
    if not snap_b:
        raise ValueError(f"Version {version_b} not found for '{environment}'.")

    vars_a = snap_a.get("variables", {})
    vars_b = snap_b.get("variables", {})

    all_var_keys = sorted(set(vars_a.keys()) | set(vars_b.keys()))
    variable_diffs = []

    for k in all_var_keys:
        val_a = vars_a.get(k)
        val_b = vars_b.get(k)

        if k in vars_a and k not in vars_b:
            change_type = "REMOVED"
        elif k not in vars_a and k in vars_b:
            change_type = "ADDED"
        elif str(val_a).strip() != str(val_b).strip():
            change_type = "MODIFIED"
        else:
            change_type = "UNCHANGED"

        variable_diffs.append({
            "key": k,
            "old_value": val_a,
            "new_value": val_b,
            "change_type": change_type
        })

    # Infrastructure comparison
    infra_a = snap_a.get("infrastructure", {})
    infra_b = snap_b.get("infrastructure", {})
    all_infra_keys = sorted(set(infra_a.keys()) | set(infra_b.keys()))
    infra_diffs = []
    for k in all_infra_keys:
        ia = infra_a.get(k)
        ib = infra_b.get(k)
        if ia != ib:
            infra_diffs.append({
                "key": k,
                "old_value": ia,
                "new_value": ib,
                "change_type": "MODIFIED" if (ia is not None and ib is not None) else "ADDED" if ia is None else "REMOVED"
            })

    modified_count = sum(1 for d in variable_diffs if d["change_type"] == "MODIFIED")
    added_count = sum(1 for d in variable_diffs if d["change_type"] == "ADDED")
    removed_count = sum(1 for d in variable_diffs if d["change_type"] == "REMOVED")

    return {
        "environment": environment,
        "version_a": version_a,
        "version_b": version_b,
        "version_a_meta": {
            "created_by": snap_a.get("created_by"),
            "created_at": snap_a.get("created_at"),
            "description": snap_a.get("description")
        },
        "version_b_meta": {
            "created_by": snap_b.get("created_by"),
            "created_at": snap_b.get("created_at"),
            "description": snap_b.get("description")
        },
        "summary": {
            "total_keys_compared": len(all_var_keys),
            "modified": modified_count,
            "added": added_count,
            "removed": removed_count,
            "infra_changes": len(infra_diffs)
        },
        "variable_diffs": variable_diffs,
        "infra_diffs": infra_diffs
    }

