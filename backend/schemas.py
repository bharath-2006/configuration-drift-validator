"""
schemas.py - Pydantic Schemas for Configuration Drift Validator
Defines strict models for requests, responses, drift reporting, and validations.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum

class SeverityEnum(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DeploymentStatusEnum(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"

class ChangeStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

# --- Environment & Configuration Items ---

class EnvVarItem(BaseModel):
    key: str
    value: Any
    data_type: Optional[str] = "string"

class InfrastructureItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    service: str = Field(default="app-service", alias="service_name")
    replicas: int = 1
    memory: str = "512Mi"
    cpu: str = "500m"
    port: int = 8080
    health_check: bool = True

class SecretMetadataItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    environment: str
    exists: bool = Field(default=True, alias="is_present")
    source: str = "secret-manager"
    last_rotated: Optional[str] = None
    age_days: int = 0

# --- Config Bundle for Ingestion & Export ---

class EnvironmentConfigBundle(BaseModel):
    environment: str
    version: int = 1
    description: Optional[str] = "Configuration snapshot"
    variables: Dict[str, Any] = {}
    infrastructure: Dict[str, Any] = {}
    secrets: List[SecretMetadataItem] = []
    created_at: Optional[str] = None

class ConfigUploadRequest(BaseModel):
    environment: str
    raw_env_content: Optional[str] = None
    raw_infra_content: Optional[str] = None
    raw_secrets_content: Optional[str] = None
    artifact_content: Optional[str] = None
    artifact_type: Optional[str] = None
    description: Optional[str] = "Manual update via dashboard"
    author: Optional[str] = "developer"

class ArtifactParseRequest(BaseModel):
    content: str
    artifact_type: Optional[str] = "auto"
    filename: Optional[str] = None
    environment: Optional[str] = "production"

class ArtifactParseResponse(BaseModel):
    status: str
    artifact_type: str
    environment: str
    parsed_variables: Dict[str, Any]
    detected_infrastructure: Dict[str, Any]
    total_keys: int
    is_schema_valid: bool
    schema_errors: List[str] = []
    message: str

# --- Runtime Snapshots ---

class RuntimeSnapshotPayload(BaseModel):
    environment: str
    app_version: Optional[str] = "1.0.0"
    snapshot_data: Dict[str, Any]

# --- Drift Result & Summary ---

class DriftDiscrepancy(BaseModel):
    environment: str
    category: str  # 'env_var', 'infrastructure', 'secret', 'runtime'
    item_key: str
    expected_val: Optional[str]
    actual_val: Optional[str]
    severity: SeverityEnum
    reason: str
    recommendation: str

class ValidationSummary(BaseModel):
    validation_run_id: str
    timestamp: str
    environment_status: Dict[str, str] # e.g. {"development": "Healthy", "staging": "Warning", "production": "Critical"}
    total_discrepancies: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    production_deployment_allowed: bool
    deployment_message: str
    discrepancies: List[DriftDiscrepancy]

# --- Change Requests & Approvals ---

class ChangeRequestCreate(BaseModel):
    environment: str
    title: str
    description: Optional[str] = ""
    proposed_changes_json: str
    requested_by: str = "developer"

class ChangeRequestReview(BaseModel):
    status: ChangeStatusEnum
    reviewed_by: str = "tech-lead"
    review_notes: Optional[str] = ""

class ChangeRequestResponse(BaseModel):
    id: int
    environment: str
    title: str
    description: Optional[str]
    proposed_changes_json: str
    risk_level: str
    status: str
    requested_by: str
    reviewed_by: Optional[str]
    review_notes: Optional[str]
    created_at: str
    reviewed_at: Optional[str]

# --- Rollback ---

class RollbackRequest(BaseModel):
    environment: str
    target_version: int
    reason: str
    performed_by: str = "devops-admin"

class RollbackRecord(BaseModel):
    id: int
    environment: str
    from_version: int
    to_version: int
    reason: str
    performed_by: str
    timestamp: str

# --- Audit Logs ---

class AuditLogEntry(BaseModel):
    id: Optional[int] = None
    timestamp: Optional[str] = None
    user: str
    action: str
    environment: str
    details: str
    risk_level: str = "INFO"

# --- Phase 2 Schemas ---

class GitCommitSimulateRequest(BaseModel):
    author: str = "developer"
    message: str = "Update configuration"
    environment: str = "production"
    changed_configs: Dict[str, Any]
    changed_files: Optional[List[str]] = None

class PreDeploymentCheckRequest(BaseModel):
    environment: str = "production"

class MonitoringScanRequest(BaseModel):
    environment: str = "production"

class NotificationItem(BaseModel):
    id: int
    title: str
    message: str
    severity: str
    category: str
    environment: Optional[str]
    is_read: bool
    created_at: str

