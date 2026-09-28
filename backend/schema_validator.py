"""
schema_validator.py - JSON Schema Validator Utility
Configuration Drift Validator

Validates configuration bundles, drift rules, and runtime snapshots
against explicit JSON schemas located in schemas/ before processing.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import jsonschema

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = BASE_DIR / "schemas"

class SchemaValidationError(ValueError):
    """Raised when an object fails JSON Schema validation."""
    pass

_CACHE: Dict[str, Dict[str, Any]] = {}

def load_schema(schema_name: str) -> Dict[str, Any]:
    """Loads a JSON schema file from the schemas/ directory."""
    if schema_name in _CACHE:
        return _CACHE[schema_name]

    filename = schema_name if schema_name.endswith(".schema.json") else f"{schema_name}.schema.json"
    schema_file = SCHEMAS_DIR / filename

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file '{filename}' does not exist in {SCHEMAS_DIR}")

    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)
        _CACHE[schema_name] = schema
        return schema

def validate_against_schema(data: Any, schema_name: str) -> Tuple[bool, list]:
    """
    Validates data against a named JSON schema.
    Returns (True, []) if valid, or (False, [error_message, ...]) if invalid.
    """
    try:
        schema = load_schema(schema_name)
        validator = jsonschema.Draft7Validator(schema)
        errors = []
        for err in validator.iter_errors(data):
            field = ".".join(str(p) for p in err.absolute_path) or "root"
            errors.append(f"Schema error at '{field}': {err.message}")
        if errors:
            return False, errors
        return True, []
    except Exception as e:
        return False, [str(e)]

def validate_environment_config(data: Dict[str, Any], environment: Optional[str] = None) -> Tuple[bool, list]:
    """Validates an environment configuration bundle against environment.schema.json."""
    if environment and "environment" not in data:
        data["environment"] = environment
    return validate_against_schema(data, "environment")

def validate_drift_rule(data: Dict[str, Any]) -> Tuple[bool, list]:
    """Validates a drift rule definition against drift-rule.schema.json."""
    return validate_against_schema(data, "drift-rule")

def validate_runtime_snapshot_data(data: Dict[str, Any]) -> Tuple[bool, list]:
    """Validates runtime container snapshot payload against runtime-snapshot.schema.json."""
    return validate_against_schema(data, "runtime-snapshot")
