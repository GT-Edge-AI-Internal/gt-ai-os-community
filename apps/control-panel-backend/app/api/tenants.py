"""
Tenant management API endpoints
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel, Field, validator
import logging
import uuid

from app.core.database import get_db
from app.core.auth import JWTHandler, get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.services.model_management_service import get_model_management_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])


# Pydantic models
class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=50)
    template: str = Field(default="standard")
    max_users: int = Field(default=100, ge=1, le=10000)
    resource_limits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    frontend_url: Optional[str] = Field(None, max_length=255, description="Frontend URL for password reset emails (e.g., https://app.company.com)")

    @validator('domain')
    def validate_domain(cls, v):
        # Only allow alphanumeric and hyphens
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Domain must contain only lowercase letters, numbers, and hyphens')
        return v

    @validator('frontend_url')
    def validate_frontend_url(cls, v):
        if v is not None and v.strip():
            import re
            # Basic URL validation
            if not re.match(r'^https?://.+', v):
                raise ValueError('Frontend URL must start with http:// or https://')
        return v


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    max_users: Optional[int] = Field(None, ge=1, le=10000)
    resource_limits: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(active|suspended|pending|archived)$")
    frontend_url: Optional[str] = Field(None, max_length=255, description="Frontend URL for password reset emails")

    # Budget configuration
    monthly_budget_cents: Optional[int] = Field(None, description="Monthly budget in cents (NULL = unlimited)")
    budget_warning_threshold: Optional[int] = Field(None, ge=1, le=100, description="Warning threshold percentage (1-100)")
    budget_critical_threshold: Optional[int] = Field(None, ge=1, le=100, description="Critical threshold percentage (1-100)")
    budget_enforcement_enabled: Optional[bool] = Field(None, description="Enable budget enforcement")

    # Hot tier storage pricing (NULL = use default $0.15/GiB/month)
    storage_price_dataset_hot: Optional[float] = Field(None, description="Dataset hot storage price per GiB/month")
    storage_price_conversation_hot: Optional[float] = Field(None, description="Conversation hot storage price per GiB/month")

    # Cold tier: Allocation-based model
    cold_storage_allocated_tibs: Optional[float] = Field(None, description="Cold storage allocation in TiBs")
    cold_storage_price_per_tib: Optional[float] = Field(None, description="Cold storage price per TiB/month (default: $10)")

    @validator('frontend_url')
    def validate_frontend_url(cls, v):
        if v is not None and v.strip():
            import re
            if not re.match(r'^https?://.+', v):
                raise ValueError('Frontend URL must start with http:// or https://')
        return v


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
    frontend_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user_count: Optional[int] = 0

    # Budget configuration
    monthly_budget_cents: Optional[int] = None
    budget_warning_threshold: Optional[int] = None
    budget_critical_threshold: Optional[int] = None
    budget_enforcement_enabled: Optional[bool] = None

    # Hot tier storage pricing
    storage_price_dataset_hot: Optional[float] = None
    storage_price_conversation_hot: Optional[float] = None

    # Cold tier allocation
    cold_storage_allocated_tibs: Optional[float] = None
    cold_storage_price_per_tib: Optional[float] = None

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]
    total: int
    page: int
    limit: int


@router.get("/", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all tenants with pagination and filtering"""
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
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
        count_query = select(func.count()).select_from(Tenant)
        if search:
            count_query = count_query.where(
                or_(
                    Tenant.name.ilike(f"%{search}%"),
                    Tenant.domain.ilike(f"%{search}%")
                )
            )
        if status:
            count_query = count_query.where(Tenant.status == status)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Tenant.created_at.desc())
        
        # Execute query
        result = await db.execute(query)
        tenants = result.scalars().all()
        
        # Get user counts for each tenant
        tenant_responses = []
        for tenant in tenants:
            user_count_query = select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
            user_count_result = await db.execute(user_count_query)
            user_count = user_count_result.scalar() or 0
            
            tenant_dict = {
                "id": tenant.id,
                "uuid": tenant.uuid,
                "name": tenant.name,
                "domain": tenant.domain,
                "template": tenant.template,
                "status": tenant.status,
                "max_users": tenant.max_users,
                "resource_limits": tenant.resource_limits or {},
                "namespace": tenant.namespace,
                "frontend_url": tenant.frontend_url,
                "created_at": tenant.created_at,
                "updated_at": tenant.updated_at,
                "user_count": user_count,
                # Budget configuration
                "monthly_budget_cents": tenant.monthly_budget_cents,
                "budget_warning_threshold": tenant.budget_warning_threshold,
                "budget_critical_threshold": tenant.budget_critical_threshold,
                "budget_enforcement_enabled": tenant.budget_enforcement_enabled,
                # Hot tier storage pricing
                "storage_price_dataset_hot": float(tenant.storage_price_dataset_hot) if tenant.storage_price_dataset_hot else None,
                "storage_price_conversation_hot": float(tenant.storage_price_conversation_hot) if tenant.storage_price_conversation_hot else None,
                # Cold tier allocation
                "cold_storage_allocated_tibs": float(tenant.cold_storage_allocated_tibs) if tenant.cold_storage_allocated_tibs else None,
                "cold_storage_price_per_tib": float(tenant.cold_storage_price_per_tib) if tenant.cold_storage_price_per_tib else 10.00,
            }
            tenant_responses.append(TenantResponse(**tenant_dict))
        
        return TenantListResponse(
            tenants=tenant_responses,
            total=total,
            page=page,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tenants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenants"
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific tenant by ID"""
    try:
        # Check permissions
        if current_user.user_type != "super_admin":
            # Regular users can only view their own tenant
            if current_user.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
        
        # Get tenant
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get user count
        user_count_query = select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
        user_count_result = await db.execute(user_count_query)
        user_count = user_count_result.scalar() or 0
        
        return TenantResponse(
            id=tenant.id,
            uuid=tenant.uuid,
            name=tenant.name,
            domain=tenant.domain,
            template=tenant.template,
            status=tenant.status,
            max_users=tenant.max_users,
            resource_limits=tenant.resource_limits or {},
            namespace=tenant.namespace,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            user_count=user_count,
            # Budget configuration
            monthly_budget_cents=tenant.monthly_budget_cents,
            budget_warning_threshold=tenant.budget_warning_threshold,
            budget_critical_threshold=tenant.budget_critical_threshold,
            budget_enforcement_enabled=tenant.budget_enforcement_enabled,
            # Hot tier storage pricing
            storage_price_dataset_hot=float(tenant.storage_price_dataset_hot) if tenant.storage_price_dataset_hot else None,
            storage_price_conversation_hot=float(tenant.storage_price_conversation_hot) if tenant.storage_price_conversation_hot else None,
            # Cold tier allocation
            cold_storage_allocated_tibs=float(tenant.cold_storage_allocated_tibs) if tenant.cold_storage_allocated_tibs else None,
            cold_storage_price_per_tib=float(tenant.cold_storage_price_per_tib) if tenant.cold_storage_price_per_tib else 10.00,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant {tenant_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenant"
        )


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new tenant"""
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Check if domain already exists
        existing = await db.execute(
            select(Tenant).where(Tenant.domain == tenant_data.domain)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain already exists"
            )
        
        # Create tenant
        tenant = Tenant(
            uuid=str(uuid.uuid4()),
            name=tenant_data.name,
            domain=tenant_data.domain,
            template=tenant_data.template,
            status="pending",
            max_users=tenant_data.max_users,
            resource_limits=tenant_data.resource_limits or {},
            namespace=f"gt-{tenant_data.domain}",
            subdomain=tenant_data.domain  # Set subdomain to match domain
        )
        
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        # Auto-assign all active models to this new tenant
        model_service = get_model_management_service(db)
        assigned_count = await model_service.auto_assign_all_models_to_tenant(tenant.id)
        logger.info(f"Auto-assigned {assigned_count} models to new tenant {tenant.domain}")

        # Add background task to deploy tenant infrastructure
        from app.services.tenant_provisioning import deploy_tenant_infrastructure
        background_tasks.add_task(deploy_tenant_infrastructure, tenant.id)

        return TenantResponse(
            id=tenant.id,
            uuid=tenant.uuid,
            name=tenant.name,
            domain=tenant.domain,
            template=tenant.template,
            status=tenant.status,
            max_users=tenant.max_users,
            resource_limits=tenant.resource_limits,
            namespace=tenant.namespace,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            user_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant"
        )


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a tenant"""
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Get tenant
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Update fields
        update_data = tenant_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tenant, field, value)
        
        tenant.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(tenant)
        
        # Get user count
        user_count_query = select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
        user_count_result = await db.execute(user_count_query)
        user_count = user_count_result.scalar() or 0
        
        return TenantResponse(
            id=tenant.id,
            uuid=tenant.uuid,
            name=tenant.name,
            domain=tenant.domain,
            template=tenant.template,
            status=tenant.status,
            max_users=tenant.max_users,
            resource_limits=tenant.resource_limits,
            namespace=tenant.namespace,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            user_count=user_count,
            # Budget configuration
            monthly_budget_cents=tenant.monthly_budget_cents,
            budget_warning_threshold=tenant.budget_warning_threshold,
            budget_critical_threshold=tenant.budget_critical_threshold,
            budget_enforcement_enabled=tenant.budget_enforcement_enabled,
            # Hot tier storage pricing
            storage_price_dataset_hot=float(tenant.storage_price_dataset_hot) if tenant.storage_price_dataset_hot else None,
            storage_price_conversation_hot=float(tenant.storage_price_conversation_hot) if tenant.storage_price_conversation_hot else None,
            # Cold tier allocation
            cold_storage_allocated_tibs=float(tenant.cold_storage_allocated_tibs) if tenant.cold_storage_allocated_tibs else None,
            cold_storage_price_per_tib=float(tenant.cold_storage_price_per_tib) if tenant.cold_storage_price_per_tib else 10.00,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant {tenant_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant"
        )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete (archive) a tenant"""
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can delete tenants"
            )
        
        # Get tenant
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Archive instead of hard delete
        tenant.status = "archived"
        tenant.deleted_at = datetime.utcnow()
        
        await db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tenant {tenant_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant"
        )


@router.post("/{tenant_id}/deploy", status_code=status.HTTP_202_ACCEPTED)
async def deploy_tenant(
    tenant_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deploy tenant infrastructure"""
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Get tenant
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Update status
        tenant.status = "deploying"
        await db.commit()
        
        # Add background task to deploy infrastructure
        from app.services.tenant_provisioning import deploy_tenant_infrastructure
        background_tasks.add_task(deploy_tenant_infrastructure, tenant_id)
        
        return {"message": "Deployment initiated", "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deploying tenant {tenant_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deploy tenant"
        )


# Optics Feature Toggle
class OpticsToggleRequest(BaseModel):
    enabled: bool = Field(..., description="Whether to enable Optics cost tracking")


class OpticsToggleResponse(BaseModel):
    tenant_id: int
    domain: str
    optics_enabled: bool
    message: str


@router.put("/{tenant_id}/optics", response_model=OpticsToggleResponse)
async def toggle_optics(
    tenant_id: int,
    request: OpticsToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle Optics cost tracking for a tenant.

    When enabled, the Optics tab will appear in the tenant's observability dashboard
    showing inference costs and storage costs.
    """
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        # Get tenant
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        # Update optics_enabled
        tenant.optics_enabled = request.enabled
        tenant.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(tenant)

        action = "enabled" if request.enabled else "disabled"
        logger.info(f"Optics {action} for tenant {tenant.domain} by {current_user.email}")

        return OpticsToggleResponse(
            tenant_id=tenant.id,
            domain=tenant.domain,
            optics_enabled=tenant.optics_enabled,
            message=f"Optics cost tracking {action} for {tenant.name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling optics for tenant {tenant_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle optics setting"
        )


@router.get("/{tenant_id}/optics")
async def get_optics_status(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current Optics status for a tenant"""
    try:
        # Require super_admin only
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        # Get tenant
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        return {
            "tenant_id": tenant.id,
            "domain": tenant.domain,
            "optics_enabled": tenant.optics_enabled or False
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting optics status for tenant {tenant_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optics status"
        )