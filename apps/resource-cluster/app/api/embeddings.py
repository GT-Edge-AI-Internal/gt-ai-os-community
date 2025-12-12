"""
Embedding Generation API Endpoints for GT 2.0 Resource Cluster

Provides OpenAI-compatible embedding API with:
- BGE-M3 model integration
- Capability-based authentication  
- Rate limiting and quota management
- Batch processing support
- Stateless operation

GT 2.0 Architecture Principles:
- Perfect Tenant Isolation: Per-request capability validation
- Zero Downtime: Stateless design, no persistent state
- Self-Contained Security: JWT capability tokens
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging
import asyncio
from datetime import datetime

from app.core.security import capability_validator, CapabilityToken
from app.api.auth import verify_capability
from app.services.embedding_service import get_embedding_service, EmbeddingService
from app.core.capability_auth import CapabilityError

router = APIRouter()
logger = logging.getLogger(__name__)


# OpenAI-compatible request/response models
class EmbeddingRequest(BaseModel):
    """OpenAI-compatible embedding request"""
    input: List[str] = Field(..., description="List of texts to embed")
    model: str = Field(default="BAAI/bge-m3", description="Embedding model name")
    encoding_format: str = Field(default="float", description="Encoding format (float)")
    dimensions: Optional[int] = Field(None, description="Number of dimensions (auto-detected)")
    user: Optional[str] = Field(None, description="User identifier")
    
    # BGE-M3 specific parameters
    instruction: Optional[str] = Field(None, description="Instruction for query/document context")
    normalize: bool = Field(True, description="Normalize embeddings to unit length")


class EmbeddingData(BaseModel):
    """Single embedding data object"""
    object: str = "embedding"
    embedding: List[float] = Field(..., description="Embedding vector")
    index: int = Field(..., description="Index of the embedding in the input")


class EmbeddingUsage(BaseModel):
    """Token usage information"""
    prompt_tokens: int = Field(..., description="Tokens in the input")
    total_tokens: int = Field(..., description="Total tokens processed")


class EmbeddingResponse(BaseModel):
    """OpenAI-compatible embedding response"""
    object: str = "list"
    data: List[EmbeddingData] = Field(..., description="List of embedding objects")
    model: str = Field(..., description="Model used for embeddings")
    usage: EmbeddingUsage = Field(..., description="Token usage information")
    
    # GT 2.0 specific metadata
    gt2_metadata: Dict[str, Any] = Field(default_factory=dict, description="GT 2.0 processing metadata")


class EmbeddingModelInfo(BaseModel):
    """Embedding model information"""
    model_name: str
    dimensions: int
    max_sequence_length: int
    max_batch_size: int
    supports_instruction: bool
    normalization_default: bool


class ServiceHealthResponse(BaseModel):
    """Service health response"""
    status: str
    service: str
    model: str
    backend_ready: bool
    last_request: Optional[str]


class BGE_M3_ConfigRequest(BaseModel):
    """BGE-M3 configuration update request"""
    is_local_mode: bool = True
    external_endpoint: Optional[str] = None


class BGE_M3_ConfigResponse(BaseModel):
    """BGE-M3 configuration response"""
    is_local_mode: bool
    current_endpoint: str
    external_endpoint: Optional[str]
    message: str


@router.post("/", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    token: CapabilityToken = Depends(verify_capability),
    x_request_id: Optional[str] = Header(None)
) -> EmbeddingResponse:
    """
    Generate embeddings for input texts using BGE-M3 model.
    
    Compatible with OpenAI Embeddings API format.
    Requires capability token with 'embeddings' permissions.
    """
    try:
        # Get embedding service
        embedding_service = get_embedding_service()
        
        # Generate embeddings
        result = await embedding_service.generate_embeddings(
            texts=request.input,
            capability_token=token.token,  # Pass raw token for verification
            instruction=request.instruction,
            request_id=x_request_id,
            normalize=request.normalize
        )
        
        # Convert to OpenAI-compatible format
        embedding_data = [
            EmbeddingData(
                embedding=embedding,
                index=i
            )
            for i, embedding in enumerate(result.embeddings)
        ]
        
        usage = EmbeddingUsage(
            prompt_tokens=result.tokens_used,
            total_tokens=result.tokens_used
        )
        
        response = EmbeddingResponse(
            data=embedding_data,
            model=result.model,
            usage=usage,
            gt2_metadata={
                "request_id": result.request_id,
                "tenant_id": result.tenant_id,
                "processing_time_ms": result.processing_time_ms,
                "dimensions": result.dimensions,
                "created_at": result.created_at
            }
        )
        
        logger.info(
            f"Generated {len(result.embeddings)} embeddings "
            f"for tenant {result.tenant_id} in {result.processing_time_ms}ms"
        )
        
        return response
        
    except CapabilityError as e:
        logger.warning(f"Capability error: {e}")
        raise HTTPException(status_code=403, detail=str(e))
        
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models", response_model=EmbeddingModelInfo)
async def get_model_info(
    token: CapabilityToken = Depends(verify_capability)
) -> EmbeddingModelInfo:
    """
    Get information about the embedding model.
    
    Requires capability token with 'embeddings' permissions.
    """
    try:
        embedding_service = get_embedding_service()
        model_info = await embedding_service.get_model_info()
        
        return EmbeddingModelInfo(**model_info)
        
    except CapabilityError as e:
        logger.warning(f"Capability error: {e}")
        raise HTTPException(status_code=403, detail=str(e))
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_service_stats(
    token: CapabilityToken = Depends(verify_capability)
) -> Dict[str, Any]:
    """
    Get embedding service statistics.
    
    Requires capability token with 'admin' permissions.
    """
    try:
        embedding_service = get_embedding_service()
        stats = await embedding_service.get_service_stats(token.token)
        
        return stats
        
    except CapabilityError as e:
        logger.warning(f"Capability error: {e}")
        raise HTTPException(status_code=403, detail=str(e))
        
    except Exception as e:
        logger.error(f"Error getting service stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=ServiceHealthResponse)
async def health_check() -> ServiceHealthResponse:
    """
    Check embedding service health.
    
    Public endpoint - no authentication required.
    """
    try:
        embedding_service = get_embedding_service()
        health = await embedding_service.health_check()
        
        return ServiceHealthResponse(**health)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Service unhealthy")


@router.post("/config/bge-m3", response_model=BGE_M3_ConfigResponse)
async def update_bge_m3_config(
    config_request: BGE_M3_ConfigRequest,
    token: CapabilityToken = Depends(verify_capability)
) -> BGE_M3_ConfigResponse:
    """
    Update BGE-M3 configuration for the embedding service.

    This allows switching between local and external endpoints at runtime.
    Requires capability token with 'admin' permissions.
    """
    try:
        # Verify admin permissions
        if not token.payload.get("admin", False):
            raise HTTPException(status_code=403, detail="Admin permissions required")

        embedding_service = get_embedding_service()

        # Update the embedding backend configuration
        backend = embedding_service.backend
        await backend.update_endpoint_config(
            is_local_mode=config_request.is_local_mode,
            external_endpoint=config_request.external_endpoint
        )

        logger.info(
            f"BGE-M3 configuration updated by {token.payload.get('tenant_id', 'unknown')}: "
            f"local_mode={config_request.is_local_mode}, "
            f"external_endpoint={config_request.external_endpoint}"
        )

        return BGE_M3_ConfigResponse(
            is_local_mode=config_request.is_local_mode,
            current_endpoint=backend.embedding_endpoint,
            external_endpoint=config_request.external_endpoint,
            message=f"BGE-M3 configuration updated to {'local' if config_request.is_local_mode else 'external'} mode"
        )

    except CapabilityError as e:
        logger.warning(f"Capability error: {e}")
        raise HTTPException(status_code=403, detail=str(e))

    except Exception as e:
        logger.error(f"Error updating BGE-M3 config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/config/bge-m3", response_model=BGE_M3_ConfigResponse)
async def get_bge_m3_config(
    token: CapabilityToken = Depends(verify_capability)
) -> BGE_M3_ConfigResponse:
    """
    Get current BGE-M3 configuration.

    Requires capability token with 'embeddings' permissions.
    """
    try:
        embedding_service = get_embedding_service()
        backend = embedding_service.backend

        # Determine if currently in local mode
        is_local_mode = "gentwo-vllm-embeddings" in backend.embedding_endpoint

        return BGE_M3_ConfigResponse(
            is_local_mode=is_local_mode,
            current_endpoint=backend.embedding_endpoint,
            external_endpoint=None,  # We don't store this currently
            message="Current BGE-M3 configuration"
        )

    except CapabilityError as e:
        logger.warning(f"Capability error: {e}")
        raise HTTPException(status_code=403, detail=str(e))

    except Exception as e:
        logger.error(f"Error getting BGE-M3 config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Legacy endpoint compatibility
@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings_legacy(
    request: EmbeddingRequest,
    token: CapabilityToken = Depends(verify_capability),
    x_request_id: Optional[str] = Header(None)
) -> EmbeddingResponse:
    """
    Legacy endpoint for embedding generation.

    Redirects to main embedding endpoint for compatibility.
    """
    return await create_embeddings(request, token, x_request_id)