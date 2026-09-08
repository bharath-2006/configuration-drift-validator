"""
test_validator.py - Unit tests for Configuration Ingestion, Normalization, and Schemas
"""

import pytest
from backend.normalizer import (
    normalize_value,
    values_are_equivalent,
    parse_env_file_content,
    parse_yaml_or_json,
    extract_host_from_url_or_endpoint
)

def test_normalize_boolean_values():
    """Verify boolean normalization across strings, ints, and casing."""
    assert normalize_value("true")[0] is True
    assert normalize_value("TRUE")[0] is True
    assert normalize_value("yes")[0] is True
    assert normalize_value("1")[0] is True
    assert normalize_value(True)[0] is True

    assert normalize_value("false")[0] is False
    assert normalize_value("FALSE")[0] is False
    assert normalize_value("no")[0] is False
    assert normalize_value("0")[0] is False
    assert normalize_value(False)[0] is False

def test_normalize_numeric_values():
    """Verify numbers as strings vs primitives."""
    assert normalize_value("5432")[0] == 5432
    assert normalize_value(5432)[0] == 5432
    assert normalize_value("8080")[0] == 8080
    assert values_are_equivalent("5432", 5432) is True
    assert values_are_equivalent("8080", 8080) is True

def test_normalize_whitespace_and_quotes():
    """Verify trimming and quote stripping."""
    assert normalize_value(' "dev-db" ')[0] == "dev-db"
    assert normalize_value(" 'staging-db' ")[0] == "staging-db"
    assert values_are_equivalent("  dev-db  ", "dev-db") is True

def test_parse_env_file_content():
    """Verify parsing raw .env string with comments and spaces."""
    content = """
    # This is a comment
    APP_ENV=production
    DEBUG=false

    DATABASE_HOST=prod-db
    PORT="8080"
    """
    parsed = parse_env_file_content(content)
    assert parsed["APP_ENV"] == "production"
    assert parsed["DEBUG"] == "false"
    assert parsed["DATABASE_HOST"] == "prod-db"
    assert parsed["PORT"] == "8080"

def test_extract_host_from_url():
    """Verify endpoint hostname extraction."""
    assert extract_host_from_url_or_endpoint("http://dev-db:5432") == "dev-db"
    assert extract_host_from_url_or_endpoint("postgres://user:pass@staging-db:5432/app") == "staging-db"
    assert extract_host_from_url_or_endpoint("prod-db") == "prod-db"
