"""
normalizer.py - Input Normalization and Parsing Utilities
Ensures robust parsing of .env, YAML, JSON, and sanitizes adversarial inputs:
- Whitespace stripping
- Quote removal
- Boolean canonicalization ("true" == True == "True")
- Numeric string coercion ("5432" == 5432)
- Hostname extraction from connection URLs
"""

import re
import json
import yaml
from typing import Any, Dict, Tuple, Optional

def normalize_value(val: Any) -> Tuple[Any, str]:
    """
    Normalizes a configuration value into a canonical Python primitive and returns (canonical_val, type_name).
    Handles strings, booleans, integers, floats, None.
    """
    if val is None:
        return None, "null"

    if isinstance(val, bool):
        return val, "bool"

    if isinstance(val, (int, float)):
        return val, "number"

    if isinstance(val, str):
        cleaned = val.strip()
        # Strip outer single or double quotes if present
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()

        # Boolean conversion
        if cleaned.lower() in ("true", "yes", "1", "enabled"):
            return True, "bool"
        if cleaned.lower() in ("false", "no", "0", "disabled"):
            return False, "bool"

        # Integer conversion
        if re.match(r"^-?\d+$", cleaned):
            try:
                return int(cleaned), "int"
            except ValueError:
                pass

        # Float conversion
        if re.match(r"^-?\d+\.\d+$", cleaned):
            try:
                return float(cleaned), "float"
            except ValueError:
                pass

        return cleaned, "string"

    return val, type(val).__name__

def values_are_equivalent(val1: Any, val2: Any) -> bool:
    """
    Compares two values after canonical normalization.
    Returns True if semantically equal, False otherwise.
    E.g. "true" == True, "8080" == 8080, "  dev-db  " == "dev-db".
    """
    norm1, type1 = normalize_value(val1)
    norm2, type2 = normalize_value(val2)

    # If both are numbers (int vs float like 500 vs 500.0)
    if type1 in ("int", "number") and type2 in ("int", "number"):
        return float(norm1) == float(norm2)

    return norm1 == norm2

def parse_env_file_content(content: str) -> Dict[str, str]:
    """
    Parses raw .env text into a clean key-value dictionary.
    Ignores empty lines and comments starting with #.
    """
    result = {}
    if not content:
        return result

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Strip quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            result[key] = val
    return result

def parse_yaml_or_json(content: str) -> Dict[str, Any]:
    """
    Parses either YAML or JSON string into Python dict safely.
    """
    if not content or not content.strip():
        return {}
    try:
        # YAML parser handles both YAML and JSON natively
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception as e:
        raise ValueError(f"Failed to parse YAML/JSON: {str(e)}")

def extract_host_from_url_or_endpoint(endpoint: str) -> str:
    """
    Extracts host name if endpoint is a URL or connection string.
    E.g., "http://dev-db:5432" -> "dev-db", "postgresql://user:pass@staging-db/db" -> "staging-db".
    """
    if not isinstance(endpoint, str):
        return ""
    clean = endpoint.strip()
    match = re.search(r"://(?:[^:@]+:[^:@]+@)?([^:/]+)", clean)
    if match:
        return match.group(1).lower()
    # Otherwise return raw stripped string
    return clean.split(":")[0].strip().lower()
