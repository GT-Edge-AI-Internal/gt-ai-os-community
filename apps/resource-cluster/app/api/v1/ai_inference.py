"""
GT 2.0 Resource Cluster - AI Inference API (OpenAI Compatible Format)

IMPORTANT: This module maintains OpenAI API compatibility for AI model inference.
Other Resource Cluster endpoints use CB-REST standard.
"""
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from urllib.parse import urlparse
import logging
import json
import asyncio
import time
import uuid

logger = logging.getLogger(__name__)


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
router = APIRouter(prefix="/ai", tags=["AI Inference"])


# OpenAI Compatible Request/Response Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, agent")
    content: Optional[str] = Field(None, description="Message content")
    name: Optional[str] = Field(None, description="Optional name for the message")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls made by the agent")
    tool_call_id: Optional[str] = Field(None, description="ID of the tool call this message is responding to")


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model identifier")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(1, ge=1, le=10)
    stream: Optional[bool] = Field(False)
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_cents: Optional[int] = Field(None, description="Total cost in cents")


class ModelUsageBreakdown(BaseModel):
    """Per-model token usage for Compound responses"""
    model: str
    prompt_tokens: int
    completion_tokens: int
    input_cost_dollars: Optional[float] = None
    output_cost_dollars: Optional[float] = None
    total_cost_dollars: Optional[float] = None


class ToolCostBreakdown(BaseModel):
    """Per-tool cost for Compound responses"""
    tool: str
    cost_dollars: float


class CostBreakdown(BaseModel):
    """Detailed cost breakdown for Compound models"""
    models: List[ModelUsageBreakdown] = Field(default_factory=list)
    tools: List[ToolCostBreakdown] = Field(default_factory=list)
    total_cost_dollars: float = 0.0
    total_cost_cents: int = 0


class UsageBreakdown(BaseModel):
    """Usage breakdown for Compound responses"""
    models: List[Dict[str, Any]] = Field(default_factory=list)


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Usage
    system_fingerprint: Optional[str] = None
    # Compound-specific fields (optional)
    usage_breakdown: Optional[UsageBreakdown] = Field(None, description="Per-model usage for Compound models")
    executed_tools: Optional[List[str]] = Field(None, description="Tools executed by Compound models")
    cost_breakdown: Optional[CostBreakdown] = Field(None, description="Detailed cost breakdown for Compound models")


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]] = Field(..., description="Text to embed")
    model: str = Field(..., description="Embedding model")
    encoding_format: Optional[str] = Field("float", description="Encoding format")
    user: Optional[str] = None


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: Usage


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Image description")
    model: str = Field("dall-e-3", description="Image model")
    n: Optional[int] = Field(1, ge=1, le=10)
    size: Optional[str] = Field("1024x1024")
    quality: Optional[str] = Field("standard")
    style: Optional[str] = Field("vivid")
    response_format: Optional[str] = Field("url")
    user: Optional[str] = None


class ImageData(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: List[ImageData]


# Import real LLM Gateway
from app.services.llm_gateway import LLMGateway
from app.services.admin_model_config_service import get_admin_model_service

# Initialize real LLM service
llm_gateway = LLMGateway()
admin_model_service = get_admin_model_service()


async def process_chat_completion(request: ChatCompletionRequest, tenant_id: str = None) -> ChatCompletionResponse:
    """Process chat completion using real LLM Gateway with admin configurations"""
    try:
        # Get model configuration from admin service
        # First try by model_id string, then by UUID for new UUID-based selection
        model_config = await admin_model_service.get_model_config(request.model)
        if not model_config:
            # Try looking up by UUID (frontend may send database UUID)
            model_config = await admin_model_service.get_model_by_uuid(request.model)
        if not model_config:
            raise ValueError(f"Model {request.model} not found in admin configuration")

        # Store the actual model_id for external API calls (in case request.model is a UUID)
        actual_model_id = model_config.model_id

        if not model_config.is_active:
            raise ValueError(f"Model {actual_model_id} is not active")

        # Tenant ID is required for API key lookup
        if not tenant_id:
            raise ValueError("Tenant ID is required for chat completions - no fallback to environment variables")

        # Check tenant access - use actual model_id for access check
        has_access = await admin_model_service.check_tenant_access(tenant_id, actual_model_id)
        if not has_access:
            raise ValueError(f"Tenant {tenant_id} does not have access to model {actual_model_id}")

        # Get API key for the provider from Control Panel database (NO env fallback)
        api_key = None
        if model_config.provider == "groq":
            api_key = await admin_model_service.get_groq_api_key(tenant_id=tenant_id)

        # Route to configured endpoint (generic routing for any provider)
        endpoint_url = getattr(model_config, 'endpoint', None)
        if endpoint_url:
            return await _call_generic_api(request, model_config, endpoint_url, tenant_id, actual_model_id)
        elif model_config.provider == "groq":
            return await _call_groq_api(request, model_config, api_key, actual_model_id)
        else:
            raise ValueError(f"Provider {model_config.provider} not implemented - no endpoint configured")

    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise


async def _call_generic_api(request: ChatCompletionRequest, model_config, endpoint_url: str, tenant_id: str, actual_model_id: str = None) -> ChatCompletionResponse:
    """Call any OpenAI-compatible endpoint"""
    # Use actual_model_id for external API calls (in case request.model is a UUID)
    model_id_for_api = actual_model_id or model_config.model_id
    import httpx

    # Convert request to OpenAI format - translate GT 2.0 "agent" role to OpenAI "assistant" for external API compatibility
    api_messages = []
    for msg in request.messages:
        # Translate GT 2.0 "agent" role to OpenAI-compatible "assistant" role for external APIs
        external_role = "assistant" if msg.role == "agent" else msg.role

        # Preserve all message fields including tool_call_id, tool_calls, etc.
        api_msg = {
            "role": external_role,
            "content": msg.content
        }

        # Add tool_calls if present
        if msg.tool_calls:
            api_msg["tool_calls"] = msg.tool_calls

        # Add tool_call_id if present (for tool response messages)
        if msg.tool_call_id:
            api_msg["tool_call_id"] = msg.tool_call_id

        # Add name if present
        if msg.name:
            api_msg["name"] = msg.name

        api_messages.append(api_msg)

    api_request = {
        "model": model_id_for_api,  # Use actual model_id string, not UUID
        "messages": api_messages,
        "temperature": request.temperature,
        "max_tokens": min(request.max_tokens or 1024, model_config.max_tokens),
        "top_p": request.top_p,
        "stream": False  # Handle streaming separately
    }

    # Add tools if provided
    if request.tools:
        api_request["tools"] = request.tools
    if request.tool_choice:
        api_request["tool_choice"] = request.tool_choice

    headers = {"Content-Type": "application/json"}

    # Add API key based on endpoint - fetch from Control Panel DB (NO env fallback)
    if is_provider_endpoint(endpoint_url, ["groq.com"]):
        api_key = await admin_model_service.get_groq_api_key(tenant_id=tenant_id)
        headers["Authorization"] = f"Bearer {api_key}"
    elif is_provider_endpoint(endpoint_url, ["nvidia.com", "integrate.api.nvidia.com"]):
        # Fetch NVIDIA API key from Control Panel
        from app.clients.api_key_client import get_api_key_client, APIKeyNotConfiguredError
        client = get_api_key_client()
        try:
            key_info = await client.get_api_key(tenant_domain=tenant_id, provider="nvidia")
            headers["Authorization"] = f"Bearer {key_info['api_key']}"
        except APIKeyNotConfiguredError as e:
            raise ValueError(f"NVIDIA API key not configured for tenant '{tenant_id}'. Please add your NVIDIA API key in the Control Panel.")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint_url,
                headers=headers,
                json=api_request,
                timeout=300.0  # 5 minutes - allows complex agent operations to complete
            )

            if response.status_code != 200:
                raise ValueError(f"API error: {response.status_code} - {response.text}")

        api_response = response.json()
    except httpx.TimeoutException as e:
        logger.error(f"API timeout after 300s for endpoint {endpoint_url}")
        raise ValueError(f"API request timed out after 5 minutes - try reducing system prompt length or max_tokens")
    except httpx.HTTPStatusError as e:
        logger.error(f"API HTTP error: {e.response.status_code} - {e.response.text}")
        raise ValueError(f"API HTTP error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"API request failed: {type(e).__name__}: {e}")
        raise ValueError(f"API request failed: {type(e).__name__}: {str(e)}")

    # Convert API response to our format - translate OpenAI "assistant" back to GT 2.0 "agent"
    choices = []
    for choice in api_response["choices"]:
        # Translate OpenAI-compatible "assistant" role back to GT 2.0 "agent" role
        internal_role = "agent" if choice["message"]["role"] == "assistant" else choice["message"]["role"]

        # Preserve all message fields from API response
        message_data = {
            "role": internal_role,
            "content": choice["message"].get("content"),
        }

        # Add tool calls if present
        if "tool_calls" in choice["message"]:
            message_data["tool_calls"] = choice["message"]["tool_calls"]

        # Add tool_call_id if present (for tool response messages)
        if "tool_call_id" in choice["message"]:
            message_data["tool_call_id"] = choice["message"]["tool_call_id"]

        # Add name if present
        if "name" in choice["message"]:
            message_data["name"] = choice["message"]["name"]

        choices.append(ChatChoice(
            index=choice["index"],
            message=ChatMessage(**message_data),
            finish_reason=choice.get("finish_reason")
        ))

    # Calculate cost_breakdown for Compound models
    cost_breakdown = None
    if "compound" in request.model.lower():
        from app.core.backends.groq_proxy import GroqProxyBackend
        proxy = GroqProxyBackend()

        # Extract executed_tools from choices[0].message.executed_tools (Groq Compound format)
        executed_tools_data = []
        if "choices" in api_response and api_response["choices"]:
            message = api_response["choices"][0].get("message", {})
            raw_tools = message.get("executed_tools", [])
            # Convert to format expected by _calculate_compound_cost: list of tool names/types
            for tool in raw_tools:
                if isinstance(tool, dict):
                    # Extract tool type (e.g., "search", "code_execution")
                    tool_type = tool.get("type", "search")
                    executed_tools_data.append(tool_type)
                elif isinstance(tool, str):
                    executed_tools_data.append(tool)
            if executed_tools_data:
                logger.info(f"Compound executed_tools: {executed_tools_data}")

        # Use actual per-model breakdown from usage_breakdown if available
        usage_breakdown = api_response.get("usage_breakdown", {})
        models_data = usage_breakdown.get("models", [])

        if models_data:
            logger.info(f"Compound using per-model breakdown: {len(models_data)} model calls")
            cost_breakdown = proxy._calculate_compound_cost({
                "usage_breakdown": {"models": models_data},
                "executed_tools": executed_tools_data
            })
        else:
            # Fallback: use aggregate tokens
            usage = api_response.get("usage", {})
            cost_breakdown = proxy._calculate_compound_cost({
                "usage_breakdown": {
                    "models": [{
                        "model": api_response.get("model", request.model),
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0)
                        }
                    }]
                },
                "executed_tools": executed_tools_data
            })
        logger.info(f"Compound cost_breakdown (generic API): ${cost_breakdown.get('total_cost_dollars', 0):.6f}")

    return ChatCompletionResponse(
        id=api_response["id"],
        created=api_response["created"],
        model=api_response["model"],
        choices=choices,
        usage=Usage(
                prompt_tokens=api_response["usage"]["prompt_tokens"],
                completion_tokens=api_response["usage"]["completion_tokens"],
                total_tokens=api_response["usage"]["total_tokens"]
            ),
        cost_breakdown=cost_breakdown
        )


async def _call_groq_api(request: ChatCompletionRequest, model_config, api_key: str, actual_model_id: str = None) -> ChatCompletionResponse:
    """Call Groq API directly"""
    # Use actual_model_id for external API calls (in case request.model is a UUID)
    model_id_for_api = actual_model_id or model_config.model_id
    import httpx

    # Convert request to Groq format - translate GT 2.0 "agent" role to OpenAI "assistant" for external API compatibility
    groq_messages = []
    for msg in request.messages:
        # Translate GT 2.0 "agent" role to OpenAI-compatible "assistant" role for external APIs
        external_role = "assistant" if msg.role == "agent" else msg.role

        # Preserve all message fields including tool_call_id, tool_calls, etc.
        groq_msg = {
            "role": external_role,
            "content": msg.content
        }

        # Add tool_calls if present
        if msg.tool_calls:
            groq_msg["tool_calls"] = msg.tool_calls

        # Add tool_call_id if present (for tool response messages)
        if msg.tool_call_id:
            groq_msg["tool_call_id"] = msg.tool_call_id

        # Add name if present
        if msg.name:
            groq_msg["name"] = msg.name

        groq_messages.append(groq_msg)

    groq_request = {
        "model": model_id_for_api,  # Use actual model_id string, not UUID
        "messages": groq_messages,
        "temperature": request.temperature,
        "max_tokens": min(request.max_tokens or 1024, model_config.max_tokens),
        "top_p": request.top_p,
        "stream": False  # Handle streaming separately
    }

    # Add tools if provided
    if request.tools:
        groq_request["tools"] = request.tools
    if request.tool_choice:
        groq_request["tool_choice"] = request.tool_choice

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=groq_request,
                timeout=300.0  # 5 minutes - allows complex agent operations to complete
            )

            if response.status_code != 200:
                raise ValueError(f"Groq API error: {response.status_code} - {response.text}")

        groq_response = response.json()
    except httpx.TimeoutException as e:
        logger.error(f"Groq API timeout after 300s for model {request.model}")
        raise ValueError(f"Groq API request timed out after 5 minutes - try reducing system prompt length or max_tokens")
    except httpx.HTTPStatusError as e:
        logger.error(f"Groq API HTTP error: {e.response.status_code} - {e.response.text}")
        raise ValueError(f"Groq API HTTP error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Groq API request failed: {type(e).__name__}: {e}")
        raise ValueError(f"Groq API request failed: {type(e).__name__}: {str(e)}")

    # Convert Groq response to our format - translate OpenAI "assistant" back to GT 2.0 "agent"
    choices = []
    for choice in groq_response["choices"]:
        # Translate OpenAI-compatible "assistant" role back to GT 2.0 "agent" role
        internal_role = "agent" if choice["message"]["role"] == "assistant" else choice["message"]["role"]

        # Preserve all message fields from Groq response
        message_data = {
            "role": internal_role,
            "content": choice["message"].get("content"),
        }

        # Add tool calls if present
        if "tool_calls" in choice["message"]:
            message_data["tool_calls"] = choice["message"]["tool_calls"]

        # Add tool_call_id if present (for tool response messages)
        if "tool_call_id" in choice["message"]:
            message_data["tool_call_id"] = choice["message"]["tool_call_id"]

        # Add name if present
        if "name" in choice["message"]:
            message_data["name"] = choice["message"]["name"]

        choices.append(ChatChoice(
            index=choice["index"],
            message=ChatMessage(**message_data),
            finish_reason=choice.get("finish_reason")
        ))

    # Build response with Compound-specific fields if present
    response_data = {
        "id": groq_response["id"],
        "created": groq_response["created"],
        "model": groq_response["model"],
        "choices": choices,
        "usage": Usage(
            prompt_tokens=groq_response["usage"]["prompt_tokens"],
            completion_tokens=groq_response["usage"]["completion_tokens"],
            total_tokens=groq_response["usage"]["total_tokens"]
        )
    }

    # Extract Compound-specific fields if present (for accurate billing)
    usage_breakdown_data = None
    executed_tools_data = None

    if "usage_breakdown" in groq_response.get("usage", {}):
        usage_breakdown_data = groq_response["usage"]["usage_breakdown"]
        response_data["usage_breakdown"] = UsageBreakdown(models=usage_breakdown_data)
        logger.debug(f"Compound usage_breakdown: {usage_breakdown_data}")

    # Check for executed_tools in the response (Compound models)
    if "x_groq" in groq_response:
        x_groq = groq_response["x_groq"]
        if "usage" in x_groq and "executed_tools" in x_groq["usage"]:
            executed_tools_data = x_groq["usage"]["executed_tools"]
            response_data["executed_tools"] = executed_tools_data
            logger.debug(f"Compound executed_tools: {executed_tools_data}")

    # Calculate cost breakdown for Compound models using actual usage data
    if usage_breakdown_data or executed_tools_data:
        try:
            from app.core.backends.groq_proxy import GroqProxyBackend
            proxy = GroqProxyBackend()
            cost_breakdown = proxy._calculate_compound_cost({
                "usage_breakdown": {"models": usage_breakdown_data or []},
                "executed_tools": executed_tools_data or []
            })
            response_data["cost_breakdown"] = CostBreakdown(
                models=[ModelUsageBreakdown(**m) for m in cost_breakdown.get("models", [])],
                tools=[ToolCostBreakdown(**t) for t in cost_breakdown.get("tools", [])],
                total_cost_dollars=cost_breakdown.get("total_cost_dollars", 0.0),
                total_cost_cents=cost_breakdown.get("total_cost_cents", 0)
            )
            logger.info(f"Compound cost_breakdown: ${cost_breakdown['total_cost_dollars']:.6f} ({cost_breakdown['total_cost_cents']} cents)")
        except Exception as e:
            logger.warning(f"Failed to calculate Compound cost breakdown: {e}")

    # Fallback: If this is a Compound model and we don't have cost_breakdown yet,
    # calculate it from standard token usage (Groq may not return detailed breakdown)
    if "compound" in request.model.lower() and "cost_breakdown" not in response_data:
        try:
            from app.core.backends.groq_proxy import GroqProxyBackend
            proxy = GroqProxyBackend()

            # Build usage data from standard response tokens
            # Match the structure expected by _calculate_compound_cost
            usage = groq_response.get("usage", {})
            cost_breakdown = proxy._calculate_compound_cost({
                "usage_breakdown": {
                    "models": [{
                        "model": groq_response.get("model", request.model),
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0)
                        }
                    }]
                },
                "executed_tools": []  # No tool data available from standard response
            })

            response_data["cost_breakdown"] = CostBreakdown(
                models=[ModelUsageBreakdown(**m) for m in cost_breakdown.get("models", [])],
                tools=[],
                total_cost_dollars=cost_breakdown.get("total_cost_dollars", 0.0),
                total_cost_cents=cost_breakdown.get("total_cost_cents", 0)
            )
            logger.info(f"Compound cost_breakdown (from tokens): ${cost_breakdown['total_cost_dollars']:.6f} ({cost_breakdown['total_cost_cents']} cents)")
        except Exception as e:
            logger.warning(f"Failed to calculate Compound cost breakdown from tokens: {e}")

    return ChatCompletionResponse(**response_data)


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request
):
    """
    OpenAI-compatible chat completions endpoint
    
    This endpoint maintains full OpenAI API compatibility for seamless integration
    with existing AI tools and libraries.
    """
    try:
        # Verify capability token from Authorization header
        auth_header = http_request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        # Extract tenant ID from headers
        tenant_id = http_request.headers.get("X-Tenant-ID")
        
        # Handle streaming responses
        if request.stream:
            # codeql[py/stack-trace-exposure] returns LLM response stream, not error details
            return StreamingResponse(
                stream_chat_completion(request, tenant_id, auth_header),
                media_type="text/plain"
            )
        
        # Regular response using real LLM Gateway
        response = await process_chat_completion(request, tenant_id)
        return response
        
    except Exception as e:
        logger.error(f"Chat completion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    http_request: Request
):
    """
    OpenAI-compatible embeddings endpoint
    
    Creates embeddings for the given input text(s).
    """
    try:
        # Verify capability token
        auth_header = http_request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        # TODO: Implement embeddings via LLM Gateway (Day 3)
        raise HTTPException(status_code=501, detail="Embeddings endpoint not yet implemented")
        
    except Exception as e:
        logger.error(f"Embedding creation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/images/generations", response_model=ImageGenerationResponse)
async def create_image(
    request: ImageGenerationRequest,
    http_request: Request
):
    """
    OpenAI-compatible image generation endpoint
    
    Generates images from text prompts.
    """
    try:
        # Verify capability token
        auth_header = http_request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        # Mock response (replace with actual image generation)
        response = ImageGenerationResponse(
            created=int(time.time()),
            data=[
                ImageData(
                    url=f"https://api.gt2.com/generated/{uuid.uuid4().hex}.png",
                    revised_prompt=request.prompt
                )
                for _ in range(request.n or 1)
            ]
        )
        return response
        
    except Exception as e:
        logger.error(f"Image generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models")
async def list_models(http_request: Request):
    """
    List available AI models (OpenAI compatible format)
    """
    try:
        # Verify capability token
        auth_header = http_request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        models = {
            "object": "list",
            "data": [
                {
                    "id": "gpt-4",
                    "object": "model",
                    "created": 1687882410,
                    "owned_by": "openai",
                    "permission": [],
                    "root": "gpt-4",
                    "parent": None
                },
                {
                    "id": "claude-3-sonnet",
                    "object": "model",
                    "created": 1687882410,
                    "owned_by": "anthropic",
                    "permission": [],
                    "root": "claude-3-sonnet",
                    "parent": None
                },
                {
                    "id": "llama-3.1-70b",
                    "object": "model",
                    "created": 1687882410,
                    "owned_by": "groq",
                    "permission": [],
                    "root": "llama-3.1-70b",
                    "parent": None
                },
                {
                    "id": "text-embedding-3-small",
                    "object": "model",
                    "created": 1687882410,
                    "owned_by": "openai",
                    "permission": [],
                    "root": "text-embedding-3-small",
                    "parent": None
                }
            ]
        }
        return models
        
    except Exception as e:
        logger.error(f"List models error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def stream_chat_completion(request: ChatCompletionRequest, tenant_id: str, auth_header: str = None):
    """Stream chat completion responses using real AI providers"""
    try:
        from app.services.llm_gateway import LLMGateway, LLMRequest
        
        gateway = LLMGateway()
        
        # Create a unique request ID for this stream
        response_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        created_time = int(time.time())
        
        # Create LLM request with streaming enabled - translate GT 2.0 "agent" to OpenAI "assistant" 
        streaming_messages = []
        for msg in request.messages:
            # Translate GT 2.0 "agent" role to OpenAI-compatible "assistant" role for external APIs
            external_role = "assistant" if msg.role == "agent" else msg.role
            streaming_messages.append({"role": external_role, "content": msg.content})
        
        llm_request = LLMRequest(
            model=request.model,
            messages=streaming_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stream=True
        )
        
        # Extract real capability token from authorization header
        capability_token = "dummy_capability_token"
        user_id = "test_user"
        
        if auth_header and auth_header.startswith("Bearer "):
            capability_token = auth_header.replace("Bearer ", "")
            # TODO: Extract user ID from token if possible
            user_id = "test_user"
        
        # Stream from the LLM Gateway
        stream_generator = await gateway.chat_completion(
            request=llm_request,
            capability_token=capability_token,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        # Process streaming chunks
        async for chunk_data in stream_generator:
            # The chunk_data from Groq proxy should already be formatted
            # Parse it if it's a string, or use directly if it's already a dict
            if isinstance(chunk_data, str):
                # Extract content from SSE format like "data: {content: 'text'}"
                if chunk_data.startswith("data: "):
                    chunk_json = chunk_data[6:].strip()
                    if chunk_json and chunk_json != "[DONE]":
                        try:
                            chunk_dict = json.loads(chunk_json)
                            content = chunk_dict.get("content", "")
                        except json.JSONDecodeError:
                            content = ""
                    else:
                        content = ""
                else:
                    content = chunk_data
            else:
                content = chunk_data.get("content", "")
            
            if content:
                # Format as OpenAI-compatible streaming chunk
                stream_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content},
                        "finish_reason": None
                    }]
                }
                
                yield f"data: {json.dumps(stream_chunk)}\n\n"
        
        # Send final chunk
        final_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk", 
            "created": created_time,
            "model": request.model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "server_error"
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"