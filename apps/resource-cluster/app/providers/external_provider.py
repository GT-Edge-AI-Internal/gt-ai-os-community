"""
GT 2.0 External Provider

Handles external AI services like BGE-M3 embedding model on GT Edge network.
Provides unified interface for external model access with health monitoring.
"""

import asyncio
import httpx
import json
import time
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)
settings = get_settings()


class ExternalProvider:
    """Provider for external AI models and services"""
    
    def __init__(self):
        self.name = "external"
        self.models = {}
        self.health_status = {}
        self.circuit_breaker = {}
        self.retry_attempts = 3
        self.timeout = 30.0
        
    async def initialize(self):
        """Initialize external provider with default models"""
        await self.register_bge_m3_model()
        logger.info("External provider initialized")
    
    async def register_bge_m3_model(self):
        """Register BGE-M3 embedding model on GT Edge network"""
        model_config = {
            "model_id": "bge-m3-embedding",
            "name": "BGE-M3 Multilingual Embedding",
            "version": "1.0",
            "provider": "external",
            "model_type": "embedding",
            "endpoint": "http://10.0.0.100:8080",  # GT Edge network default
            "dimensions": 1024,
            "max_input_tokens": 8192,
            "cost_per_1k_tokens": 0.0,  # Internal model, no cost
            "description": "BGE-M3 multilingual embedding model on GT Edge network",
            "capabilities": {
                "languages": ["en", "zh", "fr", "de", "es", "ru", "ja", "ko"],
                "max_sequence_length": 8192,
                "output_dimensions": 1024,
                "supports_retrieval": True,
                "supports_clustering": True
            }
        }
        
        self.models["bge-m3-embedding"] = model_config
        await self._initialize_circuit_breaker("bge-m3-embedding")
        logger.info("Registered BGE-M3 embedding model")
    
    async def generate_embeddings(
        self,
        model_id: str,
        texts: Union[str, List[str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate embeddings using external model"""
        
        if model_id not in self.models:
            raise ProviderError(f"Model {model_id} not found in external provider")
        
        model_config = self.models[model_id]
        
        if not await self._check_circuit_breaker(model_id):
            raise ProviderError(f"Circuit breaker open for model {model_id}")
        
        # Ensure texts is a list
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            start_time = time.time()
            
            # Prepare request payload
            payload = {
                "model": model_id,
                "input": texts,
                "encoding_format": "float",
                **kwargs
            }
            
            # Make request to external model
            endpoint = model_config["endpoint"]
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{endpoint}/v1/embeddings",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "GT-2.0-Resource-Cluster/1.0"
                    }
                )
                
                response.raise_for_status()
                result = response.json()
            
            # Calculate metrics
            latency_ms = (time.time() - start_time) * 1000
            total_tokens = sum(len(text.split()) for text in texts)
            
            # Update circuit breaker with success
            await self._record_success(model_id, latency_ms)
            
            # Format response
            embeddings = []
            for i, embedding_data in enumerate(result.get("data", [])):
                embeddings.append({
                    "object": "embedding",
                    "index": i,
                    "embedding": embedding_data.get("embedding", [])
                })
            
            return {
                "object": "list",
                "data": embeddings,
                "model": model_id,
                "usage": {
                    "prompt_tokens": total_tokens,
                    "total_tokens": total_tokens
                },
                "provider": "external",
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except httpx.RequestError as e:
            await self._record_failure(model_id, str(e))
            raise ProviderError(f"External model request failed: {e}")
        except httpx.HTTPStatusError as e:
            await self._record_failure(model_id, f"HTTP {e.response.status_code}")
            raise ProviderError(f"External model returned error: {e.response.status_code}")
        except Exception as e:
            await self._record_failure(model_id, str(e))
            raise ProviderError(f"External model error: {e}")
    
    async def health_check(self, model_id: str = None) -> Dict[str, Any]:
        """Check health of external models"""
        if model_id:
            return await self._check_model_health(model_id)
        
        # Check all models
        health_results = {}
        for mid in self.models.keys():
            health_results[mid] = await self._check_model_health(mid)
        
        # Calculate overall health
        total_models = len(health_results)
        healthy_models = sum(1 for h in health_results.values() if h.get("healthy", False))
        
        return {
            "provider": "external",
            "overall_healthy": healthy_models == total_models,
            "total_models": total_models,
            "healthy_models": healthy_models,
            "health_percentage": (healthy_models / total_models * 100) if total_models > 0 else 0,
            "models": health_results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _check_model_health(self, model_id: str) -> Dict[str, Any]:
        """Check health of specific external model"""
        if model_id not in self.models:
            return {
                "healthy": False,
                "error": "Model not found",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        model_config = self.models[model_id]
        
        try:
            start_time = time.time()
            
            # Health check endpoint
            endpoint = model_config["endpoint"]
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{endpoint}/health")
                
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    return {
                        "healthy": True,
                        "latency_ms": latency_ms,
                        "endpoint": endpoint,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        "healthy": False,
                        "error": f"HTTP {response.status_code}",
                        "latency_ms": latency_ms,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _initialize_circuit_breaker(self, model_id: str):
        """Initialize circuit breaker for model"""
        self.circuit_breaker[model_id] = {
            "state": "closed",  # closed, open, half_open
            "failure_count": 0,
            "success_count": 0,
            "last_failure_time": 0,
            "failure_threshold": 5,
            "success_threshold": 3,
            "timeout": 60  # seconds to wait before trying half_open
        }
    
    async def _check_circuit_breaker(self, model_id: str) -> bool:
        """Check if circuit breaker allows requests"""
        cb = self.circuit_breaker.get(model_id, {})
        
        if cb.get("state") == "closed":
            return True
        elif cb.get("state") == "open":
            # Check if timeout has passed
            if time.time() - cb.get("last_failure_time", 0) > cb.get("timeout", 60):
                cb["state"] = "half_open"
                cb["success_count"] = 0
                return True
            return False
        elif cb.get("state") == "half_open":
            return True
        
        return False
    
    async def _record_success(self, model_id: str, latency_ms: float):
        """Record successful request for circuit breaker"""
        cb = self.circuit_breaker.get(model_id, {})
        
        if cb.get("state") == "half_open":
            cb["success_count"] += 1
            if cb["success_count"] >= cb.get("success_threshold", 3):
                cb["state"] = "closed"
                cb["failure_count"] = 0
        
        # Update health status
        self.health_status[model_id] = {
            "healthy": True,
            "last_success": time.time(),
            "latency_ms": latency_ms
        }
    
    async def _record_failure(self, model_id: str, error: str):
        """Record failed request for circuit breaker"""
        cb = self.circuit_breaker.get(model_id, {})
        
        cb["failure_count"] += 1
        cb["last_failure_time"] = time.time()
        
        if cb["failure_count"] >= cb.get("failure_threshold", 5):
            cb["state"] = "open"
        
        # Update health status
        self.health_status[model_id] = {
            "healthy": False,
            "last_failure": time.time(),
            "error": error
        }
        
        logger.warning(f"External model {model_id} failure: {error}")
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available external models"""
        return list(self.models.values())
    
    def update_model_endpoint(self, model_id: str, endpoint: str):
        """Update model endpoint (called from config sync)"""
        if model_id in self.models:
            old_endpoint = self.models[model_id]["endpoint"]
            self.models[model_id]["endpoint"] = endpoint
            logger.info(f"Updated {model_id} endpoint: {old_endpoint} -> {endpoint}")
        else:
            logger.warning(f"Attempted to update unknown model: {model_id}")


# Global external provider instance
_external_provider = None

async def get_external_provider() -> ExternalProvider:
    """Get external provider instance"""
    global _external_provider
    if _external_provider is None:
        _external_provider = ExternalProvider()
        await _external_provider.initialize()
    return _external_provider