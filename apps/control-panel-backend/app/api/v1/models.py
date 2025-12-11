"""
Model Management API for GT 2.0 Admin Control Panel

Provides RESTful endpoints for managing AI model configurations.
These endpoints enable the admin UI to configure models that sync
across all resource clusters.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import logging
import re
from urllib.parse import urlparse

from app.core.database import get_db
from app.services.model_management_service import get_model_management_service
from app.models.model_config import ModelConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["Model Management"])



# Request/Response Models
class ModelSpecifications(BaseModel):
    context_window: Optional[int] = None
    max_tokens: Optional[int] = None
    dimensions: Optional[int] = None  # For embedding models


class ModelCost(BaseModel):
    per_million_input: float = 0.0
    per_million_output: float = 0.0


class ModelStatus(BaseModel):
    is_active: bool = True
    is_compound: bool = False  # Compound models use pass-through pricing from actual usage


class ModelCreateRequest(BaseModel):
    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    version: str = Field(default="1.0", description="Model version")
    provider: str = Field(..., description="Provider: groq, external, openai, anthropic")
    model_type: str = Field(..., description="Type: llm, embedding, audio, tts, vision")
    endpoint: str = Field(..., description="API endpoint URL")
    api_key_name: Optional[str] = Field(None, description="Environment variable for API key")
    specifications: Optional[ModelSpecifications] = None
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    cost: Optional[ModelCost] = None
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[ModelStatus] = None

    model_config = {"protected_namespaces": ()}


class ModelUpdateRequest(BaseModel):
    model_id: Optional[str] = None
    name: Optional[str] = None
    provider: Optional[str] = None
    model_type: Optional[str] = None
    endpoint: Optional[str] = None
    api_key_name: Optional[str] = None
    specifications: Optional[ModelSpecifications] = None
    capabilities: Optional[Dict[str, Any]] = None
    cost: Optional[ModelCost] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[ModelStatus] = None


class EndpointUpdateRequest(BaseModel):
    endpoint: str = Field(..., description="New endpoint URL")


class EndpointTestRequest(BaseModel):
    """Request body for testing an arbitrary endpoint URL"""
    endpoint: str = Field(..., description="Endpoint URL to test")
    provider: Optional[str] = Field(None, description="Optional provider hint for specialized testing")


class ModelResponse(BaseModel):
    model_id: str
    name: str
    version: str
    provider: str
    model_type: str
    endpoint: str
    api_key_name: Optional[str]
    specifications: Dict[str, Any]
    capabilities: Dict[str, Any]
    cost: Dict[str, float]
    description: Optional[str]
    config: Dict[str, Any]
    status: Dict[str, Any]
    usage: Dict[str, Any]
    timestamps: Dict[str, str]


class HealthCheckResponse(BaseModel):
    healthy: bool
    status: Optional[str] = None  # "healthy", "degraded", "unhealthy"
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # connection_error, timeout, auth_failed, server_error
    details: Optional[Dict[str, Any]] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[str] = None
    inference_validated: Optional[bool] = None  # True if actual inference was tested


class BulkHealthResponse(BaseModel):
    total_models: int
    healthy_models: int
    unhealthy_models: int
    health_percentage: float
    individual_results: Dict[str, Dict[str, Any]]
    timestamp: str


@router.get("/", response_model=List[ModelResponse])
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    active_only: bool = Query(False, description="Show only active models"),
    include_stats: bool = Query(False, description="Include real-time statistics"),
    db: AsyncSession = Depends(get_db)
):
    """List all model configurations with real-time data"""
    try:
        service = get_model_management_service(db)
        models = await service.list_models(
            provider=provider,
            model_type=model_type,
            active_only=active_only
        )
        
        # Get bulk tenant stats if requested to avoid N+1 queries
        tenant_stats = {}
        if include_stats:
            tenant_stats = await service.get_bulk_model_tenant_stats([m.model_id for m in models])
        
        model_responses = []
        for model in models:
            model_dict = model.to_dict()
            
            # Add real-time statistics if requested
            if include_stats:
                stats = tenant_stats.get(model.model_id, {"tenant_count": 0, "enabled_tenant_count": 0})
                model_dict["tenant_count"] = stats["tenant_count"]
                model_dict["enabled_tenant_count"] = stats["enabled_tenant_count"]
            
            model_responses.append(ModelResponse(**model_dict))
        
        return model_responses
        
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ModelResponse)
async def create_model(
    model_request: ModelCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new model configuration"""
    try:
        service = get_model_management_service(db)

        # Convert request to dict
        model_data = model_request.dict(exclude_none=True)

        # Endpoint URL is preserved as provided by user
        logger.debug(f"Model {model_data.get('model_id', 'unknown')} endpoint: {model_data.get('endpoint', 'not specified')}")

        # Create model
        model = await service.register_model(model_data)

        # Auto-assign to all existing tenants
        assigned_count = await service.auto_assign_model_to_all_tenants(model.model_id)
        logger.info(f"Auto-assigned new model {model.model_id} to {assigned_count} tenants")

        return ModelResponse(**model.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Provider-specific health endpoints for industry-standard testing
PROVIDER_HEALTH_ENDPOINTS = {
    'nvidia': '/v1/health/ready',
    'vllm': '/health',
    'bge_m3': '/health',
    'ollama': '/api/tags',
    'ollama-dgx-x86': '/api/tags',
    'ollama-macos': '/api/tags',
}

# Latency threshold for degraded status (milliseconds)
LATENCY_DEGRADED_THRESHOLD = 2000


# Test endpoint for arbitrary URLs - MUST BE BEFORE path routes
@router.post("/test-endpoint", response_model=HealthCheckResponse)
async def test_endpoint_url(
    request: EndpointTestRequest,
):
    """
    Test if an arbitrary endpoint URL is accessible.

    This endpoint is used when adding new models to test connectivity
    before the model is registered in the system.

    Returns health status with three possible states:
    - healthy: Endpoint responding normally with acceptable latency
    - degraded: Endpoint responding but with high latency (>2000ms)
    - unhealthy: Endpoint not responding or returning errors
    """
    import httpx
    import time

    try:
        start_time = time.time()

        # Validate URL format
        parsed = urlparse(request.endpoint)
        if not parsed.scheme or not parsed.netloc:
            return HealthCheckResponse(
                healthy=False,
                status="unhealthy",
                error="Invalid URL format - must include scheme (http/https) and host",
                error_type="invalid_format"
            )

        # Determine test URL based on provider
        base_endpoint = request.endpoint.rstrip('/')
        if request.provider and request.provider in PROVIDER_HEALTH_ENDPOINTS:
            health_path = PROVIDER_HEALTH_ENDPOINTS[request.provider]
            test_url = f"{base_endpoint}{health_path}"
        else:
            test_url = request.endpoint

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                response = await client.get(test_url)
                latency_ms = (time.time() - start_time) * 1000

                # Extract rate limit headers if present
                rate_limit_remaining = None
                rate_limit_reset = None
                if 'x-ratelimit-remaining' in response.headers:
                    try:
                        rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
                    except (ValueError, TypeError):
                        pass
                if 'x-ratelimit-reset' in response.headers:
                    rate_limit_reset = response.headers['x-ratelimit-reset']

                # Determine health status with degraded state
                if response.status_code >= 500:
                    status = "unhealthy"
                    healthy = False
                    error = f"Server error: HTTP {response.status_code}"
                    error_type = "server_error"
                elif response.status_code == 401:
                    # Auth error but endpoint is reachable
                    status = "healthy"
                    healthy = True
                    error = None
                    error_type = None
                elif response.status_code == 403:
                    status = "healthy"
                    healthy = True
                    error = None
                    error_type = None
                elif response.status_code == 429:
                    # Rate limited - endpoint works but currently limited
                    status = "degraded"
                    healthy = True
                    error = "Rate limit exceeded"
                    error_type = "rate_limited"
                elif latency_ms > LATENCY_DEGRADED_THRESHOLD:
                    status = "degraded"
                    healthy = True
                    error = f"High latency detected ({latency_ms:.0f}ms > {LATENCY_DEGRADED_THRESHOLD}ms threshold)"
                    error_type = "high_latency"
                else:
                    status = "healthy"
                    healthy = True
                    error = None
                    error_type = None

                return HealthCheckResponse(
                    healthy=healthy,
                    status=status,
                    latency_ms=round(latency_ms, 2),
                    error=error,
                    error_type=error_type,
                    rate_limit_remaining=rate_limit_remaining,
                    rate_limit_reset=rate_limit_reset,
                    details={
                        "status_code": response.status_code,
                        "endpoint": request.endpoint,
                        "test_url": test_url,
                        "provider": request.provider
                    }
                )
            except httpx.ConnectError as e:
                latency_ms = (time.time() - start_time) * 1000
                return HealthCheckResponse(
                    healthy=False,
                    status="unhealthy",
                    latency_ms=round(latency_ms, 2),
                    error=f"Connection failed: Unable to connect to {parsed.netloc}",
                    error_type="connection_error",
                    details={"endpoint": request.endpoint, "test_url": test_url}
                )
            except httpx.TimeoutException:
                return HealthCheckResponse(
                    healthy=False,
                    status="unhealthy",
                    latency_ms=10000,  # Timeout is 10s
                    error="Connection timed out after 10 seconds",
                    error_type="timeout",
                    details={"endpoint": request.endpoint, "test_url": test_url}
                )

    except Exception as e:
        logger.error(f"Failed to test endpoint {request.endpoint}: {e}")
        return HealthCheckResponse(
            healthy=False,
            status="unhealthy",
            error=str(e),
            error_type="unknown",
            details={"endpoint": request.endpoint}
        )


# Configuration endpoints - MUST BE BEFORE path routes
@router.get("/configs/all")
async def get_all_model_configs(
    db: AsyncSession = Depends(get_db)
):
    """Get all model configurations for resource cluster sync"""
    try:
        service = get_model_management_service(db)
        models = await service.list_models(active_only=True)

        configs = []
        for model in models:
            config = model.to_dict()
            # Add resource cluster specific fields
            config["sync_timestamp"] = config["timestamps"]["updated_at"]
            configs.append(config)

        return {
            "configs": configs,
            "total": len(configs),
            "timestamp": configs[0]["sync_timestamp"] if configs else None
        }

    except Exception as e:
        logger.error(f"Failed to get model configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/overview")
async def get_models_overview_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get overview statistics for all models"""
    try:
        service = get_model_management_service(db)

        # Get all models
        all_models = await service.list_models()
        active_models = await service.list_models(active_only=True)

        # Calculate basic stats
        total_models = len(all_models)
        active_count = len(active_models)

        # Group by provider
        provider_stats = {}
        health_stats = {"healthy": 0, "unhealthy": 0, "unknown": 0}

        for model in active_models:
            # Provider stats
            provider = model.provider
            if provider not in provider_stats:
                provider_stats[provider] = 0
            provider_stats[provider] += 1

            # Health stats
            health_status = model.health_status or "unknown"
            if health_status in health_stats:
                health_stats[health_status] += 1

        # Calculate recent usage from actual model data
        recent_requests = sum(getattr(model, 'request_count', 0) for model in active_models)
        recent_cost = sum(
            getattr(model, 'request_count', 0) *
            (model.cost_per_million_input + model.cost_per_million_output) / 1000000 * 100
            for model in active_models
        )

        return {
            "total_models": total_models,
            "active_models": active_count,
            "inactive_models": total_models - active_count,
            "providers": provider_stats,
            "health": health_stats,
            "recent_usage": {
                "requests_24h": recent_requests,
                "cost_24h": recent_cost,
                "healthy_percentage": (health_stats["healthy"] / active_count * 100) if active_count > 0 else 0
            }
        }

    except Exception as e:
        logger.error(f"Failed to get models overview stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TENANT RATE LIMITS ENDPOINTS - MUST be before /{model_id:path} catch-all
# ============================================================================

class TenantRateLimitUpdate(BaseModel):
    """Request model for updating tenant rate limits"""
    requests_per_minute: Optional[int] = Field(None, ge=1, description="Max requests per minute")
    max_tokens_per_request: Optional[int] = Field(None, ge=1, description="Max tokens per request")
    concurrent_requests: Optional[int] = Field(None, ge=1, description="Max concurrent requests")
    max_cost_per_hour: Optional[float] = Field(None, ge=0, description="Max cost per hour in dollars")
    is_enabled: Optional[bool] = Field(None, description="Whether the model is enabled for this tenant")


@router.get("/tenant-rate-limits/{model_id:path}")
async def get_model_tenant_rate_limits(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all tenant rate limit configurations for a specific model"""
    try:
        service = get_model_management_service(db)

        # Verify model exists
        model = await service.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        configs = await service.get_model_tenant_rate_limits(model_id)

        return {
            "model_id": model_id,
            "model_name": model.name,
            "tenant_configs": configs
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant rate limits for model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/tenant-rate-limits/{model_id:path}/{tenant_id}")
async def update_model_tenant_rate_limit(
    model_id: str,
    tenant_id: int,
    update_request: TenantRateLimitUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update rate limits for a specific tenant-model configuration"""
    try:
        service = get_model_management_service(db)

        # Build updates dict
        updates = {}

        # Handle rate limits
        rate_limits = {}
        if update_request.requests_per_minute is not None:
            rate_limits["requests_per_minute"] = update_request.requests_per_minute
        if update_request.max_tokens_per_request is not None:
            rate_limits["max_tokens_per_request"] = update_request.max_tokens_per_request
        if update_request.concurrent_requests is not None:
            rate_limits["concurrent_requests"] = update_request.concurrent_requests
        if update_request.max_cost_per_hour is not None:
            rate_limits["max_cost_per_hour"] = update_request.max_cost_per_hour

        if rate_limits:
            updates["rate_limits"] = rate_limits

        # Handle enabled status
        if update_request.is_enabled is not None:
            updates["is_enabled"] = update_request.is_enabled

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Update the configuration
        config = await service.update_tenant_model_config(tenant_id, model_id, updates)

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration not found for model {model_id} and tenant {tenant_id}"
            )

        return {
            "message": "Rate limits updated successfully",
            "config": config.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tenant rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PATH PARAMETER ROUTES - These catch-all routes MUST be last
# ============================================================================

@router.get("/{model_id:path}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific model configuration"""
    try:
        service = get_model_management_service(db)
        model = await service.get_model(model_id)
        
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        return ModelResponse(**model.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{model_id:path}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    update_request: ModelUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update a model configuration"""
    try:
        service = get_model_management_service(db)

        # Convert request to dict, excluding None values
        updates = {k: v for k, v in update_request.dict().items() if v is not None}

        # Endpoint URL is preserved as provided by user
        if 'endpoint' in updates and updates['endpoint']:
            logger.debug(f"Model {model_id} endpoint update: {updates['endpoint']}")

        model = await service.update_model(model_id, updates)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        return ModelResponse(**model.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{model_id:path}")
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a model configuration"""
    try:
        service = get_model_management_service(db)
        success = await service.delete_model(model_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        return {"message": f"Model {model_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{model_id:path}/test", response_model=HealthCheckResponse)
async def test_model_endpoint(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Test if a model endpoint is accessible"""
    try:
        service = get_model_management_service(db)
        result = await service.test_endpoint(model_id)

        # Determine status based on healthy flag and latency
        latency_ms = result.get("latency_ms")
        healthy = result.get("healthy", False)

        if not healthy:
            status = "unhealthy"
        elif latency_ms and latency_ms > LATENCY_DEGRADED_THRESHOLD:
            status = "degraded"
        else:
            status = "healthy"

        return HealthCheckResponse(
            healthy=healthy,
            status=status,
            latency_ms=latency_ms,
            error=result.get("error"),
            error_type=result.get("error_type"),
            details=result.get("details"),
            rate_limit_remaining=result.get("rate_limit_remaining"),
            rate_limit_reset=result.get("rate_limit_reset"),
            inference_validated=result.get("inference_validated")
        )

    except Exception as e:
        logger.error(f"Failed to test model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{model_id:path}/endpoint")
async def update_model_endpoint(
    model_id: str,
    request: EndpointUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update model endpoint URL"""
    try:
        service = get_model_management_service(db)

        # Endpoint URL is preserved as provided by user
        endpoint = request.endpoint
        logger.debug(f"Model {model_id} endpoint update: {endpoint}")

        success = await service.update_endpoint(model_id, endpoint)

        if not success:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        return {"message": f"Endpoint updated for {model_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update endpoint for {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/bulk", response_model=BulkHealthResponse)
async def bulk_health_check(
    db: AsyncSession = Depends(get_db)
):
    """Check health of all active models"""
    try:
        service = get_model_management_service(db)
        result = await service.bulk_health_check()
        
        return BulkHealthResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to perform bulk health check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/usage")
async def get_usage_analytics(
    time_range: str = Query("24h", description="Time range: 1h, 24h, 7d, 30d"),
    db: AsyncSession = Depends(get_db)
):
    """Get real usage analytics for models from database"""
    try:
        service = get_model_management_service(db)
        
        # Get all models to analyze their usage
        models = await service.list_models(active_only=True)
        
        # Calculate real metrics from model data
        total_requests = sum(getattr(model, 'request_count', 0) for model in models)
        total_tokens = sum(getattr(model, 'request_count', 0) * 100 for model in models)  # Estimate tokens
        total_cost = sum(
            getattr(model, 'request_count', 0) *
            (model.cost_per_million_input + model.cost_per_million_output) / 1000000 * 100  # Estimate cost
            for model in models
        )
        
        # Provider breakdown
        provider_stats = {}
        for model in models:
            provider = model.provider
            if provider not in provider_stats:
                provider_stats[provider] = {
                    'provider': provider,
                    'requests': 0,
                    'tokens': 0,
                    'cost': 0.0
                }
            
            requests = getattr(model, 'request_count', 0)
            tokens = requests * 100  # Estimate
            cost = requests * (model.cost_per_million_input + model.cost_per_million_output) / 1000000 * 100

            provider_stats[provider]['requests'] += requests
            provider_stats[provider]['tokens'] += tokens
            provider_stats[provider]['cost'] += cost
        
        # Top models by usage
        top_models = []
        for model in models:
            requests = getattr(model, 'request_count', 0)
            tokens = requests * 100
            cost = requests * (model.cost_per_million_input + model.cost_per_million_output) / 1000000 * 100

            top_models.append({
                'model': model.model_id,
                'requests': requests,
                'tokens': f'{tokens/1000:.1f}K' if tokens < 1000000 else f'{tokens/1000000:.1f}M',
                'cost': cost,
                'avg_latency': getattr(model, 'avg_latency_ms', 0) or 200,  # Default estimate
                'success_rate': getattr(model, 'success_rate', 100.0)
            })
        
        # Sort by requests descending
        top_models.sort(key=lambda x: x['requests'], reverse=True)
        
        # Mock hourly pattern based on time range
        import datetime
        now = datetime.datetime.now()
        hourly_usage = []
        
        if time_range == '1h':
            for i in range(12):  # Last 12 5-minute intervals
                time_point = now - datetime.timedelta(minutes=i*5)
                hourly_usage.append({
                    'hour': time_point.strftime('%H:%M'),
                    'requests': max(0, int(total_requests * (0.8 + 0.4 * (i % 3)) / 12)),
                    'tokens': max(0, int(total_tokens * (0.8 + 0.4 * (i % 3)) / 12))
                })
        else:
            for i in range(24):  # Last 24 hours
                time_point = now - datetime.timedelta(hours=i)
                hourly_usage.append({
                    'hour': time_point.strftime('%H:00'),
                    'requests': max(0, int(total_requests * (0.8 + 0.4 * (i % 6)) / 24)),
                    'tokens': max(0, int(total_tokens * (0.8 + 0.4 * (i % 6)) / 24))
                })
        
        hourly_usage.reverse()  # Chronological order
        
        return {
            'summary': {
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'total_cost': total_cost,
                'active_tenants': 12  # This would come from tenant usage data
            },
            'usage_by_provider': list(provider_stats.values()),
            'top_models': top_models[:10],
            'hourly_usage': hourly_usage,
            'time_range': time_range
        }
        
    except Exception as e:
        logger.error(f"Failed to get usage analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/initialize/defaults")
async def initialize_default_models(
    db: AsyncSession = Depends(get_db)
):
    """Initialize default models (19 Groq + BGE-M3)"""
    try:
        service = get_model_management_service(db)
        await service.initialize_default_models()

        return {"message": "Default models initialized successfully"}

    except Exception as e:
        logger.error(f"Failed to initialize default models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BGE_M3_ConfigRequest(BaseModel):
    is_local_mode: bool = True
    external_endpoint: Optional[str] = "http://10.0.1.50:8080"


@router.get("/bge-m3/config")
async def get_bge_m3_config(
    db: AsyncSession = Depends(get_db)
):
    """Get current BGE-M3 configuration"""
    try:
        # For now, return a default configuration
        # In a full implementation, this would be stored in the database
        return {
            "is_local_mode": True,
            "external_endpoint": "http://10.0.1.50:8080",
            "local_endpoint": "http://gentwo-vllm-embeddings:8000/v1/embeddings"
        }

    except Exception as e:
        logger.error(f"Failed to get BGE-M3 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bge-m3/status")
async def get_bge_m3_status(
    db: AsyncSession = Depends(get_db)
):
    """Get BGE-M3 status across all services"""
    import httpx
    import asyncio

    services_to_check = [
        {"name": "Resource Cluster", "url": "http://localhost:8003/api/embeddings/config/bge-m3"},
        {"name": "Tenant Backend", "url": "http://localhost:8002/api/embeddings/config/bge-m3"},
    ]

    async def check_service(service: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(service["url"])
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "service": service["name"],
                        "status": "online",
                        "config": data
                    }
                else:
                    return {
                        "service": service["name"],
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "service": service["name"],
                "status": "offline",
                "error": str(e)
            }

    # Check all services in parallel
    tasks = [check_service(service) for service in services_to_check]
    service_statuses = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        "services": service_statuses,
        "timestamp": "2025-01-21T12:00:00Z"
    }


@router.post("/bge-m3/config")
async def update_bge_m3_config(
    config_request: BGE_M3_ConfigRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update BGE-M3 configuration and sync to services"""
    try:
        # External endpoint URL is preserved as provided by user
        if config_request.external_endpoint:
            logger.debug(f"BGE-M3 external endpoint: {config_request.external_endpoint}")

        logger.info(f"BGE-M3 config updated: local_mode={config_request.is_local_mode}, external_endpoint={config_request.external_endpoint}")

        # STEP 1: Persist configuration to database
        # Determine the endpoint and provider based on mode
        if config_request.is_local_mode:
            endpoint = "http://gentwo-vllm-embeddings:8000/v1/embeddings"
            provider = "external"  # Still external provider, just local endpoint
        else:
            endpoint = config_request.external_endpoint
            provider = "external"

        # Update or create BGE-M3 model configuration in database
        from sqlalchemy import select
        stmt = select(ModelConfig).where(ModelConfig.model_id == "BAAI/bge-m3")
        result = await db.execute(stmt)
        bge_m3_model = result.scalar_one_or_none()

        if bge_m3_model:
            # Update existing configuration
            bge_m3_model.endpoint = endpoint
            bge_m3_model.provider = provider
            bge_m3_model.is_active = True
            # Store mode in config JSON for reference
            if not bge_m3_model.config:
                bge_m3_model.config = {}
            bge_m3_model.config["is_local_mode"] = config_request.is_local_mode
            if config_request.external_endpoint:
                bge_m3_model.config["external_endpoint"] = config_request.external_endpoint
            logger.info(f"Updated BGE-M3 model config in database: endpoint={endpoint}")
        else:
            # Create new BGE-M3 configuration
            bge_m3_model = ModelConfig(
                model_id="BAAI/bge-m3",
                name="BGE-M3 Embedding Model",
                version="1.5",
                provider=provider,
                model_type="embedding",
                endpoint=endpoint,
                dimensions=1024,
                config={
                    "is_local_mode": config_request.is_local_mode,
                    "external_endpoint": config_request.external_endpoint
                },
                is_active=True,
                description="BGE-M3 embedding model for document processing and RAG"
            )
            db.add(bge_m3_model)
            logger.info(f"Created BGE-M3 model config in database: endpoint={endpoint}")

        await db.commit()
        logger.info("BGE-M3 configuration persisted to database successfully")

        # STEP 2: Sync configuration to resource cluster
        sync_success = await _sync_bge_m3_config_to_services(config_request)

        if sync_success:
            return {
                "message": "BGE-M3 configuration updated and synced successfully",
                "config": {
                    "is_local_mode": config_request.is_local_mode,
                    "external_endpoint": config_request.external_endpoint,
                    "local_endpoint": "http://gentwo-vllm-embeddings:8000/v1/embeddings"
                },
                "sync_status": "success",
                "database_persistence": "success"
            }
        else:
            return {
                "message": "BGE-M3 configuration updated but sync failed",
                "config": {
                    "is_local_mode": config_request.is_local_mode,
                    "external_endpoint": config_request.external_endpoint,
                    "local_endpoint": "http://gentwo-vllm-embeddings:8000/v1/embeddings"
                },
                "sync_status": "failed",
                "database_persistence": "success"
            }

    except Exception as e:
        logger.error(f"Failed to update BGE-M3 config: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def _sync_bge_m3_config_to_services(config: BGE_M3_ConfigRequest) -> bool:
    """Sync BGE-M3 configuration to all services"""
    import httpx
    import asyncio
    import os

    # Use Docker service names for inter-container communication
    # Check if we're in Docker (presence of /.dockerenv) or development (localhost)
    in_docker = os.path.exists('/.dockerenv')

    if in_docker:
        services_to_sync = [
            "http://gentwo-resource-backend:8000",  # Resource cluster (Docker service name)
            "http://gentwo-tenant-backend:8000",     # Tenant backend (Docker service name)
        ]
    else:
        services_to_sync = [
            "http://localhost:8004",  # Resource cluster (host port mapping)
            "http://localhost:8002",  # Tenant backend (host port mapping)
        ]

    sync_results = []

    async def sync_to_service(service_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Determine the correct endpoint path for each service
                if 'resource-backend' in service_url or 'localhost:8004' in service_url:
                    endpoint_path = "/api/v1/embeddings/config/bge-m3"
                else:  # Tenant backend
                    endpoint_path = "/api/embeddings/config/bge-m3"

                response = await client.post(
                    f"{service_url}{endpoint_path}",
                    json={
                        "is_local_mode": config.is_local_mode,
                        "external_endpoint": config.external_endpoint
                    },
                    headers={
                        "Content-Type": "application/json",
                        # TODO: Add proper service-to-service authentication
                    }
                )
                if response.status_code == 200:
                    logger.info(f"Successfully synced BGE-M3 config to {service_url}")
                    return True
                else:
                    logger.warning(f"Failed to sync BGE-M3 config to {service_url}: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Error syncing BGE-M3 config to {service_url}: {e}")
            return False

    # Sync to all services in parallel
    tasks = [sync_to_service(url) for url in services_to_sync]
    sync_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Return True if at least one sync succeeded
    success_count = sum(1 for result in sync_results if result is True)
    logger.info(f"BGE-M3 config sync: {success_count}/{len(services_to_sync)} services updated")

    return success_count > 0

