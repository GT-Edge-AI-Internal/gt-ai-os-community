"""
Message schemas for RabbitMQ cross-cluster communication
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class CommandType(str, Enum):
    """Types of admin commands"""
    # Tenant commands
    TENANT_PROVISION = "tenant_provision"
    TENANT_DEPLOY = "tenant_deploy"
    TENANT_SUSPEND = "tenant_suspend"
    TENANT_RESUME = "tenant_resume"
    TENANT_DELETE = "tenant_delete"
    TENANT_UPDATE_CONFIG = "tenant_update_config"
    
    # Resource commands
    RESOURCE_ASSIGN = "resource_assign"
    RESOURCE_UNASSIGN = "resource_unassign"
    RESOURCE_UPDATE = "resource_update"
    RESOURCE_HEALTH_CHECK = "resource_health_check"
    
    # User commands
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_SUSPEND = "user_suspend"
    USER_DELETE = "user_delete"
    
    # System commands
    SYSTEM_HEALTH_CHECK = "system_health_check"
    SYSTEM_UPDATE_CONFIG = "system_update_config"
    SYSTEM_BACKUP = "system_backup"
    SYSTEM_RESTORE = "system_restore"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of system alerts"""
    SECURITY = "security"
    HEALTH = "health"
    DEPLOYMENT = "deployment"
    RESOURCE = "resource"
    TENANT = "tenant"
    PERFORMANCE = "performance"


class TenantProvisionCommand(BaseModel):
    """Command to provision a new tenant"""
    tenant_id: int
    tenant_name: str
    domain: str
    template: str = "basic"
    namespace: str
    max_users: int = 100
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    initial_resources: List[int] = Field(default_factory=list)  # Resource IDs to assign
    admin_email: str
    admin_name: str
    configuration: Dict[str, Any] = Field(default_factory=dict)


class TenantDeployCommand(BaseModel):
    """Command to deploy tenant infrastructure"""
    tenant_id: int
    namespace: str
    deployment_config: Dict[str, Any] = Field(default_factory=dict)
    kubernetes_config: Dict[str, Any] = Field(default_factory=dict)
    storage_config: Dict[str, Any] = Field(default_factory=dict)
    network_config: Dict[str, Any] = Field(default_factory=dict)
    force_redeploy: bool = False


class ResourceAssignmentCommand(BaseModel):
    """Command to assign resources to tenant"""
    tenant_id: int
    namespace: str
    resource_ids: List[int]
    usage_limits: Dict[str, Any] = Field(default_factory=dict)
    custom_config: Dict[str, Any] = Field(default_factory=dict)
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class ResourceHealthCheckCommand(BaseModel):
    """Command to check resource health"""
    resource_ids: List[int]
    check_types: List[str] = Field(default=["connectivity", "performance", "availability"])
    timeout_seconds: int = 30
    detailed_diagnostics: bool = False


class DeploymentStatusUpdate(BaseModel):
    """Update on deployment status"""
    command_id: str
    tenant_id: int
    namespace: str
    status: str  # 'started', 'in_progress', 'completed', 'failed'
    progress_percentage: Optional[int] = None
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SystemAlert(BaseModel):
    """System alert message"""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    source: str  # Which cluster/component generated the alert
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    affected_tenants: List[str] = Field(default_factory=list)
    affected_resources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    auto_resolved: bool = False
    resolution_steps: List[str] = Field(default_factory=list)


class CommandResponse(BaseModel):
    """Response to admin command"""
    command_id: str
    command_type: str
    success: bool
    status_code: int = 200
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    execution_time_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UserProvisionCommand(BaseModel):
    """Command to provision a new user"""
    tenant_id: int
    namespace: str
    email: str
    full_name: str
    user_type: str = "tenant_user"
    capabilities: List[str] = Field(default_factory=list)
    access_groups: List[str] = Field(default_factory=list)
    initial_password: Optional[str] = None
    send_welcome_email: bool = True


class BackupCommand(BaseModel):
    """Command to initiate backup"""
    backup_id: str
    tenant_id: Optional[int] = None  # None for system-wide backup
    namespace: Optional[str] = None
    backup_type: str = "full"  # 'full', 'incremental', 'differential'
    include_databases: bool = True
    include_files: bool = True
    include_configurations: bool = True
    destination: str = "s3"  # 's3', 'local', 'nfs'
    retention_days: int = 30
    encryption_enabled: bool = True


class MetricsSnapshot(BaseModel):
    """System metrics snapshot"""
    tenant_id: Optional[int] = None
    namespace: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Resource metrics
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    network_in_mbps: float
    network_out_mbps: float
    
    # Application metrics
    active_users: int
    api_calls_per_minute: int
    average_response_time_ms: float
    error_rate_percent: float
    
    # AI/ML metrics
    tokens_consumed: int
    embeddings_generated: int
    documents_processed: int
    rag_queries_executed: int
    
    # Storage metrics
    database_size_gb: float
    vector_store_size_gb: float
    object_storage_size_gb: float
    
    details: Dict[str, Any] = Field(default_factory=dict)