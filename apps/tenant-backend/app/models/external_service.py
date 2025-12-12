"""
External Service Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for external service entities using the PostgreSQL + PGVector backend.
Manages external web services integration with SSO and iframe embedding.
Perfect tenant isolation - each tenant has separate external service data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


def generate_uuid():
    """Generate a unique identifier"""
    return str(uuid.uuid4())


class ServiceStatus(str, Enum):
    """Service status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"


class AccessLevel(str, Enum):
    """Access level enumeration"""
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ADMIN_ONLY = "admin_only"
    RESTRICTED = "restricted"


class ExternalServiceInstance(BaseServiceModel):
    """
    External service instance model for GT 2.0 service-based architecture.
    
    Represents external web services like Canvas LMS, Jupyter Hub, CTFd
    with SSO integration and iframe embedding.
    """
    
    # Core service properties
    service_name: str = Field(..., min_length=1, max_length=100, description="Service name")
    service_type: str = Field(..., min_length=1, max_length=50, description="Service type")
    service_url: str = Field(..., description="Service URL")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Service configuration
    config: Dict[str, Any] = Field(default_factory=dict, description="Service configuration")
    auth_config: Dict[str, Any] = Field(default_factory=dict, description="Authentication configuration")
    iframe_config: Dict[str, Any] = Field(default_factory=dict, description="Iframe embedding configuration")
    
    # Service details
    description: Optional[str] = Field(None, max_length=500, description="Service description")
    version: str = Field(default="1.0.0", max_length=50, description="Service version")
    provider: str = Field(..., max_length=100, description="Service provider")
    
    # Access control
    access_level: AccessLevel = Field(default=AccessLevel.AUTHENTICATED, description="Access level required")
    allowed_users: List[str] = Field(default_factory=list, description="Allowed user IDs")
    allowed_roles: List[str] = Field(default_factory=list, description="Allowed user roles")
    
    # Status and monitoring
    status: ServiceStatus = Field(default=ServiceStatus.ACTIVE, description="Service status")
    health_check_url: Optional[str] = Field(None, description="Health check endpoint")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    is_healthy: bool = Field(default=True, description="Health status")
    
    # Usage statistics
    total_access_count: int = Field(default=0, description="Total access count")
    active_user_count: int = Field(default=0, description="Current active users")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Service tags")
    category: str = Field(default="general", max_length=50, description="Service category")
    priority: int = Field(default=10, ge=1, le=100, description="Display priority")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "external_service_instances"
    
    def activate(self) -> None:
        """Activate the service"""
        self.status = ServiceStatus.ACTIVE
        self.update_timestamp()
    
    def deactivate(self) -> None:
        """Deactivate the service"""
        self.status = ServiceStatus.INACTIVE
        self.update_timestamp()
    
    def record_access(self, user_id: str) -> None:
        """Record service access"""
        self.total_access_count += 1
        self.last_accessed = datetime.utcnow()
        self.update_timestamp()
    
    def update_health_status(self, is_healthy: bool) -> None:
        """Update health status"""
        self.is_healthy = is_healthy
        self.last_health_check = datetime.utcnow()
        self.update_timestamp()


class ServiceAccessLog(BaseServiceModel):
    """
    Service access log model for tracking usage and security.
    
    Logs all access attempts to external services for auditing.
    """
    
    # Core access properties
    service_id: str = Field(..., description="External service instance ID")
    user_id: str = Field(..., description="User who accessed the service")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Access details
    access_type: str = Field(..., max_length=50, description="Type of access")
    ip_address: Optional[str] = Field(None, max_length=45, description="User IP address")
    user_agent: Optional[str] = Field(None, max_length=500, description="User agent string")
    
    # Session information
    session_id: Optional[str] = Field(None, description="User session ID")
    session_duration_seconds: Optional[int] = Field(None, description="Session duration")
    
    # Access result
    access_granted: bool = Field(default=True, description="Whether access was granted")
    denial_reason: Optional[str] = Field(None, description="Reason for access denial")
    
    # Additional metadata
    referrer_url: Optional[str] = Field(None, description="Referrer URL")
    access_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional access data")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "service_access_logs"


class ServiceTemplate(BaseServiceModel):
    """
    Service template model for reusable service configurations.
    
    Defines templates for common external service integrations.
    """
    
    # Core template properties
    template_name: str = Field(..., min_length=1, max_length=100, description="Template name")
    service_type: str = Field(..., min_length=1, max_length=50, description="Service type")
    template_description: str = Field(..., max_length=500, description="Template description")
    
    # Template configuration
    default_config: Dict[str, Any] = Field(default_factory=dict, description="Default service configuration")
    default_auth_config: Dict[str, Any] = Field(default_factory=dict, description="Default auth configuration")
    default_iframe_config: Dict[str, Any] = Field(default_factory=dict, description="Default iframe configuration")
    
    # Template metadata
    version: str = Field(default="1.0.0", max_length=50, description="Template version")
    provider: str = Field(..., max_length=100, description="Service provider")
    supported_versions: List[str] = Field(default_factory=list, description="Supported service versions")
    
    # Documentation
    setup_instructions: Optional[str] = Field(None, description="Setup instructions")
    configuration_schema: Dict[str, Any] = Field(default_factory=dict, description="Configuration schema")
    example_config: Dict[str, Any] = Field(default_factory=dict, description="Example configuration")
    
    # Template status
    is_active: bool = Field(default=True, description="Whether template is active")
    is_verified: bool = Field(default=False, description="Whether template is verified")
    usage_count: int = Field(default=0, description="Number of times used")
    
    # Access control
    is_public: bool = Field(default=True, description="Whether template is publicly available")
    created_by: str = Field(..., description="Creator of the template")
    tenant_id: Optional[str] = Field(None, description="Tenant ID if tenant-specific")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "service_templates"
    
    def increment_usage(self) -> None:
        """Increment usage count"""
        self.usage_count += 1
        self.update_timestamp()
    
    def verify_template(self) -> None:
        """Mark template as verified"""
        self.is_verified = True
        self.update_timestamp()


# Create/Update/Response models - minimal for now

class ExternalServiceInstanceCreate(BaseCreateModel):
    """Model for creating external service instances"""
    service_name: str = Field(..., min_length=1, max_length=100)
    service_type: str = Field(..., min_length=1, max_length=50)
    service_url: str
    tenant_id: str
    provider: str = Field(..., max_length=100)


class ExternalServiceInstanceUpdate(BaseUpdateModel):
    """Model for updating external service instances"""
    service_name: Optional[str] = Field(None, min_length=1, max_length=100)
    service_url: Optional[str] = None
    status: Optional[ServiceStatus] = None
    is_healthy: Optional[bool] = None


class ExternalServiceInstanceResponse(BaseResponseModel):
    """Model for external service instance API responses"""
    id: str
    service_name: str
    service_type: str
    service_url: str
    tenant_id: str
    provider: str
    status: ServiceStatus
    is_healthy: bool
    created_at: datetime
    updated_at: datetime