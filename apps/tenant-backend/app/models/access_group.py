"""
Access Group Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for access group entities using the PostgreSQL + PGVector backend.
Implements simplified Tenant → User hierarchy with access groups for resource sharing.
NO TEAM ENTITIES - using access groups instead for collaboration.
Perfect tenant isolation - each tenant has separate access data.
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


class AccessGroup(str, Enum):
    """Resource access levels within a tenant"""
    INDIVIDUAL = "individual"      # Private to owner
    TEAM = "team"                  # Shared with specific users  
    ORGANIZATION = "organization"   # Read-only for all tenant users


class TenantStructure(BaseServiceModel):
    """
    Simplified hierarchy model for GT 2.0 service-based architecture.
    
    Direct tenant-to-user relationship with access groups for sharing.
    NO TEAM ENTITIES - using access groups instead for collaboration.
    """
    
    # Core tenant properties
    tenant_domain: str = Field(..., description="Tenant domain (e.g., customer1.com)")
    tenant_id: str = Field(..., description="Unique tenant identifier")
    
    # Tenant settings
    settings: Dict[str, Any] = Field(default_factory=dict, description="Tenant-wide settings")
    
    # Statistics
    user_count: int = Field(default=0, description="Number of users")
    resource_count: int = Field(default=0, description="Number of resources")
    
    # Status
    is_active: bool = Field(default=True, description="Whether tenant is active")
    
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
        return "tenant_structures"
    
    def activate(self) -> None:
        """Activate the tenant"""
        self.is_active = True
        self.update_timestamp()
    
    def deactivate(self) -> None:
        """Deactivate the tenant"""
        self.is_active = False
        self.update_timestamp()


class User(BaseServiceModel):
    """
    User model for GT 2.0 service-based architecture.
    
    User within a tenant with role-based permissions.
    """
    
    # Core user properties
    user_id: str = Field(default_factory=generate_uuid, description="Unique user identifier")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    role: str = Field(..., description="User role (admin, developer, analyst, student)")
    tenant_domain: str = Field(..., description="Parent tenant domain")
    
    # User status
    is_active: bool = Field(default=True, description="Whether user is active")
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")
    
    # User settings
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    
    # Statistics
    owned_resources_count: int = Field(default=0, description="Number of owned resources")
    team_resources_count: int = Field(default=0, description="Number of team resources accessible")
    
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
        return "users"
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_active = datetime.utcnow()
        self.update_timestamp()
    
    def can_access_resource(self, resource_access_group: AccessGroup, resource_owner_id: str, 
                           resource_team_members: List[str]) -> bool:
        """Check if user can access a resource"""
        # Owner always has access
        if resource_owner_id == self.user_id:
            return True
        
        # Organization-wide resources
        if resource_access_group == AccessGroup.ORGANIZATION:
            return True
        
        # Team resources
        if resource_access_group == AccessGroup.TEAM:
            return self.user_id in resource_team_members
        
        return False
    
    def can_modify_resource(self, resource_owner_id: str) -> bool:
        """Check if user can modify a resource"""
        # Only owner can modify
        return resource_owner_id == self.user_id


class Resource(BaseServiceModel):
    """
    Base resource model for GT 2.0 service-based architecture.
    
    Base class for any resource (agent, dataset, automation, etc.)
    with file-based storage and access control.
    """
    
    # Core resource properties
    resource_uuid: str = Field(default_factory=generate_uuid, description="Unique resource identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Resource name")
    resource_type: str = Field(..., max_length=50, description="Type of resource")
    owner_id: str = Field(..., description="Owner user ID")
    tenant_domain: str = Field(..., description="Parent tenant domain")
    
    # Access control
    access_group: AccessGroup = Field(default=AccessGroup.INDIVIDUAL, description="Access level")
    team_members: List[str] = Field(default_factory=list, description="Team member IDs for team access")
    
    # File storage
    file_path: Optional[str] = Field(None, description="File-based storage path")
    file_permissions: str = Field(default="700", description="Unix file permissions")
    
    # Resource metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Resource-specific metadata")
    description: Optional[str] = Field(None, max_length=1000, description="Resource description")
    
    # Statistics
    access_count: int = Field(default=0, description="Number of times accessed")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    
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
        return "resources"
    
    def update_access_group(self, new_group: AccessGroup, team_members: Optional[List[str]] = None) -> None:
        """Update resource access group"""
        self.access_group = new_group
        self.team_members = team_members if new_group == AccessGroup.TEAM else []
        self.update_timestamp()
    
    def add_team_member(self, user_id: str) -> None:
        """Add user to team access"""
        if self.access_group == AccessGroup.TEAM and user_id not in self.team_members:
            self.team_members.append(user_id)
            self.update_timestamp()
    
    def remove_team_member(self, user_id: str) -> None:
        """Remove user from team access"""
        if user_id in self.team_members:
            self.team_members.remove(user_id)
            self.update_timestamp()
    
    def record_access(self, user_id: str) -> None:
        """Record resource access"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        self.update_timestamp()
    
    def get_file_permissions(self) -> str:
        """
        Get Unix file permissions based on access group.
        All files created with 700 permissions (owner only).
        OS User: gt-{tenant_domain}-{pod_id}
        """
        return "700"  # Owner read/write/execute only


# Create/Update/Response models

class AccessGroupModel(BaseCreateModel):
    """API model for access group configuration"""
    access_group: AccessGroup = Field(..., description="Access level")
    team_members: List[str] = Field(default_factory=list, description="Team member IDs if team access")


class ResourceCreate(BaseCreateModel):
    """Model for creating resources"""
    name: str = Field(..., min_length=1, max_length=200)
    resource_type: str = Field(..., max_length=50)
    owner_id: str
    tenant_domain: str
    access_group: AccessGroup = Field(default=AccessGroup.INDIVIDUAL)
    team_members: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = Field(None, max_length=1000)


class ResourceUpdate(BaseUpdateModel):
    """Model for updating resources"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    access_group: Optional[AccessGroup] = None
    team_members: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    description: Optional[str] = Field(None, max_length=1000)


class ResourceResponse(BaseResponseModel):
    """Model for resource API responses"""
    id: str
    resource_uuid: str
    name: str
    resource_type: str
    owner_id: str
    tenant_domain: str
    access_group: AccessGroup
    team_members: List[str]
    file_path: Optional[str]
    metadata: Dict[str, Any]
    description: Optional[str]
    access_count: int
    last_accessed: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseCreateModel):
    """Model for creating users"""
    email: str
    full_name: str
    role: str
    tenant_domain: str
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserUpdate(BaseUpdateModel):
    """Model for updating users"""
    full_name: Optional[str] = None
    role: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserResponse(BaseResponseModel):
    """Model for user API responses"""
    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    tenant_domain: str
    is_active: bool
    last_active: Optional[datetime]
    preferences: Dict[str, Any]
    owned_resources_count: int
    team_resources_count: int
    created_at: datetime
    updated_at: datetime