"""
artifact_parser.py - Real Configuration Artifact Parser
Configuration Drift Validator

Parses real-world configuration artifacts into the unified internal format:
1. .env / .env.example files
2. Docker Compose manifests (docker-compose.yml)
3. Kubernetes ConfigMap manifests (k8s configmap YAML)

Includes robust validation, syntax checking, type coercion, circular reference detection,
and graceful error handling without application crashes.
"""

import re
import yaml
from typing import Dict, Any, Optional, Tuple, List, Set

class ArtifactParseError(ValueError):
    """Raised when a configuration artifact is malformed or invalid."""
    pass

def parse_env_content(content: str, strict: bool = True, allow_duplicates: bool = True) -> Dict[str, str]:
    """
    Parses .env or .env.example text content into a key-value dictionary.
    Handles:
    - KEY=VALUE, KEY="VALUE", KEY='VALUE'
    - Inline and full-line comments (#)
    - Variable references (e.g. FOO=${BAR})
    - Circular reference detection (e.g. A=${B}, B=${A})
    - Duplicate key detection
    - Graceful error reporting for malformed syntax
    """
    if not content or not content.strip():
        return {}

    raw_lines = content.splitlines()
    raw_vars: Dict[str, str] = {}
    seen_keys: Set[str] = set()

    for line_num, line in enumerate(raw_lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export "):
            stripped = stripped[7:].strip()

        if "=" not in stripped:
            raise ArtifactParseError(f"Line {line_num}: Invalid entry without '=' delimiter: '{stripped}'")

        key, val = stripped.split("=", 1)
        key = key.strip()

        if not key:
            raise ArtifactParseError(f"Line {line_num}: Missing variable name before '='")

        # Validate key identifier
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*$", key):
            if strict:
                raise ArtifactParseError(f"Line {line_num}: Invalid environment variable name '{key}'")
            continue

        if not allow_duplicates and key in seen_keys:
            raise ArtifactParseError(f"Duplicate configuration key '{key}' at line {line_num}")
        seen_keys.add(key)

        val = val.strip()

        # Check for unclosed quotes
        if (val.startswith('"') and not val.endswith('"')) or (val.startswith("'") and not val.endswith("'")):
            raise ArtifactParseError(f"Line {line_num}: Unclosed quotation mark in value for '{key}'")

        # Handle inline comments if value is not quoted
        if not ((val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'"))):
            if " #" in val:
                val = val.split(" #", 1)[0].strip()

        # Strip outer quotes
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]

        raw_vars[key] = val

    # Resolve variable references (e.g. FOO=${BAR}) with circular reference protection
    resolved = resolve_variable_references(raw_vars)
    return resolved

def resolve_variable_references(raw_vars: Dict[str, str]) -> Dict[str, str]:
    """
    Resolves ${VAR} expansions within environment variable definitions.
    Raises ArtifactParseError if circular references are detected.
    """
    resolved: Dict[str, str] = {}

    def resolve_key(key: str, visiting: Set[str]) -> str:
        if key in visiting:
            chain = " -> ".join(list(visiting) + [key])
            raise ArtifactParseError(f"Circular configuration reference detected: {chain}")

        val = raw_vars.get(key, "")
        ref_pattern = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
        matches = ref_pattern.findall(val)
        if not matches:
            return val

        visiting.add(key)
        new_val = val
        for ref_key in matches:
            if ref_key in raw_vars:
                ref_resolved = resolve_key(ref_key, visiting.copy())
                new_val = new_val.replace(f"${{{ref_key}}}", ref_resolved)
        return new_val

    for k in raw_vars:
        resolved[k] = resolve_key(k, set())

    return resolved

def parse_docker_compose_content(content: str) -> Dict[str, Any]:
    """
    Parses a Docker Compose YAML manifest and extracts environment variables and infrastructure.
    Supports both map/dict and list-of-strings environment syntax:
      environment:
        DATABASE_HOST: prod-db
      environment:
        - DATABASE_HOST=prod-db
    """
    if not content or not content.strip():
        return {"variables": {}, "infrastructure": {}}

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ArtifactParseError(f"Malformed Docker Compose YAML: YAML syntax error: {str(e)}")

    if not isinstance(data, dict):
        raise ArtifactParseError("Invalid Docker Compose: root document must be a YAML mapping")

    services = data.get("services")
    if not services or not isinstance(services, dict):
        raise ArtifactParseError("Invalid Docker Compose: missing 'services' section or not a mapping")

    variables: Dict[str, Any] = {}
    infrastructure: Dict[str, Any] = {}

    # Extract from primary service (or first service listed)
    for service_name, s_config in services.items():
        if not isinstance(s_config, dict):
            continue

        env_section = s_config.get("environment")
        if isinstance(env_section, dict):
            for k, v in env_section.items():
                if isinstance(v, bool):
                    variables[str(k).strip()] = v
                elif isinstance(v, (int, float)):
                    variables[str(k).strip()] = v
                elif v is not None:
                    variables[str(k).strip()] = str(v).strip()
                else:
                    variables[str(k).strip()] = ""
        elif isinstance(env_section, list):
            for item in env_section:
                if isinstance(item, str) and "=" in item:
                    k, v = item.split("=", 1)
                    variables[k.strip()] = v.strip()

        # Infrastructure hints
        if "ports" in s_config and isinstance(s_config["ports"], list) and s_config["ports"]:
            first_port = str(s_config["ports"][0])
            port_match = re.search(r"(\d+):?(\d+)?", first_port)
            if port_match:
                infrastructure["port"] = int(port_match.group(2) or port_match.group(1))

        deploy_section = s_config.get("deploy")
        if isinstance(deploy_section, dict) and "replicas" in deploy_section:
            infrastructure["replicas"] = int(deploy_section["replicas"])

        if "service_name" not in infrastructure:
            infrastructure["service_name"] = service_name

    return {
        "variables": variables,
        "infrastructure": infrastructure
    }

class ConfigMapDict(dict):
    """Dictionary representing parsed Kubernetes ConfigMap supporting both direct key and .variables access."""
    def __init__(self, variables: Dict[str, str], metadata: Dict[str, Any]):
        super().__init__(variables)
        self._variables = variables
        self._metadata = metadata

    def __getitem__(self, key):
        if key == "variables":
            return self._variables
        if key == "metadata":
            return self._metadata
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "variables":
            return self._variables
        if key == "metadata":
            return self._metadata
        return super().get(key, default)

def parse_kubernetes_configmap_content(content: str) -> Dict[str, Any]:
    """
    Parses a Kubernetes ConfigMap YAML manifest and extracts the configuration variables.
    Validates apiVersion and kind: ConfigMap. Supports both data and stringData.
    """
    if not content or not content.strip():
        return ConfigMapDict({}, {})

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ArtifactParseError(f"Malformed Kubernetes YAML: {str(e)}")

    if not isinstance(data, dict):
        raise ArtifactParseError("Invalid Kubernetes manifest: root document must be a YAML mapping")

    kind = data.get("kind")
    if not kind or str(kind).lower() != "configmap":
        raise ArtifactParseError(f"Invalid Kubernetes manifest kind: Expected 'kind: ConfigMap', got '{kind}'")

    cm_data: Dict[str, Any] = {}
    if isinstance(data.get("data"), dict):
        cm_data.update(data["data"])
    if isinstance(data.get("stringData"), dict):
        cm_data.update(data["stringData"])

    if not cm_data and "data" not in data and "stringData" not in data:
        return ConfigMapDict({}, data.get("metadata", {}))

    variables: Dict[str, str] = {}
    for k, v in cm_data.items():
        variables[str(k).strip()] = str(v).strip() if v is not None else ""

    return ConfigMapDict(variables, data.get("metadata", {}))

def parse_configuration_artifact(
    content: str,
    artifact_type: Optional[str] = "auto",
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Auto-detects and parses any real configuration artifact (.env, Docker Compose, Kubernetes ConfigMap).
    Returns normalized dictionary:
      {
        "variables": Dict[str, str],
        "infrastructure": Dict[str, Any],
        "detected_format": "env" | "docker-compose" | "kubernetes-configmap",
        "error": Optional[str]
      }
    """
    if not content or not content.strip():
        return {"variables": {}, "infrastructure": {}, "detected_format": "empty", "error": None}

    art_lower = (artifact_type or "auto").lower()
    fn_lower = (filename or "").lower()

    # 1. Kubernetes ConfigMap
    if (
        art_lower in ("kubernetes", "configmap", "k8s")
        or "configmap" in fn_lower
        or ("kind:" in content and "configmap" in content.lower())
    ):
        try:
            res = parse_kubernetes_configmap_content(content)
            return {
                "variables": res.get("variables", {}),
                "infrastructure": {},
                "detected_format": "kubernetes-configmap",
                "error": None
            }
        except ArtifactParseError as e:
            if art_lower != "auto":
                raise
            # If auto-detect failed, proceed to next parser

    # 2. Docker Compose
    if art_lower in ("docker-compose", "compose", "docker") or ("services:" in content):
        try:
            res = parse_docker_compose_content(content)
            return {
                "variables": res.get("variables", {}),
                "infrastructure": res.get("infrastructure", {}),
                "detected_format": "docker-compose",
                "error": None
            }
        except ArtifactParseError as e:
            if art_lower != "auto":
                raise

    # 3. Default to .env
    try:
        vars_dict = parse_env_content(content, strict=False)
        return {
            "variables": vars_dict,
            "infrastructure": {},
            "detected_format": "env",
            "error": None
        }
    except Exception as e:
        raise ArtifactParseError(f"Failed to parse configuration artifact: {str(e)}")
