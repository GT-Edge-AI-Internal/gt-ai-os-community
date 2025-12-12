"""
Integration Proxy API for GT 2.0

RESTful API for secure external service integration through the Resource Cluster.
Provides capability-based access control and sandbox restrictions.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field

from app.core.security import verify_capability_token
from app.services.integration_proxy import (
    IntegrationProxyService, ProxyRequest, ProxyResponse, IntegrationConfig,
    IntegrationType, SandboxLevel
)

router = APIRouter()


# Request/Response Models
class ExecuteIntegrationRequest(BaseModel):
    """Request to execute integration"""
    integration_id: str = Field(..., description="Integration ID to execute")
    method: str = Field(..., description="HTTP method (GET, POST, PUT, DELETE)")
    endpoint: str = Field(..., description="Endpoint path or full URL")
    headers: Optional[Dict[str, str]] = Field(None, description="Request headers")
    data: Optional[Dict[str, Any]] = Field(None, description="Request data")
    params: Optional[Dict[str, str]] = Field(None, description="Query parameters")
    timeout_override: Optional[int] = Field(None, description="Override timeout in seconds")


class IntegrationExecutionResponse(BaseModel):
    """Response from integration execution"""
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]]
    headers: Dict[str, str]
    execution_time_ms: int
    sandbox_applied: bool
    restrictions_applied: List[str]
    error_message: Optional[str]


class CreateIntegrationRequest(BaseModel):
    """Request to create integration configuration"""
    name: str = Field(..., description="Human-readable integration name")
    integration_type: str = Field(..., description="Type of integration")
    base_url: str = Field(..., description="Base URL for the service")
    authentication_method: str = Field(..., description="Authentication method")
    auth_config: Dict[str, Any] = Field(..., description="Authentication configuration")
    sandbox_level: str = Field("basic", description="Sandbox restriction level")
    max_requests_per_hour: int = Field(1000, description="Rate limit per hour")
    max_response_size_bytes: int = Field(10485760, description="Max response size (10MB default)")
    timeout_seconds: int = Field(30, description="Request timeout")
    allowed_methods: Optional[List[str]] = Field(None, description="Allowed HTTP methods")
    allowed_endpoints: Optional[List[str]] = Field(None, description="Allowed endpoints")
    blocked_endpoints: Optional[List[str]] = Field(None, description="Blocked endpoints")
    allowed_domains: Optional[List[str]] = Field(None, description="Allowed domains")


class IntegrationConfigResponse(BaseModel):
    """Integration configuration response"""
    id: str
    name: str
    integration_type: str
    base_url: str
    authentication_method: str
    sandbox_level: str
    max_requests_per_hour: int
    max_response_size_bytes: int
    timeout_seconds: int
    allowed_methods: List[str]
    allowed_endpoints: List[str]
    blocked_endpoints: List[str]
    allowed_domains: List[str]
    is_active: bool
    created_at: str
    created_by: str


class IntegrationUsageResponse(BaseModel):
    """Integration usage analytics response"""
    integration_id: str
    total_requests: int
    successful_requests: int
    error_count: int
    success_rate: float
    avg_execution_time_ms: float
    date_range: Dict[str, str]


# Dependency injection
async def get_integration_proxy_service() -> IntegrationProxyService:
    """Get integration proxy service"""
    return IntegrationProxyService()


@router.post("/execute", response_model=IntegrationExecutionResponse)
async def execute_integration(
    request: ExecuteIntegrationRequest,
    authorization: str = Header(...),
    proxy_service: IntegrationProxyService = Depends(get_integration_proxy_service)
):
    """
    Execute external integration with capability-based access control.
    
    - **integration_id**: ID of the configured integration
    - **method**: HTTP method (GET, POST, PUT, DELETE)
    - **endpoint**: API endpoint path or full URL
    - **headers**: Optional request headers
    - **data**: Optional request body data
    - **params**: Optional query parameters
    - **timeout_override**: Optional timeout override
    """
    try:
        # Create proxy request
        proxy_request = ProxyRequest(
            integration_id=request.integration_id,
            method=request.method.upper(),
            endpoint=request.endpoint,
            headers=request.headers,
            data=request.data,
            params=request.params,
            timeout_override=request.timeout_override
        )
        
        # Execute integration
        response = await proxy_service.execute_integration(
            request=proxy_request,
            capability_token=authorization
        )
        
        return IntegrationExecutionResponse(
            success=response.success,
            status_code=response.status_code,
            data=response.data,
            headers=response.headers,
            execution_time_ms=response.execution_time_ms,
            sandbox_applied=response.sandbox_applied,
            restrictions_applied=response.restrictions_applied,
            error_message=response.error_message
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integration execution failed: {str(e)}")


@router.get("", response_model=List[IntegrationConfigResponse])
async def list_integrations(
    authorization: str = Header(...),
    proxy_service: IntegrationProxyService = Depends(get_integration_proxy_service)
):
    """
    List available integrations based on user capabilities.
    
    Returns only integrations the user has permission to access.
    """
    try:
        integrations = await proxy_service.list_integrations(authorization)
        
        return [
            IntegrationConfigResponse(
                id=config.id,
                name=config.name,
                integration_type=config.integration_type.value,
                base_url=config.base_url,
                authentication_method=config.authentication_method,
                sandbox_level=config.sandbox_level.value,
                max_requests_per_hour=config.max_requests_per_hour,
                max_response_size_bytes=config.max_response_size_bytes,
                timeout_seconds=config.timeout_seconds,
                allowed_methods=config.allowed_methods,
                allowed_endpoints=config.allowed_endpoints,
                blocked_endpoints=config.blocked_endpoints,
                allowed_domains=config.allowed_domains,
                is_active=config.is_active,
                created_at=config.created_at.isoformat(),
                created_by=config.created_by
            )
            for config in integrations
        ]
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list integrations: {str(e)}")


@router.post("", response_model=IntegrationConfigResponse)
async def create_integration(
    request: CreateIntegrationRequest,
    authorization: str = Header(...),
    proxy_service: IntegrationProxyService = Depends(get_integration_proxy_service)
):
    """
    Create new integration configuration (admin only).
    
    - **name**: Human-readable name for the integration
    - **integration_type**: Type of integration (communication, development, etc.)
    - **base_url**: Base URL for the external service
    - **authentication_method**: oauth2, api_key, basic_auth, certificate
    - **auth_config**: Authentication details (encrypted storage)
    - **sandbox_level**: none, basic, restricted, strict
    """
    try:
        # Verify admin capability
        token_data = await verify_capability_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid capability token")
        
        # Check admin permissions
        if not any("admin" in str(cap) for cap in token_data.get("capabilities", [])):
            raise HTTPException(status_code=403, detail="Admin capability required")
        
        # Generate unique ID
        import uuid
        integration_id = str(uuid.uuid4())
        
        # Create integration config
        config = IntegrationConfig(
            id=integration_id,
            name=request.name,
            integration_type=IntegrationType(request.integration_type.lower()),
            base_url=request.base_url,
            authentication_method=request.authentication_method,
            auth_config=request.auth_config,
            sandbox_level=SandboxLevel(request.sandbox_level.lower()),
            max_requests_per_hour=request.max_requests_per_hour,
            max_response_size_bytes=request.max_response_size_bytes,
            timeout_seconds=request.timeout_seconds,
            allowed_methods=request.allowed_methods or ["GET", "POST"],
            allowed_endpoints=request.allowed_endpoints or [],
            blocked_endpoints=request.blocked_endpoints or [],
            allowed_domains=request.allowed_domains or [],
            created_by=token_data.get("sub", "unknown")
        )
        
        # Store configuration
        success = await proxy_service.store_integration_config(config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store integration configuration")
        
        return IntegrationConfigResponse(
            id=config.id,
            name=config.name,
            integration_type=config.integration_type.value,
            base_url=config.base_url,
            authentication_method=config.authentication_method,
            sandbox_level=config.sandbox_level.value,
            max_requests_per_hour=config.max_requests_per_hour,
            max_response_size_bytes=config.max_response_size_bytes,
            timeout_seconds=config.timeout_seconds,
            allowed_methods=config.allowed_methods,
            allowed_endpoints=config.allowed_endpoints,
            blocked_endpoints=config.blocked_endpoints,
            allowed_domains=config.allowed_domains,
            is_active=config.is_active,
            created_at=config.created_at.isoformat(),
            created_by=config.created_by
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create integration: {str(e)}")


@router.get("/{integration_id}/usage", response_model=IntegrationUsageResponse)
async def get_integration_usage(
    integration_id: str,
    days: int = 30,
    authorization: str = Header(...),
    proxy_service: IntegrationProxyService = Depends(get_integration_proxy_service)
):
    """
    Get usage analytics for specific integration.
    
    - **days**: Number of days to analyze (default 30)
    """
    try:
        # Verify capability for this integration
        token_data = await verify_capability_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid capability token")
        
        # Get usage analytics
        usage = await proxy_service.get_integration_usage_analytics(integration_id, days)
        
        return IntegrationUsageResponse(
            integration_id=usage["integration_id"],
            total_requests=usage["total_requests"],
            successful_requests=usage["successful_requests"],
            error_count=usage["error_count"],
            success_rate=usage["success_rate"],
            avg_execution_time_ms=usage["avg_execution_time_ms"],
            date_range=usage["date_range"]
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage analytics: {str(e)}")


# Integration type and sandbox level catalogs
@router.get("/catalog/types")
async def get_integration_types():
    """Get available integration types for UI builders"""
    return {
        "integration_types": [
            {
                "value": "communication",
                "label": "Communication",
                "description": "Slack, Teams, Discord integration"
            },
            {
                "value": "development", 
                "label": "Development",
                "description": "GitHub, GitLab, Jira integration"
            },
            {
                "value": "project_management",
                "label": "Project Management", 
                "description": "Asana, Monday.com integration"
            },
            {
                "value": "database",
                "label": "Database",
                "description": "PostgreSQL, MySQL, MongoDB connectors"
            },
            {
                "value": "custom_api",
                "label": "Custom API",
                "description": "Custom REST/GraphQL APIs"
            },
            {
                "value": "webhook",
                "label": "Webhook",
                "description": "Outbound webhook calls"
            }
        ]
    }


@router.get("/catalog/sandbox-levels")
async def get_sandbox_levels():
    """Get available sandbox levels for UI builders"""
    return {
        "sandbox_levels": [
            {
                "value": "none",
                "label": "No Restrictions",
                "description": "Trusted integrations with full access"
            },
            {
                "value": "basic",
                "label": "Basic Restrictions", 
                "description": "Basic timeout and size limits"
            },
            {
                "value": "restricted",
                "label": "Restricted Access",
                "description": "Limited API calls and data access"
            },
            {
                "value": "strict",
                "label": "Maximum Security",
                "description": "Strict restrictions and monitoring"
            }
        ]
    }


@router.get("/catalog/auth-methods")
async def get_authentication_methods():
    """Get available authentication methods for UI builders"""
    return {
        "auth_methods": [
            {
                "value": "api_key",
                "label": "API Key",
                "description": "Simple API key authentication",
                "fields": ["api_key", "key_header", "key_prefix"]
            },
            {
                "value": "basic_auth",
                "label": "Basic Authentication",
                "description": "Username and password authentication",
                "fields": ["username", "password"]
            },
            {
                "value": "oauth2",
                "label": "OAuth 2.0",
                "description": "OAuth 2.0 bearer token authentication",
                "fields": ["access_token", "refresh_token", "client_id", "client_secret"]
            },
            {
                "value": "certificate",
                "label": "Certificate",
                "description": "Client certificate authentication",
                "fields": ["cert_path", "key_path", "ca_path"]
            }
        ]
    }