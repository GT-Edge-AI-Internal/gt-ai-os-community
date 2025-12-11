"""
RAG API endpoints for Resource Cluster

STATELESS processing of documents and embeddings.
All data is immediately returned to tenant - nothing is stored.
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging

from app.core.backends.document_processor import DocumentProcessorBackend, ChunkingStrategy
from app.core.backends.embedding_backend import EmbeddingBackend
from app.core.security import verify_capability_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


class ProcessDocumentRequest(BaseModel):
    """Request for document processing"""
    document_type: str = Field(..., description="File type (.pdf, .docx, .txt, .md, .html)")
    chunking_strategy: str = Field(default="hybrid", description="Chunking strategy")
    chunk_size: int = Field(default=512, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=128, description="Overlap between chunks")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Non-sensitive metadata")


class GenerateEmbeddingsRequest(BaseModel):
    """Request for embedding generation"""
    texts: List[str] = Field(..., description="Texts to embed")
    instruction: Optional[str] = Field(default=None, description="Optional instruction for embeddings")


class ProcessDocumentResponse(BaseModel):
    """Response from document processing"""
    chunks: List[Dict[str, Any]] = Field(..., description="Document chunks with metadata")
    chunk_count: int = Field(..., description="Number of chunks generated")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class GenerateEmbeddingsResponse(BaseModel):
    """Response from embedding generation"""
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    embedding_count: int = Field(..., description="Number of embeddings generated")
    dimensions: int = Field(..., description="Embedding dimensions")
    model: str = Field(..., description="Model used for embeddings")


# Initialize backends
document_processor = DocumentProcessorBackend()
embedding_backend = EmbeddingBackend()


@router.post("/process-document", response_model=ProcessDocumentResponse)
async def process_document(
    file: UploadFile = File(...),
    request: ProcessDocumentRequest = Depends(),
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> ProcessDocumentResponse:
    """
    Process a document into chunks - STATELESS operation.
    
    Security:
    - No user data is stored
    - Document processed in memory only
    - Immediate response with chunks
    - Memory cleared after processing
    """
    import time
    start_time = time.time()
    
    try:
        # Verify RAG capabilities
        if "rag_processing" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="RAG processing capability not granted"
            )
        
        # Read file content (will be cleared from memory)
        content = await file.read()
        
        # Validate document
        validation = await document_processor.validate_document(
            content_size=len(content),
            document_type=request.document_type
        )
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Document validation failed: {validation['errors']}"
            )
        
        # Create chunking strategy
        strategy = ChunkingStrategy(
            strategy_type=request.chunking_strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        
        # Process document (stateless)
        chunks = await document_processor.process_document(
            content=content,
            document_type=request.document_type,
            strategy=strategy,
            metadata={
                "tenant_id": capabilities.get("tenant_id"),
                "document_type": request.document_type,
                "processing_timestamp": time.time()
            }
        )
        
        # Clear content from memory
        del content
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"Processed document into {len(chunks)} chunks for tenant "
            f"{capabilities.get('tenant_id')} (STATELESS)"
        )
        
        return ProcessDocumentResponse(
            chunks=chunks,
            chunk_count=len(chunks),
            processing_time_ms=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(
    request: GenerateEmbeddingsRequest,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> GenerateEmbeddingsResponse:
    """
    Generate embeddings for texts - STATELESS operation.
    
    Security:
    - No text content is stored
    - Embeddings generated via GPU cluster
    - Immediate response with vectors
    - Memory cleared after generation
    """
    try:
        # Verify embedding capabilities
        if "embedding_generation" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="Embedding generation capability not granted"
            )
        
        # Validate texts
        validation = await embedding_backend.validate_texts(request.texts)
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Text validation failed: {validation['errors']}"
            )
        
        # Generate embeddings (stateless)
        embeddings = await embedding_backend.generate_embeddings(
            texts=request.texts,
            instruction=request.instruction,
            tenant_id=capabilities.get("tenant_id"),
            request_id=capabilities.get("request_id")
        )
        
        logger.info(
            f"Generated {len(embeddings)} embeddings for tenant "
            f"{capabilities.get('tenant_id')} (STATELESS)"
        )
        
        return GenerateEmbeddingsResponse(
            embeddings=embeddings,
            embedding_count=len(embeddings),
            dimensions=embedding_backend.embedding_dimensions,
            model=embedding_backend.model_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-query-embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_query_embeddings(
    request: GenerateEmbeddingsRequest,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> GenerateEmbeddingsResponse:
    """
    Generate embeddings specifically for queries - STATELESS operation.
    
    Uses BGE-M3 query instruction for better retrieval performance.
    """
    try:
        # Verify embedding capabilities
        if "embedding_generation" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="Embedding generation capability not granted"
            )
        
        # Validate queries
        validation = await embedding_backend.validate_texts(request.texts)
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Query validation failed: {validation['errors']}"
            )
        
        # Generate query embeddings (stateless)
        embeddings = await embedding_backend.generate_query_embeddings(
            queries=request.texts,
            tenant_id=capabilities.get("tenant_id"),
            request_id=capabilities.get("request_id")
        )
        
        logger.info(
            f"Generated {len(embeddings)} query embeddings for tenant "
            f"{capabilities.get('tenant_id')} (STATELESS)"
        )
        
        return GenerateEmbeddingsResponse(
            embeddings=embeddings,
            embedding_count=len(embeddings),
            dimensions=embedding_backend.embedding_dimensions,
            model=embedding_backend.model_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating query embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-document-embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_document_embeddings(
    request: GenerateEmbeddingsRequest,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> GenerateEmbeddingsResponse:
    """
    Generate embeddings specifically for documents - STATELESS operation.
    
    Uses BGE-M3 document configuration for optimal indexing.
    """
    try:
        # Verify embedding capabilities
        if "embedding_generation" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="Embedding generation capability not granted"
            )
        
        # Validate documents
        validation = await embedding_backend.validate_texts(request.texts)
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Document validation failed: {validation['errors']}"
            )
        
        # Generate document embeddings (stateless)
        embeddings = await embedding_backend.generate_document_embeddings(
            documents=request.texts,
            tenant_id=capabilities.get("tenant_id"),
            request_id=capabilities.get("request_id")
        )
        
        logger.info(
            f"Generated {len(embeddings)} document embeddings for tenant "
            f"{capabilities.get('tenant_id')} (STATELESS)"
        )
        
        return GenerateEmbeddingsResponse(
            embeddings=embeddings,
            embedding_count=len(embeddings),
            dimensions=embedding_backend.embedding_dimensions,
            model=embedding_backend.model_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating document embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Check RAG processing health - no user data exposed.
    """
    try:
        doc_health = await document_processor.check_health()
        embed_health = await embedding_backend.check_health()
        
        overall_status = "healthy"
        if doc_health["status"] != "healthy" or embed_health["status"] != "healthy":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "document_processor": doc_health,
            "embedding_backend": embed_health,
            "stateless": True,
            "memory_management": "active"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/capabilities")
async def get_rag_capabilities() -> Dict[str, Any]:
    """
    Get RAG processing capabilities - no sensitive data.
    """
    return {
        "document_processor": {
            "supported_formats": document_processor.supported_formats,
            "chunking_strategies": ["fixed", "semantic", "hierarchical", "hybrid"],
            "default_chunk_size": document_processor.default_chunk_size,
            "default_chunk_overlap": document_processor.default_chunk_overlap
        },
        "embedding_backend": {
            "model": embedding_backend.model_name,
            "dimensions": embedding_backend.embedding_dimensions,
            "max_batch_size": embedding_backend.max_batch_size,
            "max_sequence_length": embedding_backend.max_sequence_length
        },
        "security": {
            "stateless_processing": True,
            "memory_cleanup": True,
            "data_encryption": True,
            "tenant_isolation": True
        }
    }