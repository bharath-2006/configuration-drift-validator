"""
database.py - Database Initialization and Connection Manager for SQLite
Configuration Drift Validator (College Project)

Provides lightweight SQLite connection handling and automated table creation.
Uses row factory to return dictionary-like records for easy serialization.
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager

# Database file placed in project root
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "drift_validator.db"

def get_db_connection():
    """Create and return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db():
    """Context manager for safe database transactions."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize all tables required by the Configuration Drift Validator."""
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Environments table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS environments (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            is_production BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Configuration Versions (for immutable snapshots and rollback)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuration_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment TEXT NOT NULL,
            version INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            description TEXT,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (environment) REFERENCES environments(id),
            UNIQUE(environment, version)
        );
        """)

        # 3. Environment Variables (attached to a config version)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS environment_variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            data_type TEXT DEFAULT 'string',
            FOREIGN KEY (version_id) REFERENCES configuration_versions(id) ON DELETE CASCADE
        );
        """)

        # 4. Infrastructure Definitions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS infrastructure_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            replicas INTEGER NOT NULL,
            memory TEXT NOT NULL,
            cpu TEXT NOT NULL,
            port INTEGER NOT NULL,
            health_check BOOLEAN NOT NULL DEFAULT 1,
            FOREIGN KEY (version_id) REFERENCES configuration_versions(id) ON DELETE CASCADE
        );
        """)

        # 5. Secret Metadata (ONLY metadata, NEVER real secret values)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS secret_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            environment TEXT NOT NULL,
            is_present BOOLEAN NOT NULL DEFAULT 1,
            source TEXT DEFAULT 'secret-manager',
            last_rotated TEXT,
            age_days INTEGER DEFAULT 0,
            FOREIGN KEY (version_id) REFERENCES configuration_versions(id) ON DELETE CASCADE
        );
        """)

        # 6. Runtime Snapshots (actual state captured from live containers)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runtime_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            app_version TEXT,
            raw_json TEXT NOT NULL
        );
        """)

        # 7. Drift Results (history of detected configuration discrepancies)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drift_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            validation_run_id TEXT NOT NULL,
            environment TEXT NOT NULL,
            category TEXT NOT NULL, -- env_var, infrastructure, secret, runtime
            item_key TEXT NOT NULL,
            expected_val TEXT,
            actual_val TEXT,
            severity TEXT NOT NULL, -- CRITICAL, HIGH, MEDIUM, LOW
            reason TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 8. Change Requests (Approval Workflow)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            proposed_changes_json TEXT NOT NULL,
            risk_level TEXT NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
            status TEXT DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
            requested_by TEXT NOT NULL,
            reviewed_by TEXT,
            review_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        );
        """)

        # 9. Rollback Records
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rollback_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment TEXT NOT NULL,
            from_version INTEGER NOT NULL,
            to_version INTEGER NOT NULL,
            reason TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 10. Audit Trail (Tamper-evident system activity log)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user TEXT NOT NULL,
            action TEXT NOT NULL,
            environment TEXT NOT NULL,
            details TEXT NOT NULL,
            risk_level TEXT DEFAULT 'INFO' -- INFO, LOW, MEDIUM, HIGH, CRITICAL
        );
        """)

        # Seed default environments if empty
        cursor.execute("SELECT COUNT(*) as count FROM environments;")
        if cursor.fetchone()["count"] == 0:
            cursor.executemany("""
            INSERT INTO environments (id, display_name, description, is_production)
            VALUES (?, ?, ?, ?);
            """, [
                ("development", "Development", "Local developer testing & feature prototyping", 0),
                ("staging", "Staging", "Shared integration environment resembling production", 0),
                ("production", "Production", "Live user-facing high-availability production environment", 1)
            ])

    print("Database initialized successfully at:", DB_PATH)

if __name__ == "__main__":
    init_db()
