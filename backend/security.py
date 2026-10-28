"""
security.py - Security Utilities and Protections
Configuration Drift Validator (College Project)

Provides focused, practical protections for:
1. Environment name validation (whitelist verification)
2. Secret sanitization and masking (ensuring secrets never leak in logs, errors, or reports)
3. Safe path traversal protection (preventing path injection in file uploads or artifacts)
4. Upload payload size limiting (preventing Denial-of-Service via oversized configs)
5. Sensitive key detection
"""

import re
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Union

# Whitelist of allowed environments
VALID_ENVIRONMENTS: Set[str] = {"development", "staging", "production"}

# Maximum configuration payload size in bytes (1 Megabyte is more than sufficient for configs)
MAX_CONFIG_PAYLOAD_BYTES: int = 1024 * 1024  # 1 MB

# Patterns identifying sensitive configuration keys
SENSITIVE_KEY_PATTERNS = [
    r"pass(word)?",
    r"secret",
    r"api[_-]?key",
    r"auth(orization)?[_-]?token",
    r"private[_-]?key",
    r"jwt",
    r"bearer",
    r"credential",
    r"access[_-]?token"
]
SENSITIVE_REGEX = re.compile("|".join(SENSITIVE_KEY_PATTERNS), re.IGNORECASE)

class SecurityValidationError(ValueError):
    """Raised when an untrusted input violates security policies."""
    pass

def validate_environment_name(environment: str) -> str:
    """
    Validates that the provided environment name is strictly within the allowed whitelist.
    Prevents path injection or arbitrary environment creation.
    """
    if not environment or not isinstance(environment, str):
        raise SecurityValidationError("Environment name must be a non-empty string.")
    
    clean_env = environment.strip().lower()
    if clean_env not in VALID_ENVIRONMENTS:
        raise SecurityValidationError(
            f"Invalid environment '{environment}'. Allowed environments are: {', '.join(sorted(VALID_ENVIRONMENTS))}."
        )
    return clean_env

def sanitize_safe_filename(filename: str) -> str:
    """
    Sanitizes an uploaded filename to prevent directory traversal attacks (e.g. '../../etc/passwd').
    Extracts the basename and strips dangerous characters.
    """
    if not filename:
        return "unnamed_artifact"
    # Extract only the base name (no directory components)
    base = os.path.basename(filename.replace("\\", "/"))
    # Allow alphanumeric, hyphens, underscores, dots
    clean = re.sub(r"[^A-Za-z0-9_.-]", "_", base)
    if not clean or clean.startswith("."):
        return f"safe_{clean.lstrip('.')}" if clean.lstrip('.') else "safe_artifact"
    return clean

def validate_payload_size(content: Union[str, bytes], max_bytes: int = MAX_CONFIG_PAYLOAD_BYTES) -> None:
    """
    Verifies that uploaded configuration payloads do not exceed reasonable size limits.
    Prevents memory exhaustion or regex Denial-of-Service.
    """
    byte_count = len(content.encode("utf-8")) if isinstance(content, str) else len(content)
    if byte_count > max_bytes:
        raise SecurityValidationError(
            f"Configuration payload size ({byte_count} bytes) exceeds maximum allowable limit of {max_bytes} bytes."
        )

def is_sensitive_key(key_name: str) -> bool:
    """
    Returns True if key name matches known patterns for passwords, API keys, or tokens.
    """
    if not key_name or not isinstance(key_name, str):
        return False
    return bool(SENSITIVE_REGEX.search(key_name))

def mask_secret_value(value: Any) -> str:
    """
    Returns a masked string for a secret value.
    Never exposes raw secrets in logs, reports, or error messages.
    """
    if value is None:
        return "<NULL>"
    val_str = str(value)
    if len(val_str) <= 4:
        return "********"
    # Show at most first 2 chars and last 2 chars for verification without leakage
    return f"{val_str[:2]}****{val_str[-2:]}"

def sanitize_config_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep sanitizes a configuration dictionary, masking values of sensitive keys.
    Useful when logging or generating external reports.
    """
    if not isinstance(config, dict):
        return {}
    
    sanitized: Dict[str, Any] = {}
    for k, v in config.items():
        if is_sensitive_key(k):
            sanitized[k] = mask_secret_value(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_config_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_config_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized
