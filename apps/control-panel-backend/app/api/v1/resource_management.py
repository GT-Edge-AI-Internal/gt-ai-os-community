"""
Resource Management API for GT 2.0 Control Panel

Provides comprehensive resource allocation and monitoring capabilities for admins.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.resource_allocation import ResourceAllocationService, ResourceType

router = APIRouter(prefix="/resource-management", tags=["Resource Management"])


# Pydantic models
class ResourceAllocationRequest(BaseModel):
    tenant_id: int
    template: str = Field(..., description="Resource template (startup, standard, enterprise)")


class ResourceScalingRequest(BaseModel):
    tenant_id: int
    resource_type: str = Field(..., description="Resource type to scale")
    scale_factor: float = Field(..., ge=0.1, le=10.0, description="Scaling factor (1.0 = no change)")


class ResourceUsageUpdateRequest(BaseModel):
    tenant_id: int
    resource_type: str
    usage_delta: float = Field(..., description="Change in usage (positive or negative)")


class ResourceQuotaResponse(BaseModel):
    id: int
    tenant_id: int
    resource_type: str
    max_value: float
    current_usage: float
    usage_percentage: float
    warning_threshold: float
    critical_threshold: float
    unit: str
    cost_per_unit: float
    is_active: bool
    created_at: str
    updated_at: str


class ResourceUsageResponse(BaseModel):
    resource_type: str
    current_usage: float
    max_allowed: float
    percentage_used: float
    cost_accrued: float
    last_updated: str


class ResourceAlertResponse(BaseModel):
    id: int
    tenant_id: int
    resource_type: str
    alert_level: str
    message: str
    current_usage: float
    max_value: float
    percentage_used: float
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[str]
    created_at: str


class SystemResourceOverviewResponse(BaseModel):
    timestamp: str
    resource_overview: Dict[str, Any]
    total_tenants: int


class TenantCostResponse(BaseModel):
    tenant_id: int
    period_start: str
    period_end: str
    total_cost: float
    costs_by_resource: Dict[str, Any]
    currency: str


@router.post("/allocate", status_code=status.HTTP_201_CREATED)
async def allocate_tenant_resources(
    request: ResourceAllocationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Allocate initial resources to a tenant based on template.
    """
    # Check admin permissions
    if current_user.user_type != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    
    try:
        service = ResourceAllocationService(db)
        success = await service.allocate_resources(request.tenant_id, request.template)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to allocate resources"
            )
        
        return {"message": "Resources allocated successfully", "tenant_id": request.tenant_id}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resource allocation failed: {str(e)}"
        )


@router.get("/tenant/{tenant_id}/usage", response_model=Dict[str, ResourceUsageResponse])
async def get_tenant_resource_usage(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current resource usage for a specific tenant.
    """
    # Check permissions
    if current_user.user_type != "super_admin":
        # Regular users can only view their own tenant
        if current_user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    
    try:
        service = ResourceAllocationService(db)
        usage_data = await service.get_tenant_resource_usage(tenant_id)
        
        # Convert to response format
        response = {}
        for resource_type, data in usage_data.items():
            response[resource_type] = ResourceUsageResponse(
                resource_type=data.resource_type.value,
                current_usage=data.current_usage,
                max_allowed=data.max_allowed,
                percentage_used=data.percentage_used,
                cost_accrued=data.cost_accrued,
                last_updated=data.last_updated.isoformat()
            )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resource usage: {str(e)}"
        )


@router.post("/usage/update")
async def update_resource_usage(
    request: ResourceUsageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update resource usage for a tenant (usually called by services).
    """
    # This endpoint is typically called by services, so we allow tenant users for their own tenant
    if current_user.user_type != "super_admin":
        if current_user.tenant_id != request.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    
    try:
        # Validate resource type
        try:
            resource_type = ResourceType(request.resource_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid resource type: {request.resource_type}"
            )
        
        service = ResourceAllocationService(db)
        success = await service.update_resource_usage(
            request.tenant_id,
            resource_type,
            request.usage_delta
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update resource usage (quota exceeded or not found)"
            )
        
        return {"message": "Resource usage updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update resource usage: {str(e)}"
        )


@router.post("/scale")
async def scale_tenant_resources(
    request: ResourceScalingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Scale tenant resources up or down.
    """
    # Check admin permissions
    if current_user.user_type != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    
    try:
        # Validate resource type
        try:
            resource_type = ResourceType(request.resource_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid resource type: {request.resource_type}"
            )
        
        service = ResourceAllocationService(db)
        success = await service.scale_tenant_resources(
            request.tenant_id,
            resource_type,
            request.scale_factor
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to scale resources"
            )
        
        return {
            "message": "Resources scaled successfully",
            "tenant_id": request.tenant_id,
            "resource_type": request.resource_type,
            "scale_factor": request.scale_factor
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scale resources: {str(e)}"
        )


@router.get("/tenant/{tenant_id}/costs", response_model=TenantCostResponse)
async def get_tenant_costs(
    tenant_id: int,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    days: int = Query(30, ge=1, le=365, description="Days back from now if dates not specified"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get cost breakdown for a tenant over a date range.
    """
    # Check permissions
    if current_user.user_type != "super_admin":
        if current_user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    
    try:
        # Parse dates
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(days=days)
        
        service = ResourceAllocationService(db)
        cost_data = await service.get_tenant_costs(tenant_id, start_dt, end_dt)
        
        if not cost_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No cost data found for tenant"
            )
        
        return TenantCostResponse(**cost_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant costs: {str(e)}"
        )


@router.get("/alerts", response_model=List[ResourceAlertResponse])
async def get_resource_alerts(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    hours: int = Query(24, ge=1, le=168, description="Hours back to look for alerts"),
    alert_level: Optional[str] = Query(None, description="Filter by alert level"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get resource alerts for tenant(s).
    """
    # Check permissions
    if current_user.user_type != "super_admin":
        # Regular users can only see their own tenant alerts
        if tenant_id and current_user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        tenant_id = current_user.tenant_id
    
    try:
        service = ResourceAllocationService(db)
        alerts = await service.get_resource_alerts(tenant_id, hours)
        
        # Filter by alert level if specified
        if alert_level:
            alerts = [alert for alert in alerts if alert['alert_level'] == alert_level]
        
        return [ResourceAlertResponse(**alert) for alert in alerts]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resource alerts: {str(e)}"
        )


@router.get("/system/overview", response_model=SystemResourceOverviewResponse)
async def get_system_resource_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get system-wide resource usage overview (admin only).
    """
    # Check admin permissions
    if current_user.user_type != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    
    try:
        service = ResourceAllocationService(db)
        overview = await service.get_system_resource_overview()
        
        if not overview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No system resource data available"
            )
        
        return SystemResourceOverviewResponse(**overview)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system overview: {str(e)}"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Acknowledge a resource alert.
    """
    try:
        from app.models.resource_usage import ResourceAlert
        from sqlalchemy import select, update
        
        # Get the alert
        result = await db.execute(select(ResourceAlert).where(ResourceAlert.id == alert_id))
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Check permissions
        if current_user.user_type != "super_admin":
            if current_user.tenant_id != alert.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
        
        # Acknowledge the alert
        alert.acknowledge(current_user.email)
        await db.commit()
        
        return {"message": "Alert acknowledged successfully", "alert_id": alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert: {str(e)}"
        )


@router.get("/templates")
async def get_resource_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get available resource allocation templates.
    """
    try:
        # Return hardcoded templates for now
        templates = {
            "startup": {
                "name": "startup",
                "display_name": "Startup",
                "description": "Basic resources for small teams and development",
                "monthly_cost": 99.0,
                "resources": {
                    "cpu": {"limit": 2.0, "unit": "cores"},
                    "memory": {"limit": 4096, "unit": "MB"},
                    "storage": {"limit": 10240, "unit": "MB"},
                    "api_calls": {"limit": 10000, "unit": "calls/hour"},
                    "model_inference": {"limit": 1000, "unit": "tokens"}
                }
            },
            "standard": {
                "name": "standard",
                "display_name": "Standard",
                "description": "Standard resources for production workloads",
                "monthly_cost": 299.0,
                "resources": {
                    "cpu": {"limit": 4.0, "unit": "cores"},
                    "memory": {"limit": 8192, "unit": "MB"},
                    "storage": {"limit": 51200, "unit": "MB"},
                    "api_calls": {"limit": 50000, "unit": "calls/hour"},
                    "model_inference": {"limit": 10000, "unit": "tokens"}
                }
            },
            "enterprise": {
                "name": "enterprise",
                "display_name": "Enterprise",
                "description": "High-performance resources for large organizations",
                "monthly_cost": 999.0,
                "resources": {
                    "cpu": {"limit": 16.0, "unit": "cores"},
                    "memory": {"limit": 32768, "unit": "MB"},
                    "storage": {"limit": 102400, "unit": "MB"},
                    "api_calls": {"limit": 200000, "unit": "calls/hour"},
                    "model_inference": {"limit": 100000, "unit": "tokens"},
                    "gpu_time": {"limit": 1000, "unit": "minutes"}
                }
            }
        }
        
        return {"templates": templates}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resource templates: {str(e)}"
        )


# Agent Library Templates Endpoints

class AssistantTemplateRequest(BaseModel):
    name: str
    description: str
    category: str
    icon: str = "🤖"
    system_prompt: str
    capabilities: List[str] = []
    tags: List[str] = []
    access_groups: List[str] = []


class AssistantTemplateResponse(BaseModel):
    id: str
    template_id: str
    name: str
    description: str
    category: str
    icon: str
    version: str
    status: str
    access_groups: List[str]
    deployment_count: int
    active_instances: int
    popularity_score: int
    last_updated: str
    created_by: str
    created_at: str
    capabilities: List[str]
    prompt_preview: str
    tags: List[str]
    compatibility: List[str]


@router.get("/templates/", response_model=dict)
async def list_agent_templates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List agent templates for the agent library.
    """
    try:
        # Mock data for now - replace with actual database queries
        mock_templates = [
            {
                "id": "1",
                "template_id": "cybersec_analyst",
                "name": "Cybersecurity Analyst",
                "description": "AI agent specialized in cybersecurity analysis, threat detection, and incident response",
                "category": "cybersecurity",
                "icon": "🛡️",
                "version": "1.2.0",
                "status": "published",
                "access_groups": ["security_team", "admin"],
                "deployment_count": 15,
                "active_instances": 8,
                "popularity_score": 92,
                "last_updated": "2024-01-15T10:30:00Z",
                "created_by": "admin@gt2.com",
                "created_at": "2024-01-10T14:20:00Z",
                "capabilities": ["threat_analysis", "log_analysis", "incident_response", "compliance_check"],
                "prompt_preview": "You are a cybersecurity analyst agent...",
                "tags": ["security", "analysis", "incident"],
                "compatibility": ["gpt-4", "claude-3"]
            },
            {
                "id": "2", 
                "template_id": "research_assistant",
                "name": "Research Agent",
                "description": "Academic research helper for literature review, data analysis, and paper writing",
                "category": "research",
                "icon": "📚",
                "version": "2.0.1",
                "status": "published",
                "access_groups": ["researchers", "academics"],
                "deployment_count": 23,
                "active_instances": 12,
                "popularity_score": 88,
                "last_updated": "2024-01-12T16:45:00Z",
                "created_by": "research@gt2.com",
                "created_at": "2024-01-05T09:15:00Z",
                "capabilities": ["literature_search", "data_analysis", "citation_help", "writing_assistance"],
                "prompt_preview": "You are an academic research agent...",
                "tags": ["research", "academic", "writing"],
                "compatibility": ["gpt-4", "claude-3", "llama-2"]
            },
            {
                "id": "3",
                "template_id": "code_reviewer",
                "name": "Code Reviewer",
                "description": "AI agent for code review, best practices, and security vulnerability detection",
                "category": "development",
                "icon": "💻",
                "version": "1.5.0",
                "status": "testing",
                "access_groups": ["developers", "devops"],
                "deployment_count": 7,
                "active_instances": 4,
                "popularity_score": 85,
                "last_updated": "2024-01-18T11:20:00Z",
                "created_by": "dev@gt2.com",
                "created_at": "2024-01-15T13:30:00Z",
                "capabilities": ["code_review", "security_scan", "best_practices", "refactoring"],
                "prompt_preview": "You are a senior code reviewer...",
                "tags": ["development", "code", "security"],
                "compatibility": ["gpt-4", "codex"]
            }
        ]
        
        # Apply filters
        filtered_templates = mock_templates
        if category:
            filtered_templates = [t for t in filtered_templates if t["category"] == category]
        if status:
            filtered_templates = [t for t in filtered_templates if t["status"] == status]
        
        # Apply pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_templates = filtered_templates[start:end]
        
        return {
            "data": {
                "templates": paginated_templates,
                "total": len(filtered_templates),
                "page": page,
                "limit": limit
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agent templates: {str(e)}"
        )


@router.get("/access-groups/", response_model=dict)
async def list_access_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List access groups for agent templates.
    """
    try:
        # Mock data for now
        mock_access_groups = [
            {
                "id": "1",
                "name": "security_team",
                "description": "Cybersecurity team with access to security-focused agents",
                "tenant_count": 8,
                "permissions": ["deploy_security", "manage_policies", "view_logs"]
            },
            {
                "id": "2",
                "name": "researchers",
                "description": "Academic researchers and data analysts",
                "tenant_count": 12,
                "permissions": ["deploy_research", "access_data", "export_results"]
            },
            {
                "id": "3",
                "name": "developers",
                "description": "Software development teams",
                "tenant_count": 15,
                "permissions": ["deploy_code", "review_access", "ci_cd_integration"]
            },
            {
                "id": "4",
                "name": "admin",
                "description": "System administrators with full access",
                "tenant_count": 3,
                "permissions": ["full_access", "manage_templates", "system_config"]
            }
        ]
        
        return {
            "data": {
                "access_groups": mock_access_groups
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list access groups: {str(e)}"
        )


@router.get("/deployments/", response_model=dict)
async def get_deployments(
    template_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get deployment status for agent templates.
    """
    try:
        # Mock data for now
        mock_deployments = [
            {
                "id": "1",
                "template_id": "cybersec_analyst",
                "tenant_name": "Acme Corp",
                "tenant_id": "acme-corp",
                "status": "completed",
                "deployed_at": "2024-01-16T09:30:00Z",
                "customizations": {"theme": "dark", "language": "en"}
            },
            {
                "id": "2",
                "template_id": "research_assistant",
                "tenant_name": "University Lab",
                "tenant_id": "uni-lab",
                "status": "processing",
                "customizations": {"domain": "biology", "access_level": "restricted"}
            },
            {
                "id": "3",
                "template_id": "code_reviewer",
                "tenant_name": "DevTeam Inc",
                "tenant_id": "devteam-inc",
                "status": "failed",
                "error_message": "Insufficient resources available",
                "customizations": {"languages": ["python", "javascript"]}
            }
        ]
        
        # Filter by template_id if provided
        if template_id:
            mock_deployments = [d for d in mock_deployments if d["template_id"] == template_id]
        
        return {
            "data": {
                "deployments": mock_deployments
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deployments: {str(e)}"
        )