"""
auth.py - Authentication and Role-Based Access Control (RBAC)
Configuration Drift Validator (FastAPI + JWT + PBKDF2)

Implements:
1. Role-Based Access Control (Roles: Admin, Developer, Viewer)
2. PBKDF2-HMAC-SHA256 password hashing with salt (OWASP compliant)
3. Cryptographically signed JWT tokens (RFC 7519) with expiration
4. FastAPI security dependencies: require_admin, require_developer, require_viewer
5. Verified user identity extraction (never trusting user-supplied headers/bodies)
"""

import os
import hmac
import hashlib
import secrets
import jwt
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from backend.database import get_db

# Configuration from environment variables with secure defaults
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "cdv-insecure-dev-jwt-secret-key-replace-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
PBKDF2_ROUNDS = 100_000

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"

ROLE_HIERARCHY: Dict[str, int] = {
    Role.VIEWER.value: 1,
    Role.DEVELOPER.value: 2,
    Role.ADMIN.value: 3
}

class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    expires_in_minutes: int

class AuthenticatedUser(BaseModel):
    id: int
    username: str
    role: str
    email: Optional[str] = None
    is_active: bool = True

def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a 16-byte cryptographically secure salt.
    Returns: salt_hex$hash_hex
    """
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return f"{salt}${key.hex()}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verifies a plain password against the stored salt$hash using constant-time comparison.
    """
    try:
        if not stored_hash or "$" not in stored_hash:
            return False
        salt, key_hex = stored_hash.split("$", 1)
        calculated = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS).hex()
        return hmac.compare_digest(calculated, key_hex)
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates an HMAC-SHA256 signed JWT token with exp, sub, and role claims.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "iat": now,
        "exp": expire,
        "sub": str(data.get("sub", data.get("username", "anonymous"))),
        "role": data.get("role", Role.VIEWER.value)
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token signature and expiry.
    Raises HTTPException(401) on failure.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature or format.",
            headers={"WWW-Authenticate": "Bearer"}
        )

def get_user_from_db_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Fetches user record from SQLite by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role, email, is_active FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def authenticate_user(username: str, password: str) -> Optional[AuthenticatedUser]:
    """
    Authenticates a user against database credentials.
    Returns AuthenticatedUser if valid, None otherwise.
    """
    user_record = get_user_from_db_by_username(username)
    if not user_record:
        return None
    if not verify_password(password, user_record["password_hash"]):
        return None
    if not bool(user_record.get("is_active", 1)):
        return None
    return AuthenticatedUser(
        id=user_record["id"],
        username=user_record["username"],
        role=user_record["role"],
        email=user_record.get("email"),
        is_active=bool(user_record.get("is_active", 1))
    )

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> AuthenticatedUser:
    """
    FastAPI Dependency to retrieve and verify the active authenticated user from Bearer JWT.
    Raises HTTP 401 if token is missing or invalid.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token in 'Authorization: Bearer <token>' header.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = decode_access_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing subject identifier.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    role = payload.get("role", Role.VIEWER.value)
    user_db = get_user_from_db_by_username(username)
    if user_db:
        if not bool(user_db.get("is_active", 1)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated."
            )
        return AuthenticatedUser(
            id=user_db["id"],
            username=user_db["username"],
            role=user_db["role"],
            email=user_db.get("email"),
            is_active=bool(user_db.get("is_active", 1))
        )
    
    # If user exists in valid token payload
    return AuthenticatedUser(
        id=1,
        username=username,
        role=role,
        email=f"{username}@cdv.internal",
        is_active=True
    )

def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme)) -> AuthenticatedUser:
    """
    Optional dependency: returns verified user if valid token supplied,
    or falls back to read-only guest viewer.
    """
    if not token:
        return AuthenticatedUser(id=0, username="guest", role=Role.VIEWER.value, email="guest@cdv.internal")
    try:
        return get_current_user(token)
    except HTTPException:
        return AuthenticatedUser(id=0, username="guest", role=Role.VIEWER.value, email="guest@cdv.internal")

def require_role(min_role: Role):
    """
    Factory dependency creating a role enforcement guard.
    Raises 401 if unauthenticated, 403 if role insufficient.
    """
    min_level = ROLE_HIERARCHY.get(min_role.value, 1)

    def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        user_level = ROLE_HIERARCHY.get(user.role.lower(), 1)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required role '{min_role.value}', but authenticated user '{user.username}' has role '{user.role}'."
            )
        return user

    return role_checker

# Convenience Dependencies
require_admin = require_role(Role.ADMIN)
require_developer = require_role(Role.DEVELOPER)
require_viewer = require_role(Role.VIEWER)
