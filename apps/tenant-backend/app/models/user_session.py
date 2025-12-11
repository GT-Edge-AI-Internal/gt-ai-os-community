"""
User Session Model for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for user session entities using the PostgreSQL + PGVector backend.
Stores user session data and authentication state.
Perfect tenant isolation - each tenant has separate session data.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


class SessionStatus(str, Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class UserSession(BaseServiceModel):
    """
    User session model for GT 2.0 service-based architecture.
    
    Represents a user authentication session with state management,
    preferences, and activity tracking.
    """
    
    # Core session properties
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User ID (email or unique identifier)")
    user_email: Optional[str] = Field(None, max_length=255, description="User email address")
    user_name: Optional[str] = Field(None, max_length=100, description="User display name")
    
    # Authentication details
    auth_provider: str = Field(default="jwt", max_length=50, description="Authentication provider")
    auth_method: str = Field(default="bearer", max_length=50, description="Authentication method")
    
    # Session lifecycle
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    expires_at: datetime = Field(..., description="Session expiration time")
    last_activity_at: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    
    # User preferences and state
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    session_data: Dict[str, Any] = Field(default_factory=dict, description="Session-specific data")
    
    # Activity tracking
    login_ip: Optional[str] = Field(None, max_length=45, description="Login IP address")
    user_agent: Optional[str] = Field(None, max_length=500, description="User agent string")
    activity_count: int = Field(default=1, description="Number of activities in this session")
    
    # Security
    csrf_token: Optional[str] = Field(None, max_length=64, description="CSRF protection token")
    
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
        return "user_sessions"
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at or self.status != SessionStatus.ACTIVE
    
    def extend_session(self, minutes: int = 30) -> None:
        """Extend session expiration time"""
        if self.status == SessionStatus.ACTIVE:
            self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
            self.update_timestamp()
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity_at = datetime.utcnow()
        self.activity_count += 1
        self.update_timestamp()
    
    def revoke(self) -> None:
        """Revoke the session"""
        self.status = SessionStatus.REVOKED
        self.update_timestamp()
    
    def expire(self) -> None:
        """Mark session as expired"""
        self.status = SessionStatus.EXPIRED
        self.update_timestamp()


class UserSessionCreate(BaseCreateModel):
    """Model for creating new user sessions"""
    session_id: str
    user_id: str
    user_email: Optional[str] = Field(None, max_length=255)
    user_name: Optional[str] = Field(None, max_length=100)
    auth_provider: str = Field(default="jwt", max_length=50)
    auth_method: str = Field(default="bearer", max_length=50)
    expires_at: datetime
    preferences: Dict[str, Any] = Field(default_factory=dict)
    session_data: Dict[str, Any] = Field(default_factory=dict)
    login_ip: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)
    csrf_token: Optional[str] = Field(None, max_length=64)


class UserSessionUpdate(BaseUpdateModel):
    """Model for updating user sessions"""
    user_email: Optional[str] = Field(None, max_length=255)
    user_name: Optional[str] = Field(None, max_length=100)
    status: Optional[SessionStatus] = None
    expires_at: Optional[datetime] = None
    preferences: Optional[Dict[str, Any]] = None
    session_data: Optional[Dict[str, Any]] = None
    activity_count: Optional[int] = Field(None, ge=0)
    csrf_token: Optional[str] = Field(None, max_length=64)


class UserSessionResponse(BaseResponseModel):
    """Model for user session API responses"""
    id: str
    session_id: str
    user_id: str
    user_email: Optional[str]
    user_name: Optional[str]
    auth_provider: str
    auth_method: str
    status: SessionStatus
    expires_at: datetime
    last_activity_at: datetime
    preferences: Dict[str, Any]
    session_data: Dict[str, Any]
    login_ip: Optional[str]
    user_agent: Optional[str]
    activity_count: int
    csrf_token: Optional[str]
    created_at: datetime
    updated_at: datetime