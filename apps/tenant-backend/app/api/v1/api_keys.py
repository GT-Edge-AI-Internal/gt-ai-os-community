"""
Enhanced API Keys Management API for GT 2.0

RESTful API for advanced API key management with capability-based permissions,
configurable constraints, and comprehensive audit logging.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user, verify_capability_token
from app.services.enhanced_api_keys import (
    EnhancedAPIKeyService, APIKeyConfig, APIKeyStatus, APIKeyScope, SharingPermission
)

router = APIRouter()


# Request/Response Models
class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key"""
    name: str = Field(..., description="Human-readable name for the key")
    description: Optional[str] = Field(None, description="Description of the key's purpose")
    capabilities: List[str] = Field(..., description="List of capability strings")
    scope: str = Field("user", description="Key scope: user, tenant, admin")
    expires_in_days: int = Field(90, description="Expiration time in days")
    rate_limit_per_hour: Optional[int] = Field(None, description="Custom rate limit per hour")
    daily_quota: Optional[int] = Field(None, description="Custom daily quota")
    cost_limit_cents: Optional[int] = Field(None, description="Custom cost limit in cents")
    allowed_endpoints: Optional[List[str]] = Field(None, description="Allowed endpoints")
    blocked_endpoints: Optional[List[str]] = Field(None, description="Blocked endpoints")
    allowed_ips: Optional[List[str]] = Field(None, description="Allowed IP addresses")
    tenant_constraints: Optional[Dict[str, Any]] = Field(None, description="Custom tenant constraints")


class APIKeyResponse(BaseModel):
    """API key configuration response"""
    id: str
    name: str
    description: str
    owner_id: str
    scope: str
    capabilities: List[str]
    rate_limit_per_hour: int
    daily_quota: int
    cost_limit_cents: int
    max_tokens_per_request: int
    allowed_endpoints: List[str]
    blocked_endpoints: List[str]
    allowed_ips: List[str]
    status: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_rotated: Optional[datetime]
    usage: Dict[str, Any]


class CreateAPIKeyResponse(BaseModel):
    """Response when creating a new API key"""
    api_key: APIKeyResponse
    raw_key: str = Field(..., description="The actual API key (only shown once)")
    warning: str = Field(..., description="Security warning about key storage")


class RotateAPIKeyResponse(BaseModel):
    """Response when rotating an API key"""
    api_key: APIKeyResponse
    new_raw_key: str = Field(..., description="The new API key (only shown once)")
    warning: str = Field(..., description="Security warning about updating systems")


class APIKeyUsageResponse(BaseModel):
    """API key usage analytics response"""
    total_requests: int
    total_errors: int
    avg_requests_per_day: float
    rate_limit_hits: int
    keys_analyzed: int
    date_range: Dict[str, str]
    most_used_endpoints: List[Dict[str, Any]]


class ValidateAPIKeyRequest(BaseModel):
    """Request to validate an API key"""
    api_key: str = Field(..., description="Raw API key to validate")
    endpoint: Optional[str] = Field(None, description="Endpoint being accessed")
    client_ip: Optional[str] = Field(None, description="Client IP address")


class ValidateAPIKeyResponse(BaseModel):
    """API key validation response"""
    valid: bool
    error_message: Optional[str]
    capability_token: Optional[str]
    rate_limit_remaining: Optional[int]
    quota_remaining: Optional[int]


# Dependency injection
async def get_api_key_service(
    authorization: str = Header(...),
    current_user: str = Depends(get_current_user)
) -> EnhancedAPIKeyService:
    """Get enhanced API key service"""
    # Extract tenant from token (mock implementation)
    tenant_domain = "customer1.com"  # Would extract from JWT
    
    # Use tenant-specific signing key
    signing_key = f"signing_key_for_{tenant_domain}"
    
    return EnhancedAPIKeyService(tenant_domain, signing_key)


@router.post("", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    Create a new API key with specified capabilities and constraints.
    
    - **name**: Human-readable name for the key
    - **capabilities**: List of capability strings (e.g., ["llm:gpt-4", "rag:search"])
    - **scope**: user, tenant, or admin level
    - **expires_in_days**: Expiration time (default 90 days)
    - **rate_limit_per_hour**: Custom rate limit (optional)
    - **allowed_endpoints**: Restrict to specific endpoints (optional)
    - **tenant_constraints**: Custom constraints for the key (optional)
    """
    try:
        # Convert scope string to enum
        scope = APIKeyScope(request.scope.lower())
        
        # Build constraints from request
        constraints = request.tenant_constraints or {}
        
        # Apply custom limits if provided
        if request.rate_limit_per_hour:
            constraints["rate_limit_per_hour"] = request.rate_limit_per_hour
        if request.daily_quota:
            constraints["daily_quota"] = request.daily_quota
        if request.cost_limit_cents:
            constraints["cost_limit_cents"] = request.cost_limit_cents
        
        # Create API key
        api_key, raw_key = await api_key_service.create_api_key(
            name=request.name,
            owner_id=current_user,
            capabilities=request.capabilities,
            scope=scope,
            expires_in_days=request.expires_in_days,
            constraints=constraints,
            capability_token=authorization
        )
        
        # Apply custom settings if provided
        if request.allowed_endpoints:
            api_key.allowed_endpoints = request.allowed_endpoints
        if request.blocked_endpoints:
            api_key.blocked_endpoints = request.blocked_endpoints
        if request.allowed_ips:
            api_key.allowed_ips = request.allowed_ips
        if request.description:
            api_key.description = request.description
        
        # Store updated key
        await api_key_service._store_api_key(api_key)
        
        return CreateAPIKeyResponse(
            api_key=APIKeyResponse(
                id=api_key.id,
                name=api_key.name,
                description=api_key.description,
                owner_id=api_key.owner_id,
                scope=api_key.scope.value,
                capabilities=api_key.capabilities,
                rate_limit_per_hour=api_key.rate_limit_per_hour,
                daily_quota=api_key.daily_quota,
                cost_limit_cents=api_key.cost_limit_cents,
                max_tokens_per_request=api_key.max_tokens_per_request,
                allowed_endpoints=api_key.allowed_endpoints,
                blocked_endpoints=api_key.blocked_endpoints,
                allowed_ips=api_key.allowed_ips,
                status=api_key.status.value,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                last_rotated=api_key.last_rotated,
                usage=api_key.usage.to_dict()
            ),
            raw_key=raw_key,
            warning="Store this API key securely. It will not be shown again."
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create API key: {str(e)}")


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    include_usage: bool = Query(True, description="Include usage statistics"),
    status: Optional[str] = Query(None, description="Filter by status"),
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    List API keys for the current user.
    
    - **include_usage**: Include detailed usage statistics
    - **status**: Filter by key status (active, suspended, expired, revoked)
    """
    try:
        api_keys = await api_key_service.list_user_api_keys(
            owner_id=current_user,
            capability_token=authorization,
            include_usage=include_usage
        )
        
        # Filter by status if provided
        if status:
            try:
                status_filter = APIKeyStatus(status.lower())
                api_keys = [key for key in api_keys if key.status == status_filter]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        return [
            APIKeyResponse(
                id=key.id,
                name=key.name,
                description=key.description,
                owner_id=key.owner_id,
                scope=key.scope.value,
                capabilities=key.capabilities,
                rate_limit_per_hour=key.rate_limit_per_hour,
                daily_quota=key.daily_quota,
                cost_limit_cents=key.cost_limit_cents,
                max_tokens_per_request=key.max_tokens_per_request,
                allowed_endpoints=key.allowed_endpoints,
                blocked_endpoints=key.blocked_endpoints,
                allowed_ips=key.allowed_ips,
                status=key.status.value,
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_rotated=key.last_rotated,
                usage=key.usage.to_dict()
            )
            for key in api_keys
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list API keys: {str(e)}")


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: str,
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    Get detailed information about a specific API key.
    """
    try:
        # Get user's keys and find the requested one
        user_keys = await api_key_service.list_user_api_keys(
            owner_id=current_user,
            capability_token=authorization,
            include_usage=True
        )
        
        api_key = next((key for key in user_keys if key.id == key_id), None)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        return APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            description=api_key.description,
            owner_id=api_key.owner_id,
            scope=api_key.scope.value,
            capabilities=api_key.capabilities,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            daily_quota=api_key.daily_quota,
            cost_limit_cents=api_key.cost_limit_cents,
            max_tokens_per_request=api_key.max_tokens_per_request,
            allowed_endpoints=api_key.allowed_endpoints,
            blocked_endpoints=api_key.blocked_endpoints,
            allowed_ips=api_key.allowed_ips,
            status=api_key.status.value,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            last_rotated=api_key.last_rotated,
            usage=api_key.usage.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get API key: {str(e)}")


@router.post("/{key_id}/rotate", response_model=RotateAPIKeyResponse)
async def rotate_api_key(
    key_id: str,
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    Rotate API key (generate new key value).
    
    The old key will be invalidated and a new key will be generated.
    """
    try:
        api_key, new_raw_key = await api_key_service.rotate_api_key(
            key_id=key_id,
            owner_id=current_user,
            capability_token=authorization
        )
        
        return RotateAPIKeyResponse(
            api_key=APIKeyResponse(
                id=api_key.id,
                name=api_key.name,
                description=api_key.description,
                owner_id=api_key.owner_id,
                scope=api_key.scope.value,
                capabilities=api_key.capabilities,
                rate_limit_per_hour=api_key.rate_limit_per_hour,
                daily_quota=api_key.daily_quota,
                cost_limit_cents=api_key.cost_limit_cents,
                max_tokens_per_request=api_key.max_tokens_per_request,
                allowed_endpoints=api_key.allowed_endpoints,
                blocked_endpoints=api_key.blocked_endpoints,
                allowed_ips=api_key.allowed_ips,
                status=api_key.status.value,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                last_rotated=api_key.last_rotated,
                usage=api_key.usage.to_dict()
            ),
            new_raw_key=new_raw_key,
            warning="Update all systems using this API key with the new value."
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rotate API key: {str(e)}")


@router.delete("/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    Revoke API key (mark as revoked and disable access).
    
    Revoked keys cannot be restored and will immediately stop working.
    """
    try:
        success = await api_key_service.revoke_api_key(
            key_id=key_id,
            owner_id=current_user,
            capability_token=authorization
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        
        return {
            "success": True,
            "message": f"API key {key_id} has been revoked",
            "key_id": key_id
        }
        
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke API key: {str(e)}")


@router.post("/validate", response_model=ValidateAPIKeyResponse)
async def validate_api_key(
    request: ValidateAPIKeyRequest,
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service)
):
    """
    Validate an API key and get capability token.
    
    This endpoint is used by other services to validate API keys
    and generate capability tokens for resource access.
    """
    try:
        valid, api_key, error_message = await api_key_service.validate_api_key(
            raw_key=request.api_key,
            endpoint=request.endpoint or "",
            client_ip=request.client_ip or "",
            user_agent=""
        )
        
        response = ValidateAPIKeyResponse(
            valid=valid,
            error_message=error_message,
            capability_token=None,
            rate_limit_remaining=None,
            quota_remaining=None
        )
        
        if valid and api_key:
            # Generate capability token
            capability_token = await api_key_service.generate_capability_token(api_key)
            response.capability_token = capability_token
            
            # Add rate limit and quota info
            response.rate_limit_remaining = max(0, api_key.rate_limit_per_hour - api_key.usage.requests_count)
            response.quota_remaining = max(0, api_key.daily_quota - api_key.usage.requests_count)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate API key: {str(e)}")


@router.get("/{key_id}/usage", response_model=APIKeyUsageResponse)
async def get_api_key_usage(
    key_id: str,
    days: int = Query(30, description="Number of days to analyze"),
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    Get usage analytics for a specific API key.
    
    - **days**: Number of days to analyze (default 30)
    """
    try:
        analytics = await api_key_service.get_usage_analytics(
            owner_id=current_user,
            key_id=key_id,
            days=days
        )
        
        return APIKeyUsageResponse(
            total_requests=analytics["total_requests"],
            total_errors=analytics["total_errors"],
            avg_requests_per_day=analytics["avg_requests_per_day"],
            rate_limit_hits=analytics["rate_limit_hits"],
            keys_analyzed=analytics["keys_analyzed"],
            date_range=analytics["date_range"],
            most_used_endpoints=analytics.get("most_used_endpoints", [])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage analytics: {str(e)}")


@router.get("/analytics/summary", response_model=APIKeyUsageResponse)
async def get_usage_summary(
    days: int = Query(30, description="Number of days to analyze"),
    authorization: str = Header(...),
    api_key_service: EnhancedAPIKeyService = Depends(get_api_key_service),
    current_user: str = Depends(get_current_user)
):
    """
    Get usage analytics summary for all user's API keys.
    
    - **days**: Number of days to analyze (default 30)
    """
    try:
        analytics = await api_key_service.get_usage_analytics(
            owner_id=current_user,
            key_id=None,  # All keys
            days=days
        )
        
        return APIKeyUsageResponse(
            total_requests=analytics["total_requests"],
            total_errors=analytics["total_errors"],
            avg_requests_per_day=analytics["avg_requests_per_day"],
            rate_limit_hits=analytics["rate_limit_hits"],
            keys_analyzed=analytics["keys_analyzed"],
            date_range=analytics["date_range"],
            most_used_endpoints=analytics.get("most_used_endpoints", [])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage summary: {str(e)}")


# Capability and scope catalogs for UI builders
@router.get("/catalog/capabilities")
async def get_capability_catalog():
    """Get available capabilities for UI builders"""
    return {
        "capabilities": [
            # AI/ML Resources
            {"value": "llm:gpt-4", "label": "GPT-4 Language Model", "category": "AI/ML"},
            {"value": "llm:claude-sonnet", "label": "Claude Sonnet", "category": "AI/ML"},
            {"value": "llm:groq", "label": "Groq Models", "category": "AI/ML"},
            {"value": "embedding:openai", "label": "OpenAI Embeddings", "category": "AI/ML"},
            {"value": "image:dall-e", "label": "DALL-E Image Generation", "category": "AI/ML"},
            
            # RAG & Knowledge
            {"value": "rag:search", "label": "RAG Search", "category": "Knowledge"},
            {"value": "rag:upload", "label": "Document Upload", "category": "Knowledge"},
            {"value": "rag:dataset_management", "label": "Dataset Management", "category": "Knowledge"},
            
            # Automation
            {"value": "automation:create", "label": "Create Automations", "category": "Automation"},
            {"value": "automation:execute", "label": "Execute Automations", "category": "Automation"},
            {"value": "automation:api_calls", "label": "API Call Actions", "category": "Automation"},
            {"value": "automation:webhooks", "label": "Webhook Actions", "category": "Automation"},
            
            # External Services
            {"value": "external:github", "label": "GitHub Integration", "category": "External"},
            {"value": "external:slack", "label": "Slack Integration", "category": "External"},
            
            # Administrative
            {"value": "admin:user_management", "label": "User Management", "category": "Admin"},
            {"value": "admin:tenant_settings", "label": "Tenant Settings", "category": "Admin"}
        ]
    }


@router.get("/catalog/scopes")
async def get_scope_catalog():
    """Get available scopes for UI builders"""
    return {
        "scopes": [
            {
                "value": "user",
                "label": "User Scope",
                "description": "Access to user-specific operations and data",
                "default_limits": {
                    "rate_limit_per_hour": 1000,
                    "daily_quota": 10000,
                    "cost_limit_cents": 1000
                }
            },
            {
                "value": "tenant",
                "label": "Tenant Scope", 
                "description": "Access to tenant-wide operations and data",
                "default_limits": {
                    "rate_limit_per_hour": 5000,
                    "daily_quota": 50000,
                    "cost_limit_cents": 5000
                }
            },
            {
                "value": "admin",
                "label": "Admin Scope",
                "description": "Administrative access with elevated privileges",
                "default_limits": {
                    "rate_limit_per_hour": 10000,
                    "daily_quota": 100000,
                    "cost_limit_cents": 10000
                }
            }
        ]
    }