"""
Dynamic Wiki & Documentation System Models

Supports context-aware documentation that adapts based on:
- User's current resource/tool being used
- User's role and permissions
- Tenant configuration
- Learning progress and skill level

Features:
- Versioned content management
- Role-based content visibility
- Interactive tutorials and guides
- Searchable knowledge base
- AI-powered content suggestions
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class WikiPage(Base):
    """Core wiki page model with versioning and context awareness"""
    
    __tablename__ = "wiki_pages"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Page Identity
    title = Column(String(200), nullable=False, index=True)
    slug = Column(String(250), nullable=False, unique=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # getting_started, tutorials, reference, troubleshooting
    
    # Content
    content = Column(Text, nullable=False)  # Markdown content
    excerpt = Column(String(500), nullable=True)  # Brief description
    content_type = Column(
        String(20), 
        nullable=False, 
        default="markdown",
        index=True
    )  # markdown, html, interactive
    
    # Context Targeting
    target_resources = Column(JSON, nullable=False, default=list)  # Resource IDs this content applies to
    target_roles = Column(JSON, nullable=False, default=list)  # User roles this content is for
    target_skill_levels = Column(JSON, nullable=False, default=list)  # beginner, intermediate, expert
    tenant_specific = Column(Boolean, nullable=False, default=False)  # Tenant-specific content
    
    # Metadata
    tags = Column(JSON, nullable=False, default=list)  # Searchable tags
    search_keywords = Column(Text, nullable=True)  # Additional search terms
    featured = Column(Boolean, nullable=False, default=False)  # Featured content
    priority = Column(Integer, nullable=False, default=100)  # Display priority (lower = higher priority)
    
    # Versioning
    version = Column(Integer, nullable=False, default=1)
    is_current_version = Column(Boolean, nullable=False, default=True, index=True)
    parent_page_id = Column(Integer, ForeignKey("wiki_pages.id"), nullable=True)  # For versioning
    
    # Publishing
    is_published = Column(Boolean, nullable=False, default=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Analytics
    view_count = Column(Integer, nullable=False, default=0)
    helpful_votes = Column(Integer, nullable=False, default=0)
    not_helpful_votes = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    versions = relationship("WikiPage", remote_side=[id], cascade="all, delete-orphan")
    parent_page = relationship("WikiPage", remote_side=[id])
    attachments = relationship("WikiAttachment", back_populates="wiki_page", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_wiki_context', 'category', 'is_published', 'is_current_version'),
        Index('idx_wiki_search', 'title', 'tags', 'search_keywords'),
        Index('idx_wiki_targeting', 'target_roles', 'target_skill_levels'),
    )
    
    def __repr__(self):
        return f"<WikiPage(id={self.id}, title='{self.title}', category='{self.category}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "title": self.title,
            "slug": self.slug,
            "category": self.category,
            "content": self.content,
            "excerpt": self.excerpt,
            "content_type": self.content_type,
            "target_resources": self.target_resources,
            "target_roles": self.target_roles,
            "target_skill_levels": self.target_skill_levels,
            "tenant_specific": self.tenant_specific,
            "tags": self.tags,
            "search_keywords": self.search_keywords,
            "featured": self.featured,
            "priority": self.priority,
            "version": self.version,
            "is_current_version": self.is_current_version,
            "parent_page_id": self.parent_page_id,
            "is_published": self.is_published,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "view_count": self.view_count,
            "helpful_votes": self.helpful_votes,
            "not_helpful_votes": self.not_helpful_votes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def helpfulness_score(self) -> float:
        """Calculate helpfulness score (0-100)"""
        total_votes = self.helpful_votes + self.not_helpful_votes
        if total_votes == 0:
            return 0.0
        return (self.helpful_votes / total_votes) * 100.0
    
    def increment_view(self) -> None:
        """Increment view count"""
        self.view_count += 1
    
    def add_helpful_vote(self) -> None:
        """Add helpful vote"""
        self.helpful_votes += 1
    
    def add_not_helpful_vote(self) -> None:
        """Add not helpful vote"""
        self.not_helpful_votes += 1
    
    def matches_context(self, resource_ids: List[int], user_role: str, skill_level: str) -> bool:
        """Check if page matches current user context"""
        # Check resource targeting
        if self.target_resources and not any(rid in self.target_resources for rid in resource_ids):
            return False
        
        # Check role targeting
        if self.target_roles and user_role not in self.target_roles:
            return False
        
        # Check skill level targeting
        if self.target_skill_levels and skill_level not in self.target_skill_levels:
            return False
        
        return True


class WikiAttachment(Base):
    """Attachments for wiki pages (images, files, etc.)"""
    
    __tablename__ = "wiki_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Foreign Keys
    wiki_page_id = Column(Integer, ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # File Information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False, index=True)  # image, document, video, etc.
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    
    # Storage
    storage_path = Column(String(500), nullable=False)  # Path to file in storage
    public_url = Column(String(500), nullable=True)  # Public URL if applicable
    
    # Metadata
    alt_text = Column(String(200), nullable=True)  # For accessibility
    caption = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    wiki_page = relationship("WikiPage", back_populates="attachments")
    
    def __repr__(self):
        return f"<WikiAttachment(id={self.id}, filename='{self.filename}', page_id={self.wiki_page_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "wiki_page_id": self.wiki_page_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "mime_type": self.mime_type,
            "file_size_bytes": self.file_size_bytes,
            "storage_path": self.storage_path,
            "public_url": self.public_url,
            "alt_text": self.alt_text,
            "caption": self.caption,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class InteractiveTutorial(Base):
    """Interactive step-by-step tutorials"""
    
    __tablename__ = "interactive_tutorials"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Tutorial Identity
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    difficulty_level = Column(String(20), nullable=False, default="beginner", index=True)
    estimated_duration = Column(Integer, nullable=True)  # Minutes
    
    # Tutorial Structure
    steps = Column(JSON, nullable=False, default=list)  # Ordered list of tutorial steps
    prerequisites = Column(JSON, nullable=False, default=list)  # Required knowledge/skills
    learning_objectives = Column(JSON, nullable=False, default=list)  # What user will learn
    
    # Context
    resource_id = Column(Integer, ForeignKey("ai_resources.id"), nullable=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    tags = Column(JSON, nullable=False, default=list)
    
    # Configuration
    allows_skipping = Column(Boolean, nullable=False, default=True)
    tracks_progress = Column(Boolean, nullable=False, default=True)
    provides_feedback = Column(Boolean, nullable=False, default=True)
    
    # Publishing
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Analytics
    completion_count = Column(Integer, nullable=False, default=0)
    average_completion_time = Column(Integer, nullable=True)  # Minutes
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    resource = relationship("AIResource")
    progress_records = relationship("TutorialProgress", back_populates="tutorial", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<InteractiveTutorial(id={self.id}, title='{self.title}', difficulty='{self.difficulty_level}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "title": self.title,
            "description": self.description,
            "difficulty_level": self.difficulty_level,
            "estimated_duration": self.estimated_duration,
            "steps": self.steps,
            "prerequisites": self.prerequisites,
            "learning_objectives": self.learning_objectives,
            "resource_id": self.resource_id,
            "category": self.category,
            "tags": self.tags,
            "allows_skipping": self.allows_skipping,
            "tracks_progress": self.tracks_progress,
            "provides_feedback": self.provides_feedback,
            "is_active": self.is_active,
            "completion_count": self.completion_count,
            "average_completion_time": self.average_completion_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TutorialProgress(Base):
    """User progress through interactive tutorials"""
    
    __tablename__ = "tutorial_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tutorial_id = Column(Integer, ForeignKey("interactive_tutorials.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Progress Data
    current_step = Column(Integer, nullable=False, default=0)
    completed_steps = Column(JSON, nullable=False, default=list)  # List of completed step indices
    is_completed = Column(Boolean, nullable=False, default=False)
    completion_percentage = Column(Float, nullable=False, default=0.0)
    
    # Performance
    start_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completion_time = Column(DateTime(timezone=True), nullable=True)
    total_time_spent = Column(Integer, nullable=False, default=0)  # Seconds
    
    # Feedback and Notes
    user_feedback = Column(Text, nullable=True)
    difficulty_rating = Column(Integer, nullable=True)  # 1-5 scale
    notes = Column(Text, nullable=True)  # User's personal notes
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    tutorial = relationship("InteractiveTutorial", back_populates="progress_records")
    tenant = relationship("Tenant")
    
    def __repr__(self):
        return f"<TutorialProgress(user_id={self.user_id}, tutorial_id={self.tutorial_id}, step={self.current_step})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "user_id": self.user_id,
            "tutorial_id": self.tutorial_id,
            "tenant_id": self.tenant_id,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "is_completed": self.is_completed,
            "completion_percentage": self.completion_percentage,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "total_time_spent": self.total_time_spent,
            "user_feedback": self.user_feedback,
            "difficulty_rating": self.difficulty_rating,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def advance_step(self) -> None:
        """Advance to next step"""
        if self.current_step not in self.completed_steps:
            completed = self.completed_steps or []
            completed.append(self.current_step)
            self.completed_steps = completed
        
        self.current_step += 1
        self.completion_percentage = (len(self.completed_steps) / len(self.tutorial.steps)) * 100.0
        
        if self.completion_percentage >= 100.0:
            self.is_completed = True
            self.completion_time = datetime.utcnow()


class ContextualHelp(Base):
    """Context-aware help system that provides relevant assistance based on current state"""
    
    __tablename__ = "contextual_help"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    
    # Help Context
    trigger_context = Column(String(100), nullable=False, index=True)  # page_url, resource_id, error_code, etc.
    help_type = Column(
        String(20), 
        nullable=False, 
        default="tooltip",
        index=True
    )  # tooltip, modal, sidebar, inline, notification
    
    # Content
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), nullable=False, default="markdown")
    
    # Targeting
    target_user_types = Column(JSON, nullable=False, default=list)  # User types this help applies to
    trigger_conditions = Column(JSON, nullable=False, default=dict)  # Conditions for showing help
    display_priority = Column(Integer, nullable=False, default=100)
    
    # Behavior
    is_dismissible = Column(Boolean, nullable=False, default=True)
    auto_show = Column(Boolean, nullable=False, default=False)  # Show automatically
    show_once_per_user = Column(Boolean, nullable=False, default=False)  # Only show once
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Analytics
    view_count = Column(Integer, nullable=False, default=0)
    dismiss_count = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<ContextualHelp(id={self.id}, context='{self.trigger_context}', type='{self.help_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "trigger_context": self.trigger_context,
            "help_type": self.help_type,
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "target_user_types": self.target_user_types,
            "trigger_conditions": self.trigger_conditions,
            "display_priority": self.display_priority,
            "is_dismissible": self.is_dismissible,
            "auto_show": self.auto_show,
            "show_once_per_user": self.show_once_per_user,
            "is_active": self.is_active,
            "view_count": self.view_count,
            "dismiss_count": self.dismiss_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def should_show_for_user(self, user_type: str, context_data: Dict[str, Any]) -> bool:
        """Check if help should be shown for given user and context"""
        # Check if help is active
        if not self.is_active:
            return False
        
        # Check user type targeting
        if self.target_user_types and user_type not in self.target_user_types:
            return False
        
        # Check trigger conditions
        if self.trigger_conditions:
            for condition_key, condition_value in self.trigger_conditions.items():
                if context_data.get(condition_key) != condition_value:
                    return False
        
        return True


# Search and Discovery utilities
def search_wiki_content(
    query: str,
    resource_ids: List[int] = None,
    user_role: str = None,
    skill_level: str = None,
    categories: List[str] = None,
    limit: int = 10
) -> List[WikiPage]:
    """Search wiki content with context filtering"""
    from sqlalchemy.orm import sessionmaker
    from app.core.database import engine
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        query_obj = db.query(WikiPage).filter(
            WikiPage.is_published == True,
            WikiPage.is_current_version == True
        )
        
        # Text search
        if query:
            query_obj = query_obj.filter(
                WikiPage.title.ilike(f"%{query}%") |
                WikiPage.content.ilike(f"%{query}%") |
                WikiPage.search_keywords.ilike(f"%{query}%")
            )
        
        # Category filtering
        if categories:
            query_obj = query_obj.filter(WikiPage.category.in_(categories))
        
        # Context filtering
        if resource_ids:
            query_obj = query_obj.filter(
                WikiPage.target_resources.overlap(resource_ids) |
                (WikiPage.target_resources == [])
            )
        
        if user_role:
            query_obj = query_obj.filter(
                WikiPage.target_roles.contains([user_role]) |
                (WikiPage.target_roles == [])
            )
        
        if skill_level:
            query_obj = query_obj.filter(
                WikiPage.target_skill_levels.contains([skill_level]) |
                (WikiPage.target_skill_levels == [])
            )
        
        # Order by priority and helpfulness
        query_obj = query_obj.order_by(
            WikiPage.featured.desc(),
            WikiPage.priority.asc(),
            WikiPage.helpful_votes.desc()
        )
        
        return query_obj.limit(limit).all()
    
    finally:
        db.close()