"""
GT 2.0 Resource Cluster Configuration

Central configuration for the air-gapped Resource Cluster that manages
all AI resources, document processing, and external service integrations.
"""

import os
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Resource Cluster settings with environment variable support"""
    
    # Environment
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Service Identity
    cluster_name: str = Field(default="gt-resource-cluster", description="Cluster identifier")
    service_port: int = Field(default=8003, description="Service port")
    
    # Security
    secret_key: str = Field(..., description="JWT signing key for capability tokens")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    capability_token_expire_minutes: int = Field(default=60, description="Capability token expiry")
    
    # External LLM Providers (via HAProxy)
    groq_api_key: Optional[str] = Field(default=None, description="Groq Cloud API key")
    groq_endpoints: List[str] = Field(
        default=["https://api.groq.com/openai/v1"],
        description="Groq API endpoints for load balancing"
    )
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")

    # NVIDIA NIM Configuration
    nvidia_nim_endpoint: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="NVIDIA NIM API endpoint (cloud or self-hosted)"
    )
    nvidia_nim_enabled: bool = Field(
        default=True,
        description="Enable NVIDIA NIM backend for GPU-accelerated inference"
    )
    
    # HAProxy Configuration
    haproxy_groq_endpoint: str = Field(
        default="http://haproxy-groq-lb-service.gt-resource.svc.cluster.local",
        description="HAProxy load balancer endpoint for Groq API"
    )
    haproxy_stats_endpoint: str = Field(
        default="http://haproxy-groq-lb-service.gt-resource.svc.cluster.local:8404/stats",
        description="HAProxy statistics endpoint"
    )
    haproxy_admin_socket: str = Field(
        default="/var/run/haproxy.sock",
        description="HAProxy admin socket for runtime configuration"
    )
    haproxy_enabled: bool = Field(
        default=True,
        description="Enable HAProxy load balancing for external APIs"
    )
    
    # Control Panel Integration (for API key retrieval)
    control_panel_url: str = Field(
        default="http://control-panel-backend:8000",
        description="Control Panel internal API URL for service-to-service calls"
    )
    service_auth_token: str = Field(
        default="internal-service-token",
        description="Service-to-service authentication token"
    )

    # Admin Cluster Configuration Sync
    admin_cluster_url: str = Field(
        default="http://localhost:8001",
        description="Admin cluster URL for configuration sync"
    )
    config_sync_interval: int = Field(
        default=10,
        description="Configuration sync interval in seconds"
    )
    config_sync_enabled: bool = Field(
        default=True,
        description="Enable automatic configuration sync from admin cluster"
    )
    
    # Consul Service Discovery
    consul_host: str = Field(default="localhost", description="Consul host")
    consul_port: int = Field(default=8500, description="Consul port")
    consul_token: Optional[str] = Field(default=None, description="Consul ACL token")
    
    # Document Processing
    chunking_engine_workers: int = Field(default=4, description="Parallel document processors")
    max_document_size_mb: int = Field(default=50, description="Maximum document size")
    supported_document_types: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".md", ".html", ".pptx", ".xlsx", ".csv"],
        description="Supported document formats"
    )

    # BGE-M3 Embedding Configuration
    embedding_endpoint: str = Field(
        default="http://gentwo-vllm-embeddings:8000/v1/embeddings",
        description="Default embedding endpoint (local or external)"
    )
    bge_m3_local_mode: bool = Field(
        default=True,
        description="Use local BGE-M3 embedding service (True) or external endpoint (False)"
    )
    bge_m3_external_endpoint: Optional[str] = Field(
        default=None,
        description="External BGE-M3 embedding endpoint URL (when local_mode=False)"
    )
    
    # Vector Database (ChromaDB)
    chromadb_host: str = Field(default="localhost", description="ChromaDB host")
    chromadb_port: int = Field(default=8000, description="ChromaDB port")
    chromadb_encryption_key: Optional[str] = Field(
        default=None,
        description="Encryption key for vector storage"
    )
    
    # Resource Limits
    max_concurrent_inferences: int = Field(default=100, description="Max concurrent LLM calls")
    max_tokens_per_request: int = Field(default=8000, description="Max tokens per LLM request")
    rate_limit_requests_per_minute: int = Field(default=60, description="Global rate limit")
    
    # Storage Paths
    data_directory: str = Field(
        default="/tmp/gt2-resource-cluster" if os.getenv("ENVIRONMENT") != "production" else "/data/resource-cluster",
        description="Base data directory"
    )
    template_library_path: str = Field(
        default="/tmp/gt2-resource-cluster/templates" if os.getenv("ENVIRONMENT") != "production" else "/data/resource-cluster/templates",
        description="Agent template library"
    )
    models_cache_path: str = Field(  # Renamed to avoid pydantic warning
        default="/tmp/gt2-resource-cluster/models" if os.getenv("ENVIRONMENT") != "production" else "/data/resource-cluster/models",
        description="Local model cache"
    )
    
    # Redis removed - Resource Cluster uses PostgreSQL for caching and rate limiting
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9091, description="Prometheus metrics port")
    
    # CORS Configuration (for tenant backends)
    cors_origins: List[str] = Field(
        default=["http://localhost:8002", "https://*.gt2.com"],
        description="Allowed CORS origins"
    )
    
    # Trusted Host Configuration
    trusted_hosts: List[str] = Field(
        default=["localhost", "*.gt2.com", "resource-cluster", "gentwo-resource-backend", 
                 "gt2-resource-backend", "testserver", "127.0.0.1", "*"],
        description="Allowed host headers for TrustedHostMiddleware"
    )
    
    # Feature Flags
    enable_model_caching: bool = Field(default=True, description="Cache model responses")
    enable_usage_tracking: bool = Field(default=True, description="Track resource usage")
    enable_cost_calculation: bool = Field(default=True, description="Calculate usage costs")
    
    @validator("data_directory")
    def validate_data_directory(cls, v):
        # Ensure directory exists with secure permissions
        os.makedirs(v, exist_ok=True, mode=0o700)
        return v
    
    @validator("template_library_path")
    def validate_template_library_path(cls, v):
        os.makedirs(v, exist_ok=True, mode=0o700)
        return v
    
    @validator("models_cache_path")
    def validate_models_cache_path(cls, v):
        os.makedirs(v, exist_ok=True, mode=0o700)
        return v
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


def get_settings(tenant_id: Optional[str] = None) -> Settings:
    """Get tenant-scoped application settings"""
    # For development, use a simple cache without tenant isolation
    if os.getenv("ENVIRONMENT") == "development":
        return Settings()
    
    # In production, settings should be tenant-scoped
    # This prevents global state from affecting tenant isolation
    if tenant_id:
        # Create tenant-specific settings with proper isolation
        settings = Settings()
        # Add tenant-specific configurations here if needed
        return settings
    else:
        # Default settings for non-tenant operations
        return Settings()


def get_resource_families(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get tenant-scoped resource family definitions (from CLAUDE.md)"""
    # Base resource families - can be extended per tenant in production
    return {
        "ai_ml": {
            "name": "AI/ML Resources",
            "subtypes": ["llm", "embedding", "image_generation", "function_calling"]
        },
        "rag_engine": {
            "name": "RAG Engine Resources",
            "subtypes": ["vector_db", "document_processor", "semantic_search", "retrieval"]
        },
        "agentic_workflow": {
            "name": "Agentic Workflow Resources",
            "subtypes": ["single_agent", "multi_agent", "orchestration", "memory"]
        },
        "app_integration": {
            "name": "App Integration Resources",
            "subtypes": ["oauth2", "webhook", "api_connector", "database_connector"]
        },
        "external_service": {
            "name": "External Web Services",
            "subtypes": ["iframe_embed", "sso_service", "remote_desktop", "learning_platform"]
        },
        "ai_literacy": {
            "name": "AI Literacy & Cognitive Skills",
            "subtypes": ["strategic_game", "logic_puzzle", "philosophical_dilemma", "educational_content"]
        }
    }

def get_model_configs(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get tenant-scoped model configurations for different providers"""
    # Base model configurations - can be customized per tenant in production
    return {
        "groq": {
            "llama-3.1-70b-versatile": {
                "max_tokens": 8000,
                "cost_per_1k_tokens": 0.59,
                "supports_streaming": True,
                "supports_function_calling": True
            },
            "llama-3.1-8b-instant": {
                "max_tokens": 8000,
                "cost_per_1k_tokens": 0.05,
                "supports_streaming": True,
                "supports_function_calling": True
            },
            "mixtral-8x7b-32768": {
                "max_tokens": 32768,
                "cost_per_1k_tokens": 0.27,
                "supports_streaming": True,
                "supports_function_calling": False
            }
        },
        "openai": {
            "gpt-4-turbo": {
                "max_tokens": 128000,
                "cost_per_1k_tokens": 10.0,
                "supports_streaming": True,
                "supports_function_calling": True
            },
            "gpt-3.5-turbo": {
                "max_tokens": 16385,
                "cost_per_1k_tokens": 0.5,
                "supports_streaming": True,
                "supports_function_calling": True
            }
        },
        "anthropic": {
            "claude-3-opus": {
                "max_tokens": 200000,
                "cost_per_1k_tokens": 15.0,
                "supports_streaming": True,
                "supports_function_calling": False
            },
            "claude-3-sonnet": {
                "max_tokens": 200000,
                "cost_per_1k_tokens": 3.0,
                "supports_streaming": True,
                "supports_function_calling": False
            }
        }
    }