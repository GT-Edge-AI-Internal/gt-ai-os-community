"""
Team and Organization Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for team entities using the PostgreSQL + PGVector backend.
Implements team-based collaboration with file-based isolation.
Follows GT 2.0's principle of "Elegant Simplicity Through Intelligent Architecture"
- File-based team configurations with PostgreSQL reference tracking
- Perfect tenant isolation - each tenant has separate team data
- Zero complexity addition through simple file structures
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
import os
import json

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


def generate_uuid():
    """Generate a unique identifier"""
    return str(uuid.uuid4())


class TeamType(str, Enum):
    """Team type enumeration"""
    DEPARTMENT = "department"
    PROJECT = "project"
    CROSS_FUNCTIONAL = "cross_functional"


class RoleType(str, Enum):
    """Role type enumeration"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Team(BaseServiceModel):
    """
    Team model for GT 2.0 service-based architecture.
    
    GT 2.0 Design: Teams are lightweight DuckDB references to file-based configurations.
    Team data is stored in encrypted files, not complex database relationships.
    """
    
    # Team identifier
    team_uuid: str = Field(default_factory=generate_uuid, description="Unique team identifier")
    
    # Team details
    name: str = Field(..., min_length=1, max_length=200, description="Team name")
    description: Optional[str] = Field(None, max_length=1000, description="Team description")
    team_type: TeamType = Field(default=TeamType.PROJECT, description="Team type")
    
    # File-based configuration reference
    config_file_path: str = Field(..., description="Path to team config.json")
    members_file_path: str = Field(..., description="Path to members.json")
    
    # Owner and access
    created_by: str = Field(..., description="User who created this team")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Team settings
    is_active: bool = Field(default=True, description="Whether team is active")
    is_public: bool = Field(default=False, description="Whether team is publicly visible")
    max_members: int = Field(default=50, ge=1, le=1000, description="Maximum team members")
    
    # Statistics
    member_count: int = Field(default=0, description="Current member count")
    resource_count: int = Field(default=0, description="Number of shared resources")
    
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
        return "teams"
    
    def get_config_path(self) -> str:
        """Get the full path to team configuration file"""
        return self.config_file_path
    
    def get_members_path(self) -> str:
        """Get the full path to team members file"""
        return self.members_file_path
    
    def activate(self) -> None:
        """Activate the team"""
        self.is_active = True
        self.update_timestamp()
    
    def deactivate(self) -> None:
        """Deactivate the team"""
        self.is_active = False
        self.update_timestamp()


class TeamRole(BaseServiceModel):
    """
    Team role model for user permissions within teams.
    
    Manages role-based access control for team resources.
    """
    
    # Core role properties
    team_id: str = Field(..., description="Team ID")
    user_id: str = Field(..., description="User ID")
    role_type: RoleType = Field(..., description="Role type")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Role configuration
    permissions: Dict[str, bool] = Field(default_factory=dict, description="Role permissions")
    custom_permissions: Dict[str, Any] = Field(default_factory=dict, description="Custom permissions")
    
    # Role details
    assigned_by: str = Field(..., description="User who assigned this role")
    role_description: Optional[str] = Field(None, max_length=500, description="Role description")
    
    # Status
    is_active: bool = Field(default=True, description="Whether role is active")
    expires_at: Optional[datetime] = Field(None, description="Role expiration time")
    
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
        return "team_roles"
    
    def is_expired(self) -> bool:
        """Check if role is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def has_permission(self, permission: str) -> bool:
        """Check if role has specific permission"""
        return self.permissions.get(permission, False)
    
    def grant_permission(self, permission: str) -> None:
        """Grant a permission to this role"""
        self.permissions[permission] = True
        self.update_timestamp()
    
    def revoke_permission(self, permission: str) -> None:
        """Revoke a permission from this role"""
        self.permissions[permission] = False
        self.update_timestamp()


class OrganizationSettings(BaseServiceModel):
    """
    Organization settings model for tenant-wide configuration.
    
    Manages organization-level settings and policies.
    """
    
    # Organization details
    tenant_id: str = Field(..., description="Tenant domain identifier")
    organization_name: str = Field(..., min_length=1, max_length=200, description="Organization name")
    organization_domain: str = Field(..., description="Organization domain")
    
    # Organization settings
    settings: Dict[str, Any] = Field(default_factory=dict, description="Organization settings")
    branding: Dict[str, Any] = Field(default_factory=dict, description="Branding configuration")
    
    # Team policies
    default_team_settings: Dict[str, Any] = Field(default_factory=dict, description="Default team settings")
    team_creation_policy: str = Field(default="admin_only", description="Who can create teams")
    max_teams_per_user: int = Field(default=10, ge=1, le=100, description="Max teams per user")
    
    # Security policies
    security_settings: Dict[str, Any] = Field(default_factory=dict, description="Security settings")
    data_retention_days: int = Field(default=365, ge=30, le=2555, description="Data retention period")
    
    # Feature flags
    features_enabled: Dict[str, bool] = Field(default_factory=dict, description="Enabled features")
    
    # Contact and billing
    admin_email: Optional[str] = Field(None, description="Primary admin email")
    billing_contact: Optional[str] = Field(None, description="Billing contact email")
    
    # Status
    is_active: bool = Field(default=True, description="Whether organization is active")
    
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
        return "organization_settings"
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled"""
        return self.features_enabled.get(feature, False)
    
    def enable_feature(self, feature: str) -> None:
        """Enable a feature"""
        self.features_enabled[feature] = True
        self.update_timestamp()
    
    def disable_feature(self, feature: str) -> None:
        """Disable a feature"""
        self.features_enabled[feature] = False
        self.update_timestamp()


# Create/Update/Response models

class TeamCreate(BaseCreateModel):
    """Model for creating new teams"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    team_type: TeamType = Field(default=TeamType.PROJECT)
    created_by: str
    tenant_id: str
    is_public: bool = Field(default=False)
    max_members: int = Field(default=50, ge=1, le=1000)


class TeamUpdate(BaseUpdateModel):
    """Model for updating teams"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    team_type: Optional[TeamType] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    max_members: Optional[int] = Field(None, ge=1, le=1000)


class TeamResponse(BaseResponseModel):
    """Model for team API responses"""
    id: str
    team_uuid: str
    name: str
    description: Optional[str]
    team_type: TeamType
    config_file_path: str
    members_file_path: str
    created_by: str
    tenant_id: str
    is_active: bool
    is_public: bool
    max_members: int
    member_count: int
    resource_count: int
    created_at: datetime
    updated_at: datetime


class TeamRoleCreate(BaseCreateModel):
    """Model for creating team roles"""
    team_id: str
    user_id: str
    role_type: RoleType
    tenant_id: str
    assigned_by: str
    permissions: Dict[str, bool] = Field(default_factory=dict)
    role_description: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None


class TeamRoleUpdate(BaseUpdateModel):
    """Model for updating team roles"""
    role_type: Optional[RoleType] = None
    permissions: Optional[Dict[str, bool]] = None
    custom_permissions: Optional[Dict[str, Any]] = None
    role_description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class TeamRoleResponse(BaseResponseModel):
    """Model for team role API responses"""
    id: str
    team_id: str
    user_id: str
    role_type: RoleType
    tenant_id: str
    permissions: Dict[str, bool]
    custom_permissions: Dict[str, Any]
    assigned_by: str
    role_description: Optional[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime