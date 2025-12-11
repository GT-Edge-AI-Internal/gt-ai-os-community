"""
API Key Management Endpoints
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.services.api_key_service import APIKeyService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


class SetAPIKeyRequest(BaseModel):
    """Request model for setting an API key"""
    tenant_id: int
    provider: str
    api_key: str
    api_secret: Optional[str] = None
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None


class APIKeyResponse(BaseModel):
    """Response model for API key operations"""
    tenant_id: int
    provider: str
    enabled: bool
    updated_at: str


class APIKeyStatusResponse(BaseModel):
    """Response model for API key status"""
    configured: bool
    enabled: bool
    updated_at: Optional[str]
    metadata: Optional[Dict[str, Any]]


class TestAPIKeyResponse(BaseModel):
    """Response model for API key testing"""
    provider: str
    valid: bool
    message: str
    status_code: Optional[int] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # auth_failed, rate_limited, invalid_format, insufficient_permissions
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[str] = None
    models_available: Optional[int] = None  # Count of models accessible with this key


@router.post("/set", response_model=APIKeyResponse)
async def set_api_key(
    request: SetAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set or update an API key for a tenant"""
    
    # Check permissions (must be GT admin or tenant admin)
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage API keys"
        )
    
    
    service = APIKeyService(db)
    
    try:
        result = await service.set_api_key(
            tenant_id=request.tenant_id,
            provider=request.provider,
            api_key=request.api_key,
            api_secret=request.api_secret,
            enabled=request.enabled,
            metadata=request.metadata
        )
        return APIKeyResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set API key: {str(e)}"
        )


@router.get("/tenant/{tenant_id}", response_model=Dict[str, APIKeyStatusResponse])
async def get_tenant_api_keys(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all API keys for a tenant (without decryption)"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view API keys"
        )
    
    
    service = APIKeyService(db)
    
    try:
        api_keys = await service.get_api_keys(tenant_id)
        return {
            provider: APIKeyStatusResponse(**info)
            for provider, info in api_keys.items()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/test/{tenant_id}/{provider}", response_model=TestAPIKeyResponse)
async def test_api_key(
    tenant_id: int,
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test if an API key is valid"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to test API keys"
        )
    
    
    service = APIKeyService(db)
    
    try:
        result = await service.test_api_key(tenant_id, provider)
        return TestAPIKeyResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test failed: {str(e)}"
        )


@router.put("/disable/{tenant_id}/{provider}")
async def disable_api_key(
    tenant_id: int,
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable an API key without removing it"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage API keys"
        )
    
    
    service = APIKeyService(db)
    
    try:
        success = await service.disable_api_key(tenant_id, provider)
        return {"success": success, "provider": provider, "enabled": False}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/remove/{tenant_id}/{provider}")
async def remove_api_key(
    tenant_id: int,
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Completely remove an API key"""
    
    # Check permissions (only GT admin can remove)
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only GT admins can remove API keys"
        )
    
    service = APIKeyService(db)
    
    try:
        success = await service.remove_api_key(tenant_id, provider)
        if success:
            return {"success": True, "message": f"API key for {provider} removed"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key for {provider} not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/providers", response_model=List[Dict[str, Any]])
async def get_supported_providers(
    current_user: User = Depends(get_current_user)
):
    """Get list of supported API key providers"""
    
    return APIKeyService.get_supported_providers()


@router.get("/usage/{tenant_id}/{provider}")
async def get_api_key_usage(
    tenant_id: int,
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage statistics for an API key"""
    
    # Check permissions
    if current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view usage"
        )
    
    
    service = APIKeyService(db)
    
    try:
        usage = await service.get_api_key_usage(tenant_id, provider)
        return usage
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )