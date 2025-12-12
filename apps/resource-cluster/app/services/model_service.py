"""
GT 2.0 Model Management Service - Stateless Version

Provides centralized model registry, versioning, deployment, and lifecycle management
for all AI models across the Resource Cluster using in-memory storage.
"""

import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import httpx
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ModelService:
    """Stateless model management service with in-memory registry"""
    
    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.settings = get_settings(tenant_id)
        
        # In-memory model registry for stateless operation
        self.model_registry: Dict[str, Dict[str, Any]] = {}
        self.last_cache_update = 0
        self.cache_ttl = 300  # 5 minutes
        
        # Performance tracking (in-memory)
        self.performance_metrics: Dict[str, Dict[str, Any]] = {}
        
        # Initialize with default models synchronously
        self._initialize_default_models_sync()
    
    async def register_model(
        self,
        model_id: str,
        name: str,
        version: str,
        provider: str,
        model_type: str,
        description: str = "",
        capabilities: Dict[str, Any] = None,
        parameters: Dict[str, Any] = None,
        endpoint_url: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Register a new model in the in-memory registry"""
        
        now = datetime.utcnow()
        
        # Create or update model entry
        model_entry = {
            "id": model_id,
            "name": name,
            "version": version,
            "provider": provider,
            "model_type": model_type,
            "description": description,
            "capabilities": capabilities or {},
            "parameters": parameters or {},
            
            # Performance metrics
            "max_tokens": kwargs.get("max_tokens", 4000),
            "context_window": kwargs.get("context_window", 4000),
            "cost_per_1k_tokens": kwargs.get("cost_per_1k_tokens", 0.0),
            "latency_p50_ms": kwargs.get("latency_p50_ms", 0.0),
            "latency_p95_ms": kwargs.get("latency_p95_ms", 0.0),
            
            # Deployment status
            "deployment_status": kwargs.get("deployment_status", "available"),
            "health_status": kwargs.get("health_status", "unknown"),
            "last_health_check": kwargs.get("last_health_check"),
            
            # Usage tracking
            "request_count": kwargs.get("request_count", 0),
            "error_count": kwargs.get("error_count", 0),
            "success_rate": kwargs.get("success_rate", 1.0),
            
            # Lifecycle
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "retired_at": kwargs.get("retired_at"),
            
            # Configuration
            "endpoint_url": endpoint_url,
            "api_key_required": kwargs.get("api_key_required", True),
            "rate_limits": kwargs.get("rate_limits", {})
        }
        
        self.model_registry[model_id] = model_entry
        
        logger.info(f"Registered model: {model_id} ({name} v{version})")
        return model_entry
    
    async def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model by ID"""
        return self.model_registry.get(model_id)
    
    async def list_models(
        self,
        provider: str = None,
        model_type: str = None,
        deployment_status: str = None,
        health_status: str = None
    ) -> List[Dict[str, Any]]:
        """List models with optional filters"""
        
        models = list(self.model_registry.values())
        
        # Apply filters
        if provider:
            models = [m for m in models if m["provider"] == provider]
        if model_type:
            models = [m for m in models if m["model_type"] == model_type]
        if deployment_status:
            models = [m for m in models if m["deployment_status"] == deployment_status]
        if health_status:
            models = [m for m in models if m["health_status"] == health_status]
        
        # Sort by created_at desc
        models.sort(key=lambda x: x["created_at"], reverse=True)
        return models
    
    async def update_model_status(
        self,
        model_id: str,
        deployment_status: str = None,
        health_status: str = None
    ) -> bool:
        """Update model deployment and health status"""
        
        model = self.model_registry.get(model_id)
        if not model:
            return False
        
        if deployment_status:
            model["deployment_status"] = deployment_status
        if health_status:
            model["health_status"] = health_status
            model["last_health_check"] = datetime.utcnow().isoformat()
        
        model["updated_at"] = datetime.utcnow().isoformat()
        
        return True
    
    async def track_model_usage(
        self,
        model_id: str,
        success: bool = True,
        latency_ms: float = None
    ):
        """Track model usage and performance metrics"""
        
        model = self.model_registry.get(model_id)
        if not model:
            return
        
        # Update usage counters
        model["request_count"] += 1
        if not success:
            model["error_count"] += 1
        
        # Calculate success rate
        model["success_rate"] = (model["request_count"] - model["error_count"]) / model["request_count"]
        
        # Update latency metrics (simple running average)
        if latency_ms is not None:
            if model["latency_p50_ms"] == 0:
                model["latency_p50_ms"] = latency_ms
            else:
                # Simple exponential moving average
                alpha = 0.1
                model["latency_p50_ms"] = alpha * latency_ms + (1 - alpha) * model["latency_p50_ms"]
            
            # P95 approximation (conservative estimate)
            model["latency_p95_ms"] = max(model["latency_p95_ms"], latency_ms * 1.5)
        
        model["updated_at"] = datetime.utcnow().isoformat()
    
    async def retire_model(self, model_id: str, reason: str = "") -> bool:
        """Retire a model (mark as no longer available)"""
        
        model = self.model_registry.get(model_id)
        if not model:
            return False
        
        model["deployment_status"] = "retired"
        model["retired_at"] = datetime.utcnow().isoformat()
        model["updated_at"] = datetime.utcnow().isoformat()
        
        if reason:
            model["description"] += f"\n\nRetired: {reason}"
        
        logger.info(f"Retired model: {model_id} - {reason}")
        return True
    
    async def check_model_health(self, model_id: str) -> Dict[str, Any]:
        """Check health of a specific model"""
        
        model = await self.get_model(model_id)
        if not model:
            return {"healthy": False, "error": "Model not found"}
        
        # Generic health check for any provider with endpoint
        if "endpoint" in model and model["endpoint"]:
            return await self._check_generic_model_health(model)
        elif model["provider"] == "groq":
            return await self._check_groq_model_health(model)
        elif model["provider"] == "openai":
            return await self._check_openai_model_health(model)
        elif model["provider"] == "local":
            return await self._check_local_model_health(model)
        else:
            return {"healthy": False, "error": f"No health check method for provider: {model['provider']}"}
    
    async def _check_groq_model_health(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Health check for Groq models"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    models = response.json()
                    model_ids = [m["id"] for m in models.get("data", [])]
                    is_available = model["id"] in model_ids
                    
                    await self.update_model_status(
                        model["id"],
                        health_status="healthy" if is_available else "unhealthy"
                    )
                    
                    return {
                        "healthy": is_available,
                        "latency_ms": response.elapsed.total_seconds() * 1000,
                        "available_models": len(model_ids)
                    }
                else:
                    await self.update_model_status(model["id"], health_status="unhealthy")
                    return {"healthy": False, "error": f"API error: {response.status_code}"}
        
        except Exception as e:
            await self.update_model_status(model["id"], health_status="unhealthy")
            return {"healthy": False, "error": str(e)}
    
    async def _check_openai_model_health(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Health check for OpenAI models"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    models = response.json()
                    model_ids = [m["id"] for m in models.get("data", [])]
                    is_available = model["id"] in model_ids
                    
                    await self.update_model_status(
                        model["id"],
                        health_status="healthy" if is_available else "unhealthy"
                    )
                    
                    return {
                        "healthy": is_available,
                        "latency_ms": response.elapsed.total_seconds() * 1000
                    }
                else:
                    await self.update_model_status(model["id"], health_status="unhealthy")
                    return {"healthy": False, "error": f"API error: {response.status_code}"}
        
        except Exception as e:
            await self.update_model_status(model["id"], health_status="unhealthy")
            return {"healthy": False, "error": str(e)}

    async def _check_generic_model_health(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Generic health check for any provider with configured endpoint"""
        try:
            endpoint_url = model.get("endpoint")
            if not endpoint_url:
                return {"healthy": False, "error": "No endpoint URL configured"}

            # Try a simple health check by making a minimal request
            async with httpx.AsyncClient(timeout=10.0) as client:
                # For OpenAI-compatible endpoints, try a models list request
                try:
                    # Try /v1/models endpoint first (common for OpenAI-compatible APIs)
                    models_url = endpoint_url.replace("/chat/completions", "/models").replace("/v1/chat/completions", "/v1/models")
                    response = await client.get(models_url)

                    if response.status_code == 200:
                        await self.update_model_status(model["id"], health_status="healthy")
                        return {
                            "healthy": True,
                            "provider": model.get("provider", "unknown"),
                            "latency_ms": 0,  # Could measure actual latency
                            "last_check": datetime.utcnow().isoformat(),
                            "details": "Endpoint responding to models request"
                        }
                except:
                    pass

                # If models endpoint doesn't work, try a basic health endpoint
                try:
                    health_url = endpoint_url.replace("/chat/completions", "/health").replace("/v1/chat/completions", "/health")
                    response = await client.get(health_url)

                    if response.status_code == 200:
                        await self.update_model_status(model["id"], health_status="healthy")
                        return {
                            "healthy": True,
                            "provider": model.get("provider", "unknown"),
                            "latency_ms": 0,
                            "last_check": datetime.utcnow().isoformat(),
                            "details": "Endpoint responding to health check"
                        }
                except:
                    pass

                # If neither works, assume healthy if endpoint is reachable at all
                await self.update_model_status(model["id"], health_status="unknown")
                return {
                    "healthy": True,  # Assume healthy for generic endpoints
                    "provider": model.get("provider", "unknown"),
                    "latency_ms": 0,
                    "last_check": datetime.utcnow().isoformat(),
                    "details": "Generic endpoint - health check not available"
                }

        except Exception as e:
            await self.update_model_status(model["id"], health_status="unhealthy")
            return {"healthy": False, "error": f"Health check failed: {str(e)}"}

    async def _check_local_model_health(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Health check for local models"""
        try:
            endpoint_url = model.get("endpoint_url")
            if not endpoint_url:
                return {"healthy": False, "error": "No endpoint URL configured"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{endpoint_url}/health",
                    timeout=5.0
                )
                
                healthy = response.status_code == 200
                await self.update_model_status(
                    model["id"],
                    health_status="healthy" if healthy else "unhealthy"
                )
                
                return {
                    "healthy": healthy,
                    "latency_ms": response.elapsed.total_seconds() * 1000
                }
        
        except Exception as e:
            await self.update_model_status(model["id"], health_status="unhealthy")
            return {"healthy": False, "error": str(e)}
    
    async def bulk_health_check(self) -> Dict[str, Any]:
        """Check health of all registered models"""
        
        models = await self.list_models()
        health_results = {}
        
        # Run health checks concurrently
        tasks = []
        for model in models:
            task = asyncio.create_task(self.check_model_health(model["id"]))
            tasks.append((model["id"], task))
        
        for model_id, task in tasks:
            try:
                health_result = await task
                health_results[model_id] = health_result
            except Exception as e:
                health_results[model_id] = {"healthy": False, "error": str(e)}
        
        # Calculate overall health statistics
        total_models = len(health_results)
        healthy_models = sum(1 for result in health_results.values() if result.get("healthy", False))
        
        return {
            "total_models": total_models,
            "healthy_models": healthy_models,
            "unhealthy_models": total_models - healthy_models,
            "health_percentage": (healthy_models / total_models * 100) if total_models > 0 else 0,
            "individual_results": health_results
        }
    
    async def get_model_analytics(
        self,
        model_id: str = None,
        timeframe_hours: int = 24
    ) -> Dict[str, Any]:
        """Get analytics for model usage and performance"""
        
        models = await self.list_models()
        if model_id:
            models = [m for m in models if m["id"] == model_id]
        
        analytics = {
            "total_models": len(models),
            "by_provider": {},
            "by_type": {},
            "performance_summary": {
                "avg_latency_p50": 0,
                "avg_success_rate": 0,
                "total_requests": 0,
                "total_errors": 0
            },
            "top_performers": [],
            "models": models
        }
        
        total_latency = 0
        total_success_rate = 0
        total_requests = 0
        total_errors = 0
        
        for model in models:
            # Provider statistics
            provider = model["provider"]
            if provider not in analytics["by_provider"]:
                analytics["by_provider"][provider] = {"count": 0, "requests": 0}
            analytics["by_provider"][provider]["count"] += 1
            analytics["by_provider"][provider]["requests"] += model["request_count"]
            
            # Type statistics
            model_type = model["model_type"]
            if model_type not in analytics["by_type"]:
                analytics["by_type"][model_type] = {"count": 0, "requests": 0}
            analytics["by_type"][model_type]["count"] += 1
            analytics["by_type"][model_type]["requests"] += model["request_count"]
            
            # Performance aggregation
            total_latency += model["latency_p50_ms"]
            total_success_rate += model["success_rate"]
            total_requests += model["request_count"]
            total_errors += model["error_count"]
        
        # Calculate averages
        if len(models) > 0:
            analytics["performance_summary"]["avg_latency_p50"] = total_latency / len(models)
            analytics["performance_summary"]["avg_success_rate"] = total_success_rate / len(models)
        
        analytics["performance_summary"]["total_requests"] = total_requests
        analytics["performance_summary"]["total_errors"] = total_errors
        
        # Top performers (by success rate and low latency)
        analytics["top_performers"] = sorted(
            [m for m in models if m["request_count"] > 0],
            key=lambda x: (x["success_rate"], -x["latency_p50_ms"]),
            reverse=True
        )[:5]
        
        return analytics
    
    async def _initialize_default_models(self):
        """Initialize registry with default models"""
        
        # Groq models
        groq_models = [
            {
                "model_id": "llama-3.1-405b-reasoning",
                "name": "Llama 3.1 405B Reasoning",
                "version": "3.1",
                "provider": "groq",
                "model_type": "llm",
                "description": "Largest Llama model optimized for complex reasoning tasks",
                "max_tokens": 8000,
                "context_window": 32768,
                "cost_per_1k_tokens": 2.5,
                "capabilities": {"reasoning": True, "function_calling": True, "streaming": True}
            },
            {
                "model_id": "llama-3.1-70b-versatile",
                "name": "Llama 3.1 70B Versatile",
                "version": "3.1",
                "provider": "groq",
                "model_type": "llm",
                "description": "Balanced Llama model for general-purpose tasks",
                "max_tokens": 8000,
                "context_window": 32768,
                "cost_per_1k_tokens": 0.8,
                "capabilities": {"general": True, "function_calling": True, "streaming": True}
            },
            {
                "model_id": "llama-3.1-8b-instant",
                "name": "Llama 3.1 8B Instant",
                "version": "3.1",
                "provider": "groq",
                "model_type": "llm",
                "description": "Fast Llama model for quick responses",
                "max_tokens": 8000,
                "context_window": 32768,
                "cost_per_1k_tokens": 0.2,
                "capabilities": {"fast": True, "streaming": True}
            },
            {
                "model_id": "mixtral-8x7b-32768",
                "name": "Mixtral 8x7B",
                "version": "1.0",
                "provider": "groq",
                "model_type": "llm",
                "description": "Mixtral model for balanced performance",
                "max_tokens": 32768,
                "context_window": 32768,
                "cost_per_1k_tokens": 0.27,
                "capabilities": {"general": True, "streaming": True}
            }
        ]
        
        for model_config in groq_models:
            await self.register_model(**model_config)
        
        logger.info("Initialized default model registry with in-memory storage")
    
    def _initialize_default_models_sync(self):
        """Initialize registry with default models synchronously"""
        
        # Groq models
        groq_models = [
            {
                "model_id": "llama-3.1-405b-reasoning",
                "name": "Llama 3.1 405B Reasoning",
                "version": "3.1",
                "provider": "groq",
                "model_type": "llm",
                "description": "Largest Llama model optimized for complex reasoning tasks",
                "max_tokens": 8000,
                "context_window": 32768,
                "cost_per_1k_tokens": 2.5,
                "capabilities": {"reasoning": True, "function_calling": True, "streaming": True}
            },
            {
                "model_id": "llama-3.1-70b-versatile",
                "name": "Llama 3.1 70B Versatile", 
                "version": "3.1",
                "provider": "groq",
                "model_type": "llm",
                "description": "Balanced Llama model for general-purpose tasks",
                "max_tokens": 8000,
                "context_window": 32768,
                "cost_per_1k_tokens": 0.8,
                "capabilities": {"general": True, "function_calling": True, "streaming": True}
            },
            {
                "model_id": "llama-3.1-8b-instant",
                "name": "Llama 3.1 8B Instant",
                "version": "3.1",
                "provider": "groq",
                "model_type": "llm",
                "description": "Fast Llama model for quick responses",
                "max_tokens": 8000,
                "context_window": 32768,
                "cost_per_1k_tokens": 0.2,
                "capabilities": {"fast": True, "streaming": True}
            },
            {
                "model_id": "mixtral-8x7b-32768",
                "name": "Mixtral 8x7B",
                "version": "1.0",
                "provider": "groq",
                "model_type": "llm", 
                "description": "Mixtral model for balanced performance",
                "max_tokens": 32768,
                "context_window": 32768,
                "cost_per_1k_tokens": 0.27,
                "capabilities": {"general": True, "streaming": True}
            },
            {
                "model_id": "groq/compound",
                "name": "Groq Compound Model",
                "version": "1.0",
                "provider": "groq",
                "model_type": "llm",
                "description": "Groq compound AI model",
                "max_tokens": 8000,
                "context_window": 8000,
                "cost_per_1k_tokens": 0.5,
                "capabilities": {"general": True, "streaming": True}
            }
        ]
        
        for model_config in groq_models:
            now = datetime.utcnow()
            model_entry = {
                "id": model_config["model_id"],
                "name": model_config["name"],
                "version": model_config["version"],
                "provider": model_config["provider"],
                "model_type": model_config["model_type"],
                "description": model_config["description"],
                "capabilities": model_config["capabilities"],
                "parameters": {},
                
                # Performance metrics
                "max_tokens": model_config["max_tokens"],
                "context_window": model_config["context_window"],
                "cost_per_1k_tokens": model_config["cost_per_1k_tokens"],
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                
                # Deployment status
                "deployment_status": "available",
                "health_status": "unknown",
                "last_health_check": None,
                
                # Usage tracking
                "request_count": 0,
                "error_count": 0,
                "success_rate": 1.0,
                
                # Lifecycle
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "retired_at": None,
                
                # Configuration
                "endpoint_url": None,
                "api_key_required": True,
                "rate_limits": {}
            }
            
            self.model_registry[model_config["model_id"]] = model_entry
        
        logger.info("Initialized default model registry with in-memory storage (sync)")
    
    async def register_or_update_model(
        self,
        model_id: str,
        name: str,
        version: str = "1.0",
        provider: str = "unknown",
        model_type: str = "llm",
        endpoint: str = "",
        api_key_name: str = None,
        specifications: Dict[str, Any] = None,
        capabilities: Dict[str, Any] = None,
        cost: Dict[str, Any] = None,
        description: str = "",
        config: Dict[str, Any] = None,
        status: Dict[str, Any] = None,
        sync_timestamp: str = None
    ) -> Dict[str, Any]:
        """Register a new model or update existing one from admin cluster sync"""
        
        specifications = specifications or {}
        capabilities = capabilities or {}
        cost = cost or {}
        config = config or {}
        status = status or {}
        
        # Check if model exists
        existing_model = self.model_registry.get(model_id)
        
        if existing_model:
            # Update existing model
            existing_model.update({
                "name": name,
                "version": version,
                "provider": provider,
                "model_type": model_type,
                "description": description,
                "capabilities": capabilities,
                "parameters": config,
                "endpoint_url": endpoint,
                "api_key_required": bool(api_key_name),
                "max_tokens": specifications.get("max_tokens", existing_model.get("max_tokens", 4000)),
                "context_window": specifications.get("context_window", existing_model.get("context_window", 4000)),
                "cost_per_1k_tokens": cost.get("per_1k_input", existing_model.get("cost_per_1k_tokens", 0.0)),
                "deployment_status": "deployed" if status.get("is_active", True) else "retired",
                "updated_at": datetime.utcnow().isoformat()
            })

            if "bge-m3" in model_id.lower():
                logger.info(f"Updated BGE-M3 model: endpoint_url={endpoint}, parameters={config}")
            logger.debug(f"Updated model: {model_id}")
            return existing_model
        else:
            # Register new model
            return await self.register_model(
                model_id=model_id,
                name=name,
                version=version,
                provider=provider,
                model_type=model_type,
                description=description,
                capabilities=capabilities,
                parameters=config,
                endpoint_url=endpoint,
                max_tokens=specifications.get("max_tokens", 4000),
                context_window=specifications.get("context_window", 4000),
                cost_per_1k_tokens=cost.get("per_1k_input", 0.0),
                api_key_required=bool(api_key_name)
            )


def get_model_service(tenant_id: Optional[str] = None) -> ModelService:
    """Get tenant-isolated model service instance"""
    return ModelService(tenant_id=tenant_id)

# Default model service for development/non-tenant operations
default_model_service = get_model_service()