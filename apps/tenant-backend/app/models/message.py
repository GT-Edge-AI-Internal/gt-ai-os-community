"""
Message Model for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for message entities using the PostgreSQL + PGVector backend.
Stores individual messages within conversations with full context tracking.
Perfect tenant isolation - each tenant has separate message data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


class MessageRole(str, Enum):
    """Message role enumeration"""
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"


class Message(BaseServiceModel):
    """
    Message model for GT 2.0 service-based architecture.
    
    Represents a single message within a conversation including content,
    role, metadata, and usage statistics.
    """
    
    # Core message properties
    conversation_id: str = Field(..., description="ID of the parent conversation")
    role: MessageRole = Field(..., description="Message role (system, user, agent, tool)")
    content: str = Field(..., description="Message content")
    
    # Optional metadata
    model_used: Optional[str] = Field(None, description="AI model used for generation")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Tool calls made")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID if this is a tool response")
    
    # Usage statistics
    tokens_used: int = Field(default=0, description="Tokens consumed by this message")
    cost_cents: int = Field(default=0, description="Cost in cents for this message")
    
    # Processing metadata
    processing_time_ms: Optional[float] = Field(None, description="Time taken to process this message")
    temperature: Optional[float] = Field(None, description="Temperature used for generation")
    max_tokens: Optional[int] = Field(None, description="Max tokens setting used")
    
    # Status
    is_edited: bool = Field(default=False, description="Whether message was edited")
    is_deleted: bool = Field(default=False, description="Whether message was deleted")
    
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
        return "messages"
    
    def mark_edited(self) -> None:
        """Mark message as edited"""
        self.is_edited = True
        self.update_timestamp()
    
    def mark_deleted(self) -> None:
        """Mark message as deleted"""
        self.is_deleted = True
        self.update_timestamp()


class MessageCreate(BaseCreateModel):
    """Model for creating new messages"""
    conversation_id: str
    role: MessageRole
    content: str
    model_used: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tool_call_id: Optional[str] = None
    tokens_used: int = Field(default=0)
    cost_cents: int = Field(default=0)
    processing_time_ms: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    model_config = ConfigDict(protected_namespaces=())


class MessageUpdate(BaseUpdateModel):
    """Model for updating messages"""
    content: Optional[str] = None
    is_edited: Optional[bool] = None
    is_deleted: Optional[bool] = None


class MessageResponse(BaseResponseModel):
    """Model for message API responses"""
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    model_used: Optional[str]
    tool_calls: List[Dict[str, Any]]
    tool_call_id: Optional[str]
    tokens_used: int
    cost_cents: int
    processing_time_ms: Optional[float]
    temperature: Optional[float]
    max_tokens: Optional[int]
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(protected_namespaces=())