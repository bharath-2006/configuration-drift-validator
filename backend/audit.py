"""
audit.py - Centralized Audit Trail Logging
Records every security and configuration change event into SQLite.
"""

from typing import Optional
from backend.database import get_db

def log_audit_event(
    user: str,
    action: str,
    environment: str,
    details: str,
    risk_level: str = "INFO"
) -> int:
    """
    Inserts a record into the audit_logs table.
    Returns the newly inserted log ID.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user, action, environment, details, risk_level)
            VALUES (?, ?, ?, ?, ?)
        """, (user, action, environment, details, risk_level))
        log_id = cursor.lastrowid
    return log_id

def get_recent_audit_logs(limit: int = 50):
    """
    Fetches the most recent audit log entries.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, user, action, environment, details, risk_level
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
