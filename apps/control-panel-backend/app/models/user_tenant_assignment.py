"""
User-Tenant Assignment Model for Multi-Tenant User Management

Manages the many-to-many relationship between users and tenants with
tenant-specific user details, roles, and capabilities.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class UserTenantAssignment(Base):
    """
    User-Tenant Assignment with tenant-specific user details and roles
    
    This model allows users to:
    - Belong to multiple tenants with different roles
    - Have tenant-specific display names and contact info
    - Have different capabilities per tenant
    - Track activity per tenant
    """
    
    __tablename__ = "user_tenant_assignments"
    
    # Composite primary key
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tenant-specific user profile
    tenant_user_role = Column(
        String(20), 
        nullable=False, 
        default="tenant_user"
    )  # super_admin, tenant_admin, tenant_user
    tenant_display_name = Column(String(100), nullable=True)  # Optional tenant-specific name
    tenant_email = Column(String(255), nullable=True, index=True)  # Optional tenant-specific email
    tenant_department = Column(String(100), nullable=True)  # Department within tenant
    tenant_title = Column(String(100), nullable=True)  # Job title within tenant
    
    # Tenant-specific authentication (optional)
    tenant_password_hash = Column(String(255), nullable=True)  # Tenant-specific password if required
    requires_2fa = Column(Boolean, nullable=False, default=False)
    last_password_change = Column(DateTime(timezone=True), nullable=True)
    
    # Tenant-specific permissions and limits
    tenant_capabilities = Column(JSON, nullable=False, default=list)  # Tenant-specific capabilities
    resource_limits = Column(
        JSON,
        nullable=False,
        default=lambda: {
            "max_conversations": 100,
            "max_datasets": 10,
            "max_agents": 20,
            "daily_api_calls": 1000
        }
    )
    
    # Status and activity tracking
    is_active = Column(Boolean, nullable=False, default=True)
    is_primary_tenant = Column(Boolean, nullable=False, default=False)  # User's main tenant
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_accessed = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Invitation tracking
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    invitation_accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="tenant_assignments")
    tenant = relationship("Tenant", back_populates="user_assignments")
    inviter = relationship("User", foreign_keys=[invited_by])
    
    # Unique constraint to prevent duplicate assignments
    __table_args__ = (
        UniqueConstraint('user_id', 'tenant_id', name='unique_user_tenant_assignment'),
    )
    
    def __repr__(self):
        return f"<UserTenantAssignment(user_id={self.user_id}, tenant_id={self.tenant_id}, role='{self.tenant_user_role}')>"
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert assignment to dictionary"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "tenant_user_role": self.tenant_user_role,
            "tenant_display_name": self.tenant_display_name,
            "tenant_email": self.tenant_email,
            "tenant_department": self.tenant_department,
            "tenant_title": self.tenant_title,
            "requires_2fa": self.requires_2fa,
            "tenant_capabilities": self.tenant_capabilities,
            "resource_limits": self.resource_limits,
            "is_active": self.is_active,
            "is_primary_tenant": self.is_primary_tenant,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "invitation_accepted_at": self.invitation_accepted_at.isoformat() if self.invitation_accepted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data["tenant_password_hash"] = self.tenant_password_hash
            data["last_password_change"] = self.last_password_change.isoformat() if self.last_password_change else None
        
        return data
    
    @property
    def is_tenant_admin(self) -> bool:
        """Check if user is tenant admin in this tenant"""
        return self.tenant_user_role in ["super_admin", "tenant_admin"]
    
    @property
    def is_super_admin(self) -> bool:
        """Check if user is super admin in this tenant"""
        return self.tenant_user_role == "super_admin"
    
    @property
    def effective_display_name(self) -> str:
        """Get effective display name (tenant-specific or fallback to user's name)"""
        if self.tenant_display_name:
            return self.tenant_display_name
        return self.user.full_name if self.user else "Unknown User"
    
    @property
    def effective_email(self) -> str:
        """Get effective email (tenant-specific or fallback to user's email)"""
        if self.tenant_email:
            return self.tenant_email
        return self.user.email if self.user else "unknown@example.com"
    
    def has_capability(self, resource: str, action: str) -> bool:
        """Check if user has specific capability in this tenant"""
        if not self.tenant_capabilities:
            return False
        
        for capability in self.tenant_capabilities:
            # Check resource match (support wildcards)
            resource_match = (
                capability.get("resource") == "*" or
                capability.get("resource") == resource or
                (capability.get("resource", "").endswith("*") and 
                 resource.startswith(capability.get("resource", "").rstrip("*")))
            )
            
            # Check action match
            actions = capability.get("actions", [])
            action_match = "*" in actions or action in actions
            
            if resource_match and action_match:
                # Check constraints if present
                constraints = capability.get("constraints", {})
                if constraints:
                    # Check validity period
                    valid_until = constraints.get("valid_until")
                    if valid_until:
                        from datetime import datetime
                        if datetime.fromisoformat(valid_until.replace('Z', '+00:00')) < datetime.now():
                            continue
                
                return True
        
        return False
    
    def update_last_access(self) -> None:
        """Update last accessed timestamp"""
        self.last_accessed = datetime.utcnow()
    
    def update_last_login(self) -> None:
        """Update last login timestamp"""
        self.last_login_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
    
    def get_resource_limit(self, resource_type: str, default: int = 0) -> int:
        """Get resource limit for specific resource type"""
        if not self.resource_limits:
            return default
        return self.resource_limits.get(resource_type, default)
    
    def can_create_resource(self, resource_type: str, current_count: int) -> bool:
        """Check if user can create another resource of given type"""
        limit = self.get_resource_limit(resource_type)
        return limit == 0 or current_count < limit  # 0 means unlimited
    
    def set_as_primary_tenant(self) -> None:
        """Mark this tenant as user's primary tenant"""
        # This should be called within a transaction to ensure only one primary per user
        self.is_primary_tenant = True
    
    def add_capability(self, resource: str, actions: List[str], constraints: Optional[Dict] = None) -> None:
        """Add a capability to this user-tenant assignment"""
        capability = {
            "resource": resource,
            "actions": actions
        }
        if constraints:
            capability["constraints"] = constraints
        
        if not self.tenant_capabilities:
            self.tenant_capabilities = []
        
        # Remove existing capability for same resource if exists
        self.tenant_capabilities = [
            cap for cap in self.tenant_capabilities 
            if cap.get("resource") != resource
        ]
        
        self.tenant_capabilities.append(capability)
    
    def remove_capability(self, resource: str) -> None:
        """Remove capability for specific resource"""
        if not self.tenant_capabilities:
            return
        
        self.tenant_capabilities = [
            cap for cap in self.tenant_capabilities 
            if cap.get("resource") != resource
        ]
    
    def get_tenant_context(self) -> Dict[str, Any]:
        """Get tenant context for JWT token"""
        return {
            "id": str(self.tenant_id),  # Ensure tenant ID is string for JWT consistency
            "domain": self.tenant.domain if self.tenant else "unknown",
            "name": self.tenant.name if self.tenant else "Unknown Tenant",
            "role": self.tenant_user_role,
            "display_name": self.effective_display_name,
            "email": self.effective_email,
            "department": self.tenant_department,
            "title": self.tenant_title,
            "capabilities": self.tenant_capabilities or [],
            "resource_limits": self.resource_limits or {},
            "is_primary": self.is_primary_tenant
        }