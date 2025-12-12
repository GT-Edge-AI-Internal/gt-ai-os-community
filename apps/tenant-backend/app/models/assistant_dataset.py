"""
Agent-Dataset Binding Model for GT 2.0 Tenant Backend

Links agents to RAG datasets for context-aware conversations.
Follows GT 2.0's principle of "Elegant Simplicity"
- Simple many-to-many relationships
- Configurable relevance thresholds
- Priority ordering for multiple datasets
"""

from datetime import datetime
from typing import Dict, Any
import uuid

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


def generate_uuid():
    """Generate a unique identifier"""
    return str(uuid.uuid4())


class AssistantDataset(Base):
    """Links agents to RAG datasets for context retrieval
    
    GT 2.0 Design: Simple binding table with configuration
    """
    
    __tablename__ = "agent_datasets"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # Foreign Keys
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("rag_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Configuration
    relevance_threshold = Column(Float, nullable=False, default=0.7)  # Minimum similarity score
    max_chunks = Column(Integer, nullable=False, default=5)  # Max chunks to retrieve
    priority_order = Column(Integer, nullable=False, default=0)  # Order when multiple datasets (lower = higher priority)
    
    # Settings
    is_active = Column(Boolean, nullable=False, default=True)
    auto_include = Column(Boolean, nullable=False, default=True)  # Automatically include in searches
    
    # Usage Statistics
    search_count = Column(Integer, nullable=False, default=0)
    chunks_retrieved_total = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    agent = relationship("Agent", backref="dataset_bindings")
    dataset = relationship("RAGDataset", backref="assistant_bindings")
    
    def __repr__(self) -> str:
        return f"<AssistantDataset(agent_id={self.agent_id}, dataset_id='{self.dataset_id}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "dataset_id": self.dataset_id,
            "relevance_threshold": self.relevance_threshold,
            "max_chunks": self.max_chunks,
            "priority_order": self.priority_order,
            "is_active": self.is_active,
            "auto_include": self.auto_include,
            "search_count": self.search_count,
            "chunks_retrieved_total": self.chunks_retrieved_total,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
    
    def increment_usage(self, chunks_retrieved: int = 0) -> None:
        """Update usage statistics"""
        self.search_count += 1
        self.chunks_retrieved_total += chunks_retrieved
        self.last_used_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class AssistantIntegration(Base):
    """Links agents to external integrations and tools
    
    GT 2.0 Design: Simple binding to resource cluster integrations
    """
    
    __tablename__ = "agent_integrations"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # Foreign Keys
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_resource_id = Column(String(36), nullable=False, index=True)  # Resource cluster integration ID
    
    # Configuration
    integration_type = Column(String(50), nullable=False)  # github, slack, jira, etc.
    enabled = Column(Boolean, nullable=False, default=True)
    config = Column(String, nullable=False, default="{}")  # JSON configuration
    
    # Permissions
    allowed_actions = Column(String, nullable=False, default="[]")  # JSON array of allowed actions
    
    # Usage Statistics
    usage_count = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    agent = relationship("Agent", backref="integration_bindings")
    
    def __repr__(self) -> str:
        return f"<AssistantIntegration(agent_id={self.agent_id}, type='{self.integration_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        import json
        
        try:
            config_obj = json.loads(self.config) if isinstance(self.config, str) else self.config
            allowed_actions_list = json.loads(self.allowed_actions) if isinstance(self.allowed_actions, str) else self.allowed_actions
        except json.JSONDecodeError:
            config_obj = {}
            allowed_actions_list = []
        
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "integration_resource_id": self.integration_resource_id,
            "integration_type": self.integration_type,
            "enabled": self.enabled,
            "config": config_obj,
            "allowed_actions": allowed_actions_list,
            "usage_count": self.usage_count,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
    
    def increment_usage(self) -> None:
        """Update usage statistics"""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def record_error(self, error_message: str) -> None:
        """Record an error from the integration"""
        self.last_error = error_message[:500]  # Truncate to 500 chars
        self.updated_at = datetime.utcnow()