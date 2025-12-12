"""
Category Model for GT 2.0 Agent Discovery

Implements a simple hierarchical category system for organizing agents.
Follows GT 2.0's principle of "Clarity Over Complexity"
- Simple parent-child relationships
- System categories that cannot be deleted
- Tenant-specific and global categories
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Category(Base):
    """Category model for organizing agents and resources
    
    GT 2.0 Design: Simple hierarchical categories without complex taxonomies
    """
    
    __tablename__ = "categories"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)  # URL-safe identifier
    
    # Category Details
    name = Column(String(100), nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(10), nullable=True)  # Emoji or icon code
    color = Column(String(20), nullable=True)  # Hex color code for UI
    
    # Hierarchy (simple parent-child)
    parent_id = Column(String(36), ForeignKey("categories.id"), nullable=True, index=True)
    
    # Scope
    is_system = Column(Boolean, nullable=False, default=False)  # Protected from deletion
    is_global = Column(Boolean, nullable=False, default=True)   # Available to all tenants
    
    # Display Order
    sort_order = Column(Integer, nullable=False, default=0)
    
    # Usage Statistics (cached)
    assistant_count = Column(Integer, nullable=False, default=0)
    dataset_count = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', slug='{self.slug}')>"
    
    def to_dict(self, include_children: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "parent_id": self.parent_id,
            "is_system": self.is_system,
            "is_global": self.is_global,
            "sort_order": self.sort_order,
            "assistant_count": self.assistant_count,
            "dataset_count": self.dataset_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_children and self.children:
            data["children"] = [child.to_dict() for child in self.children]
        
        return data
    
    def get_full_path(self) -> str:
        """Get full category path (e.g., 'AI Tools > Research > Academic')"""
        if not self.parent_id:
            return self.display_name
        
        # Simple recursion to build path
        parent_path = self.parent.get_full_path() if self.parent else ""
        return f"{parent_path} > {self.display_name}" if parent_path else self.display_name
    
    def is_descendant_of(self, ancestor_id: int) -> bool:
        """Check if this category is a descendant of another"""
        if not self.parent_id:
            return False
        
        if self.parent_id == ancestor_id:
            return True
        
        return self.parent.is_descendant_of(ancestor_id) if self.parent else False
    
    def get_all_descendants(self) -> List["Category"]:
        """Get all descendant categories"""
        descendants = []
        
        if self.children:
            for child in self.children:
                descendants.append(child)
                descendants.extend(child.get_all_descendants())
        
        return descendants
    
    def update_counts(self, assistant_delta: int = 0, dataset_delta: int = 0) -> None:
        """Update resource counts for this category"""
        self.assistant_count = max(0, self.assistant_count + assistant_delta)
        self.dataset_count = max(0, self.dataset_count + dataset_delta)
        self.updated_at = datetime.utcnow()


# GT 2.0 Default System Categories
DEFAULT_CATEGORIES = [
    # Top-level categories
    {
        "slug": "research",
        "name": "Research & Analysis",
        "display_name": "Research & Analysis",
        "description": "Agents for research, analysis, and information synthesis",
        "icon": "🔍",
        "color": "#3B82F6",  # Blue
        "is_system": True,
        "is_global": True,
        "sort_order": 10,
    },
    {
        "slug": "development",
        "name": "Software Development",
        "display_name": "Software Development",
        "description": "Coding, debugging, and development tools",
        "icon": "💻",
        "color": "#10B981",  # Green
        "is_system": True,
        "is_global": True,
        "sort_order": 20,
    },
    {
        "slug": "cybersecurity",
        "name": "Cybersecurity",
        "display_name": "Cybersecurity",
        "description": "Security analysis, threat detection, and incident response",
        "icon": "🛡️",
        "color": "#EF4444",  # Red
        "is_system": True,
        "is_global": True,
        "sort_order": 30,
    },
    {
        "slug": "education",
        "name": "Education & Training",
        "display_name": "Education & Training",
        "description": "Educational agents and AI literacy tools",
        "icon": "🎓",
        "color": "#8B5CF6",  # Purple
        "is_system": True,
        "is_global": True,
        "sort_order": 40,
    },
    {
        "slug": "creative",
        "name": "Creative & Content",
        "display_name": "Creative & Content",
        "description": "Writing, design, and creative content generation",
        "icon": "✨",
        "color": "#F59E0B",  # Amber
        "is_system": True,
        "is_global": True,
        "sort_order": 50,
    },
    {
        "slug": "analytics",
        "name": "Data & Analytics",
        "display_name": "Data & Analytics",
        "description": "Data analysis, visualization, and insights",
        "icon": "📊",
        "color": "#06B6D4",  # Cyan
        "is_system": True,
        "is_global": True,
        "sort_order": 60,
    },
    {
        "slug": "business",
        "name": "Business & Operations",
        "display_name": "Business & Operations",
        "description": "Business analysis, planning, and operations",
        "icon": "💼",
        "color": "#64748B",  # Slate
        "is_system": True,
        "is_global": True,
        "sort_order": 70,
    },
    {
        "slug": "personal",
        "name": "Personal Productivity",
        "display_name": "Personal Productivity",
        "description": "Personal agents and productivity tools",
        "icon": "🚀",
        "color": "#14B8A6",  # Teal
        "is_system": True,
        "is_global": True,
        "sort_order": 80,
    },
    {
        "slug": "custom",
        "name": "Custom & Specialized",
        "display_name": "Custom & Specialized",
        "description": "Custom-built and specialized agents",
        "icon": "⚙️",
        "color": "#71717A",  # Zinc
        "is_system": True,
        "is_global": True,
        "sort_order": 90,
    },
]


# Sub-categories (examples)
DEFAULT_SUBCATEGORIES = [
    # Research subcategories
    {
        "slug": "research-academic",
        "name": "Academic Research",
        "display_name": "Academic Research",
        "description": "Academic papers, citations, and literature review",
        "icon": "📚",
        "parent_slug": "research",  # Will be resolved to parent_id
        "is_system": True,
        "is_global": True,
        "sort_order": 11,
    },
    {
        "slug": "research-market",
        "name": "Market Research",
        "display_name": "Market Research",
        "description": "Market analysis, competitor research, and trends",
        "icon": "📈",
        "parent_slug": "research",
        "is_system": True,
        "is_global": True,
        "sort_order": 12,
    },
    
    # Development subcategories
    {
        "slug": "dev-web",
        "name": "Web Development",
        "display_name": "Web Development",
        "description": "Frontend, backend, and full-stack development",
        "icon": "🌐",
        "parent_slug": "development",
        "is_system": True,
        "is_global": True,
        "sort_order": 21,
    },
    {
        "slug": "dev-mobile",
        "name": "Mobile Development",
        "display_name": "Mobile Development",
        "description": "iOS, Android, and cross-platform development",
        "icon": "📱",
        "parent_slug": "development",
        "is_system": True,
        "is_global": True,
        "sort_order": 22,
    },
    {
        "slug": "dev-devops",
        "name": "DevOps & Infrastructure",
        "display_name": "DevOps & Infrastructure",
        "description": "CI/CD, containerization, and infrastructure",
        "icon": "🔧",
        "parent_slug": "development",
        "is_system": True,
        "is_global": True,
        "sort_order": 23,
    },
    
    # Cybersecurity subcategories
    {
        "slug": "cyber-analysis",
        "name": "Threat Analysis",
        "display_name": "Threat Analysis",
        "description": "Threat detection, analysis, and intelligence",
        "icon": "🔍",
        "parent_slug": "cybersecurity",
        "is_system": True,
        "is_global": True,
        "sort_order": 31,
    },
    {
        "slug": "cyber-incident",
        "name": "Incident Response",
        "display_name": "Incident Response",
        "description": "Incident handling and forensics",
        "icon": "🚨",
        "parent_slug": "cybersecurity",
        "is_system": True,
        "is_global": True,
        "sort_order": 32,
    },
    
    # Education subcategories
    {
        "slug": "edu-ai-literacy",
        "name": "AI Literacy",
        "display_name": "AI Literacy",
        "description": "Understanding and working with AI systems",
        "icon": "🤖",
        "parent_slug": "education",
        "is_system": True,
        "is_global": True,
        "sort_order": 41,
    },
    {
        "slug": "edu-critical-thinking",
        "name": "Critical Thinking",
        "display_name": "Critical Thinking",
        "description": "Logic, reasoning, and problem-solving",
        "icon": "🧠",
        "parent_slug": "education",
        "is_system": True,
        "is_global": True,
        "sort_order": 42,
    },
]