"""
Comprehensive Resource database model for all GT 2.0 resource families with HA support

Supports 6 resource families:
- AI/ML Resources (LLMs, embeddings, image generation, function calling)
- RAG Engine Resources (vector databases, document processing, retrieval systems)
- Agentic Workflow Resources (multi-step AI workflows, agent frameworks)
- App Integration Resources (external tools, APIs, webhooks)
- External Web Services (Canvas LMS, CTFd, Guacamole, iframe-embedded services)
- AI Literacy & Cognitive Skills (educational games, puzzles, learning content)
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class AIResource(Base):
    """Comprehensive Resource model for managing all GT 2.0 resource families with HA support"""
    
    __tablename__ = "ai_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    resource_type = Column(
        String(50), 
        nullable=False,
        index=True
    )  # ai_ml, rag_engine, agentic_workflow, app_integration, external_service, ai_literacy
    provider = Column(String(50), nullable=False, index=True)
    model_name = Column(String(100), nullable=True)  # Optional for non-AI resources
    
    # Resource Family Specific Fields
    resource_subtype = Column(String(50), nullable=True, index=True)  # llm, vector_db, game, etc.
    personalization_mode = Column(
        String(20), 
        nullable=False, 
        default="shared",
        index=True
    )  # shared, user_scoped, session_based
    
    # High Availability Configuration
    api_endpoints = Column(JSON, nullable=False, default=list)  # Multiple endpoints for HA
    primary_endpoint = Column(Text, nullable=True)
    api_key_encrypted = Column(Text, nullable=True)
    failover_endpoints = Column(JSON, nullable=False, default=list)  # Failover endpoints
    health_check_url = Column(Text, nullable=True)
    
    # External Service Configuration (for iframe embedding, etc.)
    iframe_url = Column(Text, nullable=True)  # For external web services
    sandbox_config = Column(JSON, nullable=False, default=dict)  # Security sandboxing options
    auth_config = Column(JSON, nullable=False, default=dict)  # Authentication configuration
    
    # Performance and Limits
    max_requests_per_minute = Column(Integer, nullable=False, default=60)
    max_tokens_per_request = Column(Integer, nullable=False, default=4000)
    cost_per_1k_tokens = Column(Float, nullable=False, default=0.0)
    latency_sla_ms = Column(Integer, nullable=False, default=5000)
    
    # Configuration and Status
    configuration = Column(JSON, nullable=False, default=dict)
    health_status = Column(String(20), nullable=False, default="unknown", index=True)  # healthy, unhealthy, unknown
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    priority = Column(Integer, nullable=False, default=100)  # For load balancing weights
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    tenant_resources = relationship("TenantResource", back_populates="ai_resource", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="ai_resource", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AIResource(id={self.id}, name='{self.name}', provider='{self.provider}')>"
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert comprehensive resource to dictionary with HA information"""
        data = {
            "id": self.id,
            "uuid": str(self.uuid),
            "name": self.name,
            "description": self.description,
            "resource_type": self.resource_type,
            "resource_subtype": self.resource_subtype,
            "provider": self.provider,
            "model_name": self.model_name,
            "personalization_mode": self.personalization_mode,
            "primary_endpoint": self.primary_endpoint,
            "health_check_url": self.health_check_url,
            "iframe_url": self.iframe_url,
            "sandbox_config": self.sandbox_config,
            "auth_config": self.auth_config,
            "max_requests_per_minute": self.max_requests_per_minute,
            "max_tokens_per_request": self.max_tokens_per_request,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "latency_sla_ms": self.latency_sla_ms,
            "configuration": self.configuration,
            "health_status": self.health_status,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data["api_key_encrypted"] = self.api_key_encrypted
            data["api_endpoints"] = self.api_endpoints
            data["failover_endpoints"] = self.failover_endpoints
        
        return data
    
    # Resource Family Properties
    @property
    def is_ai_ml(self) -> bool:
        """Check if resource is an AI/ML resource"""
        return self.resource_type == "ai_ml"
    
    @property
    def is_rag_engine(self) -> bool:
        """Check if resource is a RAG engine"""
        return self.resource_type == "rag_engine"
    
    @property
    def is_agentic_workflow(self) -> bool:
        """Check if resource is an agentic workflow"""
        return self.resource_type == "agentic_workflow"
    
    @property
    def is_app_integration(self) -> bool:
        """Check if resource is an app integration"""
        return self.resource_type == "app_integration"
    
    @property
    def is_external_service(self) -> bool:
        """Check if resource is an external web service"""
        return self.resource_type == "external_service"
    
    @property
    def is_ai_literacy(self) -> bool:
        """Check if resource is an AI literacy resource"""
        return self.resource_type == "ai_literacy"
    
    # AI/ML Subtype Properties (legacy compatibility)
    @property
    def is_llm(self) -> bool:
        """Check if resource is an LLM"""
        return self.is_ai_ml and self.resource_subtype == "llm"
    
    @property
    def is_embedding(self) -> bool:
        """Check if resource is an embedding model"""
        return self.is_ai_ml and self.resource_subtype == "embedding"
    
    @property
    def is_image_generation(self) -> bool:
        """Check if resource is an image generation model"""
        return self.is_ai_ml and self.resource_subtype == "image_generation"
    
    @property
    def is_function_calling(self) -> bool:
        """Check if resource supports function calling"""
        return self.is_ai_ml and self.resource_subtype == "function_calling"
    
    # Personalization Properties
    @property
    def is_shared(self) -> bool:
        """Check if resource uses shared data model"""
        return self.personalization_mode == "shared"
    
    @property
    def is_user_scoped(self) -> bool:
        """Check if resource uses user-scoped data model"""
        return self.personalization_mode == "user_scoped"
    
    @property
    def is_session_based(self) -> bool:
        """Check if resource uses session-based data model"""
        return self.personalization_mode == "session_based"
    
    @property
    def is_healthy(self) -> bool:
        """Check if resource is currently healthy"""
        return self.health_status == "healthy" and self.is_active
    
    @property
    def has_failover(self) -> bool:
        """Check if resource has failover endpoints configured"""
        return bool(self.failover_endpoints and len(self.failover_endpoints) > 0)
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration based on resource type and subtype"""
        if self.is_ai_ml:
            return self._get_ai_ml_config()
        elif self.is_rag_engine:
            return self._get_rag_engine_config()
        elif self.is_agentic_workflow:
            return self._get_agentic_workflow_config()
        elif self.is_app_integration:
            return self._get_app_integration_config()
        elif self.is_external_service:
            return self._get_external_service_config()
        elif self.is_ai_literacy:
            return self._get_ai_literacy_config()
        else:
            return {}
    
    def _get_ai_ml_config(self) -> Dict[str, Any]:
        """Get AI/ML specific configuration"""
        if self.resource_subtype == "llm":
            return {
                "max_tokens": 4000,
                "temperature": 0.7,
                "top_p": 1.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "stream": False,
                "stop": None
            }
        elif self.resource_subtype == "embedding":
            return {
                "dimensions": 1536,
                "batch_size": 100,
                "encoding_format": "float"
            }
        elif self.resource_subtype == "image_generation":
            return {
                "size": "1024x1024",
                "quality": "standard",
                "style": "natural",
                "response_format": "url"
            }
        elif self.resource_subtype == "function_calling":
            return {
                "max_tokens": 4000,
                "temperature": 0.1,
                "function_call": "auto",
                "tools": []
            }
        return {}
    
    def _get_rag_engine_config(self) -> Dict[str, Any]:
        """Get RAG engine specific configuration"""
        return {
            "chunk_size": 512,
            "chunk_overlap": 50,
            "similarity_threshold": 0.7,
            "max_results": 10,
            "rerank": True,
            "include_metadata": True
        }
    
    def _get_agentic_workflow_config(self) -> Dict[str, Any]:
        """Get agentic workflow specific configuration"""
        return {
            "max_iterations": 10,
            "timeout_seconds": 300,
            "auto_approve": False,
            "human_in_loop": True,
            "retry_on_failure": True,
            "max_retries": 3
        }
    
    def _get_app_integration_config(self) -> Dict[str, Any]:
        """Get app integration specific configuration"""
        return {
            "timeout_seconds": 30,
            "retry_attempts": 3,
            "rate_limit_per_minute": 60,
            "webhook_secret": None,
            "auth_method": "api_key"
        }
    
    def _get_external_service_config(self) -> Dict[str, Any]:
        """Get external service specific configuration"""
        return {
            "iframe_sandbox": [
                "allow-same-origin",
                "allow-scripts",
                "allow-forms",
                "allow-popups"
            ],
            "csp_policy": "default-src 'self'",
            "session_timeout": 3600,
            "auto_logout": True,
            "single_sign_on": True
        }
    
    def _get_ai_literacy_config(self) -> Dict[str, Any]:
        """Get AI literacy resource specific configuration"""
        return {
            "difficulty_adaptive": True,
            "progress_tracking": True,
            "multiplayer_enabled": False,
            "explanation_mode": True,
            "hint_system": True,
            "time_limits": False
        }
    
    def merge_config(self, custom_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge custom configuration with defaults"""
        default_config = self.get_default_config()
        merged_config = default_config.copy()
        merged_config.update(custom_config or {})
        merged_config.update(self.configuration or {})
        return merged_config
    
    def get_available_endpoints(self) -> List[str]:
        """Get all available endpoints for this resource"""
        endpoints = []
        if self.primary_endpoint:
            endpoints.append(self.primary_endpoint)
        if self.api_endpoints:
            endpoints.extend([ep for ep in self.api_endpoints if ep != self.primary_endpoint])
        if self.failover_endpoints:
            endpoints.extend([ep for ep in self.failover_endpoints if ep not in endpoints])
        return endpoints
    
    def get_healthy_endpoints(self) -> List[str]:
        """Get list of healthy endpoints (for HA routing)"""
        if self.is_healthy:
            return self.get_available_endpoints()
        return []
    
    def update_health_status(self, status: str, last_check: Optional[datetime] = None) -> None:
        """Update health status of the resource"""
        self.health_status = status
        self.last_health_check = last_check or datetime.utcnow()
    
    def calculate_cost(self, tokens_used: int) -> int:
        """Calculate cost in cents for token usage"""
        if self.cost_per_1k_tokens <= 0:
            return 0
        return int((tokens_used / 1000) * self.cost_per_1k_tokens * 100)
    
    @classmethod
    def get_groq_defaults(cls) -> Dict[str, Any]:
        """Get default configuration for Groq resources"""
        return {
            "provider": "groq",
            "api_endpoints": ["https://api.groq.com/openai/v1"],
            "primary_endpoint": "https://api.groq.com/openai/v1",
            "health_check_url": "https://api.groq.com/openai/v1/models",
            "max_requests_per_minute": 30,
            "max_tokens_per_request": 8000,
            "latency_sla_ms": 3000,
            "priority": 100
        }