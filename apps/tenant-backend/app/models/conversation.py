"""
Conversation Model for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for conversation entities using the PostgreSQL + PGVector backend.
Stores conversation metadata and settings for AI chat sessions.
Perfect tenant isolation - each tenant has separate conversation data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


class ConversationStatus(str, Enum):
    """Conversation status enumeration"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Conversation(BaseServiceModel):
    """
    Conversation model for GT 2.0 service-based architecture.
    
    Represents a chat session with an AI agent including metadata,
    configuration, and usage statistics.
    """
    
    # Core conversation properties
    title: str = Field(..., min_length=1, max_length=200, description="Conversation title")
    agent_id: Optional[str] = Field(None, description="Associated agent ID")
    
    # User information  
    created_by: str = Field(..., description="User email or ID who created this")
    user_name: Optional[str] = Field(None, max_length=100, description="User display name")
    
    # Configuration
    system_prompt: Optional[str] = Field(None, description="Custom system prompt override")
    model_id: str = Field(default="groq:llama3-70b-8192", description="AI model identifier")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Model parameters and settings")
    
    # Status and metadata
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE, description="Conversation status")
    tags: List[str] = Field(default_factory=list, description="Conversation tags")
    
    # Statistics
    message_count: int = Field(default=0, description="Number of messages in conversation")
    total_tokens_used: int = Field(default=0, description="Total tokens used")
    total_cost_cents: int = Field(default=0, description="Total cost in cents")
    
    # Timestamps
    last_activity_at: Optional[datetime] = Field(None, description="Last activity timestamp")
    
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
        return "conversations"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """Create from dictionary"""
        return cls(
            agent_id=data.get("agent_id"),
            title=data.get("title", ""),
            system_prompt=data.get("system_prompt"),
            model_id=data.get("model_id", "groq:llama3-70b-8192"),
            created_by=data.get("created_by", ""),
            user_name=data.get("user_name"),
            configuration=data.get("configuration", {}),
            tags=data.get("tags", []),
        )
    
    def update_statistics(self, message_count: int, tokens_used: int, cost_cents: int) -> None:
        """Update conversation statistics"""
        self.message_count = message_count
        self.total_tokens_used = tokens_used
        self.total_cost_cents = cost_cents
        self.last_activity_at = datetime.utcnow()
        self.update_timestamp()
    
    def archive(self) -> None:
        """Archive this conversation"""
        self.status = ConversationStatus.ARCHIVED
        self.update_timestamp()
    
    def delete(self) -> None:
        """Mark conversation as deleted"""
        self.status = ConversationStatus.DELETED
        self.update_timestamp()


class ConversationCreate(BaseCreateModel):
    """Model for creating new conversations"""
    title: str = Field(..., min_length=1, max_length=200)
    agent_id: Optional[str] = None
    created_by: str
    user_name: Optional[str] = Field(None, max_length=100)
    system_prompt: Optional[str] = None
    model_id: str = Field(default="groq:llama3-70b-8192")
    configuration: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(protected_namespaces=())


class ConversationUpdate(BaseUpdateModel):
    """Model for updating conversations"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    system_prompt: Optional[str] = None
    model_id: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[ConversationStatus] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(protected_namespaces=())


class ConversationResponse(BaseResponseModel):
    """Model for conversation API responses"""
    id: str
    title: str
    agent_id: Optional[str]
    created_by: str
    user_name: Optional[str]
    system_prompt: Optional[str]
    model_id: str
    configuration: Dict[str, Any]
    status: ConversationStatus
    tags: List[str]
    message_count: int
    total_tokens_used: int
    total_cost_cents: int
    last_activity_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(protected_namespaces=())