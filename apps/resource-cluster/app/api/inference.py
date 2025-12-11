"""
LLM Inference API endpoints

Provides capability-based access to LLM models with:
- Token validation and capability checking
- Multiple model support (Groq, OpenAI, Anthropic)
- Streaming and non-streaming responses
- Usage tracking and cost calculation
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
import logging

from app.core.security import capability_validator, CapabilityToken
from app.core.backends import get_backend
from app.api.auth import verify_capability
from app.services.model_router import get_model_router

router = APIRouter()
logger = logging.getLogger(__name__)


class InferenceRequest(BaseModel):
    """LLM inference request supporting both prompt and messages format"""
    prompt: Optional[str] = Field(default=None, description="Input prompt for the model")
    messages: Optional[list] = Field(default=None, description="Conversation messages in OpenAI format")
    model: str = Field(default="llama-3.1-70b-versatile", description="Model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4000, ge=1, le=32000, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Enable streaming response")
    system_prompt: Optional[str] = Field(default=None, description="System prompt for context")
    tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="Available tools for function calling")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Tool choice strategy")
    user_id: Optional[str] = Field(default=None, description="User identifier for tenant isolation")
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier for isolation")


class InferenceResponse(BaseModel):
    """LLM inference response"""
    content: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    usage: Dict[str, Any] = Field(..., description="Token usage and cost information")
    latency_ms: float = Field(..., description="Inference latency in milliseconds")


@router.post("/", response_model=InferenceResponse)
async def execute_inference(
    request: InferenceRequest,
    token: CapabilityToken = Depends(verify_capability)
) -> InferenceResponse:
    """Execute LLM inference with capability checking"""
    
    # Validate request format
    if not request.prompt and not request.messages:
        raise HTTPException(
            status_code=400,
            detail="Either 'prompt' or 'messages' must be provided"
        )
    
    # Check if user has access to the requested model
    resource = f"llm:{request.model.replace('-', '_')}"
    if not capability_validator.check_resource_access(token, resource, "inference"):
        # Try generic LLM access
        if not capability_validator.check_resource_access(token, "llm:*", "inference"):
            # Try groq specific access
            if not capability_validator.check_resource_access(token, "llm:groq", "inference"):
                raise HTTPException(
                    status_code=403,
                    detail=f"No capability for model: {request.model}"
                )
    
    # Get resource limits from token
    limits = capability_validator.get_resource_limits(token, resource)
    
    # Apply token limits
    max_tokens = min(
        request.max_tokens,
        limits.get("max_tokens_per_request", request.max_tokens)
    )
    
    # Ensure tenant isolation
    user_id = request.user_id or token.sub
    tenant_id = request.tenant_id or token.tenant_id
    
    try:
        # Get model router for tenant
        model_router = await get_model_router(tenant_id)
        
        # Prepare prompt for routing
        prompt = request.prompt
        if request.system_prompt and prompt:
            prompt = f"{request.system_prompt}\n\n{prompt}"
        
        # Route inference request to appropriate provider
        result = await model_router.route_inference(
            model_id=request.model,
            prompt=prompt,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=max_tokens,
            stream=False,
            user_id=user_id,
            tenant_id=tenant_id,
            tools=request.tools,
            tool_choice=request.tool_choice
        )
        
        return InferenceResponse(**result)
        
    except Exception as e:
        logger.error(f"Inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")


@router.post("/stream")
async def stream_inference(
    request: InferenceRequest,
    token: CapabilityToken = Depends(verify_capability)
):
    """Stream LLM inference responses"""
    
    # Validate request format
    if not request.prompt and not request.messages:
        raise HTTPException(
            status_code=400,
            detail="Either 'prompt' or 'messages' must be provided"
        )
    
    # Check streaming capability
    resource = f"llm:{request.model.replace('-', '_')}"
    if not capability_validator.check_resource_access(token, resource, "streaming"):
        if not capability_validator.check_resource_access(token, "llm:*", "streaming"):
            if not capability_validator.check_resource_access(token, "llm:groq", "streaming"):
                raise HTTPException(
                    status_code=403,
                    detail="No streaming capability for this model"
                )
    
    # Ensure tenant isolation
    user_id = request.user_id or token.sub
    tenant_id = request.tenant_id or token.tenant_id
    
    try:
        # Get model router for tenant
        model_router = await get_model_router(tenant_id)
        
        # Prepare prompt for routing
        prompt = request.prompt
        if request.system_prompt and prompt:
            prompt = f"{request.system_prompt}\n\n{prompt}"
        
        # For now, fall back to groq backend for streaming (TODO: implement streaming in model router)
        backend = get_backend("groq_proxy")
        
        # Handle different request formats
        if request.messages:
            # Use messages format for streaming
            async def generate():
                async for chunk in backend._stream_inference_with_messages(
                    messages=request.messages,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    user_id=user_id,
                    tenant_id=tenant_id
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
        else:
            # Use prompt format for streaming
            async def generate():
                async for chunk in backend._stream_inference(
                    messages=[{"role": "user", "content": prompt}],
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    user_id=user_id,
                    tenant_id=tenant_id
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")


@router.get("/models")
async def list_available_models(
    token: CapabilityToken = Depends(verify_capability)
) -> Dict[str, Any]:
    """List available models based on user capabilities"""
    
    try:
        # Get model router for token's tenant
        tenant_id = getattr(token, 'tenant_id', None)
        model_router = await get_model_router(tenant_id)
        
        # Get all available models from registry
        all_models = await model_router.list_available_models()
        
        # Filter based on user capabilities
        accessible_models = []
        for model in all_models:
            resource = f"llm:{model['id'].replace('-', '_')}"
            if capability_validator.check_resource_access(token, resource, "inference"):
                accessible_models.append(model)
            elif capability_validator.check_resource_access(token, "llm:*", "inference"):
                accessible_models.append(model)
        
        return {
            "models": accessible_models,
            "total": len(accessible_models)
        }
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")