"""
Resource-specific configuration schemas for comprehensive resource management

Defines Pydantic models for validating configuration data for each resource family:
- AI/ML Resources (LLMs, embeddings, image generation, function calling)
- RAG Engine Resources (vector databases, document processing, retrieval systems)
- Agentic Workflow Resources (multi-step AI workflows, agent frameworks)
- App Integration Resources (external tools, APIs, webhooks)
- External Web Services (Canvas LMS, CTFd, Guacamole, iframe-embedded services)
- AI Literacy & Cognitive Skills (educational games, puzzles, learning content)
"""
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


# Base Configuration Schema
class BaseResourceConfig(BaseModel):
    """Base configuration for all resource types"""
    timeout_seconds: Optional[int] = Field(30, ge=1, le=3600, description="Request timeout in seconds")
    retry_attempts: Optional[int] = Field(3, ge=0, le=10, description="Number of retry attempts")
    rate_limit_per_minute: Optional[int] = Field(60, ge=1, le=10000, description="Rate limit per minute")


# AI/ML Resource Configurations
class LLMConfig(BaseResourceConfig):
    """Configuration for LLM resources"""
    max_tokens: Optional[int] = Field(4000, ge=1, le=100000, description="Maximum tokens per request")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Top-p sampling parameter")
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    stream: Optional[bool] = Field(False, description="Enable streaming responses")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    system_prompt: Optional[str] = Field(None, description="Default system prompt")


class EmbeddingConfig(BaseResourceConfig):
    """Configuration for embedding model resources"""
    dimensions: Optional[int] = Field(1536, ge=128, le=8192, description="Embedding dimensions")
    batch_size: Optional[int] = Field(100, ge=1, le=1000, description="Batch processing size")
    encoding_format: Optional[Literal["float", "base64"]] = Field("float", description="Output encoding format")
    normalize_embeddings: Optional[bool] = Field(True, description="Normalize embedding vectors")


class ImageGenerationConfig(BaseResourceConfig):
    """Configuration for image generation resources"""
    size: Optional[str] = Field("1024x1024", description="Image dimensions")
    quality: Optional[Literal["standard", "hd"]] = Field("standard", description="Image quality")
    style: Optional[Literal["natural", "vivid"]] = Field("natural", description="Image style")
    response_format: Optional[Literal["url", "b64_json"]] = Field("url", description="Response format")
    n: Optional[int] = Field(1, ge=1, le=10, description="Number of images to generate")


class FunctionCallingConfig(BaseResourceConfig):
    """Configuration for function calling resources"""
    max_tokens: Optional[int] = Field(4000, ge=1, le=100000, description="Maximum tokens per request")
    temperature: Optional[float] = Field(0.1, ge=0.0, le=2.0, description="Sampling temperature")
    function_call: Optional[Union[str, Dict[str, str]]] = Field("auto", description="Function call behavior")
    tools: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Available tools/functions")
    parallel_tool_calls: Optional[bool] = Field(True, description="Allow parallel tool calls")


# RAG Engine Configurations
class VectorDatabaseConfig(BaseResourceConfig):
    """Configuration for vector database resources"""
    chunk_size: Optional[int] = Field(512, ge=64, le=8192, description="Document chunk size")
    chunk_overlap: Optional[int] = Field(50, ge=0, le=500, description="Chunk overlap size")
    similarity_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Similarity threshold")
    max_results: Optional[int] = Field(10, ge=1, le=100, description="Maximum search results")
    rerank: Optional[bool] = Field(True, description="Enable result reranking")
    include_metadata: Optional[bool] = Field(True, description="Include document metadata")
    similarity_metric: Optional[Literal["cosine", "euclidean", "dot_product"]] = Field("cosine", description="Similarity metric")


class DocumentProcessorConfig(BaseResourceConfig):
    """Configuration for document processing resources"""
    supported_formats: Optional[List[str]] = Field(
        default_factory=lambda: ["pdf", "docx", "txt", "md", "html"],
        description="Supported document formats"
    )
    extract_images: Optional[bool] = Field(False, description="Extract images from documents")
    ocr_enabled: Optional[bool] = Field(False, description="Enable OCR for scanned documents")
    preserve_formatting: Optional[bool] = Field(True, description="Preserve document formatting")
    max_file_size_mb: Optional[int] = Field(50, ge=1, le=1000, description="Maximum file size in MB")


# Agentic Workflow Configurations
class WorkflowConfig(BaseResourceConfig):
    """Configuration for agentic workflow resources"""
    max_iterations: Optional[int] = Field(10, ge=1, le=100, description="Maximum workflow iterations")
    timeout_seconds: Optional[int] = Field(300, ge=30, le=3600, description="Workflow timeout")
    auto_approve: Optional[bool] = Field(False, description="Auto-approve workflow steps")
    human_in_loop: Optional[bool] = Field(True, description="Require human approval")
    retry_on_failure: Optional[bool] = Field(True, description="Retry failed steps")
    max_retries: Optional[int] = Field(3, ge=0, le=10, description="Maximum retry attempts per step")
    parallel_execution: Optional[bool] = Field(False, description="Enable parallel step execution")
    checkpoint_enabled: Optional[bool] = Field(True, description="Save workflow checkpoints")


class AgentFrameworkConfig(BaseResourceConfig):
    """Configuration for agent framework resources"""
    agent_type: Optional[str] = Field("conversational", description="Type of agent")
    memory_enabled: Optional[bool] = Field(True, description="Enable agent memory")
    memory_type: Optional[Literal["buffer", "summary", "vector"]] = Field("buffer", description="Memory storage type")
    max_memory_size: Optional[int] = Field(1000, ge=100, le=10000, description="Maximum memory entries")
    tools_enabled: Optional[bool] = Field(True, description="Enable agent tools")
    max_tool_calls: Optional[int] = Field(5, ge=1, le=20, description="Maximum tool calls per turn")


# App Integration Configurations
class APIIntegrationConfig(BaseResourceConfig):
    """Configuration for API integration resources"""
    auth_method: Optional[Literal["api_key", "bearer_token", "oauth2", "basic_auth"]] = Field("api_key", description="Authentication method")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Default headers")
    webhook_enabled: Optional[bool] = Field(False, description="Enable webhook support")
    webhook_secret: Optional[str] = Field(None, description="Webhook validation secret")
    rate_limit_strategy: Optional[Literal["fixed", "sliding", "token_bucket"]] = Field("fixed", description="Rate limiting strategy")


class WebhookConfig(BaseResourceConfig):
    """Configuration for webhook resources"""
    endpoint_url: Optional[str] = Field(None, description="Webhook endpoint URL")
    secret_token: Optional[str] = Field(None, description="Secret for webhook validation")
    supported_events: Optional[List[str]] = Field(default_factory=list, description="Supported event types")
    retry_policy: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"max_retries": 3, "backoff_multiplier": 2},
        description="Retry policy for failed webhooks"
    )
    signature_header: Optional[str] = Field("X-Hub-Signature-256", description="Signature header name")


# External Service Configurations
class IframeServiceConfig(BaseResourceConfig):
    """Configuration for iframe-embedded external services"""
    iframe_url: str = Field(..., description="URL to embed in iframe")
    sandbox_permissions: Optional[List[str]] = Field(
        default_factory=lambda: ["allow-same-origin", "allow-scripts", "allow-forms", "allow-popups"],
        description="Iframe sandbox permissions"
    )
    csp_policy: Optional[str] = Field("default-src 'self'", description="Content Security Policy")
    session_timeout: Optional[int] = Field(3600, ge=300, le=86400, description="Session timeout in seconds")
    auto_logout: Optional[bool] = Field(True, description="Auto logout on session timeout")
    single_sign_on: Optional[bool] = Field(True, description="Enable single sign-on")
    resize_enabled: Optional[bool] = Field(True, description="Allow iframe resizing")
    width: Optional[str] = Field("100%", description="Iframe width")
    height: Optional[str] = Field("600px", description="Iframe height")


class LMSIntegrationConfig(IframeServiceConfig):
    """Configuration for Learning Management System integration"""
    lms_type: Optional[Literal["canvas", "moodle", "blackboard", "schoology"]] = Field("canvas", description="LMS platform type")
    course_id: Optional[str] = Field(None, description="Course identifier")
    assignment_sync: Optional[bool] = Field(True, description="Sync assignments")
    grade_passback: Optional[bool] = Field(True, description="Enable grade passback")
    enrollment_sync: Optional[bool] = Field(False, description="Sync enrollments")


class CyberRangeConfig(IframeServiceConfig):
    """Configuration for cyber range environments (CTFd, Guacamole, etc.)"""
    platform_type: Optional[Literal["ctfd", "guacamole", "custom"]] = Field("ctfd", description="Cyber range platform")
    vm_template: Optional[str] = Field(None, description="Virtual machine template")
    network_isolation: Optional[bool] = Field(True, description="Enable network isolation")
    auto_destroy: Optional[bool] = Field(True, description="Auto-destroy sessions")
    max_session_duration: Optional[int] = Field(14400, ge=1800, le=86400, description="Maximum session duration")
    resource_limits: Optional[Dict[str, str]] = Field(
        default_factory=lambda: {"cpu": "2", "memory": "4Gi", "storage": "20Gi"},
        description="Resource limits for VMs"
    )


# AI Literacy Configurations
class StrategicGameConfig(BaseResourceConfig):
    """Configuration for strategic games (Chess, Go, etc.)"""
    game_type: Literal["chess", "go", "poker", "bridge", "custom"] = Field(..., description="Type of strategic game")
    ai_opponent_model: Optional[str] = Field(None, description="AI model for opponent")
    difficulty_levels: Optional[List[str]] = Field(
        default_factory=lambda: ["beginner", "intermediate", "expert", "adaptive"],
        description="Available difficulty levels"
    )
    explanation_mode: Optional[bool] = Field(True, description="Provide move explanations")
    hint_system: Optional[bool] = Field(True, description="Enable hints")
    multiplayer_enabled: Optional[bool] = Field(False, description="Support multiple players")
    time_controls: Optional[Dict[str, int]] = Field(
        default_factory=lambda: {"blitz": 300, "rapid": 900, "classical": 1800},
        description="Time control options in seconds"
    )


class LogicPuzzleConfig(BaseResourceConfig):
    """Configuration for logic puzzles"""
    puzzle_types: Optional[List[str]] = Field(
        default_factory=lambda: ["sudoku", "logic_grid", "lateral_thinking", "mathematical"],
        description="Types of puzzles available"
    )
    difficulty_adaptive: Optional[bool] = Field(True, description="Adapt difficulty based on performance")
    progress_tracking: Optional[bool] = Field(True, description="Track user progress")
    hint_system: Optional[bool] = Field(True, description="Provide hints")
    time_limits: Optional[bool] = Field(False, description="Enable time limits")
    collaborative_solving: Optional[bool] = Field(False, description="Allow collaborative solving")


class PhilosophicalDilemmaConfig(BaseResourceConfig):
    """Configuration for philosophical dilemma resources"""
    dilemma_categories: Optional[List[str]] = Field(
        default_factory=lambda: ["ethics", "epistemology", "metaphysics", "logic"],
        description="Categories of philosophical dilemmas"
    )
    ai_socratic_method: Optional[bool] = Field(True, description="Use AI for Socratic questioning")
    debate_mode: Optional[bool] = Field(True, description="Enable debate functionality")
    argument_analysis: Optional[bool] = Field(True, description="Analyze argument structure")
    bias_detection: Optional[bool] = Field(True, description="Detect cognitive biases")
    multi_perspective: Optional[bool] = Field(True, description="Present multiple perspectives")


class EducationalContentConfig(BaseResourceConfig):
    """Configuration for educational content resources"""
    content_type: Optional[Literal["interactive", "video", "text", "mixed"]] = Field("mixed", description="Type of content")
    adaptive_learning: Optional[bool] = Field(True, description="Adapt to learner progress")
    assessment_enabled: Optional[bool] = Field(True, description="Include assessments")
    prerequisite_checking: Optional[bool] = Field(True, description="Check prerequisites")
    learning_analytics: Optional[bool] = Field(True, description="Collect learning analytics")
    personalization_level: Optional[Literal["none", "basic", "advanced"]] = Field("basic", description="Personalization level")


# Configuration Union Type
ResourceConfigType = Union[
    # AI/ML
    LLMConfig,
    EmbeddingConfig,
    ImageGenerationConfig,
    FunctionCallingConfig,
    # RAG Engine
    VectorDatabaseConfig,
    DocumentProcessorConfig,
    # Agentic Workflow
    WorkflowConfig,
    AgentFrameworkConfig,
    # App Integration
    APIIntegrationConfig,
    WebhookConfig,
    # External Service
    IframeServiceConfig,
    LMSIntegrationConfig,
    CyberRangeConfig,
    # AI Literacy
    StrategicGameConfig,
    LogicPuzzleConfig,
    PhilosophicalDilemmaConfig,
    EducationalContentConfig
]


def get_config_schema(resource_type: str, resource_subtype: str) -> BaseResourceConfig:
    """Get the appropriate configuration schema for a resource type and subtype"""
    if resource_type == "ai_ml":
        if resource_subtype == "llm":
            return LLMConfig()
        elif resource_subtype == "embedding":
            return EmbeddingConfig()
        elif resource_subtype == "image_generation":
            return ImageGenerationConfig()
        elif resource_subtype == "function_calling":
            return FunctionCallingConfig()
    elif resource_type == "rag_engine":
        if resource_subtype == "vector_database":
            return VectorDatabaseConfig()
        elif resource_subtype == "document_processor":
            return DocumentProcessorConfig()
    elif resource_type == "agentic_workflow":
        if resource_subtype == "workflow":
            return WorkflowConfig()
        elif resource_subtype == "agent_framework":
            return AgentFrameworkConfig()
    elif resource_type == "app_integration":
        if resource_subtype == "api":
            return APIIntegrationConfig()
        elif resource_subtype == "webhook":
            return WebhookConfig()
    elif resource_type == "external_service":
        if resource_subtype == "lms":
            return LMSIntegrationConfig()
        elif resource_subtype == "cyber_range":
            return CyberRangeConfig()
        elif resource_subtype == "iframe":
            return IframeServiceConfig()
    elif resource_type == "ai_literacy":
        if resource_subtype == "strategic_game":
            return StrategicGameConfig()
        elif resource_subtype == "logic_puzzle":
            return LogicPuzzleConfig()
        elif resource_subtype == "philosophical_dilemma":
            return PhilosophicalDilemmaConfig()
        elif resource_subtype == "educational_content":
            return EducationalContentConfig()
    
    # Default fallback
    return BaseResourceConfig()


def validate_resource_config(resource_type: str, resource_subtype: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate resource configuration data against the appropriate schema"""
    schema = get_config_schema(resource_type, resource_subtype)
    
    # Create instance with provided data
    if resource_type == "ai_ml":
        if resource_subtype == "llm":
            validated = LLMConfig(**config_data)
        elif resource_subtype == "embedding":
            validated = EmbeddingConfig(**config_data)
        elif resource_subtype == "image_generation":
            validated = ImageGenerationConfig(**config_data)
        elif resource_subtype == "function_calling":
            validated = FunctionCallingConfig(**config_data)
        else:
            validated = BaseResourceConfig(**config_data)
    elif resource_type == "rag_engine":
        if resource_subtype == "vector_database":
            validated = VectorDatabaseConfig(**config_data)
        elif resource_subtype == "document_processor":
            validated = DocumentProcessorConfig(**config_data)
        else:
            validated = BaseResourceConfig(**config_data)
    elif resource_type == "agentic_workflow":
        if resource_subtype == "workflow":
            validated = WorkflowConfig(**config_data)
        elif resource_subtype == "agent_framework":
            validated = AgentFrameworkConfig(**config_data)
        else:
            validated = BaseResourceConfig(**config_data)
    elif resource_type == "app_integration":
        if resource_subtype == "api":
            validated = APIIntegrationConfig(**config_data)
        elif resource_subtype == "webhook":
            validated = WebhookConfig(**config_data)
        else:
            validated = BaseResourceConfig(**config_data)
    elif resource_type == "external_service":
        if resource_subtype == "lms":
            validated = LMSIntegrationConfig(**config_data)
        elif resource_subtype == "cyber_range":
            validated = CyberRangeConfig(**config_data)
        elif resource_subtype == "iframe":
            validated = IframeServiceConfig(**config_data)
        else:
            validated = BaseResourceConfig(**config_data)
    elif resource_type == "ai_literacy":
        if resource_subtype == "strategic_game":
            validated = StrategicGameConfig(**config_data)
        elif resource_subtype == "logic_puzzle":
            validated = LogicPuzzleConfig(**config_data)
        elif resource_subtype == "philosophical_dilemma":
            validated = PhilosophicalDilemmaConfig(**config_data)
        elif resource_subtype == "educational_content":
            validated = EducationalContentConfig(**config_data)
        else:
            validated = BaseResourceConfig(**config_data)
    else:
        validated = BaseResourceConfig(**config_data)
    
    return validated.dict(exclude_unset=True)