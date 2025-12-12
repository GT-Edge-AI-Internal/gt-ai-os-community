"""
User database model
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class User(Base):
    """User model with capability-based authorization"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    user_type = Column(
        String(20),
        nullable=False,
        default="tenant_user"
    )  # super_admin, tenant_admin, tenant_user
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    current_tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # Current active tenant for multi-tenant users
    capabilities = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)  # For billing calculation
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Two-Factor Authentication fields
    tfa_enabled = Column(Boolean, nullable=False, default=False)
    tfa_secret = Column(Text, nullable=True)  # Encrypted TOTP secret
    tfa_required = Column(Boolean, nullable=False, default=False)  # Admin can enforce TFA

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant_assignments = relationship("UserTenantAssignment", foreign_keys="UserTenantAssignment.user_id", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    resource_data = relationship("UserResourceData", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreferences", back_populates="user", cascade="all, delete-orphan", uselist=False)
    progress = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", passive_deletes=True)  # Let DB CASCADE handle deletion

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', user_type='{self.user_type}')>"

    def to_dict(self, include_sensitive: bool = False, include_tenants: bool = False) -> Dict[str, Any]:
        """Convert user to dictionary"""
        data = {
            "id": self.id,
            "uuid": str(self.uuid),
            "email": self.email,
            "full_name": self.full_name,
            "user_type": self.user_type,
            "current_tenant_id": self.current_tenant_id,
            "capabilities": self.capabilities,
            "is_active": self.is_active,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # TFA fields (never include tfa_secret for security)
            "tfa_enabled": self.tfa_enabled,
            "tfa_required": self.tfa_required,
            "tfa_status": self.tfa_status
        }

        if include_tenants:
            data["tenant_assignments"] = [
                assignment.to_dict() for assignment in self.tenant_assignments
                if assignment.is_active and not assignment.deleted_at
            ]

        if include_sensitive:
            data["hashed_password"] = self.hashed_password

        return data

    @property
    def is_super_admin(self) -> bool:
        """Check if user is super admin"""
        return self.user_type == "super_admin"

    @property
    def is_tenant_admin(self) -> bool:
        """Check if user is tenant admin"""
        return self.user_type == "tenant_admin"

    @property
    def is_tenant_user(self) -> bool:
        """Check if user is regular tenant user"""
        return self.user_type == "tenant_user"

    @property
    def tfa_status(self) -> str:
        """Get TFA status: disabled, enabled, or enforced"""
        if self.tfa_required:
            return "enforced"
        elif self.tfa_enabled:
            return "enabled"
        else:
            return "disabled"

    def has_capability(self, resource: str, action: str) -> bool:
        """Check if user has specific capability"""
        if not self.capabilities:
            return False

        for capability in self.capabilities:
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

    def get_tenant_assignment(self, tenant_id: int) -> Optional['UserTenantAssignment']:
        """Get user's assignment for specific tenant"""
        from app.models.user_tenant_assignment import UserTenantAssignment
        for assignment in self.tenant_assignments:
            if assignment.tenant_id == tenant_id and assignment.is_active and not assignment.deleted_at:
                return assignment
        return None

    def get_current_tenant_assignment(self) -> Optional['UserTenantAssignment']:
        """Get user's current active tenant assignment"""
        if not self.current_tenant_id:
            return self.get_primary_tenant_assignment()
        return self.get_tenant_assignment(self.current_tenant_id)

    def get_primary_tenant_assignment(self) -> Optional['UserTenantAssignment']:
        """Get user's primary tenant assignment"""
        for assignment in self.tenant_assignments:
            if assignment.is_primary_tenant and assignment.is_active and not assignment.deleted_at:
                return assignment
        # Fallback to first active assignment
        active_assignments = [a for a in self.tenant_assignments if a.is_active and not a.deleted_at]
        return active_assignments[0] if active_assignments else None

    def get_available_tenants(self) -> List['UserTenantAssignment']:
        """Get all tenant assignments user has access to"""
        return [
            assignment for assignment in self.tenant_assignments
            if assignment.is_active and not assignment.deleted_at
        ]

    def has_tenant_access(self, tenant_id: int) -> bool:
        """Check if user has access to specific tenant"""
        return self.get_tenant_assignment(tenant_id) is not None

    def switch_to_tenant(self, tenant_id: int) -> bool:
        """Switch user's current tenant context"""
        if self.has_tenant_access(tenant_id):
            self.current_tenant_id = tenant_id
            return True
        return False

    def get_tenant_capabilities(self, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get capabilities for specific tenant or current tenant"""
        target_tenant_id = tenant_id or self.current_tenant_id
        if not target_tenant_id:
            return []

        assignment = self.get_tenant_assignment(target_tenant_id)
        if not assignment:
            return []

        return assignment.tenant_capabilities or []

    def has_tenant_capability(self, resource: str, action: str, tenant_id: Optional[int] = None) -> bool:
        """Check if user has specific capability in tenant"""
        target_tenant_id = tenant_id or self.current_tenant_id
        if not target_tenant_id:
            return False

        assignment = self.get_tenant_assignment(target_tenant_id)
        if not assignment:
            return False

        return assignment.has_capability(resource, action)

    def is_tenant_admin(self, tenant_id: Optional[int] = None) -> bool:
        """Check if user is admin in specific tenant"""
        target_tenant_id = tenant_id or self.current_tenant_id
        if not target_tenant_id:
            return False

        assignment = self.get_tenant_assignment(target_tenant_id)
        if not assignment:
            return False

        return assignment.is_tenant_admin

    def get_current_tenant_context(self) -> Optional[Dict[str, Any]]:
        """Get current tenant context for JWT token"""
        assignment = self.get_current_tenant_assignment()
        if not assignment:
            return None
        return assignment.get_tenant_context()