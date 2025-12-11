"""
Tenant Model Configuration Database Schema for GT 2.0 Admin Control Panel

This model manages which AI models are available to which tenants,
along with tenant-specific permissions and rate limits.
"""

from sqlalchemy import Column, String, JSON, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.database import Base


class TenantModelConfig(Base):
    """Configuration linking tenants to available models with permissions"""
    __tablename__ = "tenant_model_configs"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    # New UUID foreign key to model_configs.id
    model_config_id = Column(UUID(as_uuid=True), ForeignKey("model_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    # Keep model_id for backwards compatibility and easier queries (denormalized)
    model_id = Column(String(255), nullable=False, index=True)
    
    # Configuration
    is_enabled = Column(Boolean, default=True, nullable=False)
    
    # Tenant-specific capabilities (JSON object)
    # Example: {"reasoning": true, "function_calling": false, "vision": true}
    tenant_capabilities = Column(JSON, default={})
    
    # Tenant-specific rate limits (JSON object)
    # Storage: max_requests_per_hour (database format)
    # API returns: requests_per_minute (1000/min = 60000/hour)
    # Example: {"max_requests_per_hour": 60000, "max_tokens_per_request": 4000, "concurrent_requests": 5}
    rate_limits = Column(JSON, default=lambda: {
        "max_requests_per_hour": 60000,  # 1000 requests per minute
        "max_tokens_per_request": 4000,
        "concurrent_requests": 5,
        "max_cost_per_hour": 10.0
    })
    
    # Usage constraints (JSON object)
    # Example: {"allowed_users": ["admin", "developer"], "blocked_users": [], "time_restrictions": {}}
    usage_constraints = Column(JSON, default={})
    
    # Priority for this tenant (higher = more priority when resources are limited)
    priority = Column(Integer, default=1, nullable=False)
    
    # Lifecycle timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="model_configs")
    model_config = relationship("ModelConfig", back_populates="tenant_configs")
    
    # Unique constraint - one config per tenant-model pair (using UUID now)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'model_config_id', name='unique_tenant_model_config'),
    )
    
    def __repr__(self):
        return f"<TenantModelConfig(tenant_id={self.tenant_id}, model_id='{self.model_id}', enabled={self.is_enabled})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for API responses.

        Translation layer: Converts database per-hour values to per-minute for API.
        Database stores max_requests_per_hour, API returns requests_per_minute.
        """
        # Get raw rate limits from database
        db_rate_limits = self.rate_limits or {}

        # Translate max_requests_per_hour to requests_per_minute
        api_rate_limits = {}
        for key, value in db_rate_limits.items():
            if key == "max_requests_per_hour":
                # Convert to per-minute for API response
                api_rate_limits["requests_per_minute"] = value // 60
            else:
                # Keep other fields as-is
                api_rate_limits[key] = value

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "model_config_id": str(self.model_config_id) if self.model_config_id else None,
            "model_id": self.model_id,
            "is_enabled": self.is_enabled,
            "tenant_capabilities": self.tenant_capabilities or {},
            "rate_limits": api_rate_limits,  # Translated to per-minute
            "usage_constraints": self.usage_constraints or {},
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def can_user_access(self, user_capabilities: List[str], user_id: str) -> bool:
        """
        Check if a user can access this model based on tenant configuration
        
        Args:
            user_capabilities: List of user capability strings
            user_id: User identifier
            
        Returns:
            True if user can access the model
        """
        if not self.is_enabled:
            return False
        
        constraints = self.usage_constraints or {}
        
        # Check if user is explicitly blocked
        if user_id in constraints.get("blocked_users", []):
            return False
        
        # Check if there's an allowed users list and user is not in it
        allowed_users = constraints.get("allowed_users", [])
        if allowed_users and user_id not in allowed_users:
            return False
        
        # Check if user has required capabilities for tenant-specific model access
        required_caps = constraints.get("required_capabilities", [])
        if required_caps:
            for required_cap in required_caps:
                if required_cap not in user_capabilities:
                    return False
        
        return True
    
    def get_effective_rate_limits(self) -> Dict[str, Any]:
        """Get effective rate limits with defaults (database format: per-hour)"""
        defaults = {
            "max_requests_per_hour": 60000,  # 1000 requests per minute
            "max_tokens_per_request": 4000,
            "concurrent_requests": 5,
            "max_cost_per_hour": 10.0
        }

        rate_limits = self.rate_limits or {}
        return {**defaults, **rate_limits}
    
    def check_rate_limit(self, metric: str, current_value: float) -> bool:
        """
        Check if current usage is within rate limits
        
        Args:
            metric: Rate limit metric name
            current_value: Current usage value
            
        Returns:
            True if within limits
        """
        limits = self.get_effective_rate_limits()
        limit = limits.get(metric)
        
        if limit is None:
            return True  # No limit set
        
        return current_value <= limit
    
    @classmethod
    def create_default_config(
        cls,
        tenant_id: int,
        model_id: str,
        model_config_id: Optional['UUID'] = None,
        custom_rate_limits: Optional[Dict[str, Any]] = None,
        custom_capabilities: Optional[Dict[str, Any]] = None
    ) -> 'TenantModelConfig':
        """
        Create a default tenant model configuration

        Args:
            tenant_id: Tenant identifier
            model_id: Model identifier (string, for backwards compatibility)
            model_config_id: UUID of the model_configs record (required for FK)
            custom_rate_limits: Optional custom rate limits
            custom_capabilities: Optional custom capabilities

        Returns:
            New TenantModelConfig instance
        """
        default_rate_limits = {
            "max_requests_per_hour": 60000,  # 1000 requests per minute
            "max_tokens_per_request": 4000,
            "concurrent_requests": 5,
            "max_cost_per_hour": 10.0
        }

        if custom_rate_limits:
            default_rate_limits.update(custom_rate_limits)

        return cls(
            tenant_id=tenant_id,
            model_config_id=model_config_id,
            model_id=model_id,
            is_enabled=True,
            tenant_capabilities=custom_capabilities or {},
            rate_limits=default_rate_limits,
            usage_constraints={},
            priority=1
        )