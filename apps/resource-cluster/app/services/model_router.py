"""
GT 2.0 Model Router

Routes inference requests to appropriate providers based on model registry.
Integrates with provider factory for dynamic provider selection.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncIterator
from datetime import datetime

from app.services.model_service import get_model_service
from app.providers import get_provider_factory
from app.core.backends import get_backend
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class ModelRouter:
    """Routes model requests to appropriate providers"""
    
    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id
        # Use default model service for shared model registry (config sync writes to default)
        # Note: Tenant isolation is handled via capability tokens, not separate databases
        self.model_service = get_model_service(None)
        self.provider_factory = None
        self.backend_cache = {}
        
    async def initialize(self):
        """Initialize model router"""
        try:
            self.provider_factory = await get_provider_factory()
            logger.info(f"Model router initialized for tenant: {self.tenant_id or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize model router: {e}")
            raise
    
    async def route_inference(
        self,
        model_id: str,
        prompt: Optional[str] = None,
        messages: Optional[list] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        stream: bool = False,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Route inference request to appropriate provider"""
        
        # Get model configuration from registry
        model_config = await self.model_service.get_model(model_id)
        if not model_config:
            raise ProviderError(f"Model {model_id} not found in registry")
        
        provider = model_config["provider"]
        
        # Track model usage
        start_time = datetime.utcnow()
        
        try:
            # Route to configured endpoint (generic routing for any provider)
            endpoint_url = model_config.get("endpoint")
            if not endpoint_url:
                raise ProviderError(f"No endpoint configured for model {model_id}")

            result = await self._route_to_generic_endpoint(
                endpoint_url, model_id, prompt, messages, temperature, max_tokens, stream, user_id, tenant_id, tools, tool_choice, **kwargs
            )
            
            # Calculate latency
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Track successful usage
            await self.model_service.track_model_usage(
                model_id, success=True, latency_ms=latency_ms
            )
            
            return result
            
        except Exception as e:
            # Track failed usage
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.model_service.track_model_usage(
                model_id, success=False, latency_ms=latency_ms
            )
            logger.error(f"Model routing failed for {model_id}: {e}")
            raise
    
    async def _route_to_groq(
        self,
        model_id: str,
        prompt: Optional[str],
        messages: Optional[list],
        temperature: float,
        max_tokens: int,
        stream: bool,
        user_id: Optional[str],
        tenant_id: Optional[str],
        tools: Optional[list],
        tool_choice: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Route request to Groq backend"""
        try:
            backend = get_backend("groq_proxy")
            if not backend:
                raise ProviderError("Groq backend not available")
            
            if messages:
                return await backend.execute_inference_with_messages(
                    messages=messages,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    tools=tools,
                    tool_choice=tool_choice
                )
            else:
                return await backend.execute_inference(
                    prompt=prompt,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    user_id=user_id,
                    tenant_id=tenant_id
                )
                
        except Exception as e:
            logger.error(f"Groq routing failed: {e}")
            raise ProviderError(f"Groq inference failed: {e}")
    
    async def _route_to_external(
        self,
        model_id: str,
        prompt: Optional[str],
        messages: Optional[list],
        temperature: float,
        max_tokens: int,
        stream: bool,
        user_id: Optional[str],
        tenant_id: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Route request to external provider"""
        try:
            if not self.provider_factory:
                await self.initialize()
            
            external_provider = self.provider_factory.get_provider("external")
            if not external_provider:
                raise ProviderError("External provider not available")
            
            # For embedding models
            if model_id == "bge-m3-embedding":
                # Convert prompt/messages to text list
                texts = []
                if messages:
                    texts = [msg.get("content", "") for msg in messages if msg.get("content")]
                elif prompt:
                    texts = [prompt]
                
                return await external_provider.generate_embeddings(
                    model_id=model_id,
                    texts=texts
                )
            else:
                raise ProviderError(f"External model {model_id} not supported for inference")
                
        except Exception as e:
            logger.error(f"External routing failed: {e}")
            raise ProviderError(f"External inference failed: {e}")
    
    async def _route_to_openai(
        self,
        model_id: str,
        prompt: Optional[str],
        messages: Optional[list],
        temperature: float,
        max_tokens: int,
        stream: bool,
        user_id: Optional[str],
        tenant_id: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Route request to OpenAI provider"""
        raise ProviderError("OpenAI provider not implemented - use Groq models instead")

    async def _route_to_generic_endpoint(
        self,
        endpoint_url: str,
        model_id: str,
        prompt: Optional[str],
        messages: Optional[list],
        temperature: float,
        max_tokens: int,
        stream: bool,
        user_id: Optional[str],
        tenant_id: Optional[str],
        tools: Optional[list],
        tool_choice: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Route request to any configured endpoint using OpenAI-compatible API"""
        import httpx
        import time

        try:
            # Build OpenAI-compatible request
            request_data = {
                "model": model_id,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }

            # Use messages if provided, otherwise convert prompt to messages
            if messages:
                request_data["messages"] = messages
            elif prompt:
                request_data["messages"] = [{"role": "user", "content": prompt}]
            else:
                raise ProviderError("Either messages or prompt must be provided")

            # Add tools if provided
            if tools:
                request_data["tools"] = tools
            if tool_choice:
                request_data["tool_choice"] = tool_choice

            # Add any additional parameters
            request_data.update(kwargs)

            logger.info(f"Routing request to endpoint: {endpoint_url}")
            logger.debug(f"Request data: {request_data}")

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    endpoint_url,
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Endpoint {endpoint_url} returned {response.status_code}: {error_text}")
                    raise ProviderError(f"Endpoint error: {response.status_code} - {error_text}")

                result = response.json()
                logger.debug(f"Endpoint response: {result}")
                return result

        except httpx.RequestError as e:
            logger.error(f"Request to {endpoint_url} failed: {e}")
            raise ProviderError(f"Connection to endpoint failed: {str(e)}")
        except Exception as e:
            logger.error(f"Generic endpoint routing failed: {e}")
            raise ProviderError(f"Inference failed: {str(e)}")

    async def list_available_models(self) -> list:
        """List all available models from registry"""
        # Get all models (deployment status filtering available if needed)
        models = await self.model_service.list_models()
        return models
    
    async def get_model_health(self, model_id: str) -> Dict[str, Any]:
        """Check health of specific model"""
        return await self.model_service.check_model_health(model_id)


# Global model router instances per tenant
_model_routers = {}


async def get_model_router(tenant_id: Optional[str] = None) -> ModelRouter:
    """Get model router instance for tenant"""
    global _model_routers
    
    cache_key = tenant_id or "default"
    
    if cache_key not in _model_routers:
        router = ModelRouter(tenant_id)
        await router.initialize()
        _model_routers[cache_key] = router
    
    return _model_routers[cache_key]