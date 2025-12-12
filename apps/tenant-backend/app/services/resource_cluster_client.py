"""
Resource Cluster Client for GT 2.0 Tenant Backend

Handles communication with the Resource Cluster for AI/ML operations.
Manages capability token generation and LLM inference requests.
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator, List
from datetime import timedelta
import asyncio
from jose import jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_model_rate_limit(
    tenant_id: str,
    model_id: str,
    control_panel_url: str
) -> int:
    """
    Fetch rate limit for a model from Control Panel API.

    Returns requests_per_minute (converted from max_requests_per_hour in database).
    Fails fast if Control Panel is unreachable (GT 2.0 principle: no fallbacks).

    Args:
        tenant_id: Tenant identifier
        model_id: Model identifier
        control_panel_url: Control Panel API base URL

    Returns:
        Requests per minute limit

    Raises:
        RuntimeError: If Control Panel API is unreachable
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{control_panel_url}/api/v1/tenant-models/tenants/{tenant_id}/models/{model_id}"
            logger.debug(f"Fetching rate limit from Control Panel: {url}")

            response = await client.get(url)

            if response.status_code == 404:
                logger.warning(f"Model {model_id} not configured for tenant {tenant_id}, using default")
                return 1000  # Default: 1000 requests/minute

            response.raise_for_status()
            config = response.json()

            # API now returns requests_per_minute directly (translated from DB per-hour)
            rate_limits = config.get("rate_limits", {})
            requests_per_minute = rate_limits.get("requests_per_minute", 1000)

            logger.info(f"Model {model_id} rate limit: {requests_per_minute} requests/minute")
            return requests_per_minute

    except httpx.HTTPStatusError as e:
        logger.error(f"Control Panel API error: {e.response.status_code}")
        raise RuntimeError(f"Failed to fetch rate limit: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Control Panel API unreachable: {e}")
        raise RuntimeError(f"Control Panel unreachable at {control_panel_url}")
    except Exception as e:
        logger.error(f"Unexpected error fetching rate limit: {e}")
        raise RuntimeError(f"Failed to fetch rate limit: {e}")


class ResourceClusterClient:
    """Client for communicating with GT 2.0 Resource Cluster"""
    
    def __init__(self):
        self.settings = get_settings()
        self.resource_cluster_url = self.settings.resource_cluster_url
        self.secret_key = self.settings.secret_key
        self.algorithm = "HS256"
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def generate_capability_token(
        self,
        user_id: str,
        tenant_id: str,
        assistant_config: Dict[str, Any],
        expires_minutes: int = 30
    ) -> str:
        """
        Generate capability token for resource access.

        Fetches real rate limits from Control Panel (single source of truth).
        Fails fast if Control Panel is unreachable.
        """

        # Extract capabilities from agent configuration
        capabilities = []

        # Add LLM capability with real rate limit from Control Panel
        model = assistant_config.get("resource_preferences", {}).get("primary_llm", "llama-3.1-70b-versatile")

        # Fetch real rate limit from Control Panel API
        requests_per_minute = await fetch_model_rate_limit(
            tenant_id=tenant_id,
            model_id=model,
            control_panel_url=self.settings.control_panel_url
        )

        capabilities.append({
            "resource": f"llm:groq",
            "actions": ["inference", "streaming"],
            "constraints": {  # Changed from "limits" to match LLM gateway expectations
                "max_tokens_per_request": assistant_config.get("resource_preferences", {}).get("max_tokens", 4000),
                "max_requests_per_minute": requests_per_minute  # Real limit from database (converted from per-hour)
            }
        })
        
        # Add RAG capabilities if configured
        if assistant_config.get("capabilities", {}).get("rag_enabled"):
            capabilities.append({
                "resource": "rag:semantic_search",
                "actions": ["search", "retrieve"],
                "limits": {
                    "max_results": 10
                }
            })
        
        # Add embedding capability if RAG is enabled
        if assistant_config.get("capabilities", {}).get("embeddings_enabled"):
            capabilities.append({
                "resource": "embedding:text-embedding-3-small",
                "actions": ["generate"],
                "limits": {
                    "max_texts_per_request": 100
                }
            })
        
        # Create token payload
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "capabilities": capabilities,
            "exp": asyncio.get_event_loop().time() + (expires_minutes * 60),
            "iat": asyncio.get_event_loop().time()
        }
        
        # Sign token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        return token
    
    async def execute_inference(
        self,
        prompt: str,
        assistant_config: Dict[str, Any],
        user_id: str,
        tenant_id: str,
        stream: bool = False,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Execute LLM inference via Resource Cluster"""

        # Generate capability token (now async - fetches real rate limits)
        token = await self.generate_capability_token(user_id, tenant_id, assistant_config)
        
        # Prepare request
        model = assistant_config.get("resource_preferences", {}).get("primary_llm", "llama-3.1-70b-versatile")
        temperature = assistant_config.get("resource_preferences", {}).get("temperature", 0.7)
        max_tokens = assistant_config.get("resource_preferences", {}).get("max_tokens", 4000)
        
        # Build messages array with system prompt
        messages = []
        
        # Add system prompt from agent
        system_prompt = assistant_config.get("prompt", "You are a helpful AI agent.")
        messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation context if provided
        if conversation_context:
            messages.extend(conversation_context)
        
        # Add current user message
        messages.append({"role": "user", "content": prompt})
        
        # Prepare request payload
        request_data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "user_id": user_id,
            "tenant_id": tenant_id
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            if stream:
                return await self._stream_inference(request_data, headers)
            else:
                response = await self.client.post(
                    f"{self.resource_cluster_url}/api/v1/inference/",
                    json=request_data,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during inference: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during inference: {e}")
            raise
    
    async def _stream_inference(
        self,
        request_data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> AsyncIterator[str]:
        """Stream inference responses"""
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.resource_cluster_url}/api/v1/inference/stream",
                json=request_data,
                headers=headers,
                timeout=60.0
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if "content" in chunk:
                                yield chunk["content"]
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse streaming chunk: {data}")
                            continue
    
    async def generate_embeddings(
        self,
        texts: List[str],
        user_id: str,
        tenant_id: str,
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """Generate embeddings for texts"""
        
        # Generate capability token with embedding permission
        assistant_config = {"capabilities": {"embeddings_enabled": True}}
        token = self.generate_capability_token(user_id, tenant_id, assistant_config)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        request_data = {
            "texts": texts,
            "model": model
        }
        
        try:
            response = await self.client.post(
                f"{self.resource_cluster_url}/api/v1/embeddings/",
                json=request_data,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embeddings", [])
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during embedding generation: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    async def search_rag(
        self,
        query: str,
        collection: str,
        user_id: str,
        tenant_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search RAG collection for relevant documents"""
        
        # Generate capability token with RAG permission
        assistant_config = {"capabilities": {"rag_enabled": True}}
        token = self.generate_capability_token(user_id, tenant_id, assistant_config)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        request_data = {
            "query": query,
            "collection": collection,
            "top_k": top_k
        }
        
        try:
            response = await self.client.post(
                f"{self.resource_cluster_url}/api/v1/rag/search",
                json=request_data,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            return result.get("results", [])
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during RAG search: {e}")
            # Return empty results on error for now
            return []
        except Exception as e:
            logger.error(f"Error searching RAG: {e}")
            return []
    
    async def get_agent_templates(
        self,
        user_id: str,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Get available agent templates from Resource Cluster"""
        
        # Generate basic capability token
        token = self.generate_capability_token(user_id, tenant_id, {})
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            response = await self.client.get(
                f"{self.resource_cluster_url}/api/v1/templates/",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching templates: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching templates: {e}")
            return []
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()