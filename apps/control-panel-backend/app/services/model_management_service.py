"""
Model Management Service for GT 2.0 Admin Control Panel

This service manages AI model configurations across the entire GT 2.0 platform.
It provides the "single pane of glass" for admins to configure all models
and syncs changes to resource clusters via RabbitMQ.
"""

import httpx
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
import logging

from app.models.model_config import ModelConfig, ModelUsageLog
from app.models.tenant_model_config import TenantModelConfig
from app.models.tenant import Tenant
from app.services.message_bus import MessageBusService

logger = logging.getLogger(__name__)


def translate_rate_limits_to_db(api_rate_limits: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Translate API rate limits (per-minute) to database format (per-hour).

    API uses requests_per_minute, database stores max_requests_per_hour.
    This is the inverse of TenantModelConfig.to_dict() translation.

    Args:
        api_rate_limits: Rate limits from API request (per-minute)

    Returns:
        Rate limits for database storage (per-hour)
    """
    if not api_rate_limits:
        return None

    db_rate_limits = {}
    for key, value in api_rate_limits.items():
        if key == "requests_per_minute":
            # Convert per-minute to per-hour for database
            db_rate_limits["max_requests_per_hour"] = value * 60
        else:
            # Keep other fields as-is
            db_rate_limits[key] = value

    return db_rate_limits


class ModelManagementService:
    """Central service for managing AI model configurations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_bus = MessageBusService()
    
    async def register_model(self, model_data: Dict[str, Any]) -> ModelConfig:
        """Register a new model in the admin database"""
        try:
            # Check if model already exists for this provider (same model_id + provider is not allowed)
            query = select(ModelConfig).filter(
                ModelConfig.model_id == model_data["model_id"],
                ModelConfig.provider == model_data["provider"]
            )
            result = await self.db.execute(query)
            existing = result.scalars().first()
            if existing:
                raise ValueError(f"Model {model_data['model_id']} already exists for provider {model_data['provider']}")
            
            # Create new model configuration
            model = ModelConfig.from_dict(model_data)
            self.db.add(model)
            await self.db.commit()
            await self.db.refresh(model)
            
            # Notify all resource clusters
            await self.notify_clusters("model_added", model.to_dict())
            
            logger.info(f"Registered new model: {model.model_id}")
            return model
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to register model: {e}")
            raise
    
    async def update_model(self, model_id: str, updates: Dict[str, Any]) -> Optional[ModelConfig]:
        """Update an existing model configuration"""
        try:
            query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
            result = await self.db.execute(query)
            model = result.scalars().first()
            if not model:
                return None
            
            # Update fields
            for field, value in updates.items():
                if field == "specifications":
                    if "context_window" in value:
                        model.context_window = value["context_window"]
                    if "max_tokens" in value:
                        model.max_tokens = value["max_tokens"]
                    if "dimensions" in value:
                        model.dimensions = value["dimensions"]
                elif field == "cost":
                    if "per_million_input" in value:
                        model.cost_per_million_input = value["per_million_input"]
                    if "per_million_output" in value:
                        model.cost_per_million_output = value["per_million_output"]
                elif field == "status":
                    if "is_active" in value:
                        model.is_active = value["is_active"]
                    if "is_compound" in value:
                        model.is_compound = value["is_compound"]
                elif hasattr(model, field):
                    setattr(model, field, value)
            
            model.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(model)
            
            # Notify all resource clusters
            await self.notify_clusters("model_updated", model.to_dict())
            
            logger.info(f"Updated model: {model.model_id}")
            return model
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update model: {e}")
            raise
    
    async def delete_model(self, model_id: str) -> bool:
        """Permanently delete a model configuration"""
        try:
            query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
            result = await self.db.execute(query)
            model = result.scalars().first()
            if not model:
                return False

            # Hard delete - permanently remove from database
            await self.db.delete(model)
            await self.db.commit()

            # Notify all resource clusters
            await self.notify_clusters("model_deleted", {"model_id": model_id})

            logger.info(f"Permanently deleted model: {model_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete model: {e}")
            raise
    
    async def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get a specific model configuration"""
        query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def list_models(
        self, 
        provider: Optional[str] = None,
        model_type: Optional[str] = None,
        active_only: bool = False
    ) -> List[ModelConfig]:
        """List all model configurations with optional filters"""
        query = select(ModelConfig)
        
        if provider:
            query = query.filter(ModelConfig.provider == provider)
        if model_type:
            query = query.filter(ModelConfig.model_type == model_type)
        if active_only:
            query = query.filter(ModelConfig.is_active == True)
        
        query = query.order_by(ModelConfig.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_endpoint(self, model_id: str, endpoint: str) -> bool:
        """Update model endpoint configuration"""
        try:
            query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
            result = await self.db.execute(query)
            model = result.scalars().first()
            if not model:
                return False
            
            old_endpoint = model.endpoint
            model.endpoint = endpoint
            model.updated_at = datetime.utcnow()
            await self.db.commit()
            
            # Notify all resource clusters
            await self.notify_clusters("endpoint_updated", {
                "model_id": model_id,
                "old_endpoint": old_endpoint,
                "new_endpoint": endpoint
            })
            
            logger.info(f"Updated endpoint for {model_id}: {endpoint}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update endpoint: {e}")
            return False
    
    async def test_endpoint(self, model_id: str) -> Dict[str, Any]:
        """Test if a model endpoint is accessible"""
        model = await self.get_model(model_id)
        if not model:
            return {"healthy": False, "error": "Model not found", "error_type": "not_found"}

        try:
            if model.provider == "groq":
                return await self._test_groq_endpoint(model)
            elif model.provider == "nvidia":
                return await self._test_nvidia_endpoint(model)
            elif model.provider == "external":
                return await self._test_external_endpoint(model)
            elif model.provider == "openai":
                return await self._test_openai_endpoint(model)
            else:
                return {"healthy": False, "error": f"Unknown provider: {model.provider}", "error_type": "unknown_provider"}

        except Exception as e:
            logger.error(f"Endpoint test failed for {model_id}: {e}")
            return {"healthy": False, "error": str(e), "error_type": "exception"}
    
    async def _test_groq_endpoint(self, model: ModelConfig) -> Dict[str, Any]:
        """Test Groq endpoint health with model validation and rate limit extraction"""
        try:
            api_key = self._get_api_key('GROQ_API_KEY')
            if not api_key:
                return {
                    "healthy": False,
                    "error": "GROQ_API_KEY not configured",
                    "error_type": "missing_api_key"
                }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )

                latency_ms = response.elapsed.total_seconds() * 1000

                # Extract rate limit headers
                rate_limit_remaining = None
                rate_limit_reset = None
                if 'x-ratelimit-remaining-requests' in response.headers:
                    try:
                        rate_limit_remaining = int(response.headers['x-ratelimit-remaining-requests'])
                    except (ValueError, TypeError):
                        pass
                if 'x-ratelimit-reset-requests' in response.headers:
                    rate_limit_reset = response.headers['x-ratelimit-reset-requests']

                if response.status_code == 200:
                    models = response.json()
                    available_models = [m["id"] for m in models.get("data", [])]
                    is_available = model.model_id in available_models

                    # Update health status
                    await self._update_health_status(
                        model.model_id,
                        "healthy" if is_available else "unhealthy"
                    )

                    return {
                        "healthy": is_available,
                        "latency_ms": latency_ms,
                        "available_models": len(available_models),
                        "rate_limit_remaining": rate_limit_remaining,
                        "rate_limit_reset": rate_limit_reset,
                        "details": {
                            "model_in_catalog": is_available,
                            "catalog_size": len(available_models)
                        },
                        "error": None if is_available else f"Model {model.model_id} not found in Groq catalog",
                        "error_type": None if is_available else "model_not_found"
                    }
                elif response.status_code == 401:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "error": "Invalid or expired API key",
                        "error_type": "auth_failed",
                        "latency_ms": latency_ms
                    }
                elif response.status_code == 429:
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "error": "Rate limit exceeded",
                        "error_type": "rate_limited",
                        "latency_ms": latency_ms,
                        "rate_limit_remaining": rate_limit_remaining,
                        "rate_limit_reset": rate_limit_reset
                    }
                else:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "error": f"API error: HTTP {response.status_code}",
                        "error_type": "server_error" if response.status_code >= 500 else "api_error",
                        "latency_ms": latency_ms
                    }

        except httpx.ConnectError:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection failed: Unable to reach Groq API",
                "error_type": "connection_error"
            }
        except httpx.TimeoutException:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection timed out",
                "error_type": "timeout"
            }
        except Exception as e:
            await self._update_health_status(model.model_id, "unhealthy")
            return {"healthy": False, "error": str(e), "error_type": "exception"}

    async def _test_nvidia_endpoint(self, model: ModelConfig) -> Dict[str, Any]:
        """Test NVIDIA NIM endpoint health with dedicated health endpoint"""
        try:
            api_key = self._get_api_key('NVIDIA_API_KEY')
            if not api_key:
                return {
                    "healthy": False,
                    "error": "NVIDIA_API_KEY not configured",
                    "error_type": "missing_api_key"
                }

            async with httpx.AsyncClient() as client:
                # NVIDIA NIM has a dedicated health endpoint
                # Try the /v1/health/ready endpoint first (industry standard for NIM)
                base_endpoint = model.endpoint.rstrip('/').replace('/chat/completions', '').replace('/completions', '')
                health_url = f"{base_endpoint}/v1/health/ready"

                try:
                    health_response = await client.get(health_url, timeout=10.0)
                    latency_ms = health_response.elapsed.total_seconds() * 1000

                    if health_response.status_code == 200:
                        await self._update_health_status(model.model_id, "healthy")
                        return {
                            "healthy": True,
                            "latency_ms": latency_ms,
                            "details": {
                                "endpoint_type": "nvidia_nim",
                                "health_endpoint": health_url
                            }
                        }
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass  # Fall through to models endpoint test

                # Fallback: test the models endpoint with auth
                response = await client.get(
                    "https://integrate.api.nvidia.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )

                latency_ms = response.elapsed.total_seconds() * 1000

                # Extract rate limit headers
                rate_limit_remaining = None
                rate_limit_reset = None
                if 'x-ratelimit-remaining' in response.headers:
                    try:
                        rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
                    except (ValueError, TypeError):
                        pass
                if 'x-ratelimit-reset' in response.headers:
                    rate_limit_reset = response.headers['x-ratelimit-reset']

                if response.status_code == 200:
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "rate_limit_remaining": rate_limit_remaining,
                        "rate_limit_reset": rate_limit_reset,
                        "details": {"endpoint_type": "nvidia_nim"}
                    }
                elif response.status_code == 401:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "error": "Invalid or expired NVIDIA API key",
                        "error_type": "auth_failed",
                        "latency_ms": latency_ms
                    }
                elif response.status_code == 429:
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "error": "Rate limit exceeded",
                        "error_type": "rate_limited",
                        "latency_ms": latency_ms,
                        "rate_limit_remaining": rate_limit_remaining,
                        "rate_limit_reset": rate_limit_reset
                    }
                else:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "error": f"API error: HTTP {response.status_code}",
                        "error_type": "server_error" if response.status_code >= 500 else "api_error",
                        "latency_ms": latency_ms
                    }

        except httpx.ConnectError:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection failed: Unable to reach NVIDIA API",
                "error_type": "connection_error"
            }
        except httpx.TimeoutException:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection timed out",
                "error_type": "timeout"
            }
        except Exception as e:
            await self._update_health_status(model.model_id, "unhealthy")
            return {"healthy": False, "error": str(e), "error_type": "exception"}

    async def _test_external_endpoint(self, model: ModelConfig) -> Dict[str, Any]:
        """Test external endpoint health (e.g., BGE-M3 on GT Edge network)"""
        try:
            async with httpx.AsyncClient() as client:
                # Try health endpoint first (standard for vLLM, BGE-M3)
                health_url = f"{model.endpoint.rstrip('/')}/health"
                try:
                    response = await client.get(health_url, timeout=5.0)
                    latency_ms = response.elapsed.total_seconds() * 1000

                    if response.status_code == 200:
                        await self._update_health_status(model.model_id, "healthy")
                        response_data = None
                        try:
                            if response.headers.get('content-type', '').startswith('application/json'):
                                response_data = response.json()
                        except Exception:
                            pass

                        return {
                            "healthy": True,
                            "latency_ms": latency_ms,
                            "details": {
                                "health_endpoint": health_url,
                                "response": response_data or "OK"
                            }
                        }
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass  # Fall through to root endpoint test

                # Try root endpoint as fallback
                response = await client.get(model.endpoint, timeout=5.0)
                latency_ms = response.elapsed.total_seconds() * 1000

                if response.status_code == 200:
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "details": {"endpoint": model.endpoint}
                    }
                elif response.status_code >= 500:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "latency_ms": latency_ms,
                        "error": f"Server error: HTTP {response.status_code}",
                        "error_type": "server_error"
                    }
                else:
                    # 4xx errors mean endpoint is reachable
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "details": {"endpoint": model.endpoint, "status_code": response.status_code}
                    }

        except httpx.ConnectError:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": f"Connection failed: Unable to reach {model.endpoint}",
                "error_type": "connection_error"
            }
        except httpx.TimeoutException:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection timed out",
                "error_type": "timeout"
            }
        except Exception as e:
            await self._update_health_status(model.model_id, "unhealthy")
            return {"healthy": False, "error": str(e), "error_type": "exception"}
    
    async def _test_openai_endpoint(self, model: ModelConfig) -> Dict[str, Any]:
        """Test OpenAI endpoint health"""
        try:
            api_key = self._get_api_key('OPENAI_API_KEY')
            if not api_key:
                return {
                    "healthy": False,
                    "error": "OPENAI_API_KEY not configured",
                    "error_type": "missing_api_key"
                }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )

                latency_ms = response.elapsed.total_seconds() * 1000

                if response.status_code == 200:
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "latency_ms": latency_ms
                    }
                elif response.status_code == 401:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "error": "Invalid or expired API key",
                        "error_type": "auth_failed",
                        "latency_ms": latency_ms
                    }
                elif response.status_code == 429:
                    await self._update_health_status(model.model_id, "healthy")
                    return {
                        "healthy": True,
                        "error": "Rate limit exceeded",
                        "error_type": "rate_limited",
                        "latency_ms": latency_ms
                    }
                else:
                    await self._update_health_status(model.model_id, "unhealthy")
                    return {
                        "healthy": False,
                        "error": f"API error: HTTP {response.status_code}",
                        "error_type": "server_error" if response.status_code >= 500 else "api_error",
                        "latency_ms": latency_ms
                    }

        except httpx.ConnectError:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection failed: Unable to reach OpenAI API",
                "error_type": "connection_error"
            }
        except httpx.TimeoutException:
            await self._update_health_status(model.model_id, "unhealthy")
            return {
                "healthy": False,
                "error": "Connection timed out",
                "error_type": "timeout"
            }
        except Exception as e:
            await self._update_health_status(model.model_id, "unhealthy")
            return {"healthy": False, "error": str(e), "error_type": "exception"}
    
    async def _update_health_status(self, model_id: str, status: str):
        """Update model health status in database"""
        try:
            query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
            result = await self.db.execute(query)
            model = result.scalars().first()
            if model:
                model.health_status = status
                model.last_health_check = datetime.utcnow()
                await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update health status for {model_id}: {e}")
    
    def _get_api_key(self, env_var: str) -> str:
        """Get API key from environment variables"""
        import os
        return os.getenv(env_var, "")
    
    async def notify_clusters(self, event_type: str, data: Dict[str, Any]):
        """Notify all resource clusters of model configuration changes"""
        try:
            message = {
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "admin-control-panel"
            }

            # Send via RabbitMQ to resource cluster
            await self.message_bus.send_resource_command(
                command_type="model_config_update",
                payload=message,
                wait_for_response=False
            )

            # Security Note: model_id is not sensitive data - it's a public model identifier
            # like "groq/llama-3.1-8b-instant". Logging it is safe and necessary for operations.
            logger.info(f"Notified clusters of {event_type} for model {data.get('model_id', 'unknown')}")

            # Force immediate sync in resource cluster via HTTP (backup to RabbitMQ)
            await self._sync_resource_cluster()

        except Exception as e:
            logger.error(f"Failed to notify clusters: {e}")

    async def _sync_resource_cluster(self):
        """Force resource cluster to sync model configuration immediately via HTTP"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post("http://gentwo-resource-backend:8004/api/v1/models/sync")
                if response.status_code == 200:
                    logger.info("✅ Resource cluster synced successfully via HTTP")
                else:
                    logger.warning(f"⚠️ Resource cluster sync returned status {response.status_code}")
        except httpx.TimeoutException:
            logger.warning("⚠️ Resource cluster sync timed out (cluster may be slow)")
        except httpx.ConnectError:
            logger.warning("⚠️ Resource cluster unavailable (will sync via periodic polling)")
        except Exception as e:
            logger.warning(f"⚠️ Resource cluster sync failed: {e}")
    
    async def bulk_health_check(self) -> Dict[str, Any]:
        """Check health of all registered models"""
        models = await self.list_models(active_only=True)
        results = {}
        
        # Run health checks concurrently
        tasks = []
        for model in models:
            task = asyncio.create_task(self.test_endpoint(model.model_id))
            tasks.append((model.model_id, task))
        
        for model_id, task in tasks:
            try:
                result = await task
                results[model_id] = result
            except Exception as e:
                results[model_id] = {"healthy": False, "error": str(e)}
        
        # Calculate summary statistics
        total_models = len(results)
        healthy_models = sum(1 for r in results.values() if r.get("healthy", False))
        
        return {
            "total_models": total_models,
            "healthy_models": healthy_models,
            "unhealthy_models": total_models - healthy_models,
            "health_percentage": (healthy_models / total_models * 100) if total_models > 0 else 0,
            "individual_results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_usage_analytics(
        self,
        days: int = 30,
        model_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get usage analytics for models"""
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Base query
            query = select(ModelUsageLog).filter(
                ModelUsageLog.timestamp >= start_date,
                ModelUsageLog.timestamp <= end_date
            )
            
            if model_id:
                query = query.filter(ModelUsageLog.model_id == model_id)
            if tenant_id:
                query = query.filter(ModelUsageLog.tenant_id == tenant_id)
            
            result = await self.db.execute(query)
            logs = result.scalars().all()
            
            # Calculate analytics
            total_requests = len(logs)
            total_tokens = sum(log.tokens_total for log in logs)
            total_cost = sum(log.cost for log in logs)
            avg_latency = sum(log.latency_ms or 0 for log in logs) / total_requests if total_requests > 0 else 0
            success_rate = sum(1 for log in logs if log.success) / total_requests * 100 if total_requests > 0 else 100
            
            # Group by model
            models_stats = {}
            for log in logs:
                if log.model_id not in models_stats:
                    models_stats[log.model_id] = {
                        "requests": 0,
                        "tokens": 0,
                        "cost": 0,
                        "latency_sum": 0,
                        "success_count": 0
                    }
                
                stats = models_stats[log.model_id]
                stats["requests"] += 1
                stats["tokens"] += log.tokens_total
                stats["cost"] += log.cost
                stats["latency_sum"] += log.latency_ms or 0
                if log.success:
                    stats["success_count"] += 1
            
            # Format model stats
            formatted_models = []
            for model_id, stats in models_stats.items():
                formatted_models.append({
                    "model_id": model_id,
                    "requests": stats["requests"],
                    "tokens": stats["tokens"],
                    "cost": stats["cost"],
                    "avg_latency": stats["latency_sum"] / stats["requests"] if stats["requests"] > 0 else 0,
                    "success_rate": stats["success_count"] / stats["requests"] * 100 if stats["requests"] > 0 else 100
                })
            
            return {
                "summary": {
                    "total_requests": total_requests,
                    "total_tokens": total_tokens,
                    "total_cost": total_cost,
                    "avg_latency": avg_latency,
                    "success_rate": success_rate
                },
                "models": sorted(formatted_models, key=lambda x: x["requests"], reverse=True),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get usage analytics: {e}")
            raise
    
    async def initialize_default_models(self):
        """Initialize default models on first startup"""
        try:
            # Check if models already exist
            count_query = select(func.count()).select_from(ModelConfig)
            result = await self.db.execute(count_query)
            existing_count = result.scalar()
            if existing_count > 0:
                logger.info(f"Models already initialized ({existing_count} found)")
                return
            
            from .default_models import get_default_models
            default_models = get_default_models()
            
            for model_data in default_models:
                try:
                    await self.register_model(model_data)
                except Exception as e:
                    logger.error(f"Failed to initialize model {model_data.get('model_id')}: {e}")
            
            logger.info(f"Initialized {len(default_models)} default models")
            
        except Exception as e:
            logger.error(f"Failed to initialize default models: {e}")
            raise
    
    # ============================================================================
    # TENANT MODEL MANAGEMENT METHODS
    # ============================================================================
    
    async def assign_model_to_tenant(
        self,
        tenant_id: int,
        model_id: str,
        rate_limits: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        usage_constraints: Optional[Dict[str, Any]] = None,
        priority: int = 1
    ) -> TenantModelConfig:
        """
        Assign a model to a tenant with specific configuration
        
        Args:
            tenant_id: Tenant identifier
            model_id: Model identifier
            rate_limits: Custom rate limits for this tenant
            capabilities: Tenant-specific capabilities
            usage_constraints: Usage restrictions
            priority: Priority level (higher = more priority)
            
        Returns:
            Created TenantModelConfig
        """
        try:
            # Verify tenant exists
            tenant_query = select(Tenant).filter(Tenant.id == tenant_id)
            tenant_result = await self.db.execute(tenant_query)
            tenant = tenant_result.scalars().first()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Verify model exists
            model_query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
            model_result = await self.db.execute(model_query)
            model = model_result.scalars().first()
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            # Check if assignment already exists
            existing_query = select(TenantModelConfig).filter(
                TenantModelConfig.tenant_id == tenant_id,
                TenantModelConfig.model_id == model_id
            )
            existing_result = await self.db.execute(existing_query)
            existing = existing_result.scalars().first()
            if existing:
                raise ValueError(f"Model {model_id} already assigned to tenant {tenant_id}")
            
            # Translate API rate limits (per-minute) to database format (per-hour)
            db_rate_limits = translate_rate_limits_to_db(rate_limits)

            # Create tenant model configuration with UUID reference
            tenant_model_config = TenantModelConfig.create_default_config(
                tenant_id=tenant_id,
                model_id=model_id,
                model_config_id=model.id,  # Use the UUID primary key
                custom_rate_limits=db_rate_limits,  # Use translated per-hour values
                custom_capabilities=capabilities
            )
            
            if usage_constraints:
                tenant_model_config.usage_constraints = usage_constraints
            tenant_model_config.priority = priority
            
            self.db.add(tenant_model_config)
            await self.db.commit()
            await self.db.refresh(tenant_model_config)
            
            # Notify resource clusters
            await self.notify_clusters("tenant_model_assigned", {
                "tenant_id": tenant_id,
                "tenant_domain": tenant.domain,
                "model_id": model_id,
                "config": tenant_model_config.to_dict()
            })
            
            logger.info(f"Assigned model {model_id} to tenant {tenant_id}")
            return tenant_model_config
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to assign model to tenant: {e}")
            raise
    
    async def remove_model_from_tenant(self, tenant_id: int, model_id: str) -> bool:
        """
        Remove model access from a tenant
        
        Args:
            tenant_id: Tenant identifier
            model_id: Model identifier
            
        Returns:
            True if removed successfully
        """
        try:
            # Find existing configuration
            query = select(TenantModelConfig).filter(
                TenantModelConfig.tenant_id == tenant_id,
                TenantModelConfig.model_id == model_id
            )
            result = await self.db.execute(query)
            config = result.scalars().first()
            if not config:
                return False
            
            # Get tenant domain for notification
            tenant_query = select(Tenant).filter(Tenant.id == tenant_id)
            tenant_result = await self.db.execute(tenant_query)
            tenant = tenant_result.scalars().first()
            
            # Remove configuration
            await self.db.delete(config)
            await self.db.commit()
            
            # Notify resource clusters
            if tenant:
                await self.notify_clusters("tenant_model_removed", {
                    "tenant_id": tenant_id,
                    "tenant_domain": tenant.domain,
                    "model_id": model_id
                })
            
            logger.info(f"Removed model {model_id} from tenant {tenant_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to remove model from tenant: {e}")
            raise
    
    async def update_tenant_model_config(
        self,
        tenant_id: int,
        model_id: str,
        updates: Dict[str, Any]
    ) -> Optional[TenantModelConfig]:
        """
        Update tenant model configuration
        
        Args:
            tenant_id: Tenant identifier
            model_id: Model identifier
            updates: Configuration updates
            
        Returns:
            Updated TenantModelConfig or None if not found
        """
        try:
            # Find existing configuration
            query = select(TenantModelConfig).filter(
                TenantModelConfig.tenant_id == tenant_id,
                TenantModelConfig.model_id == model_id
            )
            result = await self.db.execute(query)
            config = result.scalars().first()
            if not config:
                return None
            
            # Update fields with translation for rate_limits
            for field, value in updates.items():
                if field == "rate_limits":
                    # Translate API per-minute values to database per-hour values
                    db_rate_limits = translate_rate_limits_to_db(value)
                    setattr(config, field, db_rate_limits)
                elif hasattr(config, field):
                    setattr(config, field, value)

            config.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(config)
            
            # Get tenant domain for notification
            tenant_query = select(Tenant).filter(Tenant.id == tenant_id)
            tenant_result = await self.db.execute(tenant_query)
            tenant = tenant_result.scalars().first()
            
            # Notify resource clusters
            if tenant:
                await self.notify_clusters("tenant_model_updated", {
                    "tenant_id": tenant_id,
                    "tenant_domain": tenant.domain,
                    "model_id": model_id,
                    "config": config.to_dict()
                })
            
            logger.info(f"Updated tenant model config for {model_id} in tenant {tenant_id}")
            return config
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update tenant model config: {e}")
            raise
    
    async def get_tenant_models(
        self,
        tenant_id: int,
        enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all models available to a tenant

        Args:
            tenant_id: Tenant identifier
            enabled_only: Only return enabled models

        Returns:
            List of models with tenant-specific configuration
        """
        try:
            # Build query for tenant model configurations (join on UUID)
            query = select(TenantModelConfig, ModelConfig).join(
                ModelConfig, TenantModelConfig.model_config_id == ModelConfig.id
            ).filter(TenantModelConfig.tenant_id == tenant_id)
            
            if enabled_only:
                query = query.filter(
                    TenantModelConfig.is_enabled == True,
                    ModelConfig.is_active == True
                )
            
            result = await self.db.execute(query)
            records = result.all()
            
            # Format response
            models = []
            for tenant_config, model_config in records:
                model_dict = model_config.to_dict()
                model_dict["tenant_config"] = tenant_config.to_dict()
                models.append(model_dict)
            
            return models
            
        except Exception as e:
            logger.error(f"Failed to get tenant models: {e}")
            raise
    
    async def get_model_tenants(self, model_id: str) -> List[Dict[str, Any]]:
        """
        Get all tenants that have access to a model
        
        Args:
            model_id: Model identifier
            
        Returns:
            List of tenants with their configurations
        """
        try:
            query = select(TenantModelConfig, Tenant).join(
                Tenant, TenantModelConfig.tenant_id == Tenant.id
            ).filter(TenantModelConfig.model_id == model_id)
            
            result = await self.db.execute(query)
            records = result.all()
            
            # Format response
            tenants = []
            for tenant_config, tenant in records:
                tenant_dict = tenant.to_dict()
                tenant_dict["model_config"] = tenant_config.to_dict()
                tenants.append(tenant_dict)
            
            return tenants
            
        except Exception as e:
            logger.error(f"Failed to get model tenants: {e}")
            raise
    
    async def get_bulk_model_tenant_stats(self, model_ids: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Get tenant statistics for multiple models in a single query
        
        Args:
            model_ids: List of model identifiers
            
        Returns:
            Dict mapping model_id to stats dict with tenant_count and enabled_tenant_count
        """
        try:
            # Single query to get all tenant configs for all models
            query = select(TenantModelConfig.model_id, TenantModelConfig.is_enabled).filter(
                TenantModelConfig.model_id.in_(model_ids)
            )
            
            result = await self.db.execute(query)
            records = result.all()
            
            # Group by model_id and count
            stats = {}
            for model_id in model_ids:
                stats[model_id] = {"tenant_count": 0, "enabled_tenant_count": 0}
            
            for record in records:
                model_id = record.model_id
                if model_id in stats:
                    stats[model_id]["tenant_count"] += 1
                    if record.is_enabled:
                        stats[model_id]["enabled_tenant_count"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get bulk model tenant stats: {e}")
            # Return empty stats for all models to avoid breaking the API
            return {model_id: {"tenant_count": 0, "enabled_tenant_count": 0} for model_id in model_ids}
    
    async def check_tenant_model_access(
        self,
        tenant_id: int,
        model_id: str,
        user_capabilities: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a tenant/user can access a specific model

        Args:
            tenant_id: Tenant identifier
            model_id: Model identifier (string)
            user_capabilities: User capabilities for additional checks
            user_id: User identifier for constraint checks

        Returns:
            Dictionary with access information
        """
        try:
            # Get tenant model configuration (join via UUID, filter by model_id string)
            query = select(TenantModelConfig, ModelConfig).join(
                ModelConfig, TenantModelConfig.model_config_id == ModelConfig.id
            ).filter(
                TenantModelConfig.tenant_id == tenant_id,
                ModelConfig.model_id == model_id  # Filter on the string model_id
            )
            
            result = await self.db.execute(query)
            record = result.first()
            
            if not record:
                return {
                    "has_access": False,
                    "reason": "Model not assigned to tenant"
                }
            
            tenant_config, model_config = record
            
            # Check if tenant configuration allows access
            if not tenant_config.is_enabled:
                return {
                    "has_access": False,
                    "reason": "Model disabled for tenant"
                }
            
            # Check if model is active
            if not model_config.is_active:
                return {
                    "has_access": False,
                    "reason": "Model is inactive"
                }
            
            # Check user-specific constraints if provided
            if user_capabilities and user_id:
                if not tenant_config.can_user_access(user_capabilities, user_id):
                    return {
                        "has_access": False,
                        "reason": "User does not meet access requirements"
                    }
            
            return {
                "has_access": True,
                "tenant_config": tenant_config.to_dict(),
                "model_config": model_config.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Failed to check tenant model access: {e}")
            raise
    
    async def get_tenant_model_stats(self, tenant_id: int) -> Dict[str, Any]:
        """
        Get statistics about models for a tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Statistics dictionary
        """
        try:
            # Count total assigned models
            total_query = select(func.count()).select_from(TenantModelConfig).filter(
                TenantModelConfig.tenant_id == tenant_id
            )
            total_result = await self.db.execute(total_query)
            total_models = total_result.scalar()
            
            # Count enabled models
            enabled_query = select(func.count()).select_from(TenantModelConfig).filter(
                TenantModelConfig.tenant_id == tenant_id,
                TenantModelConfig.is_enabled == True
            )
            enabled_result = await self.db.execute(enabled_query)
            enabled_models = enabled_result.scalar()
            
            # Count by provider (join on UUID)
            provider_query = select(
                ModelConfig.provider,
                func.count()
            ).select_from(TenantModelConfig).join(
                ModelConfig, TenantModelConfig.model_config_id == ModelConfig.id
            ).filter(
                TenantModelConfig.tenant_id == tenant_id,
                TenantModelConfig.is_enabled == True
            ).group_by(ModelConfig.provider)
            
            provider_result = await self.db.execute(provider_query)
            provider_stats = dict(provider_result.all())
            
            return {
                "total_models": total_models,
                "enabled_models": enabled_models,
                "disabled_models": total_models - enabled_models,
                "providers": provider_stats,
                "availability_percentage": (enabled_models / total_models * 100) if total_models > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant model stats: {e}")
            raise
    
    async def get_all_tenant_model_configs(self) -> List[Dict[str, Any]]:
        """
        Get all tenant model configurations with joined tenant and model data

        Returns:
            List of tenant model configurations with full details
        """
        try:
            query = select(
                TenantModelConfig,
                Tenant.name.label("tenant_name"),
                Tenant.domain.label("tenant_domain"),
                ModelConfig.name.label("model_name"),
                ModelConfig.provider,
                ModelConfig.model_type
            ).join(
                Tenant, TenantModelConfig.tenant_id == Tenant.id
            ).join(
                ModelConfig, TenantModelConfig.model_config_id == ModelConfig.id
            ).order_by(Tenant.name, ModelConfig.name)

            result = await self.db.execute(query)
            rows = result.all()

            configs = []
            for row in rows:
                config_dict = row.TenantModelConfig.to_dict()
                config_dict.update({
                    "tenant_name": row.tenant_name,
                    "tenant_domain": row.tenant_domain,
                    "model_name": row.model_name or row.TenantModelConfig.model_id,
                    "provider": row.provider,
                    "model_type": row.model_type
                })
                configs.append(config_dict)

            return configs

        except Exception as e:
            logger.error(f"Failed to get all tenant model configs: {e}")
            raise

    # ============================================================================
    # AUTO-ASSIGNMENT METHODS
    # ============================================================================

    async def auto_assign_model_to_all_tenants(self, model_id: str) -> int:
        """
        Automatically assign a model to all existing tenants with default rate limits.
        Called when a new model is created.

        Args:
            model_id: The model ID to assign

        Returns:
            Number of tenants the model was assigned to
        """
        try:
            # Get the model to get its UUID
            model_query = select(ModelConfig).filter(ModelConfig.model_id == model_id)
            model_result = await self.db.execute(model_query)
            model = model_result.scalars().first()
            if not model:
                raise ValueError(f"Model {model_id} not found")

            # Get all active tenants
            tenant_query = select(Tenant).filter(Tenant.status.in_(["active", "pending"]))
            tenant_result = await self.db.execute(tenant_query)
            tenants = tenant_result.scalars().all()

            assigned_count = 0
            for tenant in tenants:
                try:
                    # Check if assignment already exists (using UUID)
                    existing_query = select(TenantModelConfig).filter(
                        TenantModelConfig.tenant_id == tenant.id,
                        TenantModelConfig.model_config_id == model.id
                    )
                    existing_result = await self.db.execute(existing_query)
                    if existing_result.scalars().first():
                        continue  # Skip if already assigned

                    # Create default configuration with UUID reference
                    tenant_model_config = TenantModelConfig.create_default_config(
                        tenant_id=tenant.id,
                        model_id=model_id,
                        model_config_id=model.id
                    )
                    self.db.add(tenant_model_config)
                    assigned_count += 1

                except Exception as e:
                    logger.warning(f"Failed to auto-assign model {model_id} to tenant {tenant.id}: {e}")
                    continue

            if assigned_count > 0:
                await self.db.commit()
                logger.info(f"Auto-assigned model {model_id} to {assigned_count} tenants")

            return assigned_count

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to auto-assign model to all tenants: {e}")
            raise

    async def auto_assign_all_models_to_tenant(self, tenant_id: int) -> int:
        """
        Automatically assign all active models to a tenant with default rate limits.
        Called when a new tenant is created.

        Args:
            tenant_id: The tenant ID to assign models to

        Returns:
            Number of models assigned to the tenant
        """
        try:
            # Get all active models
            model_query = select(ModelConfig).filter(ModelConfig.is_active == True)
            model_result = await self.db.execute(model_query)
            models = model_result.scalars().all()

            assigned_count = 0
            for model in models:
                try:
                    # Check if assignment already exists (using UUID)
                    existing_query = select(TenantModelConfig).filter(
                        TenantModelConfig.tenant_id == tenant_id,
                        TenantModelConfig.model_config_id == model.id
                    )
                    existing_result = await self.db.execute(existing_query)
                    if existing_result.scalars().first():
                        continue  # Skip if already assigned

                    # Create default configuration with UUID reference
                    tenant_model_config = TenantModelConfig.create_default_config(
                        tenant_id=tenant_id,
                        model_id=model.model_id,
                        model_config_id=model.id
                    )
                    self.db.add(tenant_model_config)
                    assigned_count += 1

                except Exception as e:
                    logger.warning(f"Failed to auto-assign model {model.model_id} to tenant {tenant_id}: {e}")
                    continue

            if assigned_count > 0:
                await self.db.commit()
                logger.info(f"Auto-assigned {assigned_count} models to tenant {tenant_id}")

            return assigned_count

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to auto-assign all models to tenant: {e}")
            raise

    async def get_model_tenant_rate_limits(self, model_id: str) -> List[Dict[str, Any]]:
        """
        Get all tenant rate limit configurations for a specific model.

        Args:
            model_id: The model ID to get rate limits for

        Returns:
            List of tenant configurations with rate limits
        """
        try:
            query = select(
                TenantModelConfig,
                Tenant.id.label("tenant_id"),
                Tenant.name.label("tenant_name"),
                Tenant.domain.label("tenant_domain")
            ).join(
                Tenant, TenantModelConfig.tenant_id == Tenant.id
            ).filter(
                TenantModelConfig.model_id == model_id
            ).order_by(Tenant.name)

            result = await self.db.execute(query)
            rows = result.all()

            configs = []
            for row in rows:
                config = row.TenantModelConfig.to_dict()
                config.update({
                    "tenant_name": row.tenant_name,
                    "tenant_domain": row.tenant_domain
                })
                configs.append(config)

            return configs

        except Exception as e:
            logger.error(f"Failed to get model tenant rate limits: {e}")
            raise


def get_model_management_service(db: AsyncSession) -> ModelManagementService:
    """Get model management service instance"""
    return ModelManagementService(db)