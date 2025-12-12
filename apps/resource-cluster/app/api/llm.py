"""
LLM API endpoints for GT 2.0 Resource Cluster

Provides OpenAI-compatible API for LLM inference with:
- Multi-provider routing (Groq, OpenAI, Anthropic)
- Capability-based authentication
- Rate limiting and quota management
- Response streaming support
- Model availability management

GT 2.0 Security Features:
- JWT capability token authentication
- Tenant isolation in all operations
- No persistent state stored
- Stateless request processing
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.capability_auth import verify_capability_token, get_current_capability
from app.services.llm_gateway import get_llm_gateway, LLMRequest, LLMGateway

logger = logging.getLogger(__name__)
router = APIRouter(tags=["llm"])


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request"""
    model: str = Field(..., description="Model to use for completion")
    messages: list = Field(..., description="List of messages")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Presence penalty")
    stop: Optional[list] = Field(None, description="Stop sequences")
    stream: bool = Field(False, description="Whether to stream the response")
    functions: Optional[list] = Field(None, description="Available functions for function calling")
    function_call: Optional[Dict[str, Any]] = Field(None, description="Function call configuration")
    user: Optional[str] = Field(None, description="User identifier for tracking")


class ModelListResponse(BaseModel):
    """Response for model list endpoint"""
    object: str = "list"
    data: list = Field(..., description="List of available models")


@router.post("/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    authorization: str = Header(..., description="Bearer token"),
    capability_payload: Dict[str, Any] = Depends(get_current_capability),
    gateway: LLMGateway = Depends(get_llm_gateway)
):
    """
    Create a chat completion using the specified model.
    
    Compatible with OpenAI API format for easy integration.
    """
    try:
        # Extract capability token from Authorization header
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        capability_token = authorization[7:]  # Remove "Bearer " prefix
        
        # Get user and tenant from capability payload
        user_id = capability_payload.get("sub", "unknown")
        tenant_id = capability_payload.get("tenant_id", "unknown")
        
        # Create internal LLM request
        llm_request = LLMRequest(
            model=request.model,
            messages=request.messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop=request.stop,
            stream=request.stream,
            functions=request.functions,
            function_call=request.function_call,
            user=request.user or user_id
        )
        
        # Process request through gateway
        result = await gateway.chat_completion(
            request=llm_request,
            capability_token=capability_token,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        # Handle streaming vs non-streaming response
        if request.stream:
            # codeql[py/stack-trace-exposure] returns LLM response stream, not error details
            return StreamingResponse(
                result,
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/plain; charset=utf-8"
                }
            )
        else:
            return JSONResponse(content=result.to_dict())
    
    except ValueError as e:
        logger.warning(f"Invalid LLM request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    except PermissionError as e:
        logger.warning(f"Permission denied for LLM request: {e}")
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.error(f"LLM request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    capability_payload: Dict[str, Any] = Depends(get_current_capability),
    gateway: LLMGateway = Depends(get_llm_gateway)
):
    """
    List available models.
    
    Returns models available to the user based on their capabilities.
    """
    try:
        # Get all available models
        models = await gateway.get_available_models()
        
        # Filter models based on user capabilities
        user_capabilities = capability_payload.get("capabilities", [])
        llm_capability = None
        
        for cap in user_capabilities:
            if cap.get("resource") == "llm":
                llm_capability = cap
                break
        
        if llm_capability:
            allowed_models = llm_capability.get("constraints", {}).get("allowed_models", [])
            if allowed_models:
                models = [model for model in models if model["id"] in allowed_models]
        
        # Format response to match OpenAI API
        formatted_models = []
        for model in models:
            formatted_models.append({
                "id": model["id"],
                "object": "model",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "owned_by": f"gt2-{model['provider']}",
                "permission": [],
                "root": model["id"],
                "parent": None,
                "max_tokens": model["max_tokens"],
                "context_window": model["context_window"],
                "capabilities": model["capabilities"],
                "supports_streaming": model["supports_streaming"],
                "supports_functions": model["supports_functions"]
            })
        
        return ModelListResponse(data=formatted_models)
    
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve models")


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    capability_payload: Dict[str, Any] = Depends(get_current_capability),
    gateway: LLMGateway = Depends(get_llm_gateway)
):
    """
    Get information about a specific model.
    """
    try:
        models = await gateway.get_available_models()
        
        # Find the requested model
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Check if user has access to this model
        user_capabilities = capability_payload.get("capabilities", [])
        llm_capability = None
        
        for cap in user_capabilities:
            if cap.get("resource") == "llm":
                llm_capability = cap
                break
        
        if llm_capability:
            allowed_models = llm_capability.get("constraints", {}).get("allowed_models", [])
            if allowed_models and model_id not in allowed_models:
                raise HTTPException(status_code=403, detail="Access to model not allowed")
        
        # Format response
        return {
            "id": model["id"],
            "object": "model",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "owned_by": f"gt2-{model['provider']}",
            "permission": [],
            "root": model["id"],
            "parent": None,
            "max_tokens": model["max_tokens"],
            "context_window": model["context_window"],
            "capabilities": model["capabilities"],
            "supports_streaming": model["supports_streaming"],
            "supports_functions": model["supports_functions"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model {model_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve model")


@router.get("/stats")
async def get_gateway_stats(
    capability_payload: Dict[str, Any] = Depends(get_current_capability),
    gateway: LLMGateway = Depends(get_llm_gateway)
):
    """
    Get LLM gateway statistics.
    
    Requires admin capability for detailed stats.
    """
    try:
        # Check if user has admin capabilities
        user_capabilities = capability_payload.get("capabilities", [])
        has_admin = any(
            cap.get("resource") == "admin" 
            for cap in user_capabilities
        )
        
        stats = await gateway.get_gateway_stats()
        
        if has_admin:
            # Return full stats for admins
            return stats
        else:
            # Return limited stats for regular users
            return {
                "total_requests": stats["total_requests"],
                "success_rate": (
                    stats["successful_requests"] / max(stats["total_requests"], 1)
                ) * 100,
                "available_models": len([
                    model for model in await gateway.get_available_models()
                ]),
                "timestamp": stats["timestamp"]
            }
    
    except Exception as e:
        logger.error(f"Failed to get gateway stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/health")
async def health_check(
    gateway: LLMGateway = Depends(get_llm_gateway)
):
    """
    Health check endpoint for the LLM gateway.
    
    Public endpoint for load balancer health checks.
    """
    try:
        health = await gateway.health_check()
        
        if health["status"] == "healthy":
            return JSONResponse(content=health, status_code=200)
        else:
            return JSONResponse(content=health, status_code=503)
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "error": "Health check failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            status_code=503
        )


# Provider-specific endpoints for debugging and monitoring

@router.post("/providers/groq/test")
async def test_groq_connection(
    capability_payload: Dict[str, Any] = Depends(get_current_capability),
    gateway: LLMGateway = Depends(get_llm_gateway)
):
    """
    Test connection to Groq API.
    
    Requires admin capability.
    """
    try:
        # Check admin capability
        user_capabilities = capability_payload.get("capabilities", [])
        has_admin = any(
            cap.get("resource") == "admin" 
            for cap in user_capabilities
        )
        
        if not has_admin:
            raise HTTPException(status_code=403, detail="Admin capability required")
        
        # Test simple request to Groq
        test_request = LLMRequest(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10,
            stream=False
        )
        
        # Use system capability token for testing
        # TODO: Generate system token or use admin token
        capability_token = "system-test-token"
        user_id = "system-test"
        tenant_id = "system"
        
        result = await gateway._process_groq_request(
            test_request, 
            "test-request-id",
            gateway.models["llama3-8b-8192"]
        )
        
        return {
            "status": "success",
            "provider": "groq",
            "response_received": bool(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Groq connection test failed: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "provider": "groq",
                "error": "Groq connection test failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            status_code=500
        )