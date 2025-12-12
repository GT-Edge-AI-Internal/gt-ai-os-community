"""
GT 2.0 Agent Model - Service-Based Architecture

Pydantic models for agent entities using the PostgreSQL + PGVector backend.
Complete migration - all assistant terminology has been replaced with agent.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import Field, ConfigDict, field_validator
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


class AgentStatus(str, Enum):
    """Agent status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class AgentVisibility(str, Enum):
    """Agent visibility levels"""
    INDIVIDUAL = "individual"
    TEAM = "team"  
    ORGANIZATION = "organization"


class Agent(BaseServiceModel):
    """
    Agent model for GT 2.0 service-based architecture.
    
    Represents an AI agent configuration with capabilities, model settings,
    and access control for perfect tenant isolation.
    """
    
    # Core agent properties
    name: str = Field(..., min_length=1, max_length=255, description="Agent display name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent description")
    instructions: Optional[str] = Field(None, description="System instructions for the agent")
    
    # Model configuration
    model_provider: str = Field(default="groq", description="AI model provider")
    model_name: str = Field(default="llama3-groq-8b-8192-tool-use-preview", description="Model identifier")
    model_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Model-specific configuration")
    
    # Capabilities and tools
    capabilities: Optional[List[str]] = Field(default_factory=list, description="Agent capabilities")
    tools: Optional[List[str]] = Field(default_factory=list, description="Available tools")

    # MCP (Model Context Protocol) tool configuration
    mcp_servers: Optional[List[str]] = Field(default_factory=list, description="MCP servers this agent can access")
    rag_enabled: bool = Field(default=False, description="Whether agent can access RAG tools")
    
    # Access control
    owner_id: str = Field(..., description="User ID of the agent owner")
    access_group: str = Field(default="individual", description="Access group for sharing")
    visibility: AgentVisibility = Field(default=AgentVisibility.INDIVIDUAL, description="Agent visibility level")
    
    # Status and metadata
    status: AgentStatus = Field(default=AgentStatus.ACTIVE, description="Agent status")
    featured: bool = Field(default=False, description="Whether agent is featured")
    tags: Optional[List[str]] = Field(default_factory=list, description="Agent tags for categorization")
    category: Optional[str] = Field(None, max_length=100, description="Agent category")
    
    # Usage statistics
    conversation_count: int = Field(default=0, description="Number of conversations")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")

    # UI/UX Enhancement Fields
    disclaimer: Optional[str] = Field(None, max_length=500, description="Disclaimer text shown in chat")
    easy_prompts: Optional[List[str]] = Field(default_factory=list, max_length=10, description="Quick-access preset prompts (max 10)")

    @field_validator('disclaimer')
    @classmethod
    def validate_disclaimer(cls, v):
        """Validate disclaimer length"""
        if v and len(v) > 500:
            raise ValueError('Disclaimer must be 500 characters or less')
        return v

    @field_validator('easy_prompts')
    @classmethod
    def validate_easy_prompts(cls, v):
        """Validate easy prompts count"""
        if v and len(v) > 10:
            raise ValueError('Maximum 10 easy prompts allowed')
        return v

    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),  # Allow model_ fields
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "agents"
    
    def increment_usage(self):
        """Increment usage statistics"""
        self.conversation_count += 1
        self.last_used_at = datetime.utcnow()
        self.update_timestamp()


class AgentCreate(BaseCreateModel):
    """Model for creating new agents"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    instructions: Optional[str] = None
    model_provider: str = Field(default="groq")
    model_name: str = Field(default="llama3-groq-8b-8192-tool-use-preview")
    model_settings: Optional[Dict[str, Any]] = Field(default_factory=dict)
    capabilities: Optional[List[str]] = Field(default_factory=list)
    tools: Optional[List[str]] = Field(default_factory=list)
    mcp_servers: Optional[List[str]] = Field(default_factory=list)
    rag_enabled: bool = Field(default=False)
    owner_id: str
    access_group: str = Field(default="individual")
    visibility: AgentVisibility = Field(default=AgentVisibility.INDIVIDUAL)
    tags: Optional[List[str]] = Field(default_factory=list)
    category: Optional[str] = None
    disclaimer: Optional[str] = Field(None, max_length=500)
    easy_prompts: Optional[List[str]] = Field(default_factory=list)

    model_config = ConfigDict(protected_namespaces=())


class AgentUpdate(BaseUpdateModel):
    """Model for updating agents"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    instructions: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_settings: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    access_group: Optional[str] = None
    visibility: Optional[AgentVisibility] = None
    status: Optional[AgentStatus] = None
    featured: Optional[bool] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    disclaimer: Optional[str] = None
    easy_prompts: Optional[List[str]] = None

    model_config = ConfigDict(protected_namespaces=())


class AgentResponse(BaseResponseModel):
    """Model for agent API responses"""
    id: str
    name: str
    description: Optional[str]
    instructions: Optional[str]
    model_provider: str
    model_name: str
    model_settings: Dict[str, Any]
    capabilities: List[str]
    tools: List[str]
    owner_id: str
    access_group: str
    visibility: AgentVisibility
    status: AgentStatus
    featured: bool
    tags: List[str]
    category: Optional[str]
    conversation_count: int
    usage_count: int = 0  # Alias for conversation_count for frontend compatibility
    last_used_at: Optional[datetime]
    disclaimer: Optional[str]
    easy_prompts: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(protected_namespaces=())


