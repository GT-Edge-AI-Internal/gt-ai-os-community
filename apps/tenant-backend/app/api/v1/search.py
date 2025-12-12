"""
Search API for GT 2.0 Tenant Backend

Provides hybrid vector + text search capabilities using PGVector.
Supports semantic similarity search, full-text search, and hybrid ranking.
"""

from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field
import logging
import httpx
import time

from app.core.security import get_current_user
from app.services.pgvector_search_service import (
    PGVectorSearchService,
    HybridSearchResult,
    SearchConfig,
    get_pgvector_search_service
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["search"])


async def get_user_context(
    x_tenant_domain: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Get user context from headers (for internal services).
    Handles email, UUID, and numeric ID formats for user identification.
    """
    logger.info(f"🔍 GET_USER_CONTEXT: x_tenant_domain='{x_tenant_domain}', x_user_id='{x_user_id}'")

    # Validate required headers
    if not x_tenant_domain or not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing required headers: X-Tenant-Domain and X-User-ID"
        )

    # Validate and clean inputs
    x_tenant_domain = x_tenant_domain.strip() if x_tenant_domain else None
    x_user_id = x_user_id.strip() if x_user_id else None

    if not x_tenant_domain or not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid empty headers: X-Tenant-Domain and X-User-ID cannot be empty"
        )

    logger.info(f"🔍 GET_USER_CONTEXT: Processing user_id='{x_user_id}' for tenant='{x_tenant_domain}'")

    # Use ensure_user_uuid to handle all user ID formats (email, UUID, numeric)
    from app.core.user_resolver import ensure_user_uuid
    try:
        resolved_uuid = await ensure_user_uuid(x_user_id, x_tenant_domain)
        logger.info(f"🔍 GET_USER_CONTEXT: Resolved user_id '{x_user_id}' to UUID '{resolved_uuid}'")

        # Determine original email if input was UUID
        user_email = x_user_id if "@" in x_user_id else None

        # If we don't have an email, try to get it from the database
        if not user_email:
            try:
                from app.core.postgresql_client import get_postgresql_client
                client = await get_postgresql_client()
                async with client.get_connection() as conn:
                    tenant_schema = f"tenant_{x_tenant_domain.replace('.', '_').replace('-', '_')}"
                    user_row = await conn.fetchrow(
                        f"SELECT email FROM {tenant_schema}.users WHERE id = $1",
                        resolved_uuid
                    )
                    if user_row:
                        user_email = user_row['email']
                    else:
                        # Fallback to UUID as email for backward compatibility
                        user_email = resolved_uuid
                        logger.warning(f"Could not find email for UUID {resolved_uuid}, using UUID as email")
            except Exception as e:
                logger.warning(f"Failed to lookup email for UUID {resolved_uuid}: {e}")
                user_email = resolved_uuid

        context = {
            "tenant_domain": x_tenant_domain,
            "id": resolved_uuid,
            "sub": resolved_uuid,
            "email": user_email,
            "user_type": "internal_service"
        }
        logger.info(f"🔍 GET_USER_CONTEXT: Returning context: {context}")
        return context

    except ValueError as e:
        logger.error(f"🔍 GET_USER_CONTEXT ERROR: Failed to resolve user_id '{x_user_id}': {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user identifier '{x_user_id}': {str(e)}"
        )
    except Exception as e:
        logger.error(f"🔍 GET_USER_CONTEXT ERROR: Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal error processing user context"
        )


# Request/Response Models

class SearchRequest(BaseModel):
    """Request for hybrid search"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    dataset_ids: Optional[List[str]] = Field(None, description="Optional dataset IDs to search within")
    search_type: str = Field("hybrid", description="Search type: hybrid, vector, text")
    max_results: int = Field(10, ge=1, le=200, description="Maximum results to return")

    # Advanced search parameters
    vector_weight: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Weight for vector similarity")
    text_weight: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="Weight for text relevance")
    min_similarity: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="Minimum similarity threshold")
    rerank_results: Optional[bool] = Field(True, description="Apply result re-ranking")


class SimilarChunksRequest(BaseModel):
    """Request for finding similar chunks"""
    chunk_id: str = Field(..., description="Reference chunk ID")
    similarity_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity")
    max_results: int = Field(5, ge=1, le=20, description="Maximum results")
    exclude_same_document: bool = Field(True, description="Exclude chunks from same document")


class SearchResultResponse(BaseModel):
    """Individual search result"""
    chunk_id: str
    document_id: str
    dataset_id: Optional[str]
    text: str
    metadata: Dict[str, Any]
    vector_similarity: float
    text_relevance: float
    hybrid_score: float
    rank: int


class SearchResponse(BaseModel):
    """Search response with results and metadata"""
    query: str
    search_type: str
    total_results: int
    results: List[SearchResultResponse]
    search_time_ms: float
    config: Dict[str, Any]


class ConversationSearchRequest(BaseModel):
    """Request for searching conversation history"""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    days_back: Optional[int] = Field(30, ge=1, le=365, description="Number of days back to search")
    max_results: Optional[int] = Field(5, ge=1, le=200, description="Maximum results to return")
    agent_filter: Optional[List[str]] = Field(None, description="Filter by agent names/IDs")
    include_user_messages: Optional[bool] = Field(True, description="Include user messages in results")


class DocumentChunksResponse(BaseModel):
    """Response for document chunks"""
    document_id: str
    total_chunks: int
    chunks: List[Dict[str, Any]]


# Search Endpoints

@router.post("/", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    user_context: Dict[str, Any] = Depends(get_user_context)
):
    """
    Perform hybrid search across user's documents and datasets.

    Combines vector similarity search with full-text search for optimal results.
    """
    try:
        import time
        start_time = time.time()

        logger.info(f"🔍 SEARCH_API START: request={request.dict()}")
        logger.info(f"🔍 SEARCH_API: user_context={user_context}")

        # Extract tenant info
        tenant_domain = user_context.get("tenant_domain", "test")
        user_id = user_context.get("id", user_context.get("sub", None))
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Missing user ID in authentication context"
            )
        logger.info(f"🔍 SEARCH_API: extracted tenant_domain='{tenant_domain}', user_id='{user_id}'")

        # Validate weights sum to 1.0 for hybrid search
        if request.search_type == "hybrid":
            total_weight = (request.vector_weight or 0.7) + (request.text_weight or 0.3)
            if abs(total_weight - 1.0) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail="Vector weight and text weight must sum to 1.0"
                )

        # Initialize search service
        logger.info(f"🔍 SEARCH_API: Initializing search service with tenant_id='{tenant_domain}', user_id='{user_id}'")
        search_service = get_pgvector_search_service(
            tenant_id=tenant_domain,
            user_id=user_id
        )

        # Configure search parameters
        config = SearchConfig(
            vector_weight=request.vector_weight or 0.7,
            text_weight=request.text_weight or 0.3,
            min_vector_similarity=request.min_similarity or 0.3,
            min_text_relevance=0.01,  # Fix: Use appropriate ts_rank_cd threshold
            max_results=request.max_results,
            rerank_results=request.rerank_results or True
        )
        logger.info(f"🔍 SEARCH_API: Search config created: {config.__dict__}")

        # Execute search based on type
        results = []
        logger.info(f"🔍 SEARCH_API: Executing {request.search_type} search")
        if request.search_type == "hybrid":
            logger.info(f"🔍 SEARCH_API: Calling hybrid_search with query='{request.query}', user_id='{user_id}', dataset_ids={request.dataset_ids}")
            results = await search_service.hybrid_search(
                query=request.query,
                user_id=user_id,
                dataset_ids=request.dataset_ids,
                config=config,
                limit=request.max_results
            )
            logger.info(f"🔍 SEARCH_API: Hybrid search returned {len(results)} results")
        elif request.search_type == "vector":
            # Generate query embedding first
            query_embedding = await search_service._generate_query_embedding(
                request.query,
                user_id
            )
            results = await search_service.vector_similarity_search(
                query_embedding=query_embedding,
                user_id=user_id,
                dataset_ids=request.dataset_ids,
                similarity_threshold=config.min_vector_similarity,
                limit=request.max_results
            )
        elif request.search_type == "text":
            results = await search_service.full_text_search(
                query=request.query,
                user_id=user_id,
                dataset_ids=request.dataset_ids,
                limit=request.max_results
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid search_type. Must be 'hybrid', 'vector', or 'text'"
            )

        # Calculate search time
        search_time_ms = (time.time() - start_time) * 1000

        # Convert results to response format
        result_responses = [
            SearchResultResponse(
                chunk_id=str(result.chunk_id),
                document_id=str(result.document_id),
                dataset_id=str(result.dataset_id) if result.dataset_id else None,
                text=result.text,
                metadata=result.metadata if isinstance(result.metadata, dict) else {},
                vector_similarity=result.vector_similarity,
                text_relevance=result.text_relevance,
                hybrid_score=result.hybrid_score,
                rank=result.rank
            )
            for result in results
        ]

        logger.info(
            f"Search completed: query='{request.query}', "
            f"type={request.search_type}, results={len(results)}, "
            f"time={search_time_ms:.1f}ms"
        )

        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            total_results=len(results),
            results=result_responses,
            search_time_ms=search_time_ms,
            config={
                "vector_weight": config.vector_weight,
                "text_weight": config.text_weight,
                "min_similarity": config.min_vector_similarity,
                "rerank_enabled": config.rerank_results
            }
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/documents/{document_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    document_id: str,
    include_embeddings: bool = Query(False, description="Include embedding vectors"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all chunks for a specific document.

    Useful for understanding document structure and chunk boundaries.
    """
    try:
        # Extract tenant info
        tenant_domain = user_context.get("tenant_domain", "test")
        user_id = user_context.get("id", user_context.get("sub", None))
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Missing user ID in authentication context"
            )

        search_service = get_pgvector_search_service(
            tenant_id=tenant_domain,
            user_id=user_id
        )

        chunks = await search_service.get_document_chunks(
            document_id=document_id,
            user_id=user_id,
            include_embeddings=include_embeddings
        )

        return DocumentChunksResponse(
            document_id=document_id,
            total_chunks=len(chunks),
            chunks=chunks
        )

    except Exception as e:
        logger.error(f"Failed to get document chunks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/similar-chunks", response_model=SearchResponse)
async def find_similar_chunks(
    request: SimilarChunksRequest,
    user_context: Dict[str, Any] = Depends(get_user_context)
):
    """
    Find chunks similar to a reference chunk.

    Useful for exploring related content and building context.
    """
    try:
        import time
        start_time = time.time()

        # Extract tenant info
        tenant_domain = user_context.get("tenant_domain", "test")
        user_id = user_context.get("id", user_context.get("sub", None))
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Missing user ID in authentication context"
            )

        search_service = get_pgvector_search_service(
            tenant_id=tenant_domain,
            user_id=user_id
        )

        results = await search_service.search_similar_chunks(
            chunk_id=request.chunk_id,
            user_id=user_id,
            similarity_threshold=request.similarity_threshold,
            limit=request.max_results,
            exclude_same_document=request.exclude_same_document
        )

        search_time_ms = (time.time() - start_time) * 1000

        # Convert results to response format
        result_responses = [
            SearchResultResponse(
                chunk_id=str(result.chunk_id),
                document_id=str(result.document_id),
                dataset_id=str(result.dataset_id) if result.dataset_id else None,
                text=result.text,
                metadata=result.metadata if isinstance(result.metadata, dict) else {},
                vector_similarity=result.vector_similarity,
                text_relevance=result.text_relevance,
                hybrid_score=result.hybrid_score,
                rank=result.rank
            )
            for result in results
        ]

        logger.info(f"Similar chunks search: found {len(results)} results in {search_time_ms:.1f}ms")

        return SearchResponse(
            query=f"Similar to chunk {request.chunk_id}",
            search_type="vector_similarity",
            total_results=len(results),
            results=result_responses,
            search_time_ms=search_time_ms,
            config={
                "similarity_threshold": request.similarity_threshold,
                "exclude_same_document": request.exclude_same_document
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Similar chunks search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


class DocumentSearchRequest(BaseModel):
    """Request for searching specific documents"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    document_ids: List[str] = Field(..., description="Document IDs to search within")
    search_type: str = Field("hybrid", description="Search type: hybrid, vector, text")
    max_results: int = Field(5, ge=1, le=20, description="Maximum results per document")
    min_similarity: Optional[float] = Field(0.6, ge=0.0, le=1.0, description="Minimum similarity threshold")


@router.post("/documents", response_model=SearchResponse)
async def search_documents_specific(
    request: DocumentSearchRequest,
    user_context: Dict[str, Any] = Depends(get_user_context)
):
    """
    Search within specific documents for relevant chunks.

    Used by MCP RAG server for document-specific queries.
    """
    try:
        import time
        start_time = time.time()

        # Extract tenant info
        tenant_domain = user_context.get("tenant_domain", "test")
        user_id = user_context.get("id", user_context.get("sub", None))
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Missing user ID in authentication context"
            )

        # Initialize search service
        search_service = get_pgvector_search_service(
            tenant_id=tenant_domain,
            user_id=user_id
        )

        # Configure search for documents
        config = SearchConfig(
            vector_weight=0.7,
            text_weight=0.3,
            min_vector_similarity=request.min_similarity or 0.6,
            min_text_relevance=0.1,
            max_results=request.max_results,
            rerank_results=True
        )

        # Execute search with document filter
        # First resolve dataset IDs from document IDs to satisfy security constraints
        dataset_ids = await search_service.get_dataset_ids_from_documents(request.document_ids, user_id)
        if not dataset_ids:
            logger.warning(f"No dataset IDs found for documents: {request.document_ids}")
            return SearchResponse(
                query=request.query,
                search_type=request.search_type,
                total_results=0,
                results=[],
                search_time_ms=0.0,
                config={}
            )

        results = []
        if request.search_type == "hybrid":
            results = await search_service.hybrid_search(
                query=request.query,
                user_id=user_id,
                dataset_ids=dataset_ids,  # Use resolved dataset IDs
                config=config,
                limit=request.max_results * len(request.document_ids)  # Allow more results for filtering
            )
            # Filter results to only include specified documents
            results = [r for r in results if r.document_id in request.document_ids][:request.max_results]

        elif request.search_type == "vector":
            query_embedding = await search_service._generate_query_embedding(
                request.query,
                user_id
            )
            results = await search_service.vector_similarity_search(
                query_embedding=query_embedding,
                user_id=user_id,
                dataset_ids=dataset_ids,  # Use resolved dataset IDs
                similarity_threshold=config.min_vector_similarity,
                limit=request.max_results * len(request.document_ids)
            )
            # Filter by document IDs
            results = [r for r in results if r.document_id in request.document_ids][:request.max_results]

        elif request.search_type == "text":
            results = await search_service.full_text_search(
                query=request.query,
                user_id=user_id,
                dataset_ids=dataset_ids,  # Use resolved dataset IDs
                limit=request.max_results * len(request.document_ids)
            )
            # Filter by document IDs
            results = [r for r in results if r.document_id in request.document_ids][:request.max_results]

        search_time_ms = (time.time() - start_time) * 1000

        # Convert results to response format
        result_responses = [
            SearchResultResponse(
                chunk_id=str(result.chunk_id),
                document_id=str(result.document_id),
                dataset_id=str(result.dataset_id) if result.dataset_id else None,
                text=result.text,
                metadata=result.metadata if isinstance(result.metadata, dict) else {},
                vector_similarity=result.vector_similarity,
                text_relevance=result.text_relevance,
                hybrid_score=result.hybrid_score,
                rank=result.rank
            )
            for result in results
        ]

        logger.info(
            f"Document search completed: query='{request.query}', "
            f"documents={len(request.document_ids)}, results={len(results)}, "
            f"time={search_time_ms:.1f}ms"
        )

        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            total_results=len(results),
            results=result_responses,
            search_time_ms=search_time_ms,
            config={
                "document_ids": request.document_ids,
                "min_similarity": request.min_similarity,
                "max_results_per_document": request.max_results
            }
        )

    except Exception as e:
        logger.error(f"Document search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def search_health_check(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Health check for search service functionality.

    Verifies that PGVector extension and search capabilities are working.
    """
    try:
        # Extract tenant info
        tenant_domain = user_context.get("tenant_domain", "test")
        user_id = user_context.get("id", user_context.get("sub", None))
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Missing user ID in authentication context"
            )

        search_service = get_pgvector_search_service(
            tenant_id=tenant_domain,
            user_id=user_id
        )

        # Test basic connectivity and PGVector functionality
        from app.core.postgresql_client import get_postgresql_client
        client = await get_postgresql_client()
        async with client.get_connection() as conn:
            # Test PGVector extension
            result = await conn.fetchval("SELECT 1 + 1")
            if result != 2:
                raise Exception("Basic database connectivity failed")

            # Test PGVector extension (this will fail if extension is not installed)
            await conn.fetchval("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")

        return {
            "status": "healthy",
            "tenant_id": tenant_domain,
            "pgvector_available": True,
            "search_service": "operational"
        }

    except Exception as e:
        logger.error(f"Search health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": "Search service health check failed",
            "tenant_id": tenant_domain,
            "pgvector_available": False,
            "search_service": "error"
        }


@router.post("/conversations")
async def search_conversations(
    request: ConversationSearchRequest,
    current_user: Dict[str, Any] = Depends(get_user_context),
    x_tenant_domain: Optional[str] = Header(None, alias="X-Tenant-Domain"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Search through conversation history using MCP conversation server.

    Used by both external clients and internal MCP tools for conversation search.
    """
    try:
        # Use same user resolution pattern as document search
        tenant_domain = current_user.get("tenant_domain") or x_tenant_domain
        user_id = current_user.get("id") or current_user.get("sub") or x_user_id

        if not tenant_domain or not user_id:
            raise HTTPException(
                status_code=400,
                detail="Missing tenant_domain or user_id in request context"
            )

        logger.info(f"🔍 Conversation search: query='{request.query}', user={user_id}, tenant={tenant_domain}")

        # Get resource cluster URL
        settings = get_settings()
        mcp_base_url = getattr(settings, 'resource_cluster_url', 'http://gentwo-resource-backend:8000')

        # Build request payload for MCP execution
        request_payload = {
            "server_id": "conversation_server",
            "tool_name": "search_conversations",
            "parameters": {
                "query": request.query,
                "days_back": request.days_back or 30,
                "max_results": request.max_results or 5,
                "agent_filter": request.agent_filter,
                "include_user_messages": request.include_user_messages
            },
            "tenant_domain": tenant_domain,
            "user_id": user_id
        }

        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"🌐 Making MCP request to: {mcp_base_url}/api/v1/mcp/execute")

            response = await client.post(
                f"{mcp_base_url}/api/v1/mcp/execute",
                json=request_payload
            )

            execution_time_ms = (time.time() - start_time) * 1000
            logger.info(f"📊 MCP response: {response.status_code} ({execution_time_ms:.1f}ms)")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Conversation search successful ({execution_time_ms:.1f}ms)")
                return result
            else:
                error_text = response.text
                error_msg = f"MCP conversation search failed: {response.status_code} - {error_text}"
                logger.error(f"❌ {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Conversation search endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")