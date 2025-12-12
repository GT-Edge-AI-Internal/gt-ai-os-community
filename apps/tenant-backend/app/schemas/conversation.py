"""
Conversation schemas for GT 2.0 Tenant Backend

Pydantic models for conversation-related API request/response validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class ConversationCreate(BaseModel):
    """Request to create a new conversation"""
    agent_id: str = Field(..., description="Agent UUID to chat with")
    title: Optional[str] = Field(None, description="Conversation title")
    initial_message: Optional[str] = Field(None, description="First message to send")


class ConversationUpdate(BaseModel):
    """Request to update a conversation"""
    title: Optional[str] = Field(None, description="New conversation title")
    system_prompt: Optional[str] = Field(None, description="Updated system prompt")


class MessageCreate(BaseModel):
    """Request to send a message"""
    content: str = Field(..., description="Message content")
    context_sources: Optional[List[str]] = Field(None, description="Context source IDs")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")


class MessageResponse(BaseModel):
    """Message response"""
    id: Optional[str] = Field(None, description="Message ID")
    message_id: Optional[str] = Field(None, description="Message ID (alternative)")
    content: Optional[str] = Field(None, description="Message content")
    role: Optional[str] = Field(None, description="Message role")
    tokens_used: Optional[int] = Field(None, description="Tokens consumed")
    model_used: Optional[str] = Field(None, description="Model used for generation")
    context_sources: Optional[List[str]] = Field(None, description="RAG context source documents")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    stream: Optional[bool] = Field(None, description="Whether response is streamed")
    stream_endpoint: Optional[str] = Field(None, description="Stream endpoint URL")

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class MessageListResponse(BaseModel):
    """Response for listing messages"""
    messages: List[MessageResponse]
    conversation_id: int
    total: int


class ConversationResponse(BaseModel):
    """Conversation response"""
    id: int = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    agent_id: str = Field(..., description="Agent ID")
    model_id: str = Field(..., description="Model identifier")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    message_count: int = Field(0, description="Total message count")
    total_tokens: int = Field(0, description="Total tokens used")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    messages: Optional[List[MessageResponse]] = Field(None, description="Conversation messages")

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class ConversationWithUnread(ConversationResponse):
    """Conversation response with unread message count"""
    unread_count: int = Field(0, description="Number of unread messages")


class ConversationListResponse(BaseModel):
    """Response for listing conversations"""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int