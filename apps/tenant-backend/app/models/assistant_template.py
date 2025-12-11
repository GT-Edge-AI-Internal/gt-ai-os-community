"""
Agent Template Models for GT 2.0

Defines agent templates, custom builders, and MCP integration models.
Follows the simplified hierarchy with file-based storage.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import json
from pathlib import Path

from app.models.access_group import AccessGroup, Resource


class AssistantType(str, Enum):
    """Pre-defined agent types from architecture"""
    RESEARCH = "research_assistant"
    CODING = "coding_assistant"
    CYBER_ANALYST = "cyber_analyst"
    EDUCATIONAL = "educational_tutor"
    CUSTOM = "custom"


class PersonalityConfig(BaseModel):
    """Agent personality configuration"""
    tone: str = Field(default="balanced", description="formal | balanced | casual")
    explanation_depth: str = Field(default="intermediate", description="beginner | intermediate | expert")
    interaction_style: str = Field(default="collaborative", description="teaching | collaborative | direct")


class ResourcePreferences(BaseModel):
    """Agent resource preferences"""
    primary_llm: str = Field(default="gpt-4", description="Primary LLM model")
    fallback_models: List[str] = Field(default_factory=list, description="Fallback model list")
    context_length: int = Field(default=4000, description="Maximum context length")
    temperature: float = Field(default=0.7, description="Response temperature")
    streaming_enabled: bool = Field(default=True, description="Enable streaming responses")


class MemorySettings(BaseModel):
    """Agent memory configuration"""
    conversation_retention: str = Field(default="session", description="session | temporary | permanent")
    context_window_size: int = Field(default=10, description="Number of messages to retain")
    learning_from_interactions: bool = Field(default=False, description="Learn from user interactions")
    max_memory_size_mb: int = Field(default=50, description="Maximum memory size in MB")


class AssistantTemplate(BaseModel):
    """
    Pre-configured agent template
    Stored in Resource Cluster library
    """
    template_id: str
    name: str
    description: str
    category: AssistantType
    
    # Core configuration
    system_prompt: str = Field(description="System prompt with variable substitution")
    default_capabilities: List[str] = Field(default_factory=list, description="Default capability requirements")
    
    # Configurations
    personality_config: PersonalityConfig = Field(default_factory=PersonalityConfig)
    resource_preferences: ResourcePreferences = Field(default_factory=ResourcePreferences)
    memory_settings: MemorySettings = Field(default_factory=MemorySettings)
    
    # Metadata
    icon_path: Optional[str] = None
    version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Access control
    required_access_groups: List[str] = Field(default_factory=list)
    minimum_role: Optional[str] = None
    
    def to_instance(self, user_id: str, instance_name: str, tenant_domain: str) -> "AssistantInstance":
        """Create an instance from this template"""
        return AssistantInstance(
            id=f"{user_id}-{instance_name}-{datetime.utcnow().timestamp()}",
            template_id=self.template_id,
            name=instance_name,
            description=f"Instance of {self.name}",
            owner_id=user_id,
            tenant_domain=tenant_domain,
            
            # Copy configurations
            system_prompt=self.system_prompt,
            capabilities=self.default_capabilities.copy(),
            personality_config=self.personality_config.model_copy(),
            resource_preferences=self.resource_preferences.model_copy(),
            memory_settings=self.memory_settings.model_copy(),
            
            # Instance specific
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )


class AssistantInstance(Resource):
    """
    User's instance of an agent
    Inherits from Resource for access control
    """
    template_id: Optional[str] = Field(default=None, description="Source template if from template")
    
    # Agent configuration
    system_prompt: str
    capabilities: List[str] = Field(default_factory=list)
    personality_config: PersonalityConfig = Field(default_factory=PersonalityConfig)
    resource_preferences: ResourcePreferences = Field(default_factory=ResourcePreferences)
    memory_settings: MemorySettings = Field(default_factory=MemorySettings)
    
    # Resource bindings
    linked_datasets: List[str] = Field(default_factory=list, description="Linked RAG dataset IDs")
    linked_tools: List[str] = Field(default_factory=list, description="Linked tool/integration IDs")
    linked_models: List[str] = Field(default_factory=list, description="Specific model overrides")
    
    # Usage tracking
    conversation_count: int = Field(default=0)
    total_messages: int = Field(default=0)
    total_tokens_used: int = Field(default=0)
    last_used: Optional[datetime] = None
    
    # File storage paths (created by controller)
    config_file_path: Optional[str] = None
    memory_file_path: Optional[str] = None
    
    def get_file_structure(self) -> Dict[str, str]:
        """Get expected file structure for agent storage"""
        base_path = f"/data/{self.tenant_domain}/users/{self.owner_id}/agents/{self.id}"
        return {
            "config": f"{base_path}/config.json",
            "prompt": f"{base_path}/prompt.md",
            "capabilities": f"{base_path}/capabilities.json",
            "memory": f"{base_path}/memory/",
            "resources": f"{base_path}/resources/"
        }
    
    def update_from_template(self, template: AssistantTemplate):
        """Update instance from template (for version updates)"""
        self.system_prompt = template.system_prompt
        self.personality_config = template.personality_config.model_copy()
        self.resource_preferences = template.resource_preferences.model_copy()
        self.updated_at = datetime.utcnow()
    
    def add_linked_dataset(self, dataset_id: str):
        """Link a RAG dataset to this agent"""
        if dataset_id not in self.linked_datasets:
            self.linked_datasets.append(dataset_id)
            self.updated_at = datetime.utcnow()
    
    def remove_linked_dataset(self, dataset_id: str):
        """Unlink a RAG dataset"""
        if dataset_id in self.linked_datasets:
            self.linked_datasets.remove(dataset_id)
            self.updated_at = datetime.utcnow()


class AssistantBuilder(BaseModel):
    """Configuration for building custom agents"""
    name: str
    description: Optional[str] = None
    base_template: Optional[AssistantType] = None
    
    # Custom configuration
    system_prompt: str
    personality_config: PersonalityConfig = Field(default_factory=PersonalityConfig)
    resource_preferences: ResourcePreferences = Field(default_factory=ResourcePreferences)
    memory_settings: MemorySettings = Field(default_factory=MemorySettings)
    
    # Capabilities
    requested_capabilities: List[str] = Field(default_factory=list)
    required_models: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    
    def build_instance(self, user_id: str, tenant_domain: str) -> AssistantInstance:
        """Build agent instance from configuration"""
        return AssistantInstance(
            id=f"custom-{user_id}-{datetime.utcnow().timestamp()}",
            template_id=None,  # Custom build
            name=self.name,
            description=self.description or f"Custom agent by {user_id}",
            owner_id=user_id,
            tenant_domain=tenant_domain,
            resource_type="agent",
            
            # Apply configurations
            system_prompt=self.system_prompt,
            capabilities=self.requested_capabilities,
            personality_config=self.personality_config,
            resource_preferences=self.resource_preferences,
            memory_settings=self.memory_settings,
            
            # Default access
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )


# Pre-defined templates from architecture
BUILTIN_TEMPLATES = {
    AssistantType.RESEARCH: AssistantTemplate(
        template_id="research_assistant_v1",
        name="Research & Analysis Agent",
        description="Specialized in information synthesis and analysis with citations",
        category=AssistantType.RESEARCH,
        system_prompt="""You are a research agent specialized in information synthesis and analysis.
Focus on providing well-sourced, analytical responses with clear reasoning.
Always cite your sources and provide evidence for your claims.
When uncertain, clearly state the limitations of your knowledge.""",
        default_capabilities=[
            "llm:gpt-4",
            "rag:semantic_search",
            "tools:web_search",
            "export:citations"
        ],
        personality_config=PersonalityConfig(
            tone="formal",
            explanation_depth="expert",
            interaction_style="collaborative"
        ),
        resource_preferences=ResourcePreferences(
            primary_llm="gpt-4",
            fallback_models=["claude-sonnet", "gpt-3.5-turbo"],
            context_length=8000,
            temperature=0.7
        ),
        required_access_groups=["research_tools"]
    ),
    
    AssistantType.CODING: AssistantTemplate(
        template_id="coding_assistant_v1",
        name="Software Development Agent",
        description="Code quality, debugging, and development best practices",
        category=AssistantType.CODING,
        system_prompt="""You are a software development agent focused on code quality and best practices.
Provide clear explanations, suggest improvements, and help debug issues.
Follow the principle of clean, maintainable code.
Always consider security implications in your suggestions.""",
        default_capabilities=[
            "llm:claude-sonnet",
            "tools:github_integration",
            "resources:documentation",
            "export:code_snippets"
        ],
        personality_config=PersonalityConfig(
            tone="balanced",
            explanation_depth="intermediate",
            interaction_style="direct"
        ),
        resource_preferences=ResourcePreferences(
            primary_llm="claude-sonnet",
            fallback_models=["gpt-4", "codellama"],
            context_length=16000,
            temperature=0.5
        ),
        required_access_groups=["development_tools"]
    ),
    
    AssistantType.CYBER_ANALYST: AssistantTemplate(
        template_id="cyber_analyst_v1",
        name="Cybersecurity Analysis Agent",
        description="Threat detection, incident response, and security best practices",
        category=AssistantType.CYBER_ANALYST,
        system_prompt="""You are a cybersecurity analyst agent for threat detection and response.
Prioritize security best practices and provide actionable recommendations.
Consider defense-in-depth strategies and zero-trust principles.
Always emphasize the importance of continuous monitoring and improvement.""",
        default_capabilities=[
            "llm:gpt-4",
            "tools:security_scanning",
            "resources:threat_intelligence",
            "export:security_reports"
        ],
        personality_config=PersonalityConfig(
            tone="formal",
            explanation_depth="expert",
            interaction_style="direct"
        ),
        resource_preferences=ResourcePreferences(
            primary_llm="gpt-4",
            fallback_models=["claude-sonnet"],
            context_length=8000,
            temperature=0.3
        ),
        required_access_groups=["cybersecurity_advanced"]
    ),
    
    AssistantType.EDUCATIONAL: AssistantTemplate(
        template_id="educational_tutor_v1",
        name="AI Literacy Educational Agent",
        description="Critical thinking development and AI collaboration skills",
        category=AssistantType.EDUCATIONAL,
        system_prompt="""You are an educational agent focused on developing critical thinking and AI literacy.
Use socratic questioning and encourage deep analysis of problems.
Help students understand both the capabilities and limitations of AI.
Foster independent thinking while teaching effective AI collaboration.""",
        default_capabilities=[
            "llm:claude-sonnet",
            "games:strategic_thinking",
            "puzzles:logic_reasoning",
            "analytics:learning_progress"
        ],
        personality_config=PersonalityConfig(
            tone="casual",
            explanation_depth="beginner",
            interaction_style="teaching"
        ),
        resource_preferences=ResourcePreferences(
            primary_llm="claude-sonnet",
            fallback_models=["gpt-4"],
            context_length=4000,
            temperature=0.8
        ),
        required_access_groups=["ai_literacy"]
    )
}


class AssistantTemplateLibrary:
    """
    Manages the agent template library
    Templates stored in Resource Cluster, cached locally
    """
    
    def __init__(self, resource_cluster_url: str):
        self.resource_cluster_url = resource_cluster_url
        self.cache_path = Path("/tmp/agent_templates_cache")
        self.cache_path.mkdir(exist_ok=True)
        self._templates_cache: Dict[str, AssistantTemplate] = {}
    
    async def get_template(self, template_id: str) -> Optional[AssistantTemplate]:
        """Get template by ID, using cache if available"""
        if template_id in self._templates_cache:
            return self._templates_cache[template_id]
        
        # Check built-in templates
        for template_type, template in BUILTIN_TEMPLATES.items():
            if template.template_id == template_id:
                self._templates_cache[template_id] = template
                return template
        
        # Would fetch from Resource Cluster in production
        return None
    
    async def list_templates(
        self, 
        category: Optional[AssistantType] = None,
        access_groups: Optional[List[str]] = None
    ) -> List[AssistantTemplate]:
        """List available templates with filtering"""
        templates = list(BUILTIN_TEMPLATES.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if access_groups:
            templates = [
                t for t in templates 
                if any(g in access_groups for g in t.required_access_groups)
            ]
        
        return templates
    
    async def deploy_template(
        self,
        template_id: str,
        user_id: str,
        instance_name: str,
        tenant_domain: str,
        customizations: Optional[Dict[str, Any]] = None
    ) -> AssistantInstance:
        """Deploy template as user instance"""
        template = await self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Create instance
        instance = template.to_instance(user_id, instance_name, tenant_domain)
        
        # Apply customizations
        if customizations:
            if "personality" in customizations:
                instance.personality_config = PersonalityConfig(**customizations["personality"])
            if "resources" in customizations:
                instance.resource_preferences = ResourcePreferences(**customizations["resources"])
            if "memory" in customizations:
                instance.memory_settings = MemorySettings(**customizations["memory"])
        
        return instance


# API Models
class AssistantTemplateResponse(BaseModel):
    """API response for agent template"""
    template_id: str
    name: str
    description: str
    category: str
    required_access_groups: List[str]
    version: str
    created_at: datetime


class AssistantInstanceResponse(BaseModel):
    """API response for agent instance"""
    id: str
    name: str
    description: str
    template_id: Optional[str]
    owner_id: str
    access_group: AccessGroup
    team_members: List[str]
    conversation_count: int
    last_used: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class CreateAssistantRequest(BaseModel):
    """Request to create agent from template or custom"""
    template_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    customizations: Optional[Dict[str, Any]] = None
    
    # For custom agents
    system_prompt: Optional[str] = None
    personality_config: Optional[PersonalityConfig] = None
    resource_preferences: Optional[ResourcePreferences] = None
    memory_settings: Optional[MemorySettings] = None