"""
GT 2.0 Resource Allocation Management Service

Manages CPU, memory, storage, and API quotas for tenants following GT 2.0 principles:
- Granular resource control per tenant
- Real-time usage monitoring
- Automatic scaling within limits
- Cost tracking and optimization
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_

from app.models.tenant import Tenant
from app.models.resource_usage import ResourceUsage, ResourceQuota, ResourceAlert
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ResourceType(Enum):
    """Types of resources that can be allocated"""
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    API_CALLS = "api_calls"
    GPU_TIME = "gpu_time"
    VECTOR_OPERATIONS = "vector_operations"
    MODEL_INFERENCE = "model_inference"


class AlertLevel(Enum):
    """Resource usage alert levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ResourceLimit:
    """Resource limit configuration"""
    resource_type: ResourceType
    max_value: float
    warning_threshold: float = 0.8  # 80% of max
    critical_threshold: float = 0.95  # 95% of max
    unit: str = "units"
    cost_per_unit: float = 0.0


@dataclass
class ResourceUsageData:
    """Current resource usage data"""
    resource_type: ResourceType
    current_usage: float
    max_allowed: float
    percentage_used: float
    cost_accrued: float
    last_updated: datetime


class ResourceAllocationService:
    """
    Service for managing resource allocation and monitoring usage across tenants.
    
    Features:
    - Dynamic quota allocation
    - Real-time usage tracking
    - Automatic scaling policies
    - Cost optimization
    - Alert generation
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Default resource templates
        self.resource_templates = {
            "startup": {
                ResourceType.CPU: ResourceLimit(ResourceType.CPU, 2.0, unit="cores", cost_per_unit=0.10),
                ResourceType.MEMORY: ResourceLimit(ResourceType.MEMORY, 4096, unit="MB", cost_per_unit=0.05),
                ResourceType.STORAGE: ResourceLimit(ResourceType.STORAGE, 10240, unit="MB", cost_per_unit=0.01),
                ResourceType.API_CALLS: ResourceLimit(ResourceType.API_CALLS, 10000, unit="calls/hour", cost_per_unit=0.001),
                ResourceType.MODEL_INFERENCE: ResourceLimit(ResourceType.MODEL_INFERENCE, 1000, unit="tokens", cost_per_unit=0.002),
            },
            "standard": {
                ResourceType.CPU: ResourceLimit(ResourceType.CPU, 4.0, unit="cores", cost_per_unit=0.10),
                ResourceType.MEMORY: ResourceLimit(ResourceType.MEMORY, 8192, unit="MB", cost_per_unit=0.05),
                ResourceType.STORAGE: ResourceLimit(ResourceType.STORAGE, 51200, unit="MB", cost_per_unit=0.01),
                ResourceType.API_CALLS: ResourceLimit(ResourceType.API_CALLS, 50000, unit="calls/hour", cost_per_unit=0.001),
                ResourceType.MODEL_INFERENCE: ResourceLimit(ResourceType.MODEL_INFERENCE, 10000, unit="tokens", cost_per_unit=0.002),
            },
            "enterprise": {
                ResourceType.CPU: ResourceLimit(ResourceType.CPU, 16.0, unit="cores", cost_per_unit=0.10),
                ResourceType.MEMORY: ResourceLimit(ResourceType.MEMORY, 32768, unit="MB", cost_per_unit=0.05),
                ResourceType.STORAGE: ResourceLimit(ResourceType.STORAGE, 102400, unit="MB", cost_per_unit=0.01),
                ResourceType.API_CALLS: ResourceLimit(ResourceType.API_CALLS, 200000, unit="calls/hour", cost_per_unit=0.001),
                ResourceType.MODEL_INFERENCE: ResourceLimit(ResourceType.MODEL_INFERENCE, 100000, unit="tokens", cost_per_unit=0.002),
                ResourceType.GPU_TIME: ResourceLimit(ResourceType.GPU_TIME, 1000, unit="minutes", cost_per_unit=0.50),
            }
        }
    
    async def allocate_resources(self, tenant_id: int, template: str = "standard") -> bool:
        """
        Allocate initial resources to a tenant based on template.
        
        Args:
            tenant_id: Tenant database ID
            template: Resource template name
            
        Returns:
            True if allocation successful
        """
        try:
            # Get tenant
            result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                logger.error(f"Tenant {tenant_id} not found")
                return False
            
            # Get resource template
            if template not in self.resource_templates:
                logger.error(f"Unknown resource template: {template}")
                return False
            
            resources = self.resource_templates[template]
            
            # Create resource quotas
            for resource_type, limit in resources.items():
                quota = ResourceQuota(
                    tenant_id=tenant_id,
                    resource_type=resource_type.value,
                    max_value=limit.max_value,
                    warning_threshold=limit.warning_threshold,
                    critical_threshold=limit.critical_threshold,
                    unit=limit.unit,
                    cost_per_unit=limit.cost_per_unit,
                    current_usage=0.0,
                    is_active=True
                )
                
                self.db.add(quota)
            
            await self.db.commit()
            
            logger.info(f"Allocated {template} resources to tenant {tenant.domain}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to allocate resources to tenant {tenant_id}: {e}")
            await self.db.rollback()
            return False
    
    async def get_tenant_resource_usage(self, tenant_id: int) -> Dict[str, ResourceUsageData]:
        """
        Get current resource usage for a tenant.
        
        Args:
            tenant_id: Tenant database ID
            
        Returns:
            Dictionary of resource usage data
        """
        try:
            # Get all quotas for tenant
            result = await self.db.execute(
                select(ResourceQuota).where(
                    and_(ResourceQuota.tenant_id == tenant_id, ResourceQuota.is_active == True)
                )
            )
            quotas = result.scalars().all()
            
            usage_data = {}
            
            for quota in quotas:
                resource_type = ResourceType(quota.resource_type)
                percentage_used = (quota.current_usage / quota.max_value) * 100 if quota.max_value > 0 else 0
                
                usage_data[quota.resource_type] = ResourceUsageData(
                    resource_type=resource_type,
                    current_usage=quota.current_usage,
                    max_allowed=quota.max_value,
                    percentage_used=percentage_used,
                    cost_accrued=quota.current_usage * quota.cost_per_unit,
                    last_updated=quota.updated_at
                )
            
            return usage_data
            
        except Exception as e:
            logger.error(f"Failed to get resource usage for tenant {tenant_id}: {e}")
            return {}
    
    async def update_resource_usage(
        self, 
        tenant_id: int, 
        resource_type: ResourceType, 
        usage_delta: float
    ) -> bool:
        """
        Update resource usage for a tenant.
        
        Args:
            tenant_id: Tenant database ID
            resource_type: Type of resource being used
            usage_delta: Change in usage (positive for increase, negative for decrease)
            
        Returns:
            True if update successful
        """
        try:
            # Get resource quota
            result = await self.db.execute(
                select(ResourceQuota).where(
                    and_(
                        ResourceQuota.tenant_id == tenant_id,
                        ResourceQuota.resource_type == resource_type.value,
                        ResourceQuota.is_active == True
                    )
                )
            )
            quota = result.scalar_one_or_none()
            
            if not quota:
                logger.warning(f"No quota found for {resource_type.value} for tenant {tenant_id}")
                return False
            
            # Calculate new usage
            new_usage = max(0, quota.current_usage + usage_delta)
            
            # Check if usage exceeds quota
            if new_usage > quota.max_value:
                logger.warning(
                    f"Resource usage would exceed quota for tenant {tenant_id}: "
                    f"{resource_type.value} {new_usage} > {quota.max_value}"
                )
                return False
            
            # Update usage
            quota.current_usage = new_usage
            quota.updated_at = datetime.utcnow()
            
            # Record usage history
            usage_record = ResourceUsage(
                tenant_id=tenant_id,
                resource_type=resource_type.value,
                usage_amount=usage_delta,
                timestamp=datetime.utcnow(),
                cost=usage_delta * quota.cost_per_unit
            )
            
            self.db.add(usage_record)
            await self.db.commit()
            
            # Check for alerts
            await self._check_usage_alerts(tenant_id, quota)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update resource usage: {e}")
            await self.db.rollback()
            return False
    
    async def _check_usage_alerts(self, tenant_id: int, quota: ResourceQuota) -> None:
        """Check if resource usage triggers alerts"""
        try:
            percentage_used = (quota.current_usage / quota.max_value) if quota.max_value > 0 else 0
            
            alert_level = None
            message = None
            
            if percentage_used >= quota.critical_threshold:
                alert_level = AlertLevel.CRITICAL
                message = f"Critical: {quota.resource_type} usage at {percentage_used:.1f}%"
            elif percentage_used >= quota.warning_threshold:
                alert_level = AlertLevel.WARNING
                message = f"Warning: {quota.resource_type} usage at {percentage_used:.1f}%"
            
            if alert_level:
                # Check if we already have a recent alert
                recent_alert = await self.db.execute(
                    select(ResourceAlert).where(
                        and_(
                            ResourceAlert.tenant_id == tenant_id,
                            ResourceAlert.resource_type == quota.resource_type,
                            ResourceAlert.alert_level == alert_level.value,
                            ResourceAlert.created_at >= datetime.utcnow() - timedelta(hours=1)
                        )
                    )
                )
                
                if not recent_alert.scalar_one_or_none():
                    # Create new alert
                    alert = ResourceAlert(
                        tenant_id=tenant_id,
                        resource_type=quota.resource_type,
                        alert_level=alert_level.value,
                        message=message,
                        current_usage=quota.current_usage,
                        max_value=quota.max_value,
                        percentage_used=percentage_used
                    )
                    
                    self.db.add(alert)
                    await self.db.commit()
                    
                    logger.warning(f"Resource alert for tenant {tenant_id}: {message}")
        
        except Exception as e:
            logger.error(f"Failed to check usage alerts: {e}")
    
    async def get_tenant_costs(self, tenant_id: int, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Calculate costs for a tenant over a date range.
        
        Args:
            tenant_id: Tenant database ID
            start_date: Start of cost calculation period
            end_date: End of cost calculation period
            
        Returns:
            Cost breakdown by resource type
        """
        try:
            # Get usage records for the period
            result = await self.db.execute(
                select(ResourceUsage).where(
                    and_(
                        ResourceUsage.tenant_id == tenant_id,
                        ResourceUsage.timestamp >= start_date,
                        ResourceUsage.timestamp <= end_date
                    )
                )
            )
            usage_records = result.scalars().all()
            
            # Calculate costs by resource type
            costs_by_type = {}
            total_cost = 0.0
            
            for record in usage_records:
                if record.resource_type not in costs_by_type:
                    costs_by_type[record.resource_type] = {
                        "total_usage": 0.0,
                        "total_cost": 0.0,
                        "usage_events": 0
                    }
                
                costs_by_type[record.resource_type]["total_usage"] += record.usage_amount
                costs_by_type[record.resource_type]["total_cost"] += record.cost
                costs_by_type[record.resource_type]["usage_events"] += 1
                total_cost += record.cost
            
            return {
                "tenant_id": tenant_id,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_cost": round(total_cost, 4),
                "costs_by_resource": costs_by_type,
                "currency": "USD"
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate costs for tenant {tenant_id}: {e}")
            return {}
    
    async def scale_tenant_resources(
        self, 
        tenant_id: int, 
        resource_type: ResourceType, 
        scale_factor: float
    ) -> bool:
        """
        Scale tenant resources up or down.
        
        Args:
            tenant_id: Tenant database ID
            resource_type: Type of resource to scale
            scale_factor: Scaling factor (1.5 = 50% increase, 0.8 = 20% decrease)
            
        Returns:
            True if scaling successful
        """
        try:
            # Get current quota
            result = await self.db.execute(
                select(ResourceQuota).where(
                    and_(
                        ResourceQuota.tenant_id == tenant_id,
                        ResourceQuota.resource_type == resource_type.value,
                        ResourceQuota.is_active == True
                    )
                )
            )
            quota = result.scalar_one_or_none()
            
            if not quota:
                logger.error(f"No quota found for {resource_type.value} for tenant {tenant_id}")
                return False
            
            # Calculate new limit
            new_max_value = quota.max_value * scale_factor
            
            # Ensure we don't scale below current usage
            if new_max_value < quota.current_usage:
                logger.warning(
                    f"Cannot scale {resource_type.value} below current usage: "
                    f"{new_max_value} < {quota.current_usage}"
                )
                return False
            
            # Update quota
            quota.max_value = new_max_value
            quota.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            logger.info(
                f"Scaled {resource_type.value} for tenant {tenant_id} by {scale_factor}x to {new_max_value}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to scale resources for tenant {tenant_id}: {e}")
            await self.db.rollback()
            return False
    
    async def get_system_resource_overview(self) -> Dict[str, Any]:
        """
        Get system-wide resource usage overview.
        
        Returns:
            System resource usage statistics
        """
        try:
            # Get aggregate usage by resource type
            result = await self.db.execute(
                select(
                    ResourceQuota.resource_type,
                    func.sum(ResourceQuota.current_usage).label('total_usage'),
                    func.sum(ResourceQuota.max_value).label('total_allocated'),
                    func.count(ResourceQuota.tenant_id).label('tenant_count')
                ).where(ResourceQuota.is_active == True)
                .group_by(ResourceQuota.resource_type)
            )
            
            overview = {}
            
            for row in result:
                resource_type = row.resource_type
                total_usage = float(row.total_usage or 0)
                total_allocated = float(row.total_allocated or 0)
                tenant_count = int(row.tenant_count or 0)
                
                utilization = (total_usage / total_allocated) * 100 if total_allocated > 0 else 0
                
                overview[resource_type] = {
                    "total_usage": total_usage,
                    "total_allocated": total_allocated,
                    "utilization_percentage": round(utilization, 2),
                    "tenant_count": tenant_count
                }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "resource_overview": overview,
                "total_tenants": len(set([row.tenant_count for row in result]))
            }
            
        except Exception as e:
            logger.error(f"Failed to get system resource overview: {e}")
            return {}
    
    async def get_resource_alerts(self, tenant_id: Optional[int] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get resource alerts for tenant(s).
        
        Args:
            tenant_id: Specific tenant ID (None for all tenants)
            hours: Hours back to look for alerts
            
        Returns:
            List of alert dictionaries
        """
        try:
            query = select(ResourceAlert).where(
                ResourceAlert.created_at >= datetime.utcnow() - timedelta(hours=hours)
            )
            
            if tenant_id:
                query = query.where(ResourceAlert.tenant_id == tenant_id)
            
            query = query.order_by(ResourceAlert.created_at.desc())
            
            result = await self.db.execute(query)
            alerts = result.scalars().all()
            
            return [
                {
                    "id": alert.id,
                    "tenant_id": alert.tenant_id,
                    "resource_type": alert.resource_type,
                    "alert_level": alert.alert_level,
                    "message": alert.message,
                    "current_usage": alert.current_usage,
                    "max_value": alert.max_value,
                    "percentage_used": alert.percentage_used,
                    "created_at": alert.created_at.isoformat()
                }
                for alert in alerts
            ]
            
        except Exception as e:
            logger.error(f"Failed to get resource alerts: {e}")
            return []