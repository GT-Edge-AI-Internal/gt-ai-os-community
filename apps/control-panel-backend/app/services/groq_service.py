"""
Groq LLM integration service with high availability and failover support
"""
import asyncio
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime, timedelta
import httpx
import json
import logging
from contextlib import asynccontextmanager

from app.models.ai_resource import AIResource
from app.models.usage import UsageRecord

logger = logging.getLogger(__name__)


class GroqAPIError(Exception):
    """Custom exception for Groq API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class GroqClient:
    """High-availability Groq API client with automatic failover"""
    
    def __init__(self, resource: AIResource, api_key: str):
        self.resource = resource
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        self._current_endpoint_index = 0
        self._endpoint_failures = {}
        self._rate_limit_reset = None
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _get_next_endpoint(self) -> Optional[str]:
        """Get next available endpoint with circuit breaker logic"""
        endpoints = self.resource.get_available_endpoints()
        if not endpoints:
            return None
            
        # Try current endpoint first if not in failure state
        current_endpoint = endpoints[self._current_endpoint_index % len(endpoints)]
        failure_info = self._endpoint_failures.get(current_endpoint)
        
        if not failure_info or failure_info["reset_time"] < datetime.utcnow():
            return current_endpoint
            
        # Find next healthy endpoint
        for i in range(len(endpoints)):
            endpoint = endpoints[(self._current_endpoint_index + i + 1) % len(endpoints)]
            failure_info = self._endpoint_failures.get(endpoint)
            
            if not failure_info or failure_info["reset_time"] < datetime.utcnow():
                self._current_endpoint_index = (self._current_endpoint_index + i + 1) % len(endpoints)
                return endpoint
                
        return None
    
    def _mark_endpoint_failed(self, endpoint: str, backoff_minutes: int = 5):
        """Mark endpoint as failed with exponential backoff"""
        current_failures = self._endpoint_failures.get(endpoint, {"count": 0})
        current_failures["count"] += 1
        
        # Exponential backoff: 5min, 10min, 20min, 40min, max 60min
        backoff_time = min(backoff_minutes * (2 ** (current_failures["count"] - 1)), 60)
        current_failures["reset_time"] = datetime.utcnow() + timedelta(minutes=backoff_time)
        
        self._endpoint_failures[endpoint] = current_failures
        logger.warning(f"Marked endpoint {endpoint} as failed for {backoff_time} minutes (failure #{current_failures['count']})")
    
    def _reset_endpoint_failures(self, endpoint: str):
        """Reset failure count for successful endpoint"""
        if endpoint in self._endpoint_failures:
            del self._endpoint_failures[endpoint]
    
    async def _make_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with automatic failover"""
        last_error = None
        
        for attempt in range(len(self.resource.get_available_endpoints()) + 1):
            endpoint = self._get_next_endpoint()
            if not endpoint:
                raise GroqAPIError("No healthy endpoints available")
                
            url = f"{endpoint.rstrip('/')}/{path.lstrip('/')}"
            
            try:
                logger.debug(f"Making {method} request to {url}")
                response = await self.client.request(method, url, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("retry-after", "60"))
                    self._rate_limit_reset = datetime.utcnow() + timedelta(seconds=retry_after)
                    raise GroqAPIError(f"Rate limited, retry after {retry_after} seconds", 429)
                
                # Handle server errors with failover
                if response.status_code >= 500:
                    self._mark_endpoint_failed(endpoint)
                    last_error = GroqAPIError(f"Server error: {response.status_code}", response.status_code, response.text)
                    continue
                
                # Handle client errors (don't retry)
                if response.status_code >= 400:
                    raise GroqAPIError(f"Client error: {response.status_code}", response.status_code, response.text)
                
                # Success - reset failures for this endpoint
                self._reset_endpoint_failures(endpoint)
                return response.json()
                
            except httpx.RequestError as e:
                logger.warning(f"Request failed for endpoint {endpoint}: {e}")
                self._mark_endpoint_failed(endpoint)
                last_error = GroqAPIError(f"Request failed: {str(e)}")
                continue
        
        # All endpoints failed
        raise last_error or GroqAPIError("All endpoints failed")
    
    async def health_check(self) -> bool:
        """Check if the Groq API is healthy"""
        try:
            await self._make_request("GET", "models")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models"""
        response = await self._make_request("GET", "models")
        return response.get("data", [])
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create chat completion"""
        config = self.resource.merge_config(kwargs)
        payload = {
            "model": model or self.resource.model_name,
            "messages": messages,
            "stream": stream,
            **config
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        start_time = time.time()
        response = await self._make_request("POST", "chat/completions", json=payload)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log performance metrics
        if latency_ms > self.resource.latency_sla_ms:
            logger.warning(f"Request exceeded SLA: {latency_ms}ms > {self.resource.latency_sla_ms}ms")
        
        return {
            **response,
            "_metadata": {
                "latency_ms": latency_ms,
                "model_used": payload["model"],
                "endpoint_used": self._get_next_endpoint()
            }
        }
    
    async def chat_completion_stream(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create streaming chat completion"""
        config = self.resource.merge_config(kwargs)
        payload = {
            "model": model or self.resource.model_name,
            "messages": messages,
            "stream": True,
            **config
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        endpoint = self._get_next_endpoint()
        if not endpoint:
            raise GroqAPIError("No healthy endpoints available")
            
        url = f"{endpoint.rstrip('/')}/chat/completions"
        
        async with self.client.stream("POST", url, json=payload) as response:
            if response.status_code >= 400:
                error_text = await response.aread()
                raise GroqAPIError(f"Stream error: {response.status_code}", response.status_code, error_text.decode())
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data.strip() == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue


class GroqService:
    """Service for managing Groq resources and API interactions"""
    
    def __init__(self):
        self._clients: Dict[int, GroqClient] = {}
    
    @asynccontextmanager
    async def get_client(self, resource: AIResource, api_key: str):
        """Get or create a Groq client for the resource"""
        if resource.id not in self._clients:
            self._clients[resource.id] = GroqClient(resource, api_key)
        
        try:
            yield self._clients[resource.id]
        finally:
            # Keep clients alive for reuse, cleanup handled separately
            pass
    
    async def health_check_resource(self, resource: AIResource, api_key: str) -> bool:
        """Perform health check on a Groq resource"""
        try:
            async with self.get_client(resource, api_key) as client:
                is_healthy = await client.health_check()
                resource.update_health_status("healthy" if is_healthy else "unhealthy")
                return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for resource {resource.id}: {e}")
            resource.update_health_status("unhealthy")
            return False
    
    async def chat_completion(
        self,
        resource: AIResource,
        api_key: str,
        messages: List[Dict[str, str]],
        user_email: str,
        tenant_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Create chat completion with usage tracking"""
        async with self.get_client(resource, api_key) as client:
            response = await client.chat_completion(messages, **kwargs)
            
            # Extract usage information
            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            
            # Calculate cost
            cost_cents = resource.calculate_cost(total_tokens)
            
            # Create usage record (would be saved to database)
            usage_record = {
                "tenant_id": tenant_id,
                "resource_id": resource.id,
                "user_email": user_email,
                "request_type": "chat_completion",
                "tokens_used": total_tokens,
                "cost_cents": cost_cents,
                "model_used": response.get("_metadata", {}).get("model_used", resource.model_name),
                "latency_ms": response.get("_metadata", {}).get("latency_ms", 0)
            }
            
            logger.info(f"Chat completion: {total_tokens} tokens, ${cost_cents/100:.4f} cost")
            
            return {
                **response,
                "_usage_record": usage_record
            }
    
    async def cleanup_clients(self):
        """Cleanup inactive clients"""
        for resource_id, client in list(self._clients.items()):
            try:
                await client.client.aclose()
            except Exception:
                pass
        self._clients.clear()


# Global service instance
groq_service = GroqService()