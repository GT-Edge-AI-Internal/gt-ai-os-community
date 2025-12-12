"""
LLM Gateway Service for GT 2.0 Resource Cluster

Provides unified access to LLM providers with:
- Groq Cloud integration for fast inference
- OpenAI API compatibility
- Rate limiting and quota management
- Capability-based authentication
- Model routing and load balancing
- Response streaming support

GT 2.0 Architecture Principles:
- Stateless: No persistent connections or state
- Zero downtime: Circuit breakers and failover
- Self-contained: No external configuration dependencies
- Capability-based: JWT token authorization
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import uuid
import httpx
from enum import Enum
from urllib.parse import urlparse

from app.core.config import get_settings


def is_provider_endpoint(endpoint_url: str, provider_domains: List[str]) -> bool:
    """
    Safely check if URL belongs to a specific provider.

    Uses proper URL parsing to prevent bypass via URLs like
    'evil.groq.com.attacker.com' or 'groq.com.evil.com'.
    """
    try:
        parsed = urlparse(endpoint_url)
        hostname = (parsed.hostname or "").lower()
        for domain in provider_domains:
            domain = domain.lower()
            # Match exact domain or subdomain (e.g., api.groq.com matches groq.com)
            if hostname == domain or hostname.endswith(f".{domain}"):
                return True
        return False
    except Exception:
        return False
from app.core.capability_auth import verify_capability_token, CapabilityError
from app.services.admin_model_config_service import get_admin_model_service, AdminModelConfig

logger = logging.getLogger(__name__)
settings = get_settings()


class ModelProvider(str, Enum):
    """Supported LLM providers"""
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    NVIDIA = "nvidia"
    LOCAL = "local"


class ModelCapability(str, Enum):
    """Model capabilities for routing"""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    CODE = "code"


@dataclass
class ModelConfig:
    """Model configuration and capabilities"""
    model_id: str
    provider: ModelProvider
    capabilities: List[ModelCapability]
    max_tokens: int
    context_window: int
    cost_per_token: float
    rate_limit_rpm: int
    supports_streaming: bool
    supports_functions: bool
    is_available: bool = True


@dataclass
class LLMRequest:
    """Standardized LLM request format"""
    model: str
    messages: List[Dict[str, str]]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    stream: bool = False
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    user: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        result = asdict(self)
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class LLMResponse:
    """Standardized LLM response format"""
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    provider: str
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return asdict(self)


class LLMGateway:
    """
    LLM Gateway with unified API and multi-provider support.
    
    Provides OpenAI-compatible API while routing to optimal providers
    based on model capabilities, availability, and cost.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.http_client = httpx.AsyncClient(timeout=120.0)
        self.admin_service = get_admin_model_service()
        
        # Rate limiting tracking
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        
        # Provider health tracking
        self.provider_health: Dict[ModelProvider, bool] = {
            provider: True for provider in ModelProvider
        }
        
        # Request statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "provider_usage": {provider.value: 0 for provider in ModelProvider},
            "model_usage": {},
            "average_latency": 0.0
        }
        
        logger.info("LLM Gateway initialized with admin-configured models")
    
    async def get_available_models(self, tenant_id: Optional[str] = None) -> List[AdminModelConfig]:
        """Get available models, optionally filtered by tenant"""
        if tenant_id:
            return await self.admin_service.get_tenant_models(tenant_id)
        else:
            return await self.admin_service.get_all_models(active_only=True)
    
    async def get_model_config(self, model_id: str, tenant_id: Optional[str] = None) -> Optional[AdminModelConfig]:
        """Get configuration for a specific model"""
        config = await self.admin_service.get_model_config(model_id)
        
        # Check tenant access if tenant_id provided
        if config and tenant_id:
            has_access = await self.admin_service.check_tenant_access(tenant_id, model_id)
            if not has_access:
                return None
        
        return config
    
    async def get_groq_api_key(self) -> Optional[str]:
        """Get Groq API key from admin service"""
        return await self.admin_service.get_groq_api_key()
    
    def _initialize_model_configs(self) -> Dict[str, ModelConfig]:
        """Initialize supported model configurations"""
        models = {}
        
        # Groq models (fast inference)
        groq_models = [
            ModelConfig(
                model_id="llama3-8b-8192",
                provider=ModelProvider.GROQ,
                capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
                max_tokens=8192,
                context_window=8192,
                cost_per_token=0.00001,
                rate_limit_rpm=30,
                supports_streaming=True,
                supports_functions=False
            ),
            ModelConfig(
                model_id="llama3-70b-8192",
                provider=ModelProvider.GROQ,
                capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
                max_tokens=8192,
                context_window=8192,
                cost_per_token=0.00008,
                rate_limit_rpm=15,
                supports_streaming=True,
                supports_functions=False
            ),
            ModelConfig(
                model_id="mixtral-8x7b-32768",
                provider=ModelProvider.GROQ,
                capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
                max_tokens=32768,
                context_window=32768,
                cost_per_token=0.00005,
                rate_limit_rpm=20,
                supports_streaming=True,
                supports_functions=False
            ),
            ModelConfig(
                model_id="gemma-7b-it",
                provider=ModelProvider.GROQ,
                capabilities=[ModelCapability.CHAT],
                max_tokens=8192,
                context_window=8192,
                cost_per_token=0.00001,
                rate_limit_rpm=30,
                supports_streaming=True,
                supports_functions=False
            )
        ]
        
        # OpenAI models (function calling, embeddings)
        openai_models = [
            ModelConfig(
                model_id="gpt-4-turbo-preview",
                provider=ModelProvider.OPENAI,
                capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION],
                max_tokens=4096,
                context_window=128000,
                cost_per_token=0.00003,
                rate_limit_rpm=10,
                supports_streaming=True,
                supports_functions=True
            ),
            ModelConfig(
                model_id="gpt-3.5-turbo",
                provider=ModelProvider.OPENAI,
                capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING],
                max_tokens=4096,
                context_window=16385,
                cost_per_token=0.000002,
                rate_limit_rpm=60,
                supports_streaming=True,
                supports_functions=True
            ),
            ModelConfig(
                model_id="text-embedding-3-small",
                provider=ModelProvider.OPENAI,
                capabilities=[ModelCapability.EMBEDDING],
                max_tokens=8191,
                context_window=8191,
                cost_per_token=0.00000002,
                rate_limit_rpm=3000,
                supports_streaming=False,
                supports_functions=False
            )
        ]
        
        # Add all models to registry
        for model_list in [groq_models, openai_models]:
            for model in model_list:
                models[model.model_id] = model
        
        return models
    
    async def chat_completion(
        self,
        request: LLMRequest,
        capability_token: str,
        user_id: str,
        tenant_id: str
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """
        Process chat completion request with capability validation.
        
        Args:
            request: LLM request parameters
            capability_token: JWT capability token
            user_id: User identifier for rate limiting
            tenant_id: Tenant identifier for isolation
            
        Returns:
            LLM response or streaming generator
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        try:
            # Verify capabilities
            await self._verify_llm_capability(capability_token, request.model, user_id, tenant_id)
            
            # Validate model availability
            model_config = self.models.get(request.model)
            if not model_config:
                raise ValueError(f"Model {request.model} not supported")
            
            if not model_config.is_available:
                raise ValueError(f"Model {request.model} is currently unavailable")
            
            # Check rate limits
            await self._check_rate_limits(user_id, model_config)
            
            # Route to configured endpoint (generic routing for any provider)
            if hasattr(model_config, 'endpoint') and model_config.endpoint:
                result = await self._process_generic_request(request, request_id, model_config, tenant_id)
            elif model_config.provider == ModelProvider.GROQ:
                result = await self._process_groq_request(request, request_id, model_config, tenant_id)
            elif model_config.provider == ModelProvider.OPENAI:
                result = await self._process_openai_request(request, request_id, model_config)
            else:
                raise ValueError(f"Provider {model_config.provider} not implemented - ensure endpoint is configured")
            
            # Update statistics
            latency = time.time() - start_time
            await self._update_stats(request.model, model_config.provider, latency, True)
            
            logger.info(f"LLM request completed: {request_id} ({latency:.3f}s)")
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            await self._update_stats(request.model, ModelProvider.GROQ, latency, False)
            
            logger.error(f"LLM request failed: {request_id} - {e}")
            raise
    
    async def _verify_llm_capability(
        self,
        capability_token: str,
        model: str,
        user_id: str,
        tenant_id: str
    ) -> None:
        """Verify user has capability to use specific model"""
        try:
            payload = await verify_capability_token(capability_token)
            
            # Check tenant match
            if payload.get("tenant_id") != tenant_id:
                raise CapabilityError("Tenant mismatch in capability token")
            
            # Find LLM capability (match "llm" or "llm:provider" format)
            capabilities = payload.get("capabilities", [])
            llm_capability = None

            for cap in capabilities:
                resource = cap.get("resource", "")
                if resource == "llm" or resource.startswith("llm:"):
                    llm_capability = cap
                    break
            
            if not llm_capability:
                raise CapabilityError("No LLM capability found in token")
            
            # Check model access
            allowed_models = llm_capability.get("constraints", {}).get("allowed_models", [])
            if allowed_models and model not in allowed_models:
                raise CapabilityError(f"Model {model} not allowed in capability")
            
            # Check rate limits (per-minute window)
            max_requests_per_minute = llm_capability.get("constraints", {}).get("max_requests_per_minute")
            if max_requests_per_minute:
                await self._check_user_rate_limit(user_id, max_requests_per_minute)
            
        except CapabilityError:
            raise
        except Exception as e:
            raise CapabilityError(f"Capability verification failed: {e}")
    
    async def _check_rate_limits(self, user_id: str, model_config: ModelConfig) -> None:
        """Check if user is within rate limits for model"""
        now = time.time()
        minute_ago = now - 60
        
        # Initialize user rate limit tracking
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = {}
        
        if model_config.model_id not in self.rate_limits[user_id]:
            self.rate_limits[user_id][model_config.model_id] = []
        
        user_requests = self.rate_limits[user_id][model_config.model_id]
        
        # Remove old requests
        user_requests[:] = [req_time for req_time in user_requests if req_time > minute_ago]
        
        # Check limit
        if len(user_requests) >= model_config.rate_limit_rpm:
            raise ValueError(f"Rate limit exceeded for model {model_config.model_id}")
        
        # Add current request
        user_requests.append(now)
    
    async def _check_user_rate_limit(self, user_id: str, max_requests_per_minute: int) -> None:
        """
        Check user's rate limit with per-minute enforcement window.

        Enforces limits from Control Panel database (single source of truth).
        Time window: 60 seconds (not 1 hour).

        Args:
            user_id: User identifier
            max_requests_per_minute: Maximum requests allowed in 60-second window

        Raises:
            ValueError: If rate limit exceeded
        """
        now = time.time()
        minute_ago = now - 60  # 60-second window (was 3600 for hour)

        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = {}

        if "total_requests" not in self.rate_limits[user_id]:
            self.rate_limits[user_id]["total_requests"] = []

        total_requests = self.rate_limits[user_id]["total_requests"]

        # Remove requests outside the 60-second window
        total_requests[:] = [req_time for req_time in total_requests if req_time > minute_ago]

        # Check limit
        if len(total_requests) >= max_requests_per_minute:
            raise ValueError(
                f"Rate limit exceeded: {max_requests_per_minute} requests per minute. "
                f"Try again in {int(60 - (now - total_requests[0]))} seconds."
            )

        # Add current request
        total_requests.append(now)
    
    async def _process_groq_request(
        self,
        request: LLMRequest,
        request_id: str,
        model_config: ModelConfig,
        tenant_id: str
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """
        Process request using Groq API with tenant-specific API key.

        API keys are fetched from Control Panel database - NO environment variable fallback.
        """
        try:
            # Get API key from Control Panel database (NO env fallback)
            api_key = await self._get_tenant_api_key(tenant_id)

            # Prepare Groq API request
            groq_request = {
                "model": request.model,
                "messages": request.messages,
                "max_tokens": min(request.max_tokens or 1024, model_config.max_tokens),
                "temperature": request.temperature or 0.7,
                "top_p": request.top_p or 1.0,
                "stream": request.stream
            }

            if request.stop:
                groq_request["stop"] = request.stop

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            if request.stream:
                return self._stream_groq_response(groq_request, headers, request_id)
            else:
                return await self._get_groq_response(groq_request, headers, request_id)

        except Exception as e:
            logger.error(f"Groq API request failed: {e}")
            raise ValueError(f"Groq API error: {e}")

    async def _get_tenant_api_key(self, tenant_id: str) -> str:
        """
        Get API key for tenant from Control Panel database.

        NO environment variable fallback - per GT 2.0 NO FALLBACKS principle.
        """
        from app.clients.api_key_client import get_api_key_client, APIKeyNotConfiguredError

        client = get_api_key_client()

        try:
            key_info = await client.get_api_key(tenant_domain=tenant_id, provider="groq")
            return key_info["api_key"]
        except APIKeyNotConfiguredError as e:
            logger.error(f"No Groq API key for tenant '{tenant_id}': {e}")
            raise ValueError(f"No Groq API key configured for tenant '{tenant_id}'. Please configure in Control Panel → API Keys.")
        except RuntimeError as e:
            logger.error(f"Control Panel error: {e}")
            raise ValueError(f"Unable to retrieve API key - service unavailable: {e}")

    async def _get_tenant_nvidia_api_key(self, tenant_id: str) -> str:
        """
        Get NVIDIA NIM API key for tenant from Control Panel database.

        NO environment variable fallback - per GT 2.0 NO FALLBACKS principle.
        """
        from app.clients.api_key_client import get_api_key_client, APIKeyNotConfiguredError

        client = get_api_key_client()

        try:
            key_info = await client.get_api_key(tenant_domain=tenant_id, provider="nvidia")
            return key_info["api_key"]
        except APIKeyNotConfiguredError as e:
            logger.error(f"No NVIDIA API key for tenant '{tenant_id}': {e}")
            raise ValueError(f"No NVIDIA API key configured for tenant '{tenant_id}'. Please configure in Control Panel → API Keys.")
        except RuntimeError as e:
            logger.error(f"Control Panel error: {e}")
            raise ValueError(f"Unable to retrieve API key - service unavailable: {e}")
    
    async def _get_groq_response(
        self,
        groq_request: Dict[str, Any],
        headers: Dict[str, str],
        request_id: str
    ) -> LLMResponse:
        """Get non-streaming response from Groq"""
        try:
            response = await self.http_client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=groq_request,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Convert to standardized format
            return LLMResponse(
                id=data.get("id", request_id),
                object=data.get("object", "chat.completion"),
                created=data.get("created", int(time.time())),
                model=data.get("model", groq_request["model"]),
                choices=data.get("choices", []),
                usage=data.get("usage", {}),
                provider="groq",
                request_id=request_id
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API HTTP error: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Groq API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise ValueError(f"Groq API request failed: {e}")
    
    async def _stream_groq_response(
        self,
        groq_request: Dict[str, Any],
        headers: Dict[str, str],
        request_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream response from Groq"""
        try:
            async with self.http_client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                json=groq_request,
                headers=headers
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            # Add provider and request_id to chunk
                            data["provider"] = "groq"
                            data["request_id"] = request_id
                            yield f"data: {json.dumps(data)}\n\n"
                        except json.JSONDecodeError:
                            continue
                
                yield "data: [DONE]\n\n"
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq streaming error: {e.response.status_code}")
            yield f"data: {json.dumps({'error': f'Groq API error: {e.response.status_code}'})}\n\n"
        except Exception as e:
            logger.error(f"Groq streaming error: {e}")
            yield f"data: {json.dumps({'error': f'Streaming error: {e}'})}\n\n"

    async def _process_generic_request(
        self,
        request: LLMRequest,
        request_id: str,
        model_config: Any,
        tenant_id: str
    ) -> LLMResponse:
        """
        Process request using generic endpoint (OpenAI-compatible).

        For Groq endpoints, API keys are fetched from Control Panel database.
        """
        try:
            # Build OpenAI-compatible request
            generic_request = {
                "model": request.model,
                "messages": request.messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": request.stream
            }

            # Add optional parameters
            if hasattr(request, 'tools') and request.tools:
                generic_request["tools"] = request.tools
            if hasattr(request, 'tool_choice') and request.tool_choice:
                generic_request["tool_choice"] = request.tool_choice

            headers = {"Content-Type": "application/json"}

            endpoint_url = model_config.endpoint

            # For Groq endpoints, use tenant-specific API key from Control Panel DB
            if is_provider_endpoint(endpoint_url, ["groq.com"]):
                api_key = await self._get_tenant_api_key(tenant_id)
                headers["Authorization"] = f"Bearer {api_key}"
            # For NVIDIA NIM endpoints, use tenant-specific API key from Control Panel DB
            elif is_provider_endpoint(endpoint_url, ["nvidia.com", "integrate.api.nvidia.com"]):
                api_key = await self._get_tenant_nvidia_api_key(tenant_id)
                headers["Authorization"] = f"Bearer {api_key}"
            # For other endpoints, use model_config.api_key if configured
            elif hasattr(model_config, 'api_key') and model_config.api_key:
                headers["Authorization"] = f"Bearer {model_config.api_key}"

            logger.info(f"Sending request to generic endpoint: {endpoint_url}")

            if request.stream:
                return await self._stream_generic_response(generic_request, headers, endpoint_url, request_id, model_config)
            else:
                return await self._get_generic_response(generic_request, headers, endpoint_url, request_id, model_config)

        except Exception as e:
            logger.error(f"Generic request processing failed: {e}")
            raise ValueError(f"Generic inference failed: {e}")

    async def _get_generic_response(
        self,
        generic_request: Dict[str, Any],
        headers: Dict[str, str],
        endpoint_url: str,
        request_id: str,
        model_config: Any
    ) -> LLMResponse:
        """Get non-streaming response from generic endpoint"""
        try:
            response = await self.http_client.post(
                endpoint_url,
                json=generic_request,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()

            # Convert to standardized format
            return LLMResponse(
                id=data.get("id", request_id),
                object=data.get("object", "chat.completion"),
                created=data.get("created", int(time.time())),
                model=data.get("model", generic_request["model"]),
                choices=data.get("choices", []),
                usage=data.get("usage", {}),
                provider=getattr(model_config, 'provider', 'generic'),
                request_id=request_id
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Generic API HTTP error: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Generic API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Generic response error: {e}")
            raise ValueError(f"Generic response processing failed: {e}")

    async def _stream_generic_response(
        self,
        generic_request: Dict[str, Any],
        headers: Dict[str, str],
        endpoint_url: str,
        request_id: str,
        model_config: Any
    ):
        """Stream response from generic endpoint"""
        try:
            # For now, just do a non-streaming request and convert to streaming format
            # This can be enhanced to support actual streaming later
            response = await self._get_generic_response(generic_request, headers, endpoint_url, request_id, model_config)

            # Convert to streaming format
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].get("message", {}).get("content", "")
                yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Generic streaming error: {e}")
            yield f"data: {json.dumps({'error': f'Streaming error: {e}'})}\n\n"

    async def _process_openai_request(
        self,
        request: LLMRequest,
        request_id: str,
        model_config: ModelConfig
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Process request using OpenAI API"""
        try:
            # Prepare OpenAI API request
            openai_request = {
                "model": request.model,
                "messages": request.messages,
                "max_tokens": min(request.max_tokens or 1024, model_config.max_tokens),
                "temperature": request.temperature or 0.7,
                "top_p": request.top_p or 1.0,
                "stream": request.stream
            }
            
            if request.stop:
                openai_request["stop"] = request.stop
            
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json"
            }
            
            if request.stream:
                return self._stream_openai_response(openai_request, headers, request_id)
            else:
                return await self._get_openai_response(openai_request, headers, request_id)
                
        except Exception as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise ValueError(f"OpenAI API error: {e}")
    
    async def _get_openai_response(
        self,
        openai_request: Dict[str, Any],
        headers: Dict[str, str],
        request_id: str
    ) -> LLMResponse:
        """Get non-streaming response from OpenAI"""
        try:
            response = await self.http_client.post(
                "https://api.openai.com/v1/chat/completions",
                json=openai_request,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Convert to standardized format
            return LLMResponse(
                id=data.get("id", request_id),
                object=data.get("object", "chat.completion"),
                created=data.get("created", int(time.time())),
                model=data.get("model", openai_request["model"]),
                choices=data.get("choices", []),
                usage=data.get("usage", {}),
                provider="openai",
                request_id=request_id
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API HTTP error: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"OpenAI API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise ValueError(f"OpenAI API request failed: {e}")
    
    async def _stream_openai_response(
        self,
        openai_request: Dict[str, Any],
        headers: Dict[str, str],
        request_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream response from OpenAI"""
        try:
            async with self.http_client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                json=openai_request,
                headers=headers
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            # Add provider and request_id to chunk
                            data["provider"] = "openai"
                            data["request_id"] = request_id
                            yield f"data: {json.dumps(data)}\n\n"
                        except json.JSONDecodeError:
                            continue
                
                yield "data: [DONE]\n\n"
                
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI streaming error: {e.response.status_code}")
            yield f"data: {json.dumps({'error': f'OpenAI API error: {e.response.status_code}'})}\n\n"
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield f"data: {json.dumps({'error': f'Streaming error: {e}'})}\n\n"
    
    async def _update_stats(
        self,
        model: str,
        provider: ModelProvider,
        latency: float,
        success: bool
    ) -> None:
        """Update request statistics"""
        self.stats["total_requests"] += 1
        
        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1
        
        self.stats["provider_usage"][provider.value] += 1
        
        if model not in self.stats["model_usage"]:
            self.stats["model_usage"][model] = 0
        self.stats["model_usage"][model] += 1
        
        # Update rolling average latency
        total_requests = self.stats["total_requests"]
        current_avg = self.stats["average_latency"]
        self.stats["average_latency"] = ((current_avg * (total_requests - 1)) + latency) / total_requests
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models with capabilities"""
        models = []
        
        for model_id, config in self.models.items():
            if config.is_available:
                models.append({
                    "id": model_id,
                    "provider": config.provider.value,
                    "capabilities": [cap.value for cap in config.capabilities],
                    "max_tokens": config.max_tokens,
                    "context_window": config.context_window,
                    "supports_streaming": config.supports_streaming,
                    "supports_functions": config.supports_functions
                })
        
        return models
    
    async def get_gateway_stats(self) -> Dict[str, Any]:
        """Get gateway statistics"""
        return {
            **self.stats,
            "provider_health": {
                provider.value: health 
                for provider, health in self.provider_health.items()
            },
            "active_models": len([m for m in self.models.values() if m.is_available]),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the LLM gateway"""
        healthy_providers = sum(1 for health in self.provider_health.values() if health)
        total_providers = len(self.provider_health)
        
        return {
            "status": "healthy" if healthy_providers > 0 else "degraded",
            "providers_healthy": healthy_providers,
            "total_providers": total_providers,
            "available_models": len([m for m in self.models.values() if m.is_available]),
            "total_requests": self.stats["total_requests"],
            "success_rate": (
                self.stats["successful_requests"] / max(self.stats["total_requests"], 1)
            ) * 100,
            "average_latency_ms": self.stats["average_latency"] * 1000
        }
    
    async def close(self):
        """Close HTTP client and cleanup resources"""
        await self.http_client.aclose()


# Global gateway instance
llm_gateway = LLMGateway()


# Factory function for dependency injection
def get_llm_gateway() -> LLMGateway:
    """Get LLM gateway instance"""
    return llm_gateway