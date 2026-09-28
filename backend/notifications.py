"""
notifications.py - In-App Notification Manager
Configuration Drift Validator (College Project Phase 2)

Handles recording, querying, and acknowledging notifications for critical events:
- Critical drift detected
- Production deployment blocked
- High-impact change request submitted
- Runtime drift detected
- Rollback executed
"""

from typing import List, Dict, Any, Optional
from backend.database import get_db

def create_notification(
    title: str,
    message: str,
    severity: str = "INFO",  # INFO, WARNING, CRITICAL
    category: str = "drift", # drift, deployment, change_request, runtime, rollback
    environment: Optional[str] = "production"
) -> int:
    """Inserts a new notification and returns its ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (title, message, severity, category, environment)
            VALUES (?, ?, ?, ?, ?)
        """, (title, message, severity.upper(), category.lower(), environment))
        return cursor.lastrowid

def get_notifications(unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches recent notifications ordered newest first."""
    with get_db() as conn:
        cursor = conn.cursor()
        if unread_only:
            cursor.execute("""
                SELECT id, title, message, severity, category, environment, is_read, created_at
                FROM notifications
                WHERE is_read = 0
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT id, title, message, severity, category, environment, is_read, created_at
                FROM notifications
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def mark_notification_read(notification_id: int) -> bool:
    """Marks a single notification as read."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        return cursor.rowcount > 0

def mark_all_notifications_read() -> int:
    """Marks all notifications as read."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
        return cursor.rowcount
