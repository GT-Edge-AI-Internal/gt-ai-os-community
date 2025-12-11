"""
Access Groups API for GT 2.0 Tenant Backend

RESTful API endpoints for managing resource access groups and permissions.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_current_user, verify_capability_token
from app.models.access_group import (
    AccessGroup, ResourceCreate, ResourceUpdate, ResourceResponse,
    AccessGroupModel
)
from app.services.access_controller import AccessController, AccessControlMiddleware


router = APIRouter(
    prefix="/api/v1/access-groups",
    tags=["access-groups"],
    responses={404: {"description": "Not found"}},
)


async def get_access_controller(
    x_tenant_domain: str = Header(..., description="Tenant domain")
) -> AccessController:
    """Dependency to get access controller for tenant"""
    return AccessController(x_tenant_domain)


async def get_middleware(
    x_tenant_domain: str = Header(..., description="Tenant domain")
) -> AccessControlMiddleware:
    """Dependency to get access control middleware"""
    return AccessControlMiddleware(x_tenant_domain)


@router.post("/resources", response_model=ResourceResponse)
async def create_resource(
    resource: ResourceCreate,
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new resource with access control.
    
    - **name**: Resource name
    - **resource_type**: Type of resource (agent, dataset, etc.)
    - **access_group**: Access level (individual, team, organization)
    - **team_members**: List of user IDs for team access
    - **metadata**: Resource-specific metadata
    """
    try:
        # Extract bearer token
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        capability_token = authorization.replace("Bearer ", "")
        
        # Get current user
        user = await get_current_user(authorization, db)
        
        # Create resource
        created_resource = await controller.create_resource(
            user_id=user.id,
            resource_data=resource,
            capability_token=capability_token
        )
        
        return ResourceResponse(
            id=created_resource.id,
            name=created_resource.name,
            resource_type=created_resource.resource_type,
            owner_id=created_resource.owner_id,
            tenant_domain=created_resource.tenant_domain,
            access_group=created_resource.access_group,
            team_members=created_resource.team_members,
            created_at=created_resource.created_at,
            updated_at=created_resource.updated_at,
            metadata=created_resource.metadata,
            file_path=created_resource.file_path
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create resource: {str(e)}")


@router.put("/resources/{resource_id}/access", response_model=ResourceResponse)
async def update_resource_access(
    resource_id: str,
    access_update: AccessGroupModel,
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    middleware: AccessControlMiddleware = Depends(get_middleware),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update resource access group.
    
    Only the resource owner can change access settings.
    
    - **access_group**: New access level
    - **team_members**: Updated team members list (for team access)
    """
    try:
        # Get current user
        user = await get_current_user(authorization, db)
        capability_token = authorization.replace("Bearer ", "")
        
        # Verify permission
        await middleware.verify_request(
            user_id=user.id,
            resource_id=resource_id,
            action="share",
            capability_token=capability_token
        )
        
        # Update access
        updated_resource = await controller.update_resource_access(
            user_id=user.id,
            resource_id=resource_id,
            new_access_group=access_update.access_group,
            team_members=access_update.team_members
        )
        
        return ResourceResponse(
            id=updated_resource.id,
            name=updated_resource.name,
            resource_type=updated_resource.resource_type,
            owner_id=updated_resource.owner_id,
            tenant_domain=updated_resource.tenant_domain,
            access_group=updated_resource.access_group,
            team_members=updated_resource.team_members,
            created_at=updated_resource.created_at,
            updated_at=updated_resource.updated_at,
            metadata=updated_resource.metadata,
            file_path=updated_resource.file_path
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update access: {str(e)}")


@router.get("/resources", response_model=List[ResourceResponse])
async def list_accessible_resources(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all resources accessible to the current user.
    
    Returns resources based on access groups:
    - Individual: Only owned resources
    - Team: Resources shared with user's teams
    - Organization: All organization-wide resources
    """
    try:
        # Get current user
        user = await get_current_user(authorization, db)
        
        # Get accessible resources
        resources = await controller.list_accessible_resources(
            user_id=user.id,
            resource_type=resource_type
        )
        
        return [
            ResourceResponse(
                id=r.id,
                name=r.name,
                resource_type=r.resource_type,
                owner_id=r.owner_id,
                tenant_domain=r.tenant_domain,
                access_group=r.access_group,
                team_members=r.team_members,
                created_at=r.created_at,
                updated_at=r.updated_at,
                metadata=r.metadata,
                file_path=r.file_path
            )
            for r in resources
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list resources: {str(e)}")


@router.get("/resources/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    middleware: AccessControlMiddleware = Depends(get_middleware),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific resource if user has access.
    
    Checks read permission based on access group.
    """
    try:
        # Get current user
        user = await get_current_user(authorization, db)
        capability_token = authorization.replace("Bearer ", "")
        
        # Verify permission
        await middleware.verify_request(
            user_id=user.id,
            resource_id=resource_id,
            action="read",
            capability_token=capability_token
        )
        
        # Load resource
        resource = await controller._load_resource(resource_id)
        
        return ResourceResponse(
            id=resource.id,
            name=resource.name,
            resource_type=resource.resource_type,
            owner_id=resource.owner_id,
            tenant_domain=resource.tenant_domain,
            access_group=resource.access_group,
            team_members=resource.team_members,
            created_at=resource.created_at,
            updated_at=resource.updated_at,
            metadata=resource.metadata,
            file_path=resource.file_path
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get resource: {str(e)}")


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    middleware: AccessControlMiddleware = Depends(get_middleware),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Delete a resource.
    
    Only the resource owner can delete.
    """
    try:
        # Get current user
        user = await get_current_user(authorization, db)
        capability_token = authorization.replace("Bearer ", "")
        
        # Verify permission
        await middleware.verify_request(
            user_id=user.id,
            resource_id=resource_id,
            action="delete",
            capability_token=capability_token
        )
        
        # Delete resource (implementation needed)
        # await controller.delete_resource(resource_id)
        
        return {"status": "deleted", "resource_id": resource_id}
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete resource: {str(e)}")


@router.get("/stats")
async def get_resource_stats(
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get resource statistics for the current user.
    
    Returns counts by type and access group.
    """
    try:
        # Get current user
        user = await get_current_user(authorization, db)
        
        # Get stats
        stats = await controller.get_resource_stats(user_id=user.id)
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/resources/{resource_id}/team-members/{user_id}")
async def add_team_member(
    resource_id: str,
    user_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    middleware: AccessControlMiddleware = Depends(get_middleware),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Add a user to team access for a resource.
    
    Only the resource owner can add team members.
    Resource must have team access group.
    """
    try:
        # Get current user
        current_user = await get_current_user(authorization, db)
        capability_token = authorization.replace("Bearer ", "")
        
        # Verify permission
        await middleware.verify_request(
            user_id=current_user.id,
            resource_id=resource_id,
            action="share",
            capability_token=capability_token
        )
        
        # Load resource
        resource = await controller._load_resource(resource_id)
        
        # Check if team access
        if resource.access_group != AccessGroup.TEAM:
            raise HTTPException(
                status_code=400, 
                detail="Resource must have team access to add members"
            )
        
        # Add team member
        resource.add_team_member(user_id)
        
        # Save changes (implementation needed)
        # await controller.save_resource(resource)
        
        return {"status": "added", "user_id": user_id, "resource_id": resource_id}
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add team member: {str(e)}")


@router.delete("/resources/{resource_id}/team-members/{user_id}")
async def remove_team_member(
    resource_id: str,
    user_id: str,
    authorization: str = Header(..., description="Bearer token"),
    x_tenant_domain: str = Header(..., description="Tenant domain"),
    controller: AccessController = Depends(get_access_controller),
    middleware: AccessControlMiddleware = Depends(get_middleware),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Remove a user from team access for a resource.
    
    Only the resource owner can remove team members.
    """
    try:
        # Get current user
        current_user = await get_current_user(authorization, db)
        capability_token = authorization.replace("Bearer ", "")
        
        # Verify permission
        await middleware.verify_request(
            user_id=current_user.id,
            resource_id=resource_id,
            action="share",
            capability_token=capability_token
        )
        
        # Load resource
        resource = await controller._load_resource(resource_id)
        
        # Remove team member
        resource.remove_team_member(user_id)
        
        # Save changes (implementation needed)
        # await controller.save_resource(resource)
        
        return {"status": "removed", "user_id": user_id, "resource_id": resource_id}
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove team member: {str(e)}")