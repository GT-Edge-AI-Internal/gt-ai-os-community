"""
GT 2.0 Control Panel - Resources API with CB-REST Standards
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import logging
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.api_standards import (
    format_response,
    format_error,
    ErrorCode,
    APIError,
    require_capability
)
from app.services.resource_service import ResourceService
from app.services.groq_service import groq_service
from app.models.ai_resource import AIResource

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resources", tags=["AI Resources"])


# Request/Response Models
class ResourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    resource_type: str
    provider: str
    model_name: Optional[str] = None
    personalization_mode: str = "shared"
    primary_endpoint: Optional[str] = None
    api_endpoints: List[str] = []
    failover_endpoints: List[str] = []
    health_check_url: Optional[str] = None
    max_requests_per_minute: int = 60
    max_tokens_per_request: int = 4000
    cost_per_1k_tokens: float = 0.0
    configuration: Dict[str, Any] = {}


class ResourceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    personalization_mode: Optional[str] = None
    primary_endpoint: Optional[str] = None
    api_endpoints: Optional[List[str]] = None
    failover_endpoints: Optional[List[str]] = None
    health_check_url: Optional[str] = None
    max_requests_per_minute: Optional[int] = None
    max_tokens_per_request: Optional[int] = None
    cost_per_1k_tokens: Optional[float] = None
    configuration: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class BulkAssignRequest(BaseModel):
    resource_ids: List[int]
    tenant_ids: List[int]
    usage_limits: Optional[Dict[str, Any]] = None
    custom_config: Optional[Dict[str, Any]] = None


@router.get("")
async def list_resources(
    request: Request,
    db: AsyncSession = Depends(get_db),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List all AI resources with filtering and pagination
    
    CB-REST Capability Required: resource:*:read
    """
    try:
        service = ResourceService(db)
        
        # Build filters
        filters = {}
        if resource_type:
            filters['resource_type'] = resource_type
        if provider:
            filters['provider'] = provider
        if is_active is not None:
            filters['is_active'] = is_active
        if search:
            filters['search'] = search
            
        resources = await service.list_resources(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        # Get categories for easier filtering
        categories = await service.get_resource_categories()
        
        return format_response(
            data={
                "resources": [r.dict() for r in resources],
                "categories": categories,
                "total": len(resources),
                "limit": limit,
                "offset": offset
            },
            capability_used="resource:*:read",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used="resource:*:read",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.post("")
async def create_resource(
    request: Request,
    resource: ResourceCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new AI resource
    
    CB-REST Capability Required: resource:*:create
    """
    try:
        service = ResourceService(db)
        
        # Create resource
        new_resource = await service.create_resource(
            name=resource.name,
            description=resource.description,
            resource_type=resource.resource_type,
            provider=resource.provider,
            model_name=resource.model_name,
            personalization_mode=resource.personalization_mode,
            primary_endpoint=resource.primary_endpoint,
            api_endpoints=resource.api_endpoints,
            failover_endpoints=resource.failover_endpoints,
            health_check_url=resource.health_check_url,
            max_requests_per_minute=resource.max_requests_per_minute,
            max_tokens_per_request=resource.max_tokens_per_request,
            cost_per_1k_tokens=resource.cost_per_1k_tokens,
            configuration=resource.configuration,
            created_by=getattr(request.state, 'user_email', 'system')
        )
        
        # Schedule health check
        if resource.health_check_url:
            background_tasks.add_task(
                service.perform_health_check,
                new_resource.id
            )
        
        return format_response(
            data={
                "resource_id": new_resource.id,
                "uuid": new_resource.uuid,
                "health_check_scheduled": bool(resource.health_check_url)
            },
            capability_used="resource:*:create",
            request_id=getattr(request.state, 'request_id', None)
        )
    except ValueError as e:
        logger.error(f"Invalid request for resource creation: {e}", exc_info=True)
        return format_error(
            code=ErrorCode.INVALID_REQUEST,
            message="Invalid request parameters",
            capability_used="resource:*:create",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to create resource: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used="resource:*:create",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.get("/{resource_id}")
async def get_resource(
    request: Request,
    resource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific AI resource with full configuration and metrics
    
    CB-REST Capability Required: resource:{resource_id}:read
    """
    try:
        service = ResourceService(db)
        resource = await service.get_resource(resource_id)
        
        if not resource:
            return format_error(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource {resource_id} not found",
                capability_used=f"resource:{resource_id}:read",
                request_id=getattr(request.state, 'request_id', None)
            )
        
        # Get additional metrics
        metrics = await service.get_resource_metrics(resource_id)
        
        return format_response(
            data={
                **resource.dict(),
                "metrics": metrics
            },
            capability_used=f"resource:{resource_id}:read",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to get resource {resource_id}: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used=f"resource:{resource_id}:read",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.put("/{resource_id}")
async def update_resource(
    request: Request,
    resource_id: int,
    update: ResourceUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an AI resource configuration
    
    CB-REST Capability Required: resource:{resource_id}:update
    """
    try:
        service = ResourceService(db)
        
        # Update resource
        updated_resource = await service.update_resource(
            resource_id=resource_id,
            **update.dict(exclude_unset=True)
        )
        
        if not updated_resource:
            return format_error(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource {resource_id} not found",
                capability_used=f"resource:{resource_id}:update",
                request_id=getattr(request.state, 'request_id', None)
            )
        
        # Schedule health check if endpoint changed
        if update.primary_endpoint or update.health_check_url:
            background_tasks.add_task(
                service.perform_health_check,
                resource_id
            )
        
        return format_response(
            data={
                "resource_id": resource_id,
                "updated_fields": list(update.dict(exclude_unset=True).keys()),
                "health_check_required": bool(update.primary_endpoint or update.health_check_url)
            },
            capability_used=f"resource:{resource_id}:update",
            request_id=getattr(request.state, 'request_id', None)
        )
    except ValueError as e:
        logger.error(f"Invalid request for resource update: {e}", exc_info=True)
        return format_error(
            code=ErrorCode.INVALID_REQUEST,
            message="Invalid request parameters",
            capability_used=f"resource:{resource_id}:update",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to update resource {resource_id}: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used=f"resource:{resource_id}:update",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.delete("/{resource_id}")
async def delete_resource(
    request: Request,
    resource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Archive an AI resource (soft delete)
    
    CB-REST Capability Required: resource:{resource_id}:delete
    """
    try:
        service = ResourceService(db)
        
        # Get affected tenants before deletion
        affected_tenants = await service.get_resource_tenants(resource_id)
        
        # Archive resource
        success = await service.archive_resource(resource_id)
        
        if not success:
            return format_error(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource {resource_id} not found",
                capability_used=f"resource:{resource_id}:delete",
                request_id=getattr(request.state, 'request_id', None)
            )
        
        return format_response(
            data={
                "archived": True,
                "affected_tenants": len(affected_tenants)
            },
            capability_used=f"resource:{resource_id}:delete",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to delete resource {resource_id}: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used=f"resource:{resource_id}:delete",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.post("/{resource_id}/health-check")
async def check_resource_health(
    request: Request,
    resource_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Perform health check on a resource
    
    CB-REST Capability Required: resource:{resource_id}:health
    """
    try:
        service = ResourceService(db)
        
        # Perform health check
        health_result = await service.perform_health_check(resource_id)
        
        if not health_result:
            return format_error(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource {resource_id} not found",
                capability_used=f"resource:{resource_id}:health",
                request_id=getattr(request.state, 'request_id', None)
            )
        
        return format_response(
            data=health_result,
            capability_used=f"resource:{resource_id}:health",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to check health for resource {resource_id}: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used=f"resource:{resource_id}:health",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.get("/types")
async def get_resource_types(request: Request):
    """
    Get all available resource types and their access groups
    
    CB-REST Capability Required: resource:*:read
    """
    try:
        resource_types = {
            "ai_ml": {
                "name": "AI/ML Models",
                "subtypes": ["llm", "embedding", "image_generation", "function_calling", "custom_model"],
                "access_groups": ["ai_advanced", "ai_basic"]
            },
            "rag_engine": {
                "name": "RAG Engines",
                "subtypes": ["document_processor", "vector_database", "retrieval_strategy"],
                "access_groups": ["knowledge_management", "document_processing"]
            },
            "agentic_workflow": {
                "name": "Agentic Workflows",
                "subtypes": ["single_agent", "multi_agent", "workflow_chain", "collaborative_agent"],
                "access_groups": ["advanced_workflows", "automation"]
            },
            "app_integration": {
                "name": "App Integrations",
                "subtypes": ["communication_app", "development_app", "project_management_app", "database_connector"],
                "access_groups": ["integration_tools", "development_tools"]
            },
            "external_service": {
                "name": "External Web Services",
                "subtypes": ["educational_service", "cybersecurity_service", "development_service", "remote_access_service"],
                "access_groups": ["external_platforms", "remote_labs"]
            },
            "ai_literacy": {
                "name": "AI Literacy & Cognitive Skills",
                "subtypes": ["strategic_game", "logic_puzzle", "philosophical_dilemma", "educational_content"],
                "access_groups": ["ai_literacy", "educational_tools"]
            }
        }
        
        return format_response(
            data={
                "resource_types": resource_types,
                "access_groups": list(set(
                    group 
                    for rt in resource_types.values() 
                    for group in rt["access_groups"]
                ))
            },
            capability_used="resource:*:read",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to get resource types: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used="resource:*:read",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.post("/bulk/assign")
async def bulk_assign_resources(
    request: Request,
    assignment: BulkAssignRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk assign resources to tenants
    
    CB-REST Capability Required: resource:*:assign
    """
    try:
        service = ResourceService(db)
        
        results = await service.bulk_assign_resources(
            resource_ids=assignment.resource_ids,
            tenant_ids=assignment.tenant_ids,
            usage_limits=assignment.usage_limits,
            custom_config=assignment.custom_config,
            assigned_by=getattr(request.state, 'user_email', 'system')
        )
        
        return format_response(
            data={
                "operation_id": str(uuid.uuid4()),
                "assigned": results["assigned"],
                "failed": results["failed"]
            },
            capability_used="resource:*:assign",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to bulk assign resources: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used="resource:*:assign",
            request_id=getattr(request.state, 'request_id', None)
        )


@router.post("/bulk/health-check")
async def bulk_health_check(
    request: Request,
    resource_ids: List[int],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Schedule health checks for multiple resources
    
    CB-REST Capability Required: resource:*:health
    """
    try:
        service = ResourceService(db)
        
        # Schedule health checks
        for resource_id in resource_ids:
            background_tasks.add_task(
                service.perform_health_check,
                resource_id
            )
        
        return format_response(
            data={
                "operation_id": str(uuid.uuid4()),
                "scheduled_checks": len(resource_ids)
            },
            capability_used="resource:*:health",
            request_id=getattr(request.state, 'request_id', None)
        )
    except Exception as e:
        logger.error(f"Failed to schedule bulk health checks: {e}")
        return format_error(
            code=ErrorCode.SYSTEM_ERROR,
            message="Internal server error",
            capability_used="resource:*:health",
            request_id=getattr(request.state, 'request_id', None)
        )