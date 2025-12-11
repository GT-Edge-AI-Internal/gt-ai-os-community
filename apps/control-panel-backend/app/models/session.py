"""
Session database model for server-side session tracking.

OWASP/NIST Compliant Session Management (Issue #264):
- Server-side session state is authoritative
- Tracks idle timeout (30 min) and absolute timeout (8 hours)
- Session token hash stored (never plaintext)
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Session(Base):
    """Server-side session model for OWASP/NIST compliant session management"""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hash

    # Session timing (NIST SP 800-63B compliant)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    absolute_expires_at = Column(DateTime(timezone=True), nullable=False)

    # Session metadata for security auditing
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Session state
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoke_reason = Column(String(50), nullable=True)  # 'logout', 'idle_timeout', 'absolute_timeout', 'admin_revoke', 'password_change', 'cleanup_stale'
    ended_at = Column(DateTime(timezone=True), nullable=True)  # When session ended (any reason: logout, timeout, etc.)
    app_type = Column(String(20), default='control_panel', nullable=False)  # 'control_panel' or 'tenant_app'

    # Relationships
    user = relationship("User", backref="sessions")
    tenant = relationship("Tenant", backref="sessions")

    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary (excluding sensitive data)"""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "absolute_expires_at": self.absolute_expires_at.isoformat() if self.absolute_expires_at else None,
            "ip_address": self.ip_address,
            "is_active": self.is_active,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoke_reason": self.revoke_reason,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "app_type": self.app_type,
        }

    @property
    def is_expired(self) -> bool:
        """Check if session is expired (either idle or absolute)"""
        if not self.is_active:
            return True

        now = datetime.now(self.absolute_expires_at.tzinfo) if self.absolute_expires_at.tzinfo else datetime.utcnow()

        # Check absolute timeout
        if now >= self.absolute_expires_at:
            return True

        # Check idle timeout (30 minutes)
        from datetime import timedelta
        idle_timeout = timedelta(minutes=30)
        idle_expires_at = self.last_activity_at + idle_timeout

        if now >= idle_expires_at:
            return True

        return False
