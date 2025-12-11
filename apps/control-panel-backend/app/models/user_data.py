"""
User data separation models for comprehensive personalization support

Supports 3 personalization modes:
- Shared: Data shared across all users (default for most resources)
- User-scoped: Each user has isolated data (conversations, preferences, progress)
- Session-based: Data isolated per session (temporary, disposable)
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class UserResourceData(Base):
    """User-specific data for resources that support personalization"""
    
    __tablename__ = "user_resource_data"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("ai_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Data Storage
    data_type = Column(String(50), nullable=False, index=True)  # preferences, progress, state, conversation
    data_key = Column(String(100), nullable=False, index=True)  # Identifier for the specific data
    data_value = Column(JSON, nullable=False, default=dict)  # The actual data
    
    # Metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    expiry_date = Column(DateTime(timezone=True), nullable=True)  # For session-based data
    version = Column(Integer, nullable=False, default=1)  # For data versioning
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    accessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="resource_data")
    tenant = relationship("Tenant")
    resource = relationship("AIResource")
    
    def __repr__(self):
        return f"<UserResourceData(user_id={self.user_id}, resource_id={self.resource_id}, data_type='{self.data_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "data_type": self.data_type,
            "data_key": self.data_key,
            "data_value": self.data_value,
            "is_encrypted": self.is_encrypted,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None
        }
    
    @property
    def is_expired(self) -> bool:
        """Check if data has expired (for session-based resources)"""
        if not self.expiry_date:
            return False
        return datetime.utcnow() > self.expiry_date
    
    def update_access_time(self) -> None:
        """Update the last accessed timestamp"""
        self.accessed_at = datetime.utcnow()


class UserPreferences(Base):
    """User preferences for various resources and system settings"""
    
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Preference Categories
    ui_preferences = Column(JSON, nullable=False, default=dict)  # Theme, layout, accessibility
    ai_preferences = Column(JSON, nullable=False, default=dict)  # Model preferences, system prompts
    learning_preferences = Column(JSON, nullable=False, default=dict)  # AI literacy settings, difficulty
    privacy_preferences = Column(JSON, nullable=False, default=dict)  # Data sharing, analytics opt-out
    notification_preferences = Column(JSON, nullable=False, default=dict)  # Email, in-app notifications
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="preferences")
    tenant = relationship("Tenant")
    
    def __repr__(self):
        return f"<UserPreferences(user_id={self.user_id}, tenant_id={self.tenant_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "ui_preferences": self.ui_preferences,
            "ai_preferences": self.ai_preferences,
            "learning_preferences": self.learning_preferences,
            "privacy_preferences": self.privacy_preferences,
            "notification_preferences": self.notification_preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_preference(self, category: str, key: str, default: Any = None) -> Any:
        """Get a specific preference value"""
        category_data = getattr(self, f"{category}_preferences", {})
        return category_data.get(key, default)
    
    def set_preference(self, category: str, key: str, value: Any) -> None:
        """Set a specific preference value"""
        if hasattr(self, f"{category}_preferences"):
            current_prefs = getattr(self, f"{category}_preferences") or {}
            current_prefs[key] = value
            setattr(self, f"{category}_preferences", current_prefs)


class UserProgress(Base):
    """User progress tracking for AI literacy and learning resources"""
    
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("ai_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Progress Data
    skill_area = Column(String(50), nullable=False, index=True)  # chess, logic, critical_thinking, etc.
    current_level = Column(String(20), nullable=False, default="beginner")  # beginner, intermediate, expert
    experience_points = Column(Integer, nullable=False, default=0)
    completion_percentage = Column(Float, nullable=False, default=0.0)  # 0.0 to 100.0
    
    # Performance Metrics
    total_sessions = Column(Integer, nullable=False, default=0)
    total_time_minutes = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)  # 0.0 to 100.0
    average_score = Column(Float, nullable=False, default=0.0)
    
    # Detailed Progress Data
    achievements = Column(JSON, nullable=False, default=list)  # List of earned achievements
    milestones = Column(JSON, nullable=False, default=dict)  # Progress milestones
    learning_analytics = Column(JSON, nullable=False, default=dict)  # Detailed analytics data
    
    # Adaptive Learning
    difficulty_adjustments = Column(JSON, nullable=False, default=dict)  # Difficulty level adjustments
    strength_areas = Column(JSON, nullable=False, default=list)  # Areas of strength
    improvement_areas = Column(JSON, nullable=False, default=list)  # Areas needing improvement
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="progress")
    tenant = relationship("Tenant")
    resource = relationship("AIResource")
    
    def __repr__(self):
        return f"<UserProgress(user_id={self.user_id}, skill_area='{self.skill_area}', level='{self.current_level}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "skill_area": self.skill_area,
            "current_level": self.current_level,
            "experience_points": self.experience_points,
            "completion_percentage": self.completion_percentage,
            "total_sessions": self.total_sessions,
            "total_time_minutes": self.total_time_minutes,
            "success_rate": self.success_rate,
            "average_score": self.average_score,
            "achievements": self.achievements,
            "milestones": self.milestones,
            "learning_analytics": self.learning_analytics,
            "difficulty_adjustments": self.difficulty_adjustments,
            "strength_areas": self.strength_areas,
            "improvement_areas": self.improvement_areas,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }
    
    def add_achievement(self, achievement: str) -> None:
        """Add an achievement to the user's list"""
        if achievement not in self.achievements:
            achievements = self.achievements or []
            achievements.append(achievement)
            self.achievements = achievements
    
    def update_score(self, new_score: float) -> None:
        """Update average score with new score"""
        if self.total_sessions == 0:
            self.average_score = new_score
        else:
            total_score = self.average_score * self.total_sessions
            total_score += new_score
            self.total_sessions += 1
            self.average_score = total_score / self.total_sessions
    
    def calculate_success_rate(self, successful_attempts: int, total_attempts: int) -> None:
        """Calculate and update success rate"""
        if total_attempts > 0:
            self.success_rate = (successful_attempts / total_attempts) * 100.0


class SessionData(Base):
    """Session-based data for temporary, disposable user interactions"""
    
    __tablename__ = "session_data"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("ai_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Session Info
    session_id = Column(String(100), nullable=False, index=True)  # Browser/app session ID
    data_type = Column(String(50), nullable=False, index=True)  # conversation, game_state, temp_files
    data_content = Column(JSON, nullable=False, default=dict)  # Session-specific data
    
    # Auto-cleanup
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    auto_cleanup = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_accessed = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    tenant = relationship("Tenant")
    resource = relationship("AIResource")
    
    def __repr__(self):
        return f"<SessionData(session_id='{self.session_id}', user_id={self.user_id}, data_type='{self.data_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "session_id": self.session_id,
            "data_type": self.data_type,
            "data_content": self.data_content,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "auto_cleanup": self.auto_cleanup,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }
    
    @property
    def is_expired(self) -> bool:
        """Check if session data has expired"""
        return datetime.utcnow() > self.expires_at
    
    def extend_expiry(self, minutes: int = 60) -> None:
        """Extend the expiry time by specified minutes"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        self.last_accessed = datetime.utcnow()


# Data separation utility functions
def get_user_data_scope(resource, user_id: int, tenant_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Get appropriate data scope based on resource personalization mode"""
    if resource.personalization_mode == "shared":
        return {"scope": "tenant", "tenant_id": tenant_id}
    elif resource.personalization_mode == "user_scoped":
        return {"scope": "user", "user_id": user_id, "tenant_id": tenant_id}
    elif resource.personalization_mode == "session_based":
        return {"scope": "session", "user_id": user_id, "tenant_id": tenant_id, "session_id": session_id}
    else:
        # Default to shared
        return {"scope": "tenant", "tenant_id": tenant_id}


def cleanup_expired_session_data() -> None:
    """Utility function to clean up expired session data (should be run periodically)"""
    from sqlalchemy.orm import sessionmaker
    from app.core.database import engine
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Delete expired session data
        expired_count = db.query(SessionData).filter(
            SessionData.expires_at < datetime.utcnow(),
            SessionData.auto_cleanup == True
        ).delete()
        
        # Clean up expired user resource data
        expired_user_data = db.query(UserResourceData).filter(
            UserResourceData.expiry_date < datetime.utcnow(),
            UserResourceData.expiry_date.isnot(None)
        ).delete()
        
        db.commit()
        return {"session_data_cleaned": expired_count, "user_data_cleaned": expired_user_data}
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()