"""
Analytics and Dremio SQL Federation Endpoints
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.services.dremio_service import DremioService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


class TenantDashboardResponse(BaseModel):
    """Response model for tenant dashboard data"""
    tenant: Dict[str, Any]
    metrics: Dict[str, Any]
    analytics: Dict[str, Any]
    alerts: List[Dict[str, Any]]


class CustomQueryRequest(BaseModel):
    """Request model for custom analytics queries"""
    query_type: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class DatasetCreationResponse(BaseModel):
    """Response model for dataset creation"""
    tenant_id: int
    datasets_created: List[str]
    status: str


@router.get("/dashboard/{tenant_id}", response_model=TenantDashboardResponse)
async def get_tenant_dashboard(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive dashboard data for a tenant using Dremio SQL federation"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view dashboard"
        )
    
    
    service = DremioService(db)
    
    try:
        dashboard_data = await service.get_tenant_dashboard_data(tenant_id)
        return TenantDashboardResponse(**dashboard_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )


@router.post("/query/{tenant_id}")
async def execute_custom_analytics(
    tenant_id: int,
    request: CustomQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute custom analytics queries for a tenant"""
    
    # Check permissions (only admins)
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for analytics queries"
        )
    
    
    service = DremioService(db)
    
    try:
        results = await service.get_custom_analytics(
            tenant_id=tenant_id,
            query_type=request.query_type,
            start_date=request.start_date,
            end_date=request.end_date
        )
        return {
            "query_type": request.query_type,
            "results": results,
            "count": len(results)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}"
        )


@router.post("/datasets/create/{tenant_id}", response_model=DatasetCreationResponse)
async def create_virtual_datasets(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create Dremio virtual datasets for tenant analytics"""
    
    # Check permissions (only GT admin)
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only GT admins can create virtual datasets"
        )
    
    service = DremioService(db)
    
    try:
        result = await service.create_virtual_datasets(tenant_id)
        return DatasetCreationResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create datasets: {str(e)}"
        )


@router.get("/metrics/performance/{tenant_id}")
async def get_performance_metrics(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time performance metrics for a tenant"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view metrics"
        )
    
    if current_user.user_type == 'tenant_admin' and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view metrics for other tenants"
        )
    
    service = DremioService(db)
    
    try:
        metrics = await service._get_performance_metrics(tenant_id)
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch metrics: {str(e)}"
        )


@router.get("/alerts/{tenant_id}")
async def get_security_alerts(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get security and operational alerts for a tenant"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view alerts"
        )
    
    if current_user.user_type == 'tenant_admin' and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view alerts for other tenants"
        )
    
    service = DremioService(db)
    
    try:
        alerts = await service._get_security_alerts(tenant_id)
        return {
            "tenant_id": tenant_id,
            "alerts": alerts,
            "total": len(alerts),
            "critical": len([a for a in alerts if a.get('severity') == 'critical']),
            "warning": len([a for a in alerts if a.get('severity') == 'warning']),
            "info": len([a for a in alerts if a.get('severity') == 'info'])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts: {str(e)}"
        )


@router.get("/query-types")
async def get_available_query_types(
    current_user: User = Depends(get_current_user)
):
    """Get list of available analytics query types"""
    
    return {
        "query_types": [
            {
                "id": "user_activity",
                "name": "User Activity Analysis",
                "description": "Analyze user activity, token usage, and costs"
            },
            {
                "id": "resource_trends",
                "name": "Resource Usage Trends",
                "description": "View resource usage trends over time"
            },
            {
                "id": "cost_optimization",
                "name": "Cost Optimization Report",
                "description": "Identify cost optimization opportunities"
            }
        ]
    }