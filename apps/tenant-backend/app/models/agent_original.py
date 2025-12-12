"""
Agent Model for GT 2.0 Tenant Backend

File-based agent configuration with DuckDB reference tracking.
Perfect tenant isolation - each tenant has separate agent data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid
import os
import json

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import get_settings


class Agent(Base):
    """Agent model for AI agent configurations"""
    
    __tablename__ = "agents"
    
    # Primary Key - using UUID for PostgreSQL compatibility
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # Agent Details
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    template_id = Column(String(100), nullable=True, index=True)  # Template used to create this agent
    category_id = Column(String(36), nullable=True, index=True)  # Foreign key to categories table for discovery
    agent_type = Column(String(50), nullable=False, default="custom", index=True)  # Agent type/category
    prompt_template = Column(Text, nullable=True)  # System prompt template
    
    # Visibility and Sharing (GT 2.0 Team Enhancement)
    visibility = Column(String(20), nullable=False, default="private", index=True)  # private, team, organization
    tenant_id = Column(String(36), nullable=True, index=True)  # Foreign key to teams table (null for private)
    shared_with = Column(JSON, nullable=False, default=list)  # List of user emails for explicit sharing
    
    # File-based Configuration References
    config_file_path = Column(String(500), nullable=False)  # Path to config.json
    prompt_file_path = Column(String(500), nullable=False)  # Path to prompt.md
    capabilities_file_path = Column(String(500), nullable=False)  # Path to capabilities.json
    
    # User Information (from JWT token)
    created_by = Column(String(255), nullable=False, index=True)  # User email or ID
    user_id = Column(String(255), nullable=False, index=True)  # User ID (alias for created_by for API compatibility)
    user_name = Column(String(100), nullable=True)  # User display name
    
    # Agent Configuration (cached from files for quick access)
    personality_config = Column(JSON, nullable=False, default=dict)  # Tone, style, etc.
    resource_preferences = Column(JSON, nullable=False, default=dict)  # LLM preferences, etc.
    memory_settings = Column(JSON, nullable=False, default=dict)  # Conversation retention settings
    
    # Status and Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    is_favorite = Column(Boolean, nullable=False, default=False)
    tags = Column(JSON, nullable=False, default=list)  # User-defined tags
    example_prompts = Column(JSON, nullable=False, default=list)  # Up to 4 example prompts for discovery
    
    # Statistics (updated by triggers or background processes)
    conversation_count = Column(Integer, nullable=False, default=0)
    total_messages = Column(Integer, nullable=False, default=0)
    total_tokens_used = Column(Integer, nullable=False, default=0)
    total_cost_cents = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name='{self.name}', created_by='{self.created_by}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "name": self.name,
            "description": self.description,
            "template_id": self.template_id,
            "created_by": self.created_by,
            "user_name": self.user_name,
            "personality_config": self.personality_config,
            "resource_preferences": self.resource_preferences,
            "memory_settings": self.memory_settings,
            "is_active": self.is_active,
            "is_favorite": self.is_favorite,
            "tags": self.tags,
            "conversation_count": self.conversation_count,
            "total_messages": self.total_messages,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_cents": self.total_cost_cents,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Agent":
        """Create from dictionary"""
        created_by = data.get("created_by", data.get("user_id", ""))
        return cls(
            name=data.get("name", ""),
            description=data.get("description"),
            template_id=data.get("template_id"),
            agent_type=data.get("agent_type", "custom"),
            prompt_template=data.get("prompt_template", ""),
            created_by=created_by,
            user_id=created_by,  # Keep in sync
            user_name=data.get("user_name"),
            personality_config=data.get("personality_config", {}),
            resource_preferences=data.get("resource_preferences", {}),
            memory_settings=data.get("memory_settings", {}),
            tags=data.get("tags", []),
        )
    
    def get_agent_directory(self) -> str:
        """Get the file system directory for this agent"""
        settings = get_settings()
        tenant_data_path = os.path.dirname(settings.database_path)
        return os.path.join(tenant_data_path, "agents", str(self.uuid))
    
    def ensure_directory_exists(self) -> None:
        """Create agent directory with secure permissions"""
        agent_dir = self.get_agent_directory()
        os.makedirs(agent_dir, exist_ok=True, mode=0o700)
        
        # Create subdirectories
        subdirs = ["memory", "memory/conversations", "memory/context", "memory/preferences", "resources"]
        for subdir in subdirs:
            subdir_path = os.path.join(agent_dir, subdir)
            os.makedirs(subdir_path, exist_ok=True, mode=0o700)
    
    def initialize_file_paths(self) -> None:
        """Initialize file paths for this agent"""
        agent_dir = self.get_agent_directory()
        self.config_file_path = os.path.join(agent_dir, "config.json")
        self.prompt_file_path = os.path.join(agent_dir, "prompt.md")
        self.capabilities_file_path = os.path.join(agent_dir, "capabilities.json")
    
    def load_config_from_file(self) -> Dict[str, Any]:
        """Load agent configuration from file"""
        try:
            with open(self.config_file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def save_config_to_file(self, config: Dict[str, Any]) -> None:
        """Save agent configuration to file"""
        self.ensure_directory_exists()
        with open(self.config_file_path, 'w') as f:
            json.dump(config, f, indent=2, default=str)
    
    def load_prompt_from_file(self) -> str:
        """Load system prompt from file"""
        try:
            with open(self.prompt_file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return ""
    
    def save_prompt_to_file(self, prompt: str) -> None:
        """Save system prompt to file"""
        self.ensure_directory_exists()
        with open(self.prompt_file_path, 'w') as f:
            f.write(prompt)
    
    def load_capabilities_from_file(self) -> List[Dict[str, Any]]:
        """Load capabilities from file"""
        try:
            with open(self.capabilities_file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_capabilities_to_file(self, capabilities: List[Dict[str, Any]]) -> None:
        """Save capabilities to file"""
        self.ensure_directory_exists()
        with open(self.capabilities_file_path, 'w') as f:
            json.dump(capabilities, f, indent=2, default=str)
    
    def update_statistics(self, conversation_count: int = None, messages: int = None, 
                         tokens: int = None, cost_cents: int = None) -> None:
        """Update agent statistics"""
        if conversation_count is not None:
            self.conversation_count = conversation_count
        if messages is not None:
            self.total_messages += messages
        if tokens is not None:
            self.total_tokens_used += tokens
        if cost_cents is not None:
            self.total_cost_cents += cost_cents
        
        self.last_used_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the agent"""
        if tag not in self.tags:
            current_tags = self.tags or []
            current_tags.append(tag)
            self.tags = current_tags
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the agent"""
        if self.tags and tag in self.tags:
            current_tags = self.tags.copy()
            current_tags.remove(tag)
            self.tags = current_tags
    
    def get_full_configuration(self) -> Dict[str, Any]:
        """Get complete agent configuration including file-based data"""
        config = self.load_config_from_file()
        prompt = self.load_prompt_from_file()
        capabilities = self.load_capabilities_from_file()
        
        return {
            **self.to_dict(),
            "config": config,
            "prompt": prompt,
            "capabilities": capabilities,
        }
    
    def clone(self, new_name: str, user_identifier: str, modifications: Dict[str, Any] = None) -> "Agent":
        """Create a clone of this agent with modifications"""
        # Load current configuration
        config = self.load_config_from_file()
        prompt = self.load_prompt_from_file()
        capabilities = self.load_capabilities_from_file()
        
        # Apply modifications if provided
        if modifications:
            config.update(modifications.get("config", {}))
            if "prompt" in modifications:
                prompt = modifications["prompt"]
            if "capabilities" in modifications:
                capabilities = modifications["capabilities"]
        
        # Create new agent
        new_agent = Agent(
            name=new_name,
            description=f"Clone of {self.name}",
            template_id=self.template_id,
            created_by=user_identifier,
            personality_config=self.personality_config.copy(),
            resource_preferences=self.resource_preferences.copy(),
            memory_settings=self.memory_settings.copy(),
            tags=self.tags.copy() if self.tags else [],
        )
        
        return new_agent
    
    def archive(self) -> None:
        """Archive the agent (soft delete)"""
        self.is_active = False
        self.updated_at = datetime.utcnow()
    
    def unarchive(self) -> None:
        """Unarchive the agent"""
        self.is_active = True
        self.updated_at = datetime.utcnow()
    
    def favorite(self) -> None:
        """Mark agent as favorite"""
        self.is_favorite = True
        self.updated_at = datetime.utcnow()
    
    def unfavorite(self) -> None:
        """Remove favorite status"""
        self.is_favorite = False
        self.updated_at = datetime.utcnow()
    
    def is_owned_by(self, user_identifier: str) -> bool:
        """Check if agent is owned by the given user"""
        return self.created_by == user_identifier
    
    def can_be_accessed_by(self, user_identifier: str, user_teams: List[int] = None) -> bool:
        """Check if agent can be accessed by the given user
        
        GT 2.0 Access Rules:
        1. Owner always has access
        2. Team members have access if visibility is 'team' and they're in the team
        3. All organization members have access if visibility is 'organization'
        4. Explicitly shared users have access
        """
        # Owner always has access
        if self.is_owned_by(user_identifier):
            return True
        
        # Check explicit sharing
        if self.shared_with and user_identifier in self.shared_with:
            return True
        
        # Check team visibility
        if self.visibility == "team" and self.tenant_id and user_teams:
            if self.tenant_id in user_teams:
                return True
        
        # Check organization visibility
        if self.visibility == "organization":
            return True  # All authenticated users in the tenant
        
        return False
    
    @property
    def average_tokens_per_message(self) -> float:
        """Calculate average tokens per message"""
        if self.total_messages == 0:
            return 0.0
        return self.total_tokens_used / self.total_messages
    
    @property
    def total_cost_dollars(self) -> float:
        """Get total cost in dollars"""
        return self.total_cost_cents / 100.0
    
    @property
    def average_cost_per_conversation(self) -> float:
        """Calculate average cost per conversation in dollars"""
        if self.conversation_count == 0:
            return 0.0
        return self.total_cost_dollars / self.conversation_count
    
    @property
    def usage_count(self) -> int:
        """Alias for conversation_count for API compatibility"""
        return self.conversation_count
    
    @usage_count.setter
    def usage_count(self, value: int) -> None:
        """Set conversation_count via usage_count alias"""
        self.conversation_count = value


# Backward compatibility alias
Agent = Agent
