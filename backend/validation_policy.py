"""
validation_policy.py - Environment-Aware Validation Rules & Policies
Distinguishes expected environment-specific differences from dangerous configuration drift.
Defines allowed values, critical forbidden patterns, and required constraints.
"""

from typing import Dict, Any, List, Optional
from backend.normalizer import extract_host_from_url_or_endpoint, normalize_value

# Explicit allowed or expected values per environment
ENVIRONMENT_POLICIES = {
    "development": {
        "APP_ENV": ["development", "dev", "local"],
        "DEBUG": [True, False],  # Debug is allowed in dev
        "DATABASE_HOST_PATTERNS": ["dev-db", "localhost", "127.0.0.1", "dev"],
        "ALLOWED_API_DOMAINS": ["dev-api", "localhost", "127.0.0.1"],
        "ALLOWED_LOG_LEVELS": ["DEBUG", "INFO", "TRACE", "WARN"],
        "MIN_REPLICAS": 1,
        "REQUIRE_HEALTH_CHECK": False,
    },
    "staging": {
        "APP_ENV": ["staging", "stage"],
        "DEBUG": [True, False],  # Allowed for integration testing
        "DATABASE_HOST_PATTERNS": ["staging-db", "stage-db", "stage"],
        "ALLOWED_API_DOMAINS": ["staging-api", "stage-api"],
        "ALLOWED_LOG_LEVELS": ["DEBUG", "INFO", "WARN"],
        "MIN_REPLICAS": 1,
        "REQUIRE_HEALTH_CHECK": True,
    },
    "production": {
        "APP_ENV": ["production", "prod"],
        "DEBUG": [False],  # STRICTLY FALSE
        "DATABASE_HOST_PATTERNS": ["prod-db", "production-db", "prod-cluster"],
        "ALLOWED_API_DOMAINS": ["api", "prod-api", "api.company.com"],
        "ALLOWED_LOG_LEVELS": ["INFO", "WARN", "ERROR"],
        "MIN_REPLICAS": 2,
        "REQUIRE_HEALTH_CHECK": True,
    }
}

# Dangerous cross-environment pollution indicators for Production
FORBIDDEN_PROD_INDICATORS = [
    "dev-db", "localhost", "127.0.0.1", "dev-api", "staging-db", "staging-api", "test-db", "sandbox"
]

REQUIRED_ENV_VARS = [
    "APP_ENV",
    "DEBUG",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "API_URL",
    "LOG_LEVEL"
]

REQUIRED_SECRETS = [
    "DATABASE_PASSWORD",
    "API_SECRET_KEY",
    "PAYMENT_GATEWAY_TOKEN"
]

def is_expected_difference(key: str, env1: str, env2: str, val1: Any, val2: Any) -> bool:
    """
    Returns True if the difference between env1 and env2 is an expected, legitimate environment variance.
    For instance, DATABASE_HOST is dev-db in development and prod-db in production.
    """
    key_upper = key.upper()

    # Environment name identifier is naturally different
    if key_upper == "APP_ENV":
        return True

    # Expected hostnames across dev, staging, prod
    if key_upper == "DATABASE_HOST":
        str1 = str(val1).lower()
        str2 = str(val2).lower()
        valid_patterns = ["dev", "localhost", "stage", "staging", "prod", "production"]
        if any(p in str1 for p in valid_patterns) and any(p in str2 for p in valid_patterns):
            # As long as production itself doesn't contain dev/staging (which is checked separately as CRITICAL)
            if not ("production" in (env1, env2) and any(bad in (str1 if env1 == "production" else str2) for bad in ["dev", "localhost", "stage", "staging"])):
                return True

    # Expected API URLs
    if key_upper == "API_URL":
        if ("dev" in str(val1).lower() or "staging" in str(val1).lower()) and ("api" in str(val2).lower()):
            return True

    # Expected Debug flag differences
    if key_upper == "DEBUG":
        norm1, _ = normalize_value(val1)
        norm2, _ = normalize_value(val2)
        if norm1 is True and norm2 is False:
            return True

    # Expected Replicas differences (dev=1, prod=3)
    if key.lower() == "replicas":
        return True

    # Expected Memory & CPU scaling
    if key.lower() in ("memory", "cpu"):
        return True

    return False
