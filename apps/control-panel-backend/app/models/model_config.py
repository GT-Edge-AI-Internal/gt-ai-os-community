"""
Model Configuration Database Schema for GT 2.0 Admin Control Panel

This model stores configurations for all AI models across the GT 2.0 platform.
Configurations are synced to resource clusters via RabbitMQ messages.
"""

from sqlalchemy import Column, String, JSON, Boolean, DateTime, Float, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class ModelConfig(Base):
    """Model configuration stored in PostgreSQL admin database"""
    __tablename__ = "model_configs"

    # Primary key - UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Business identifier - unique per provider (same model_id can exist for different providers)
    model_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    version = Column(String(50), default="1.0")

    # Provider information
    provider = Column(String(50), nullable=False)  # groq, external, openai, anthropic, nvidia
    model_type = Column(String(50), nullable=False)  # llm, embedding, audio, tts, vision
    
    # Endpoint configuration
    endpoint = Column(String(500), nullable=False)
    api_key_name = Column(String(100))  # Environment variable name for API key
    
    # Model specifications
    context_window = Column(Integer)
    max_tokens = Column(Integer)
    dimensions = Column(Integer)  # For embedding models
    
    # Capabilities (JSON object)
    capabilities = Column(JSON, default={})
    
    # Cost information (per million tokens, as per Groq pricing)
    cost_per_million_input = Column(Float, default=0.0)
    cost_per_million_output = Column(Float, default=0.0)
    
    # Configuration and metadata
    description = Column(Text)
    config = Column(JSON, default={})  # Additional provider-specific config
    
    # Status and health
    is_active = Column(Boolean, default=True)
    health_status = Column(String(20), default="unknown")  # healthy, unhealthy, unknown
    last_health_check = Column(DateTime)

    # Compound model flag (for pass-through pricing based on actual usage)
    is_compound = Column(Boolean, default=False)
    
    # Usage tracking (will be updated from resource clusters)
    request_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    success_rate = Column(Float, default=100.0)
    avg_latency_ms = Column(Float, default=0.0)
    
    # Tenant access control (JSON array)
    # Example: {"allowed_tenants": ["tenant1", "tenant2"], "blocked_tenants": [], "global_access": true}
    tenant_restrictions = Column(JSON, default=lambda: {"global_access": True})
    
    # Required capabilities to use this model (JSON array)
    # Example: ["llm:execute", "advanced:reasoning", "vision:analyze"]
    required_capabilities = Column(JSON, default=list)
    
    # Lifecycle timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    tenant_configs = relationship("TenantModelConfig", back_populates="model_config", cascade="all, delete-orphan")

    # Unique constraint: same model_id can exist for different providers
    __table_args__ = (
        UniqueConstraint('model_id', 'provider', name='model_configs_model_id_provider_unique'),
    )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary for API responses"""
        return {
            "id": str(self.id) if self.id else None,
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "provider": self.provider,
            "model_type": self.model_type,
            "endpoint": self.endpoint,
            "api_key_name": self.api_key_name,
            "specifications": {
                "context_window": self.context_window,
                "max_tokens": self.max_tokens,
                "dimensions": self.dimensions,
            },
            "capabilities": self.capabilities or {},
            "cost": {
                "per_million_input": self.cost_per_million_input,
                "per_million_output": self.cost_per_million_output,
            },
            "description": self.description,
            "config": self.config or {},
            "status": {
                "is_active": self.is_active,
                "is_compound": self.is_compound,
                "health_status": self.health_status,
                "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            },
            "usage": {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "success_rate": self.success_rate,
                "avg_latency_ms": self.avg_latency_ms,
            },
            "access_control": {
                "tenant_restrictions": self.tenant_restrictions or {},
                "required_capabilities": self.required_capabilities or [],
            },
            "timestamps": {
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            }
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ModelConfig':
        """Create ModelConfig from dictionary"""
        # Handle both nested and flat data formats
        specifications = data.get("specifications", {})
        cost = data.get("cost", {})
        status = data.get("status", {})
        access_control = data.get("access_control", {})
        
        return cls(
            model_id=data.get("model_id"),
            name=data.get("name"),
            version=data.get("version", "1.0"),
            provider=data.get("provider"),
            model_type=data.get("model_type"),
            endpoint=data.get("endpoint"),
            api_key_name=data.get("api_key_name"),
            # Handle both nested and flat context_window/max_tokens with type conversion
            context_window=int(specifications.get("context_window") or data.get("context_window", 0)) if (specifications.get("context_window") or data.get("context_window")) else None,
            max_tokens=int(specifications.get("max_tokens") or data.get("max_tokens", 0)) if (specifications.get("max_tokens") or data.get("max_tokens")) else None,
            dimensions=int(specifications.get("dimensions") or data.get("dimensions", 0)) if (specifications.get("dimensions") or data.get("dimensions")) else None,
            capabilities=data.get("capabilities", {}),
            # Handle both nested and flat cost fields with type conversion
            cost_per_million_input=float(cost.get("per_million_input") or data.get("cost_per_million_input", 0.0)),
            cost_per_million_output=float(cost.get("per_million_output") or data.get("cost_per_million_output", 0.0)),
            description=data.get("description"),
            config=data.get("config", {}),
            # Handle both nested and flat is_active
            is_active=status.get("is_active") if status.get("is_active") is not None else data.get("is_active", True),
            # Handle both nested and flat is_compound
            is_compound=status.get("is_compound") if status.get("is_compound") is not None else data.get("is_compound", False),
            tenant_restrictions=access_control.get("tenant_restrictions", data.get("tenant_restrictions", {"global_access": True})),
            required_capabilities=access_control.get("required_capabilities", data.get("required_capabilities", [])),
        )


class ModelUsageLog(Base):
    """Log of model usage events from resource clusters"""
    __tablename__ = "model_usage_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False)
    
    # Usage metrics
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    tokens_total = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    latency_ms = Column(Float)
    
    # Request metadata
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    request_id = Column(String(100))
    
    # Timestamp
    timestamp = Column(DateTime, default=func.now())
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "model_id": self.model_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "tokens": {
                "input": self.tokens_input,
                "output": self.tokens_output,
                "total": self.tokens_total,
            },
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error_message": self.error_message,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
        }