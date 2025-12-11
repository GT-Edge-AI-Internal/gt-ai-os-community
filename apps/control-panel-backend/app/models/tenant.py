"""
Tenant database model
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, UniqueConstraint, JSON, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Tenant(Base):
    """Tenant model for multi-tenancy"""
    
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    domain = Column(String(50), unique=True, nullable=False, index=True)
    template = Column(String(20), nullable=False, default="basic")
    status = Column(
        String(20), 
        nullable=False, 
        default="pending",
        index=True
    )  # pending, deploying, active, suspended, terminated
    max_users = Column(Integer, nullable=False, default=100)
    resource_limits = Column(
        JSON, 
        nullable=False, 
        default=lambda: {"cpu": "1000m", "memory": "2Gi", "storage": "10Gi"}
    )
    namespace = Column(String(100), unique=True, nullable=False)
    subdomain = Column(String(50), unique=True, nullable=False)
    database_path = Column(String(255), nullable=True)
    encryption_key = Column(Text, nullable=True)

    # Frontend URL (for password reset emails, etc.)
    # If not set, defaults to http://localhost:3002
    frontend_url = Column(String(255), nullable=True)

    # API Keys (encrypted)
    api_keys = Column(JSON, default=dict)  # {"groq": {"key": "encrypted", "enabled": true}, ...}
    api_key_encryption_version = Column(String(20), default="v1")

    # Feature toggles
    optics_enabled = Column(Boolean, default=False)  # Enable Optics cost tracking tab

    # Budget fields (Issue #234)
    monthly_budget_cents = Column(Integer, nullable=True)  # NULL = unlimited
    budget_warning_threshold = Column(Integer, default=80)  # Percentage
    budget_critical_threshold = Column(Integer, default=90)  # Percentage
    budget_enforcement_enabled = Column(Boolean, default=True)

    # Per-tenant storage pricing overrides (Issue #218)
    # Hot tier: NULL = use system default ($0.15/GiB/month)
    storage_price_dataset_hot = Column(Numeric(10, 4), nullable=True)
    storage_price_conversation_hot = Column(Numeric(10, 4), nullable=True)

    # Cold tier: Allocation-based model
    # Monthly cost = allocated_tibs × price_per_tib
    cold_storage_allocated_tibs = Column(Numeric(10, 4), nullable=True)  # NULL = no cold storage
    cold_storage_price_per_tib = Column(Numeric(10, 2), nullable=True, default=10.00)  # Default $10/TiB/month

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    # users relationship replaced with user_assignments for multi-tenant support
    user_assignments = relationship("UserTenantAssignment", back_populates="tenant", cascade="all, delete-orphan")
    tenant_resources = relationship("TenantResource", back_populates="tenant", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")
    
    # Resource management relationships
    resource_quotas = relationship("ResourceQuota", back_populates="tenant", cascade="all, delete-orphan")
    resource_usage_records = relationship("ResourceUsage", back_populates="tenant", cascade="all, delete-orphan")
    resource_alerts = relationship("ResourceAlert", back_populates="tenant", cascade="all, delete-orphan")
    
    # Model access relationships
    model_configs = relationship("TenantModelConfig", back_populates="tenant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, domain='{self.domain}', status='{self.status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tenant to dictionary"""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "name": self.name,
            "domain": self.domain,
            "template": self.template,
            "status": self.status,
            "max_users": self.max_users,
            "resource_limits": self.resource_limits,
            "namespace": self.namespace,
            "subdomain": self.subdomain,
            "frontend_url": self.frontend_url,
            "api_keys_configured": {k: v.get('enabled', False) for k, v in (self.api_keys or {}).items()},
            "optics_enabled": self.optics_enabled or False,
            "monthly_budget_cents": self.monthly_budget_cents,
            "budget_warning_threshold": self.budget_warning_threshold or 80,
            "budget_critical_threshold": self.budget_critical_threshold or 90,
            "budget_enforcement_enabled": self.budget_enforcement_enabled or False,
            "storage_price_dataset_hot": float(self.storage_price_dataset_hot) if self.storage_price_dataset_hot else None,
            "storage_price_conversation_hot": float(self.storage_price_conversation_hot) if self.storage_price_conversation_hot else None,
            "cold_storage_allocated_tibs": float(self.cold_storage_allocated_tibs) if self.cold_storage_allocated_tibs else None,
            "cold_storage_price_per_tib": float(self.cold_storage_price_per_tib) if self.cold_storage_price_per_tib else 10.00,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_active(self) -> bool:
        """Check if tenant is active"""
        return self.status == "active" and self.deleted_at is None


class TenantResource(Base):
    """Tenant resource assignments"""
    
    __tablename__ = "tenant_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(Integer, ForeignKey("ai_resources.id", ondelete="CASCADE"), nullable=False)
    usage_limits = Column(
        JSON,
        nullable=False,
        default=lambda: {"max_requests_per_hour": 1000, "max_tokens_per_request": 4000}
    )
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="tenant_resources")
    ai_resource = relationship("AIResource", back_populates="tenant_resources")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('tenant_id', 'resource_id', name='unique_tenant_resource'),
    )
    
    def __repr__(self):
        return f"<TenantResource(tenant_id={self.tenant_id}, resource_id={self.resource_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tenant resource to dictionary"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "usage_limits": self.usage_limits,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }