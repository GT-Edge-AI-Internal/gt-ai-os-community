"""
Dataset Sharing API for GT 2.0

RESTful API for hierarchical dataset sharing with capability-based access control.
Enables secure collaboration while maintaining perfect tenant isolation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user, verify_capability_token
from app.services.dataset_sharing import (
    DatasetSharingService, DatasetShare, DatasetInfo, SharingPermission
)
from app.services.access_controller import AccessController
from app.models.access_group import AccessGroup

router = APIRouter()


# Request/Response Models
class ShareDatasetRequest(BaseModel):
    """Request to share a dataset"""
    dataset_id: str = Field(..., description="Dataset ID to share")
    access_group: str = Field(..., description="Access group: individual, team, organization")
    team_members: Optional[List[str]] = Field(None, description="Team members for team sharing")
    team_permissions: Optional[Dict[str, str]] = Field(None, description="Permissions for team members")
    expires_days: Optional[int] = Field(None, description="Expiration in days")


class UpdatePermissionRequest(BaseModel):
    """Request to update team member permissions"""
    user_id: str = Field(..., description="User ID to update")
    permission: str = Field(..., description="Permission: read, write, admin")


class DatasetShareResponse(BaseModel):
    """Dataset sharing configuration response"""
    id: str
    dataset_id: str
    owner_id: str
    access_group: str
    team_members: List[str]
    team_permissions: Dict[str, str]
    shared_at: datetime
    expires_at: Optional[datetime]
    is_active: bool


class DatasetInfoResponse(BaseModel):
    """Dataset information response"""
    id: str
    name: str
    description: str
    owner_id: str
    document_count: int
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    tags: List[str]


class SharingStatsResponse(BaseModel):
    """Sharing statistics response"""
    owned_datasets: int
    shared_with_me: int
    sharing_breakdown: Dict[str, int]
    total_team_members: int
    expired_shares: int


# Dependency injection
async def get_dataset_sharing_service(
    authorization: str = Header(...),
    current_user: str = Depends(get_current_user)
) -> DatasetSharingService:
    """Get dataset sharing service with access controller"""
    # Extract tenant from token (mock implementation)
    tenant_domain = "customer1.com"  # Would extract from JWT
    
    access_controller = AccessController(tenant_domain)
    return DatasetSharingService(tenant_domain, access_controller)


@router.post("/share", response_model=DatasetShareResponse)
async def share_dataset(
    request: ShareDatasetRequest,
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    Share a dataset with specified access group.
    
    - **dataset_id**: Dataset to share
    - **access_group**: individual, team, or organization
    - **team_members**: Required for team sharing
    - **team_permissions**: Optional custom permissions
    - **expires_days**: Optional expiration period
    """
    try:
        # Convert access group string to enum
        access_group = AccessGroup(request.access_group.lower())
        
        # Convert permission strings to enums
        team_permissions = {}
        if request.team_permissions:
            for user, perm in request.team_permissions.items():
                team_permissions[user] = SharingPermission(perm.lower())
        
        # Calculate expiration
        expires_at = None
        if request.expires_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_days)
        
        # Share dataset
        share = await sharing_service.share_dataset(
            dataset_id=request.dataset_id,
            owner_id=current_user,
            access_group=access_group,
            team_members=request.team_members,
            team_permissions=team_permissions,
            expires_at=expires_at,
            capability_token=authorization
        )
        
        return DatasetShareResponse(
            id=share.id,
            dataset_id=share.dataset_id,
            owner_id=share.owner_id,
            access_group=share.access_group.value,
            team_members=share.team_members,
            team_permissions={k: v.value for k, v in share.team_permissions.items()},
            shared_at=share.shared_at,
            expires_at=share.expires_at,
            is_active=share.is_active
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to share dataset: {str(e)}")


@router.get("/{dataset_id}", response_model=DatasetShareResponse)
async def get_dataset_sharing(
    dataset_id: str,
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    Get sharing configuration for a dataset.
    
    Returns sharing details if user has access to view them.
    """
    try:
        share = await sharing_service.get_dataset_sharing(
            dataset_id=dataset_id,
            user_id=current_user,
            capability_token=authorization
        )
        
        if not share:
            raise HTTPException(status_code=404, detail="Dataset sharing not found or access denied")
        
        return DatasetShareResponse(
            id=share.id,
            dataset_id=share.dataset_id,
            owner_id=share.owner_id,
            access_group=share.access_group.value,
            team_members=share.team_members,
            team_permissions={k: v.value for k, v in share.team_permissions.items()},
            shared_at=share.shared_at,
            expires_at=share.expires_at,
            is_active=share.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dataset sharing: {str(e)}")


@router.post("/{dataset_id}/access-check")
async def check_dataset_access(
    dataset_id: str,
    permission: str = Query("read", description="Permission to check: read, write, admin"),
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    Check if user has specified permission on dataset.
    
    - **permission**: read, write, or admin
    """
    try:
        # Convert permission string to enum
        required_permission = SharingPermission(permission.lower())
        
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id=dataset_id,
            user_id=current_user,
            permission=required_permission
        )
        
        return {
            "allowed": allowed,
            "reason": reason,
            "permission": permission,
            "user_id": current_user,
            "dataset_id": dataset_id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check access: {str(e)}")


@router.get("", response_model=List[DatasetInfoResponse])
async def list_accessible_datasets(
    include_owned: bool = Query(True, description="Include user's own datasets"),
    include_shared: bool = Query(True, description="Include datasets shared with user"),
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    List datasets accessible to user.
    
    - **include_owned**: Include user's own datasets
    - **include_shared**: Include datasets shared with user
    """
    try:
        datasets = await sharing_service.list_accessible_datasets(
            user_id=current_user,
            capability_token=authorization,
            include_owned=include_owned,
            include_shared=include_shared
        )
        
        return [
            DatasetInfoResponse(
                id=dataset.id,
                name=dataset.name,
                description=dataset.description,
                owner_id=dataset.owner_id,
                document_count=dataset.document_count,
                size_bytes=dataset.size_bytes,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                tags=dataset.tags
            )
            for dataset in datasets
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")


@router.delete("/{dataset_id}/revoke")
async def revoke_dataset_sharing(
    dataset_id: str,
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    Revoke dataset sharing (make it private).
    
    Only the dataset owner can revoke sharing.
    """
    try:
        success = await sharing_service.revoke_dataset_sharing(
            dataset_id=dataset_id,
            owner_id=current_user,
            capability_token=authorization
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to revoke sharing")
        
        return {
            "success": True,
            "message": f"Dataset {dataset_id} sharing revoked",
            "dataset_id": dataset_id
        }
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke sharing: {str(e)}")


@router.put("/{dataset_id}/permissions")
async def update_team_permissions(
    dataset_id: str,
    request: UpdatePermissionRequest,
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    Update team member permissions for a dataset.
    
    Only the dataset owner can update permissions.
    """
    try:
        # Convert permission string to enum
        permission = SharingPermission(request.permission.lower())
        
        success = await sharing_service.update_team_permissions(
            dataset_id=dataset_id,
            owner_id=current_user,
            user_id=request.user_id,
            permission=permission,
            capability_token=authorization
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update permissions")
        
        return {
            "success": True,
            "message": f"Updated {request.user_id} permission to {request.permission}",
            "dataset_id": dataset_id,
            "user_id": request.user_id,
            "permission": request.permission
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {str(e)}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update permissions: {str(e)}")


@router.get("/stats/sharing", response_model=SharingStatsResponse)
async def get_sharing_statistics(
    authorization: str = Header(...),
    sharing_service: DatasetSharingService = Depends(get_dataset_sharing_service),
    current_user: str = Depends(get_current_user)
):
    """
    Get sharing statistics for current user.
    
    Returns counts of owned, shared datasets and sharing breakdown.
    """
    try:
        stats = await sharing_service.get_sharing_statistics(
            user_id=current_user,
            capability_token=authorization
        )
        
        # Convert AccessGroup enum keys to strings
        sharing_breakdown = {
            group.value: count for group, count in stats["sharing_breakdown"].items()
        }
        
        return SharingStatsResponse(
            owned_datasets=stats["owned_datasets"],
            shared_with_me=stats["shared_with_me"],
            sharing_breakdown=sharing_breakdown,
            total_team_members=stats["total_team_members"],
            expired_shares=stats["expired_shares"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


# Action and permission catalogs for UI builders
@router.get("/catalog/permissions")
async def get_permission_catalog():
    """Get available sharing permissions for UI builders"""
    return {
        "permissions": [
            {
                "value": "read",
                "label": "Read Only",
                "description": "Can view and search dataset"
            },
            {
                "value": "write", 
                "label": "Read & Write",
                "description": "Can view, search, and add documents"
            },
            {
                "value": "admin",
                "label": "Administrator",
                "description": "Can modify sharing settings"
            }
        ]
    }


@router.get("/catalog/access-groups")
async def get_access_group_catalog():
    """Get available access groups for UI builders"""
    return {
        "access_groups": [
            {
                "value": "individual",
                "label": "Private",
                "description": "Only accessible to owner"
            },
            {
                "value": "team",
                "label": "Team",
                "description": "Shared with specific team members"
            },
            {
                "value": "organization",
                "label": "Organization",
                "description": "Read-only access for all tenant users"
            }
        ]
    }