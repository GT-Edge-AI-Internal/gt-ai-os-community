"""
Resource Usage and Quota Models for GT 2.0 Control Panel

Tracks resource allocation and usage across all tenants with granular monitoring.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResourceQuota(Base):
    """
    Resource quotas allocated to tenants.
    
    Tracks maximum allowed usage per resource type with cost tracking.
    """
    __tablename__ = "resource_quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)  # cpu, memory, storage, api_calls, etc.
    max_value = Column(Float, nullable=False)  # Maximum allowed value
    current_usage = Column(Float, default=0.0, nullable=False)  # Current usage
    warning_threshold = Column(Float, default=0.8, nullable=False)  # Warning at 80%
    critical_threshold = Column(Float, default=0.95, nullable=False)  # Critical at 95%
    unit = Column(String(20), nullable=False)  # units, MB, cores, calls/hour, etc.
    cost_per_unit = Column(Float, default=0.0, nullable=False)  # Cost per unit of usage
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="resource_quotas")

    def __repr__(self):
        return f"<ResourceQuota(tenant_id={self.tenant_id}, type={self.resource_type}, usage={self.current_usage}/{self.max_value})>"

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "max_value": self.max_value,
            "current_usage": self.current_usage,
            "usage_percentage": (self.current_usage / self.max_value * 100) if self.max_value > 0 else 0,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "unit": self.unit,
            "cost_per_unit": self.cost_per_unit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ResourceUsage(Base):
    """
    Historical resource usage records.
    
    Tracks all resource consumption events for billing and analytics.
    """
    __tablename__ = "resource_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    usage_amount = Column(Float, nullable=False)  # Amount of resource used (can be negative for refunds)
    cost = Column(Float, default=0.0, nullable=False)  # Cost of this usage
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    usage_metadata = Column(Text)  # JSON metadata about the usage event
    user_id = Column(String(100))  # User who initiated the usage (optional)
    service = Column(String(50))  # Service that generated the usage (optional)

    # Relationships
    tenant = relationship("Tenant", back_populates="resource_usage_records")

    def __repr__(self):
        return f"<ResourceUsage(tenant_id={self.tenant_id}, type={self.resource_type}, amount={self.usage_amount}, cost=${self.cost})>"

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "usage_amount": self.usage_amount,
            "cost": self.cost,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.usage_metadata,
            "user_id": self.user_id,
            "service": self.service
        }


class ResourceAlert(Base):
    """
    Resource usage alerts and notifications.
    
    Generated when resource usage exceeds thresholds.
    """
    __tablename__ = "resource_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    alert_level = Column(String(20), nullable=False, index=True)  # info, warning, critical
    message = Column(Text, nullable=False)
    current_usage = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    percentage_used = Column(Float, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_by = Column(String(100))  # User who acknowledged the alert
    acknowledged_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="resource_alerts")

    def __repr__(self):
        return f"<ResourceAlert(tenant_id={self.tenant_id}, level={self.alert_level}, type={self.resource_type})>"

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "alert_level": self.alert_level,
            "message": self.message,
            "current_usage": self.current_usage,
            "max_value": self.max_value,
            "percentage_used": self.percentage_used,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def acknowledge(self, user_id: str):
        """Acknowledge this alert"""
        self.acknowledged = True
        self.acknowledged_by = user_id
        self.acknowledged_at = datetime.utcnow()


class ResourceTemplate(Base):
    """
    Predefined resource allocation templates.
    
    Templates for different tenant tiers (startup, standard, enterprise).
    """
    __tablename__ = "resource_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    template_data = Column(Text, nullable=False)  # JSON resource configuration
    monthly_cost = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ResourceTemplate(name={self.name}, cost=${self.monthly_cost})>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "template_data": self.template_data,
            "monthly_cost": self.monthly_cost,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class SystemMetrics(Base):
    """
    System-wide resource metrics and capacity planning data.
    
    Tracks aggregate usage across all tenants for capacity planning.
    """
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    metric_metadata = Column(Text)  # JSON metadata about the metric

    def __repr__(self):
        return f"<SystemMetrics(name={self.metric_name}, value={self.metric_value}, timestamp={self.timestamp})>"

    def to_dict(self):
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metric_metadata
        }