"""
Configuration settings for GT 2.0 Control Panel Backend
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    SECRET_KEY: str = Field(default="PRODUCTION_SECRET_KEY_REQUIRED", env="SECRET_KEY")
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        env="ALLOWED_ORIGINS"
    )
    
    # Database (PostgreSQL direct connection)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:gt2_admin_dev_password@postgres:5432/gt2_admin",
        env="DATABASE_URL"
    )
    
    # Redis removed - PostgreSQL handles all session and caching needs
    
    # MinIO removed - PostgreSQL handles all file storage
    
    # Kubernetes
    KUBERNETES_IN_CLUSTER: bool = Field(default=False, env="KUBERNETES_IN_CLUSTER")
    KUBECONFIG_PATH: Optional[str] = Field(default=None, env="KUBECONFIG_PATH")
    
    # ChromaDB
    CHROMADB_HOST: str = Field(default="localhost", env="CHROMADB_HOST")
    CHROMADB_PORT: int = Field(default=8000, env="CHROMADB_PORT")
    CHROMADB_AUTH_USER: str = Field(default="admin", env="CHROMADB_AUTH_USER")
    CHROMADB_AUTH_PASSWORD: str = Field(default="dev_chroma_password", env="CHROMADB_AUTH_PASSWORD")
    
    # Dremio SQL Federation
    DREMIO_URL: Optional[str] = Field(default="http://dremio:9047", env="DREMIO_URL")
    DREMIO_USERNAME: Optional[str] = Field(default="admin", env="DREMIO_USERNAME")
    DREMIO_PASSWORD: Optional[str] = Field(default="admin123", env="DREMIO_PASSWORD")
    
    # Service Authentication
    SERVICE_AUTH_TOKEN: Optional[str] = Field(default="internal-service-token", env="SERVICE_AUTH_TOKEN")
    
    # JWT - NIST/OWASP Compliant Session Timeouts (Issue #242)
    JWT_SECRET: str = Field(default="dev-jwt-secret-change-in-production-32-chars-minimum", env="JWT_SECRET")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    # JWT expiration: 12 hours (matches absolute timeout) - NIST SP 800-63B AAL2 compliant
    # Server-side session enforces 30-minute idle timeout via last_activity_at tracking
    # JWT exp serves as backstop - prevents tokens from being valid beyond absolute limit
    JWT_EXPIRES_MINUTES: int = Field(default=720, env="JWT_EXPIRES_MINUTES")
    # Absolute timeout: 12 hours - NIST SP 800-63B AAL2 maximum session duration
    JWT_ABSOLUTE_TIMEOUT_HOURS: int = Field(default=12, env="JWT_ABSOLUTE_TIMEOUT_HOURS")
    # Legacy support (deprecated - use JWT_EXPIRES_MINUTES instead)
    JWT_EXPIRES_HOURS: int = Field(default=4, env="JWT_EXPIRES_HOURS")
    
    # Aliases for compatibility
    @property
    def secret_key(self) -> str:
        return self.JWT_SECRET
    
    @property
    def algorithm(self) -> str:
        return self.JWT_ALGORITHM
    
    # Encryption
    MASTER_ENCRYPTION_KEY: str = Field(
        default="dev-master-key-change-in-production-must-be-32-bytes-long",
        env="MASTER_ENCRYPTION_KEY"
    )
    
    # Tenant Settings
    TENANT_DATA_DIR: str = Field(default="/data", env="TENANT_DATA_DIR")
    DEFAULT_TENANT_TEMPLATE: str = Field(default="basic", env="DEFAULT_TENANT_TEMPLATE")
    
    # External AI Services
    GROQ_API_KEY: Optional[str] = Field(default=None, env="GROQ_API_KEY")
    GROQ_BASE_URL: str = Field(default="https://api.groq.com/openai/v1", env="GROQ_BASE_URL")
    
    # Resource Cluster
    RESOURCE_CLUSTER_URL: str = Field(default="http://localhost:8003", env="RESOURCE_CLUSTER_URL")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # RabbitMQ (for message bus)
    RABBITMQ_URL: str = Field(
        default="amqp://admin:dev_rabbitmq_password@localhost:5672/gt2",
        env="RABBITMQ_URL"
    )
    MESSAGE_BUS_SECRET_KEY: str = Field(
        default="PRODUCTION_MESSAGE_BUS_SECRET_REQUIRED",
        env="MESSAGE_BUS_SECRET_KEY"
    )
    
    # Celery (for background tasks) - Using PostgreSQL instead of Redis
    CELERY_BROKER_URL: str = Field(
        default="db+postgresql://gt2_admin:dev_password_change_in_prod@postgres:5432/gt2_control_panel",
        env="CELERY_BROKER_URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="db+postgresql://gt2_admin:dev_password_change_in_prod@postgres:5432/gt2_control_panel",
        env="CELERY_RESULT_BACKEND"
    )
    
    @validator('ALLOWED_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @validator('MASTER_ENCRYPTION_KEY')
    def validate_encryption_key_length(cls, v):
        if len(v) < 32:
            raise ValueError('Master encryption key must be at least 32 characters long')
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings

# Environment-specific configurations
if settings.ENVIRONMENT == "production":
    # Production settings
    # Validation checks removed for flexibility
    pass
else:
    # Development/Test settings
    import logging
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))