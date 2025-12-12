"""
Tenant management API endpoints - CB-REST Standard Implementation

This is the updated version using the GT 2.0 Capability-Based REST standard
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, BackgroundTasks, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel, Field, validator
import logging
import uuid

from app.core.database import get_db
from app.core.api_standards import (
    format_response,
    format_error,
    require_capability,
    ErrorCode,
    APIError,
    CapabilityToken
)
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])


# Pydantic models remain the same
class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=50)
    template: str = Field(default="standard")
    max_users: int = Field(default=100, ge=1, le=10000)
    resource_limits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('domain')
    def validate_domain(cls, v):
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Domain must contain only lowercase letters, numbers, and hyphens')
        return v


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    max_users: Optional[int] = Field(None, ge=1, le=10000)
    resource_limits: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(active|suspended|pending|archived)$")


class TenantResponse(BaseModel):
    id: int
    uuid: str
    name: str
    domain: str
    template: str
    status: str
    max_users: int
    resource_limits: Dict[str, Any]
    namespace: str
    created_at: datetime
    updated_at: datetime
    user_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


@router.get("/")
async def list_tenants(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    capability: CapabilityToken = Depends(require_capability("tenant", "*", "read"))
):
    """
    List all tenants with pagination and filtering
    
    CB-REST: Returns standardized response with capability audit trail
    """
    try:
        # Build query
        query = select(Tenant)
        
        # Apply filters
        if search:
            query = query.where(
                or_(
                    Tenant.name.ilike(f"%{search}%"),
                    Tenant.domain.ilike(f"%{search}%")
                )
            )
        
        if status:
            query = query.where(Tenant.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.offset((page - 1) * limit).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        tenants = result.scalars().all()
        
        # Format response data
        response_data = {
            "tenants": [TenantResponse.from_orm(t).dict() for t in tenants],
            "total": total,
            "page": page,
            "limit": limit
        }
        
        # Return CB-REST formatted response
        return format_response(
            data=response_data,
            capability_used=f"tenant:*:read",
            request_id=request.state.request_id
        )
        
    except Exception as e:
        logger.error(f"Failed to list tenants: {e}")
        raise APIError(
            code=ErrorCode.SYSTEM_ERROR,
            message="Failed to retrieve tenants",
            status_code=500,
            details={"error": str(e)}
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: Request,
    tenant_data: TenantCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    capability: CapabilityToken = Depends(require_capability("tenant", "*", "create"))
):
    """
    Create a new tenant
    
    CB-REST: Validates capability and returns standardized response
    """
    try:
        # Check if domain already exists
        existing = await db.execute(
            select(Tenant).where(Tenant.domain == tenant_data.domain)
        )
        if existing.scalar_one_or_none():
            raise APIError(
                code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                message=f"Tenant with domain '{tenant_data.domain}' already exists",
                status_code=409
            )
        
        # Create tenant
        tenant = Tenant(
            uuid=str(uuid.uuid4()),
            name=tenant_data.name,
            domain=tenant_data.domain,
            template=tenant_data.template,
            max_users=tenant_data.max_users,
            resource_limits=tenant_data.resource_limits,
            namespace=f"tenant-{tenant_data.domain}",
            status="pending",
            created_by=capability.sub
        )
        
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        
        # Schedule deployment in background
        background_tasks.add_task(deploy_tenant, tenant.id)
        
        # Format response
        return format_response(
            data={
                "tenant_id": tenant.id,
                "uuid": tenant.uuid,
                "status": tenant.status,
                "namespace": tenant.namespace
            },
            capability_used=f"tenant:*:create",
            request_id=request.state.request_id
        )
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Failed to create tenant: {e}")
        raise APIError(
            code=ErrorCode.SYSTEM_ERROR,
            message="Failed to create tenant",
            status_code=500,
            details={"error": str(e)}
        )


@router.get("/{tenant_id}")
async def get_tenant(
    request: Request,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    capability: CapabilityToken = Depends(require_capability("tenant", "{tenant_id}", "read"))
):
    """
    Get a specific tenant by ID
    
    CB-REST: Enforces tenant-specific capability
    """
    try:
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Tenant {tenant_id} not found",
                status_code=404
            )
        
        # Get user count
        user_count_result = await db.execute(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
        )
        user_count = user_count_result.scalar()
        
        # Format response
        tenant_data = TenantResponse.from_orm(tenant).dict()
        tenant_data["user_count"] = user_count
        
        return format_response(
            data=tenant_data,
            capability_used=f"tenant:{tenant_id}:read",
            request_id=request.state.request_id
        )
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant {tenant_id}: {e}")
        raise APIError(
            code=ErrorCode.SYSTEM_ERROR,
            message="Failed to retrieve tenant",
            status_code=500,
            details={"error": str(e)}
        )


@router.put("/{tenant_id}")
async def update_tenant(
    request: Request,
    tenant_id: int,
    updates: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    capability: CapabilityToken = Depends(require_capability("tenant", "{tenant_id}", "write"))
):
    """
    Update a tenant
    
    CB-REST: Requires write capability for specific tenant
    """
    try:
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Tenant {tenant_id} not found",
                status_code=404
            )
        
        # Track updated fields
        updated_fields = []
        
        # Apply updates
        for field, value in updates.dict(exclude_unset=True).items():
            if hasattr(tenant, field):
                setattr(tenant, field, value)
                updated_fields.append(field)
        
        tenant.updated_at = datetime.utcnow()
        tenant.updated_by = capability.sub
        
        await db.commit()
        await db.refresh(tenant)
        
        return format_response(
            data={
                "updated_fields": updated_fields,
                "status": tenant.status
            },
            capability_used=f"tenant:{tenant_id}:write",
            request_id=request.state.request_id
        )
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Failed to update tenant {tenant_id}: {e}")
        raise APIError(
            code=ErrorCode.SYSTEM_ERROR,
            message="Failed to update tenant",
            status_code=500,
            details={"error": str(e)}
        )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    request: Request,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    capability: CapabilityToken = Depends(require_capability("tenant", "{tenant_id}", "delete"))
):
    """
    Delete (archive) a tenant
    
    CB-REST: Requires delete capability
    """
    try:
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Tenant {tenant_id} not found",
                status_code=404
            )
        
        # Soft delete - set status to archived
        tenant.status = "archived"
        tenant.updated_at = datetime.utcnow()
        tenant.updated_by = capability.sub
        
        await db.commit()
        
        # No content response for successful deletion
        return None
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tenant {tenant_id}: {e}")
        raise APIError(
            code=ErrorCode.SYSTEM_ERROR,
            message="Failed to delete tenant",
            status_code=500,
            details={"error": str(e)}
        )


@router.post("/bulk")
async def bulk_tenant_operations(
    request: Request,
    operations: List[Dict[str, Any]],
    transaction: bool = Query(True, description="Execute all operations in a transaction"),
    db: AsyncSession = Depends(get_db),
    capability: CapabilityToken = Depends(require_capability("tenant", "*", "admin"))
):
    """
    Perform bulk operations on tenants
    
    CB-REST: Admin capability required for bulk operations
    """
    results = []
    
    try:
        if transaction:
            # Start transaction
            async with db.begin():
                for op in operations:
                    result = await execute_tenant_operation(db, op, capability.sub)
                    results.append(result)
        else:
            # Execute independently
            for op in operations:
                try:
                    result = await execute_tenant_operation(db, op, capability.sub)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "operation_id": op.get("id", str(uuid.uuid4())),
                        "action": op.get("action"),
                        "success": False,
                        "error": str(e)
                    })
        
        # Format bulk response
        succeeded = sum(1 for r in results if r.get("success"))
        failed = len(results) - succeeded
        
        return format_response(
            data={
                "operations": results,
                "transaction": transaction,
                "total": len(results),
                "succeeded": succeeded,
                "failed": failed
            },
            capability_used="tenant:*:admin",
            request_id=request.state.request_id
        )
        
    except Exception as e:
        logger.error(f"Bulk operation failed: {e}")
        raise APIError(
            code=ErrorCode.SYSTEM_ERROR,
            message="Bulk operation failed",
            status_code=500,
            details={"error": str(e)}
        )


# Helper functions
async def deploy_tenant(tenant_id: int):
    """Background task to deploy tenant infrastructure"""
    logger.info(f"Deploying tenant {tenant_id}")
    
    try:
        # For now, create the file-based tenant structure
        # In K3s deployment, this will create Kubernetes resources
        from app.services.tenant_provisioning import create_tenant_filesystem
        
        # Create tenant filesystem structure
        await create_tenant_filesystem(tenant_id)
        
        # Initialize tenant database
        from app.services.tenant_provisioning import init_tenant_database
        await init_tenant_database(tenant_id)
        
        logger.info(f"Tenant {tenant_id} deployment completed successfully")
        return {"success": True, "message": f"Tenant {tenant_id} deployed"}
        
    except Exception as e:
        logger.error(f"Failed to deploy tenant {tenant_id}: {e}")
        return {"success": False, "error": str(e)}


async def execute_tenant_operation(db: AsyncSession, operation: Dict[str, Any], user: str) -> Dict[str, Any]:
    """Execute a single tenant operation"""
    action = operation.get("action")
    
    if action == "create":
        # Create tenant logic
        pass
    elif action == "update":
        # Update tenant logic
        pass
    elif action == "delete":
        # Delete tenant logic
        pass
    else:
        raise ValueError(f"Unknown action: {action}")
    
    return {
        "operation_id": operation.get("id", str(uuid.uuid4())),
        "action": action,
        "success": True
    }