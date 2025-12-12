"""
Agent schemas for GT 2.0 Tenant Backend

Pydantic models for agent-related API request/response validation.
Implements comprehensive agent management per CLAUDE.md specifications.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class AgentTemplate(BaseModel):
    """Agent template information"""
    id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template display name")
    description: str = Field(..., description="Template description")
    icon: str = Field(..., description="Template icon emoji or URL")
    category: str = Field(..., description="Template category")
    prompt: str = Field(..., description="System prompt template")
    default_capabilities: List[str] = Field(default_factory=list, description="Default capability grants")
    personality_config: Dict[str, Any] = Field(default_factory=dict, description="Personality configuration")
    resource_preferences: Dict[str, Any] = Field(default_factory=dict, description="Resource preferences")


class AgentTemplateListResponse(BaseModel):
    """Response for listing agent templates"""
    templates: List[AgentTemplate]
    categories: List[str] = Field(default_factory=list, description="Available categories")
    total: int


class AgentCreate(BaseModel):
    """Request to create a new agent"""
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    template_id: Optional[str] = Field(None, description="Template ID to use")
    category: Optional[str] = Field(None, description="Agent category")
    prompt_template: Optional[str] = Field(None, description="System prompt template")
    model: Optional[str] = Field(None, description="AI model identifier")
    model_id: Optional[str] = Field(None, description="AI model identifier (alias for model)")
    temperature: Optional[float] = Field(None, description="Model temperature parameter")
    # max_tokens removed - now determined by model configuration
    visibility: Optional[str] = Field(None, description="Agent visibility setting")
    dataset_connection: Optional[str] = Field(None, description="RAG dataset connection type")
    selected_dataset_ids: Optional[List[str]] = Field(None, description="Selected dataset IDs for RAG")
    personality_config: Optional[Dict[str, Any]] = Field(None, description="Personality configuration")
    resource_preferences: Optional[Dict[str, Any]] = Field(None, description="Resource preferences")
    tags: Optional[List[str]] = Field(None, description="Agent tags")
    disclaimer: Optional[str] = Field(None, max_length=500, description="Disclaimer text shown in chat")
    easy_prompts: Optional[List[str]] = Field(None, description="Quick-access preset prompts (max 10)")
    team_shares: Optional[List[Dict[str, Any]]] = Field(None, description="Team sharing configuration with per-user permissions")

    model_config = ConfigDict(protected_namespaces=())


class AgentUpdate(BaseModel):
    """Request to update an agent"""
    name: Optional[str] = Field(None, description="New agent name")
    description: Optional[str] = Field(None, description="New agent description")
    category: Optional[str] = Field(None, description="Agent category")
    prompt_template: Optional[str] = Field(None, description="System prompt template")
    model: Optional[str] = Field(None, description="AI model identifier")
    temperature: Optional[float] = Field(None, description="Model temperature parameter")
    # max_tokens removed - now determined by model configuration
    visibility: Optional[str] = Field(None, description="Agent visibility setting")
    dataset_connection: Optional[str] = Field(None, description="RAG dataset connection type")
    selected_dataset_ids: Optional[List[str]] = Field(None, description="Selected dataset IDs for RAG")
    personality_config: Optional[Dict[str, Any]] = Field(None, description="Updated personality config")
    resource_preferences: Optional[Dict[str, Any]] = Field(None, description="Updated resource preferences")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    is_favorite: Optional[bool] = Field(None, description="Favorite status")
    disclaimer: Optional[str] = Field(None, max_length=500, description="Disclaimer text shown in chat")
    easy_prompts: Optional[List[str]] = Field(None, description="Quick-access preset prompts (max 10)")
    team_shares: Optional[List[Dict[str, Any]]] = Field(None, description="Update team sharing configuration")


class AgentResponse(BaseModel):
    """Response for agent operations"""
    id: str = Field(..., description="Agent UUID")
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    template_id: Optional[str] = Field(None, description="Template ID if created from template")
    category: Optional[str] = Field(None, description="Agent category")
    prompt_template: Optional[str] = Field(None, description="System prompt template")
    model: Optional[str] = Field(None, description="AI model identifier")
    temperature: Optional[float] = Field(None, description="Model temperature parameter")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for generation")
    visibility: Optional[str] = Field(None, description="Agent visibility setting")
    dataset_connection: Optional[str] = Field(None, description="RAG dataset connection type")
    selected_dataset_ids: Optional[List[str]] = Field(None, description="Selected dataset IDs for RAG")
    personality_config: Dict[str, Any] = Field(default_factory=dict, description="Personality configuration")
    resource_preferences: Dict[str, Any] = Field(default_factory=dict, description="Resource preferences")
    tags: List[str] = Field(default_factory=list, description="Agent tags")
    is_favorite: bool = Field(False, description="Favorite status")
    disclaimer: Optional[str] = Field(None, description="Disclaimer text shown in chat")
    easy_prompts: List[str] = Field(default_factory=list, description="Quick-access preset prompts")
    conversation_count: int = Field(0, description="Number of conversations")
    usage_count: int = Field(0, description="Number of conversations (alias for frontend compatibility)")
    total_cost_cents: int = Field(0, description="Total cost in cents")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    # Creator information
    created_by_name: Optional[str] = Field(None, description="Full name of the user who created this agent")
    # Permission flags for frontend
    can_edit: bool = Field(False, description="Whether current user can edit this agent")
    can_delete: bool = Field(False, description="Whether current user can delete this agent")
    is_owner: bool = Field(False, description="Whether current user owns this agent")
    # Team sharing configuration
    team_shares: Optional[List[Dict[str, Any]]] = Field(None, description="Team sharing configuration with per-user permissions")

    model_config = ConfigDict(from_attributes=True)


class AgentListResponse(BaseModel):
    """Response for listing agents"""
    data: List[AgentResponse] = Field(..., description="List of agents")
    total: int = Field(..., description="Total number of agents")
    limit: int = Field(..., description="Query limit")
    offset: int = Field(..., description="Query offset")


class AgentCapabilities(BaseModel):
    """Agent capabilities and resource access"""
    agent_id: str = Field(..., description="Agent UUID")
    capabilities: List[Dict[str, Any]] = Field(default_factory=list, description="Granted capabilities")
    resource_preferences: Dict[str, Any] = Field(default_factory=dict, description="Resource preferences")
    allowed_tools: List[str] = Field(default_factory=list, description="Allowed tool integrations")
    total: int = Field(..., description="Total capability count")


class AgentStatistics(BaseModel):
    """Agent usage statistics"""
    agent_id: str = Field(..., description="Agent UUID")
    name: str = Field(..., description="Agent name")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    conversation_count: int = Field(0, description="Total conversations")
    total_messages: int = Field(0, description="Total messages processed")
    total_tokens_used: int = Field(0, description="Total tokens consumed")
    total_cost_cents: int = Field(0, description="Total cost in cents")
    total_cost_dollars: float = Field(0.0, description="Total cost in dollars")
    average_tokens_per_message: float = Field(0.0, description="Average tokens per message")
    is_favorite: bool = Field(False, description="Favorite status")
    tags: List[str] = Field(default_factory=list, description="Agent tags")

    model_config = ConfigDict(from_attributes=True)


class AgentCloneRequest(BaseModel):
    """Request to clone an agent"""
    new_name: str = Field(..., description="Name for the cloned agent")
    modifications: Optional[Dict[str, Any]] = Field(None, description="Modifications to apply")