"""
Audit log database model
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    """System audit log for tracking all administrative actions"""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    ip_address = Column(String(45), nullable=True)  # IPv4: 15 chars, IPv6: 45 chars
    user_agent = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    tenant = relationship("Tenant", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_log(
        cls,
        action: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> "AuditLog":
        """Create a new audit log entry"""
        return cls(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )


# Common audit actions
class AuditActions:
    """Standard audit action constants"""
    
    # Authentication
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login_failed"
    
    # User management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ACTIVATE = "user.activate"
    USER_DEACTIVATE = "user.deactivate"
    
    # Tenant management
    TENANT_CREATE = "tenant.create"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE = "tenant.delete"
    TENANT_DEPLOY = "tenant.deploy"
    TENANT_SUSPEND = "tenant.suspend"
    TENANT_ACTIVATE = "tenant.activate"
    
    # Resource management
    RESOURCE_CREATE = "resource.create"
    RESOURCE_UPDATE = "resource.update"
    RESOURCE_DELETE = "resource.delete"
    RESOURCE_ASSIGN = "resource.assign"
    RESOURCE_UNASSIGN = "resource.unassign"
    
    # System actions
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    SYSTEM_CONFIG_UPDATE = "system.config_update"
    
    # Security events
    SECURITY_POLICY_UPDATE = "security.policy_update"
    SECURITY_BREACH_DETECTED = "security.breach_detected"
    SECURITY_ACCESS_DENIED = "security.access_denied"