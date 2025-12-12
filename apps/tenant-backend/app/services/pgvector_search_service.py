"""
PGVector Hybrid Search Service for GT 2.0 Tenant Backend

Provides unified vector similarity search + full-text search using PostgreSQL
with PGVector extension. Replaces ChromaDB for better performance and consistency.

Features:
- Vector similarity search using PGVector
- Full-text search using PostgreSQL built-in features
- Hybrid scoring combining both approaches
- Perfect tenant isolation using RLS
- Zero-downtime MVCC operations
"""

import logging
import asyncio
import json
import uuid as uuid_lib
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import uuid

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_

from app.core.postgresql_client import get_postgresql_client
from app.core.config import get_settings
from app.services.embedding_client import BGE_M3_EmbeddingClient

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class HybridSearchResult:
    """Result from hybrid vector + text search"""
    chunk_id: str
    document_id: str
    dataset_id: Optional[str]
    text: str
    metadata: Dict[str, Any]
    vector_similarity: float
    text_relevance: float
    hybrid_score: float
    rank: int


@dataclass
class SearchConfig:
    """Configuration for hybrid search behavior"""
    vector_weight: float = 0.7
    text_weight: float = 0.3
    min_vector_similarity: float = 0.3
    min_text_relevance: float = 0.01
    max_results: int = 100
    rerank_results: bool = True


class PGVectorSearchService:
    """
    Hybrid search service using PostgreSQL + PGVector.

    GT 2.0 Principles:
    - Perfect tenant isolation via RLS policies
    - Zero downtime MVCC operations
    - Real implementation (no mocks)
    - Operational elegance through unified storage
    """

    def __init__(self, tenant_id: str, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.settings = get_settings()
        self.embedding_client = BGE_M3_EmbeddingClient()

        # Schema naming for tenant isolation
        self.schema_name = self.settings.postgres_schema

        logger.info(f"PGVector search service initialized for tenant {tenant_id}")

    async def hybrid_search(
        self,
        query: str,
        user_id: str,
        dataset_ids: Optional[List[str]] = None,
        config: Optional[SearchConfig] = None,
        limit: int = 10
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid vector + text search across user's documents.

        Args:
            query: Search query text
            user_id: User performing search (for RLS)
            dataset_ids: Optional list of dataset IDs to search
            config: Search configuration parameters
            limit: Maximum results to return

        Returns:
            List of ranked search results
        """
        if config is None:
            config = SearchConfig()

        try:
            logger.info(f"🔍 HYBRID_SEARCH START: query='{query}', user_id='{user_id}', dataset_ids={dataset_ids}")
            logger.info(f"🔍 HYBRID_SEARCH CONFIG: vector_weight={config.vector_weight}, text_weight={config.text_weight}, min_similarity={config.min_vector_similarity}")

            # Generate query embedding via resource cluster
            logger.info(f"🔍 HYBRID_SEARCH: Generating embedding for query '{query}' with user_id '{user_id}'")
            query_embedding = await self._generate_query_embedding(query, user_id)
            logger.info(f"🔍 HYBRID_SEARCH: Generated embedding with {len(query_embedding)} dimensions")

            # Execute hybrid search query
            logger.info(f"🔍 HYBRID_SEARCH: Executing hybrid query with user_id='{user_id}', dataset_ids={dataset_ids}")
            results = await self._execute_hybrid_query(
                query=query,
                query_embedding=query_embedding,
                user_id=user_id,
                dataset_ids=dataset_ids,
                config=config,
                limit=limit
            )
            logger.info(f"🔍 HYBRID_SEARCH: Query returned {len(results)} raw results")

            # Apply re-ranking if enabled
            if config.rerank_results and len(results) > 1:
                logger.info(f"🔍 HYBRID_SEARCH: Applying re-ranking to {len(results)} results")
                results = await self._rerank_results(results, query, config)
                logger.info(f"🔍 HYBRID_SEARCH: Re-ranking complete, final result count: {len(results)}")

            logger.info(f"🔍 HYBRID_SEARCH COMPLETE: Returned {len(results)} results for user {user_id}")
            return results

        except Exception as e:
            logger.error(f"🔍 HYBRID_SEARCH ERROR: {e}")
            logger.exception("Full hybrid search error traceback:")
            raise

    async def vector_similarity_search(
        self,
        query_embedding: List[float],
        user_id: str,
        dataset_ids: Optional[List[str]] = None,
        similarity_threshold: float = 0.3,
        limit: int = 10
    ) -> List[HybridSearchResult]:
        """
        Pure vector similarity search using PGVector.

        Args:
            query_embedding: Pre-computed query embedding
            user_id: User performing search
            dataset_ids: Optional dataset filter
            similarity_threshold: Minimum cosine similarity
            limit: Maximum results

        Returns:
            Vector similarity results
        """
        try:
            logger.info(f"🔍 VECTOR_SEARCH START: user_id='{user_id}', dataset_ids={dataset_ids}, threshold={similarity_threshold}")

            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                logger.info(f"🔍 VECTOR_SEARCH: Got DB connection, resolving user UUID from '{user_id}'")

                # Resolve user UUID first
                resolved_user_id = await self._resolve_user_uuid(conn, user_id)
                logger.info(f"🔍 VECTOR_SEARCH: Resolved user_id '{user_id}' to UUID '{resolved_user_id}'")

                # RLS context removed - using schema-level isolation instead
                logger.info(f"🔍 VECTOR_SEARCH: Using resolved UUID '{resolved_user_id}' for query parameters")

                # Build query with dataset filtering
                dataset_filter = ""
                params = [query_embedding, similarity_threshold, limit]

                if dataset_ids:
                    logger.info(f"🔍 VECTOR_SEARCH: Adding dataset filter for datasets: {dataset_ids}")
                    dataset_start_idx = 4  # Start after query_embedding, similarity_threshold, limit
                    placeholders = ",".join(f"${dataset_start_idx + i}" for i in range(len(dataset_ids)))
                    dataset_filter = f"AND dataset_id = ANY(ARRAY[{placeholders}]::uuid[])"
                    params.extend(dataset_ids)
                    logger.info(f"🔍 VECTOR_SEARCH: Dataset filter SQL: {dataset_filter}")
                else:
                    logger.error(f"🔍 VECTOR_SEARCH: SECURITY ERROR - Dataset IDs are required for search operations")
                    raise ValueError("Dataset IDs are required for vector search operations. This could mean the agent has no datasets configured or dataset access control failed.")

                query_sql = f"""
                    SELECT
                        id as chunk_id,
                        document_id,
                        dataset_id,
                        content as text,
                        metadata as chunk_metadata,
                        1 - (embedding <=> $1::vector) as similarity,
                        0.0 as text_relevance,
                        1 - (embedding <=> $1::vector) as hybrid_score,
                        ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) as rank
                    FROM {self.schema_name}.document_chunks
                    WHERE 1 - (embedding <=> $1::vector) >= $2
                        {dataset_filter}
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """

                logger.info(f"🔍 VECTOR_SEARCH: Executing SQL query with {len(params)} parameters")
                logger.info(f"🔍 VECTOR_SEARCH: SQL: {query_sql}")
                logger.info(f"🔍 VECTOR_SEARCH: Params types: embedding={type(query_embedding)} (len={len(query_embedding)}), threshold={type(similarity_threshold)}, limit={type(limit)}")
                if dataset_ids:
                    logger.info(f"🔍 VECTOR_SEARCH: Dataset params: {[type(d) for d in dataset_ids]}")

                rows = await conn.fetch(query_sql, *params)
                logger.info(f"🔍 VECTOR_SEARCH: Query executed successfully, got {len(rows)} rows")

                results = [
                    HybridSearchResult(
                        chunk_id=row['chunk_id'],
                        document_id=row['document_id'],
                        dataset_id=row['dataset_id'],
                        text=row['text'],
                        metadata=row['metadata'] if row['metadata'] else {},
                        vector_similarity=float(row['similarity']),
                        text_relevance=0.0,
                        hybrid_score=float(row['hybrid_score']),
                        rank=row['rank']
                    )
                    for row in rows
                ]

                logger.info(f"Vector search returned {len(results)} results")
                return results

        except Exception as e:
            logger.error(f"Vector similarity search failed: {e}")
            raise

    async def full_text_search(
        self,
        query: str,
        user_id: str,
        dataset_ids: Optional[List[str]] = None,
        language: str = 'english',
        limit: int = 10
    ) -> List[HybridSearchResult]:
        """
        Full-text search using PostgreSQL's built-in features.

        Args:
            query: Text query
            user_id: User performing search
            dataset_ids: Optional dataset filter
            language: Text search language configuration
            limit: Maximum results

        Returns:
            Text relevance results
        """
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                # Resolve user UUID first
                resolved_user_id = await self._resolve_user_uuid(conn, user_id)
                # RLS context removed - using schema-level isolation instead

                # Build dataset filter - REQUIRE dataset_ids for security
                dataset_filter = ""
                params = [query, limit, resolved_user_id]
                if dataset_ids:
                    placeholders = ",".join(f"${i+4}" for i in range(len(dataset_ids)))
                    dataset_filter = f"AND dataset_id = ANY(ARRAY[{placeholders}]::uuid[])"
                    params.extend(dataset_ids)
                else:
                    logger.error(f"🔍 FULL_TEXT_SEARCH: SECURITY ERROR - Dataset IDs are required for search operations")
                    raise ValueError("Dataset IDs are required for full-text search operations. This could mean the agent has no datasets configured or dataset access control failed.")

                query_sql = f"""
                    SELECT
                        chunk_id,
                        document_id,
                        dataset_id,
                        content as text,
                        chunk_metadata as metadata,
                        0.0 as similarity,
                        ts_rank_cd(
                            to_tsvector('{language}', content),
                            plainto_tsquery('{language}', $1)
                        ) as text_relevance,
                        ts_rank_cd(
                            to_tsvector('{language}', content),
                            plainto_tsquery('{language}', $1)
                        ) as hybrid_score,
                        ROW_NUMBER() OVER (
                            ORDER BY ts_rank_cd(
                                to_tsvector('{language}', content),
                                plainto_tsquery('{language}', $1)
                            ) DESC
                        ) as rank
                    FROM {self.schema_name}.document_chunks
                    WHERE user_id = $3::uuid
                        AND to_tsvector('{language}', content) @@ plainto_tsquery('{language}', $1)
                        {dataset_filter}
                    ORDER BY text_relevance DESC
                    LIMIT $2
                """

                rows = await conn.fetch(query_sql, *params)

                results = [
                    HybridSearchResult(
                        chunk_id=row['chunk_id'],
                        document_id=row['document_id'],
                        dataset_id=row['dataset_id'],
                        text=row['text'],
                        metadata=row['metadata'] if row['metadata'] else {},
                        vector_similarity=0.0,
                        text_relevance=float(row['text_relevance']),
                        hybrid_score=float(row['hybrid_score']),
                        rank=row['rank']
                    )
                    for row in rows
                ]

                logger.info(f"Full-text search returned {len(results)} results")
                return results

        except Exception as e:
            logger.error(f"Full-text search failed: {e}")
            raise

    async def get_document_chunks(
        self,
        document_id: str,
        user_id: str,
        include_embeddings: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all chunks for a specific document.

        Args:
            document_id: Target document ID
            user_id: User making request
            include_embeddings: Whether to include embedding vectors

        Returns:
            List of document chunks with metadata
        """
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                # Resolve user UUID first
                resolved_user_id = await self._resolve_user_uuid(conn, user_id)
                # RLS context removed - using schema-level isolation instead

                select_fields = [
                    "id as chunk_id", "document_id", "dataset_id", "chunk_index",
                    "content", "metadata as chunk_metadata", "created_at"
                ]

                if include_embeddings:
                    select_fields.append("embedding")

                query_sql = f"""
                    SELECT {', '.join(select_fields)}
                    FROM {self.schema_name}.document_chunks
                    WHERE document_id = $1
                        AND user_id = $2::uuid
                    ORDER BY chunk_index
                """

                rows = await conn.fetch(query_sql, document_id, resolved_user_id)

                chunks = []
                for row in rows:
                    chunk = {
                        'chunk_id': row['chunk_id'],
                        'document_id': row['document_id'],
                        'dataset_id': row['dataset_id'],
                        'chunk_index': row['chunk_index'],
                        'content': row['content'],
                        'metadata': row['chunk_metadata'] if row['chunk_metadata'] else {},
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    }

                    if include_embeddings:
                        chunk['embedding'] = list(row['embedding']) if row['embedding'] else []

                    chunks.append(chunk)

                logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")
                return chunks

        except Exception as e:
            logger.error(f"Failed to get document chunks: {e}")
            raise

    async def search_similar_chunks(
        self,
        chunk_id: str,
        user_id: str,
        similarity_threshold: float = 0.5,
        limit: int = 5,
        exclude_same_document: bool = True
    ) -> List[HybridSearchResult]:
        """
        Find chunks similar to a given chunk.

        Args:
            chunk_id: Reference chunk ID
            user_id: User making request
            similarity_threshold: Minimum similarity threshold
            limit: Maximum results
            exclude_same_document: Whether to exclude chunks from same document

        Returns:
            Similar chunks ranked by similarity
        """
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                # Resolve user UUID first
                resolved_user_id = await self._resolve_user_uuid(conn, user_id)
                # RLS context removed - using schema-level isolation instead

                # Get reference chunk embedding
                ref_query = f"""
                    SELECT embedding, document_id
                    FROM {self.schema_name}.document_chunks
                    WHERE chunk_id = $1
                        AND user_id = $2::uuid
                """

                ref_result = await conn.fetchrow(ref_query, chunk_id, resolved_user_id)
                if not ref_result:
                    raise ValueError(f"Reference chunk {chunk_id} not found")

                ref_embedding = ref_result['embedding']
                ref_document_id = ref_result['document_id']

                # Build exclusion filter
                exclusion_filter = ""
                params = [ref_embedding, similarity_threshold, limit, chunk_id, resolved_user_id]
                if exclude_same_document:
                    exclusion_filter = "AND document_id != $6"
                    params.append(ref_document_id)

                # Search for similar chunks
                similarity_query = f"""
                    SELECT
                        id as chunk_id,
                        document_id,
                        dataset_id,
                        content as text,
                        metadata as chunk_metadata,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM {self.schema_name}.document_chunks
                    WHERE user_id = $5::uuid
                        AND id != $4::uuid
                        AND 1 - (embedding <=> $1::vector) >= $2
                        {exclusion_filter}
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """

                rows = await conn.fetch(similarity_query, *params)

                results = [
                    HybridSearchResult(
                        chunk_id=row['chunk_id'],
                        document_id=row['document_id'],
                        dataset_id=row['dataset_id'],
                        text=row['text'],
                        metadata=row['metadata'] if row['metadata'] else {},
                        vector_similarity=float(row['similarity']),
                        text_relevance=0.0,
                        hybrid_score=float(row['similarity']),
                        rank=i+1
                    )
                    for i, row in enumerate(rows)
                ]

                logger.info(f"Found {len(results)} similar chunks to {chunk_id}")
                return results

        except Exception as e:
            logger.error(f"Similar chunk search failed: {e}")
            raise

    # Private helper methods

    async def get_dataset_ids_from_documents(
        self,
        document_ids: List[str],
        user_id: str
    ) -> List[str]:
        """Get unique dataset IDs from a list of document IDs"""
        try:
            resolved_user_id = await self._resolve_user_id(user_id)
            dataset_ids = []

            async with self.postgresql_client.get_connection() as conn:
                # RLS context removed - using schema-level isolation instead

                # Query to get dataset IDs from document IDs
                placeholders = ",".join(f"${i+1}" for i in range(len(document_ids)))
                query = f"""
                    SELECT DISTINCT dataset_id
                    FROM {self.schema_name}.documents
                    WHERE id = ANY(ARRAY[{placeholders}]::uuid[])
                    AND user_id = ${len(document_ids)+1}::uuid
                """

                params = document_ids + [resolved_user_id]
                rows = await conn.fetch(query, *params)

                dataset_ids = [str(row['dataset_id']) for row in rows if row['dataset_id']]
                logger.info(f"🔍 Resolved {len(dataset_ids)} dataset IDs from {len(document_ids)} documents: {dataset_ids}")

                return dataset_ids

        except Exception as e:
            logger.error(f"Failed to resolve dataset IDs from documents: {e}")
            return []

    async def _generate_query_embedding(
        self,
        query: str,
        user_id: str
    ) -> List[float]:
        """Generate embedding for search query using simple BGE-M3 client"""
        try:
            # Use direct BGE-M3 embedding client with tenant/user for billing
            embeddings = await self.embedding_client.generate_embeddings(
                [query],
                tenant_id=self.tenant_id,  # Pass tenant for billing
                user_id=user_id             # Pass user for billing
            )

            if not embeddings or not embeddings[0]:
                raise ValueError("Failed to generate query embedding")

            return embeddings[0]

        except Exception as e:
            logger.error(f"Query embedding generation failed: {e}")
            raise

    async def _execute_hybrid_query(
        self,
        query: str,
        query_embedding: List[float],
        user_id: str,
        dataset_ids: Optional[List[str]],
        config: SearchConfig,
        limit: int
    ) -> List[HybridSearchResult]:
        """Execute the hybrid search combining vector + text results"""
        try:
            logger.info(f"🔍 _EXECUTE_HYBRID_QUERY START: query='{query}', user_id='{user_id}', dataset_ids={dataset_ids}")
            logger.info(f"🔍 _EXECUTE_HYBRID_QUERY CONFIG: vector_weight={config.vector_weight}, text_weight={config.text_weight}, limit={limit}")

            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Got DB connection, resolving user UUID")

                # Resolve user UUID first
                actual_user_id = await self._resolve_user_uuid(conn, user_id)
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Resolved user_id to '{actual_user_id}'")

                # RLS context removed - using schema-level isolation instead
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Using resolved UUID '{actual_user_id}' for query parameters")

                # Build dataset filter
                dataset_filter = ""
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Building parameters and dataset filter")

                # Convert embedding list to string format for PostgreSQL vector type
                embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Converted embedding to PostgreSQL vector string (length: {len(embedding_str)})")

                # Ensure UUID is properly formatted as string for PostgreSQL
                if isinstance(actual_user_id, str):
                    try:
                        # Validate it's a proper UUID and convert back to string
                        validated_uuid = str(uuid_lib.UUID(actual_user_id))
                        actual_user_id_str = validated_uuid
                        logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Validated UUID format: '{actual_user_id_str}'")
                    except ValueError:
                        # If it's not a valid UUID string, keep as is
                        actual_user_id_str = actual_user_id
                        logger.warning(f"🔍 _EXECUTE_HYBRID_QUERY: UUID validation failed, using as-is: '{actual_user_id_str}'")
                else:
                    actual_user_id_str = str(actual_user_id)
                    logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Converted user_id to string: '{actual_user_id_str}'")

                params = [embedding_str, query, config.min_vector_similarity, config.min_text_relevance, config.max_results]
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Base parameters prepared (count: {len(params)})")

                # Handle dataset filtering - REQUIRE dataset_ids for security
                if dataset_ids:
                    logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Processing dataset filter for: {dataset_ids}")
                    # Ensure dataset_ids is a list
                    if isinstance(dataset_ids, str):
                        dataset_ids = [dataset_ids]
                        logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Converted string to list: {dataset_ids}")

                    if len(dataset_ids) > 0:
                        # Generate proper placeholders for dataset IDs
                        placeholders = ",".join(f"${i+6}" for i in range(len(dataset_ids)))
                        dataset_filter = f"AND dataset_id = ANY(ARRAY[{placeholders}]::uuid[])"
                        params.extend(dataset_ids)
                        logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Dataset filter: {dataset_filter}, dataset_ids: {dataset_ids}")
                        logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Total parameters after dataset filter: {len(params)}")
                    else:
                        logger.error(f"🔍 _EXECUTE_HYBRID_QUERY: SECURITY ERROR - Empty dataset_ids list not permitted")
                        raise ValueError("Dataset IDs cannot be empty. This could mean the agent has no datasets configured or dataset access control failed.")
                else:
                    # SECURITY FIX: No dataset filter when None is NOT ALLOWED
                    logger.error(f"🔍 _EXECUTE_HYBRID_QUERY: SECURITY ERROR - Dataset IDs are required for search operations")

                    # More informative error message for debugging
                    error_msg = "Dataset IDs are required for hybrid search operations. This could mean: " \
                               "1) Agent has no datasets configured, 2) No datasets selected in UI, or " \
                               "3) Dataset access control failed. Check agent configuration and dataset permissions."
                    raise ValueError(error_msg)

                # Hybrid search query combining vector similarity and text relevance
                hybrid_query = f"""
                    WITH vector_search AS (
                        SELECT
                            id as chunk_id,
                            document_id,
                            dataset_id,
                            content,
                            metadata as chunk_metadata,
                            1 - (embedding <=> $1::vector) as vector_similarity,
                            0.0 as text_relevance
                        FROM {self.schema_name}.document_chunks
                        WHERE 1 - (embedding <=> $1::vector) >= $3
                            {dataset_filter}
                    ),
                    text_search AS (
                        SELECT
                            id as chunk_id,
                            document_id,
                            dataset_id,
                            content,
                            metadata as chunk_metadata,
                            0.0 as vector_similarity,
                            ts_rank_cd(
                                to_tsvector('english', content),
                                plainto_tsquery('english', $2)
                            ) as text_relevance
                        FROM {self.schema_name}.document_chunks
                        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $2)
                            AND ts_rank_cd(
                                to_tsvector('english', content),
                                plainto_tsquery('english', $2)
                            ) >= $4
                            {dataset_filter}
                    ),
                    combined_results AS (
                        SELECT
                            u.chunk_id,
                            dc.document_id,
                            dc.dataset_id,
                            dc.content,
                            dc.metadata as chunk_metadata,
                            COALESCE(v.vector_similarity, 0.0) as vector_similarity,
                            COALESCE(t.text_relevance, 0.0) as text_relevance,
                            (COALESCE(v.vector_similarity, 0.0) * {config.vector_weight} +
                             COALESCE(t.text_relevance, 0.0) * {config.text_weight}) as hybrid_score
                        FROM (
                            SELECT chunk_id FROM vector_search
                            UNION
                            SELECT chunk_id FROM text_search
                        ) u
                        LEFT JOIN vector_search v USING (chunk_id)
                        LEFT JOIN text_search t USING (chunk_id)
                        LEFT JOIN {self.schema_name}.document_chunks dc ON (dc.id = u.chunk_id)
                    )
                    SELECT
                        chunk_id,
                        document_id,
                        dataset_id,
                        content as text,
                        chunk_metadata as metadata,
                        vector_similarity,
                        text_relevance,
                        hybrid_score,
                        ROW_NUMBER() OVER (ORDER BY hybrid_score DESC) as rank
                    FROM combined_results
                    WHERE hybrid_score > 0.0
                    ORDER BY hybrid_score DESC
                    LIMIT $5
                """

                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Executing hybrid SQL with {len(params)} parameters")
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Parameter types: {[type(p) for p in params]}")
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Query preview: {hybrid_query[:500]}...")

                rows = await conn.fetch(hybrid_query, *params)
                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: SQL execution successful, got {len(rows)} rows")

                results = []
                for i, row in enumerate(rows):
                    result = HybridSearchResult(
                        chunk_id=row['chunk_id'],
                        document_id=row['document_id'],
                        dataset_id=row['dataset_id'],
                        text=row['text'],
                        metadata=row['metadata'] if row['metadata'] else {},
                        vector_similarity=float(row['vector_similarity']),
                        text_relevance=float(row['text_relevance']),
                        hybrid_score=float(row['hybrid_score']),
                        rank=row['rank']
                    )
                    results.append(result)
                    if i < 3:  # Log first few results for debugging
                        logger.info(f"🔍 _EXECUTE_HYBRID_QUERY: Result {i+1}: chunk_id='{result.chunk_id}', score={result.hybrid_score:.3f}")

                logger.info(f"🔍 _EXECUTE_HYBRID_QUERY COMPLETE: Processed {len(results)} results")
                return results

        except Exception as e:
            logger.error(f"🔍 _EXECUTE_HYBRID_QUERY ERROR: {e}")
            logger.exception("Full hybrid query execution error traceback:")
            raise

    async def _rerank_results(
        self,
        results: List[HybridSearchResult],
        query: str,
        config: SearchConfig
    ) -> List[HybridSearchResult]:
        """
        Apply advanced re-ranking to search results.

        This can include:
        - Query-document interaction features
        - Diversity scoring
        - Recency weighting
        - User preference learning
        """
        try:
            # For now, apply simple diversity re-ranking
            # to avoid showing too many results from the same document

            reranked = []
            document_counts = {}
            max_per_document = max(1, len(results) // 3)  # At most 1/3 from same document

            for result in results:
                doc_count = document_counts.get(result.document_id, 0)
                if doc_count < max_per_document:
                    reranked.append(result)
                    document_counts[result.document_id] = doc_count + 1

            # Re-rank the remaining items
            remaining = [r for r in results if r not in reranked]
            reranked.extend(remaining)

            # Update rank numbers
            for i, result in enumerate(reranked):
                result.rank = i + 1

            return reranked

        except Exception as e:
            logger.warning(f"Re-ranking failed, returning original results: {e}")
            return results

    async def _resolve_user_uuid(self, conn: asyncpg.Connection, user_id: str) -> str:
        """
        Resolve user email to UUID if needed.
        Returns a validated UUID string.
        """
        logger.info(f"🔍 _RESOLVE_USER_UUID START: input user_id='{user_id}' (type: {type(user_id)})")

        if "@" in user_id:  # If user_id is an email, look up the UUID
            logger.info(f"🔍 _RESOLVE_USER_UUID: Detected email format, looking up UUID for '{user_id}'")
            user_lookup_sql = f"SELECT id FROM {self.schema_name}.users WHERE email = $1"
            logger.info(f"🔍 _RESOLVE_USER_UUID: Executing SQL: {user_lookup_sql}")
            user_row = await conn.fetchrow(user_lookup_sql, user_id)
            if user_row:
                resolved_uuid = str(user_row['id'])
                logger.info(f"🔍 _RESOLVE_USER_UUID: Found UUID '{resolved_uuid}' for email '{user_id}'")
                return resolved_uuid
            else:
                logger.error(f"🔍 _RESOLVE_USER_UUID ERROR: User not found for email: {user_id}")
                raise ValueError(f"User not found: {user_id}")
        else:
            # Already a UUID
            logger.info(f"🔍 _RESOLVE_USER_UUID: Input '{user_id}' is already UUID format, returning as-is")
            return user_id

    # _set_rls_context method removed - using schema-level isolation instead of RLS


# Factory function for dependency injection
def get_pgvector_search_service(tenant_id: str, user_id: Optional[str] = None) -> PGVectorSearchService:
    """Get PGVector search service instance"""
    return PGVectorSearchService(tenant_id=tenant_id, user_id=user_id)