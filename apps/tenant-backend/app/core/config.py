"""
GT 2.0 Tenant Backend Configuration

Environment-based configuration for tenant applications with perfect isolation.
Each tenant gets its own isolated backend instance with separate database files.
"""

import os
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Environment
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Tenant Identification (Critical for isolation)
    tenant_id: str = Field(..., description="Unique tenant identifier")
    tenant_domain: str = Field(..., description="Tenant domain (e.g., customer1)")
    
    # Database Configuration (PostgreSQL + PGVector direct connection)
    database_url: str = Field(
        default="postgresql://gt2_tenant_user:gt2_tenant_dev_password@tenant-postgres-primary:5432/gt2_tenants",
        description="PostgreSQL connection URL (direct to primary)"
    )
    
    
    # PostgreSQL Configuration
    postgres_schema: str = Field(
        default="tenant_test",
        description="PostgreSQL schema for tenant data (tenant_{tenant_domain})"
    )
    postgres_pool_size: int = Field(
        default=10,
        description="Connection pool size for PostgreSQL"
    )
    postgres_max_overflow: int = Field(
        default=20,
        description="Max overflow connections for PostgreSQL pool"
    )
    
    
    # Authentication & Security
    secret_key: str = Field(..., description="JWT signing key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    
    # OAuth2 Configuration
    require_oauth2_auth: bool = Field(
        default=True, 
        description="Require OAuth2 authentication for API endpoints"
    )
    oauth2_proxy_url: str = Field(
        default="http://oauth2-proxy:4180",
        description="Internal URL of OAuth2 Proxy service"
    )
    oauth2_issuer_url: str = Field(
        default="https://auth.gt2.com",
        description="OAuth2 provider issuer URL"
    )
    oauth2_audience: str = Field(
        default="gt2-tenant-client",
        description="OAuth2 token audience"
    )
    
    # Resource Cluster Integration
    resource_cluster_url: str = Field(
        default="http://localhost:8004",
        description="URL of the Resource Cluster API"
    )
    resource_cluster_api_key: Optional[str] = Field(
        default=None,
        description="API key for Resource Cluster authentication"
    )

    # MCP Service Configuration
    mcp_service_url: str = Field(
        default="http://resource-cluster:8000",
        description="URL of the MCP service for tool execution"
    )
    
    # Control Panel Integration
    control_panel_url: str = Field(
        default="http://localhost:8001",
        description="URL of the Control Panel API"
    )
    service_auth_token: str = Field(
        default="internal-service-token",
        description="Service-to-service authentication token"
    )

    # WebSocket Configuration
    websocket_ping_interval: int = Field(default=25, description="WebSocket ping interval")
    websocket_ping_timeout: int = Field(default=20, description="WebSocket ping timeout")
    
    # File Upload Configuration
    max_file_size_mb: int = Field(default=10, description="Maximum file upload size in MB")
    allowed_file_types: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"],
        description="Allowed file extensions for upload"
    )
    upload_directory: str = Field(
        default_factory=lambda: f"/tmp/gt2-data/{os.getenv('TENANT_DOMAIN', 'default')}/uploads" if os.getenv('ENVIRONMENT') == 'test' else f"/data/{os.getenv('TENANT_DOMAIN', 'default')}/uploads",
        description="Directory for uploaded files"
    )
    temp_directory: str = Field(
        default_factory=lambda: f"/tmp/gt2-data/{os.getenv('TENANT_DOMAIN', 'default')}/temp" if os.getenv('ENVIRONMENT') == 'test' else f"/data/{os.getenv('TENANT_DOMAIN', 'default')}/temp",
        description="Temporary directory for file processing"
    )
    file_storage_path: str = Field(
        default_factory=lambda: f"/tmp/gt2-data/{os.getenv('TENANT_DOMAIN', 'default')}" if os.getenv('ENVIRONMENT') == 'test' else f"/data/{os.getenv('TENANT_DOMAIN', 'default')}",
        description="Root directory for file storage (conversation files, etc.)"
    )

    # File Context Settings (for chat attachments)
    max_chunks_per_file: int = Field(
        default=50,
        description="Maximum chunks per file (enforces diversity across files)"
    )
    max_total_file_chunks: int = Field(
        default=100,
        description="Maximum total chunks across all attached files"
    )
    file_context_token_safety_margin: float = Field(
        default=0.05,
        description="Safety margin for token budget calculations (0.05 = 5%)"
    )

    # Rate Limiting
    rate_limit_requests: int = Field(default=1000, description="Requests per minute per IP")
    rate_limit_window_seconds: int = Field(default=60, description="Rate limit window")
    
    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3001", "http://localhost:3002", "https://*.gt2.com"],
        description="Allowed CORS origins"
    )
    
    # Security
    allowed_hosts: List[str] = Field(
        default=["localhost", "*.gt2.com", "testserver", "gentwo-tenant-backend", "tenant-backend"],
        description="Allowed host headers"
    )
    
    # Vector Storage Configuration (PGVector integrated with PostgreSQL)
    vector_dimensions: int = Field(
        default=384,
        description="Vector dimensions for embeddings (all-MiniLM-L6-v2 model)"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model for document processing"
    )
    vector_similarity_threshold: float = Field(
        default=0.3,
        description="Minimum similarity threshold for vector search"
    )
    
    # Legacy ChromaDB Configuration (DEPRECATED - replaced by PGVector)
    chromadb_mode: str = Field(
        default="disabled", 
        description="ChromaDB mode - DEPRECATED, using PGVector instead"
    )
    chromadb_host: str = Field(
        default_factory=lambda: f"tenant-{os.getenv('TENANT_DOMAIN', 'test')}-chromadb",
        description="ChromaDB host - DEPRECATED"
    )
    chromadb_port: int = Field(
        default=8000,
        description="ChromaDB HTTP port - DEPRECATED"
    )
    chromadb_path: str = Field(
        default_factory=lambda: f"/data/{os.getenv('TENANT_DOMAIN', 'default')}/chromadb",
        description="ChromaDB file storage path - DEPRECATED"
    )
    
    # Redis removed - PostgreSQL handles all caching and session storage needs
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    
    # Performance
    worker_processes: int = Field(default=1, description="Number of worker processes")
    max_connections: int = Field(default=100, description="Maximum concurrent connections")
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")
    
    # Feature Flags
    enable_file_upload: bool = Field(default=True, description="Enable file upload feature")
    enable_voice_input: bool = Field(default=False, description="Enable voice input (future)")
    enable_document_analysis: bool = Field(default=True, description="Enable document analysis")
    
    @validator("tenant_id")
    def validate_tenant_id(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Tenant ID must be at least 3 characters long")
        return v
    
    @validator("tenant_domain")
    def validate_tenant_domain(cls, v):
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Tenant domain must be alphanumeric with optional hyphens/underscores")
        return v
    
    
    @validator("upload_directory")
    def validate_upload_directory(cls, v):
        # Ensure the upload directory exists with secure permissions
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
    # For development and testing, use simple settings without caching
    if os.getenv("ENVIRONMENT") in ["development", "test"]:
        return Settings()
    
    # In production, settings should be tenant-scoped
    # This prevents global state from affecting tenant isolation
    if tenant_id:
        # Create tenant-specific settings with proper isolation
        settings = Settings()
        # In production, this could load tenant-specific overrides
        return settings
    else:
        # Default settings for non-tenant operations
        return Settings()


# Security and isolation utilities
def get_tenant_data_path(tenant_domain: str) -> str:
    """Get the secure data path for a tenant"""
    if os.getenv('ENVIRONMENT') == 'test':
        return f"/tmp/gt2-data/{tenant_domain}"
    return f"/data/{tenant_domain}"


def get_tenant_database_url(tenant_domain: str) -> str:
    """Get the database URL for a specific tenant (PostgreSQL)"""
    return f"postgresql://gt2_tenant_user:gt2_tenant_dev_password@tenant-postgres:5432/gt2_tenants"


def get_tenant_schema_name(tenant_domain: str) -> str:
    """Get the PostgreSQL schema name for a specific tenant"""
    # Clean domain name for schema usage
    clean_domain = tenant_domain.replace('-', '_').replace('.', '_').lower()
    return f"tenant_{clean_domain}"


def ensure_tenant_isolation(tenant_id: str) -> None:
    """Ensure proper tenant isolation is configured"""
    settings = get_settings()
    
    if settings.tenant_id != tenant_id:
        raise ValueError(f"Tenant ID mismatch: expected {settings.tenant_id}, got {tenant_id}")
    
    # Verify database path contains tenant identifier
    if settings.tenant_domain not in settings.database_path:
        raise ValueError("Database path does not contain tenant identifier - isolation breach risk")
    
    # Verify upload directory contains tenant identifier
    if settings.tenant_domain not in settings.upload_directory:
        raise ValueError("Upload directory does not contain tenant identifier - isolation breach risk")


# Development helpers
def is_development() -> bool:
    """Check if running in development mode"""
    return get_settings().environment == "development"


def is_production() -> bool:
    """Check if running in production mode"""
    return get_settings().environment == "production"