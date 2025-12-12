"""
Dataset Summarization Service for GT 2.0

Generates comprehensive summaries for datasets based on their constituent documents.
Provides analytics, topic clustering, and overview generation for RAG optimization.
"""

import logging
import asyncio
import httpx
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import Counter

from app.core.database import get_db_session, execute_command, fetch_one, fetch_all

logger = logging.getLogger(__name__)


class DatasetSummarizer:
    """
    Service for generating dataset-level summaries and analytics.

    Features:
    - Aggregate document summaries into dataset overview
    - Topic clustering and theme analysis
    - Dataset statistics and metrics
    - Search optimization recommendations
    - RAG performance insights
    """

    def __init__(self):
        self.resource_cluster_url = "http://gentwo-resource-backend:8000"

    async def generate_dataset_summary(
        self,
        dataset_id: str,
        tenant_domain: str,
        user_id: str,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary for a dataset.

        Args:
            dataset_id: Dataset ID to summarize
            tenant_domain: Tenant domain for database context
            user_id: User requesting the summary
            force_regenerate: Force regeneration even if summary exists

        Returns:
            Dictionary with dataset summary including overview, topics,
            statistics, and search optimization insights
        """
        try:
            # Check if summary already exists and is recent
            if not force_regenerate:
                existing_summary = await self._get_existing_summary(dataset_id, tenant_domain)
                if existing_summary and self._is_summary_fresh(existing_summary):
                    logger.info(f"Using cached dataset summary for {dataset_id}")
                    return existing_summary

            # Get dataset information and documents
            dataset_info = await self._get_dataset_info(dataset_id, tenant_domain)
            if not dataset_info:
                raise ValueError(f"Dataset {dataset_id} not found")

            documents = await self._get_dataset_documents(dataset_id, tenant_domain)
            document_summaries = await self._get_document_summaries(dataset_id, tenant_domain)

            # Generate statistics
            stats = await self._calculate_dataset_statistics(dataset_id, tenant_domain)

            # Analyze topics across all documents
            topics_analysis = await self._analyze_dataset_topics(document_summaries)

            # Generate overall summary using LLM
            overview = await self._generate_dataset_overview(
                dataset_info, document_summaries, topics_analysis, stats
            )

            # Create comprehensive summary
            summary_data = {
                "dataset_id": dataset_id,
                "overview": overview,
                "statistics": stats,
                "topics": topics_analysis,
                "recommendations": await self._generate_search_recommendations(stats, topics_analysis),
                "metadata": {
                    "document_count": len(documents),
                    "has_summaries": len(document_summaries),
                    "generated_at": datetime.utcnow().isoformat(),
                    "generated_by": user_id
                }
            }

            # Store summary in database
            await self._store_dataset_summary(dataset_id, summary_data, tenant_domain, user_id)

            logger.info(f"Generated dataset summary for {dataset_id} with {len(documents)} documents")
            return summary_data

        except Exception as e:
            logger.error(f"Failed to generate dataset summary for {dataset_id}: {e}")
            # Return basic fallback summary
            return {
                "dataset_id": dataset_id,
                "overview": "Dataset summary generation failed",
                "statistics": {"error": str(e)},
                "topics": [],
                "recommendations": [],
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
            }

    async def _get_dataset_info(self, dataset_id: str, tenant_domain: str) -> Optional[Dict[str, Any]]:
        """Get basic dataset information"""
        async with get_db_session() as session:
            query = """
            SELECT id, dataset_name, description, chunking_strategy,
                   chunk_size, chunk_overlap, created_at
            FROM datasets
            WHERE id = $1
            """
            result = await fetch_one(session, query, dataset_id)
            return dict(result) if result else None

    async def _get_dataset_documents(self, dataset_id: str, tenant_domain: str) -> List[Dict[str, Any]]:
        """Get all documents in the dataset"""
        async with get_db_session() as session:
            query = """
            SELECT id, filename, original_filename, file_type,
                   file_size_bytes, chunk_count, created_at
            FROM documents
            WHERE dataset_id = $1 AND processing_status = 'completed'
            ORDER BY created_at DESC
            """
            results = await fetch_all(session, query, dataset_id)
            return [dict(row) for row in results]

    async def _get_document_summaries(self, dataset_id: str, tenant_domain: str) -> List[Dict[str, Any]]:
        """Get summaries for all documents in the dataset"""
        async with get_db_session() as session:
            query = """
            SELECT ds.document_id, ds.quick_summary, ds.detailed_analysis,
                   ds.topics, ds.metadata, ds.confidence,
                   d.filename, d.original_filename
            FROM document_summaries ds
            JOIN documents d ON ds.document_id = d.id
            WHERE d.dataset_id = $1
            ORDER BY ds.created_at DESC
            """
            results = await fetch_all(session, query, dataset_id)

            summaries = []
            for row in results:
                summary = dict(row)
                # Parse JSON fields
                if summary["topics"]:
                    summary["topics"] = json.loads(summary["topics"])
                if summary["metadata"]:
                    summary["metadata"] = json.loads(summary["metadata"])
                summaries.append(summary)

            return summaries

    async def _calculate_dataset_statistics(self, dataset_id: str, tenant_domain: str) -> Dict[str, Any]:
        """Calculate comprehensive dataset statistics"""
        async with get_db_session() as session:
            # Basic document statistics
            doc_stats_query = """
            SELECT
                COUNT(*) as total_documents,
                SUM(file_size_bytes) as total_size_bytes,
                SUM(chunk_count) as total_chunks,
                AVG(chunk_count) as avg_chunks_per_doc,
                COUNT(DISTINCT file_type) as unique_file_types
            FROM documents
            WHERE dataset_id = $1 AND processing_status = 'completed'
            """
            doc_stats = await fetch_one(session, doc_stats_query, dataset_id)

            # Chunk statistics
            chunk_stats_query = """
            SELECT
                COUNT(*) as total_vector_embeddings,
                AVG(token_count) as avg_tokens_per_chunk,
                MIN(token_count) as min_tokens,
                MAX(token_count) as max_tokens
            FROM document_chunks
            WHERE dataset_id = $1
            """
            chunk_stats = await fetch_one(session, chunk_stats_query, dataset_id)

            # File type distribution
            file_types_query = """
            SELECT file_type, COUNT(*) as count
            FROM documents
            WHERE dataset_id = $1 AND processing_status = 'completed'
            GROUP BY file_type
            ORDER BY count DESC
            """
            file_types_results = await fetch_all(session, file_types_query, dataset_id)
            file_types = {row["file_type"]: row["count"] for row in file_types_results}

            return {
                "documents": {
                    "total": doc_stats["total_documents"] or 0,
                    "total_size_mb": round((doc_stats["total_size_bytes"] or 0) / 1024 / 1024, 2),
                    "avg_chunks_per_document": round(doc_stats["avg_chunks_per_doc"] or 0, 1),
                    "unique_file_types": doc_stats["unique_file_types"] or 0,
                    "file_type_distribution": file_types
                },
                "chunks": {
                    "total": chunk_stats["total_vector_embeddings"] or 0,
                    "avg_tokens": round(chunk_stats["avg_tokens_per_chunk"] or 0, 1),
                    "token_range": {
                        "min": chunk_stats["min_tokens"] or 0,
                        "max": chunk_stats["max_tokens"] or 0
                    }
                },
                "search_readiness": {
                    "has_vectors": (chunk_stats["total_vector_embeddings"] or 0) > 0,
                    "vector_coverage": 1.0 if (doc_stats["total_chunks"] or 0) == (chunk_stats["total_vector_embeddings"] or 0) else 0.0
                }
            }

    async def _analyze_dataset_topics(self, document_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze topics across all document summaries"""
        if not document_summaries:
            return {"main_topics": [], "topic_distribution": {}, "confidence": 0.0}

        # Collect all topics from document summaries
        all_topics = []
        for summary in document_summaries:
            topics = summary.get("topics", [])
            if isinstance(topics, list):
                all_topics.extend(topics)

        # Count topic frequencies
        topic_counts = Counter(all_topics)

        # Get top topics
        main_topics = [topic for topic, count in topic_counts.most_common(10)]

        # Calculate topic distribution
        total_topics = len(all_topics)
        topic_distribution = {}
        if total_topics > 0:
            for topic, count in topic_counts.items():
                topic_distribution[topic] = round(count / total_topics, 3)

        # Calculate confidence based on number of summaries available
        confidence = min(1.0, len(document_summaries) / 5.0)  # Full confidence with 5+ documents

        return {
            "main_topics": main_topics,
            "topic_distribution": topic_distribution,
            "confidence": confidence,
            "total_unique_topics": len(topic_counts)
        }

    async def _generate_dataset_overview(
        self,
        dataset_info: Dict[str, Any],
        document_summaries: List[Dict[str, Any]],
        topics_analysis: Dict[str, Any],
        stats: Dict[str, Any]
    ) -> str:
        """Generate LLM-powered overview of the dataset"""

        # Create context for LLM
        context = f"""Dataset: {dataset_info['dataset_name']}
Description: {dataset_info.get('description', 'No description provided')}

Statistics:
- {stats['documents']['total']} documents ({stats['documents']['total_size_mb']} MB)
- {stats['chunks']['total']} text chunks for search
- Average {stats['documents']['avg_chunks_per_document']} chunks per document

Main Topics: {', '.join(topics_analysis['main_topics'][:5])}

Document Summaries:
"""

        # Add sample document summaries
        for i, summary in enumerate(document_summaries[:3]):  # First 3 documents
            context += f"\n{i+1}. {summary['filename']}: {summary['quick_summary']}"

        prompt = f"""Analyze this dataset and provide a comprehensive 2-3 paragraph overview.

{context}

Focus on:
1. What type of content this dataset contains
2. The main themes and topics covered
3. How useful this would be for AI-powered search and retrieval
4. Any notable patterns or characteristics

Provide a professional, informative summary suitable for users exploring their datasets."""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.resource_cluster_url}/api/v1/ai/chat/completions",
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a data analysis expert. Provide clear, insightful dataset summaries."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    },
                    headers={
                        "X-Tenant-ID": "default",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    llm_response = response.json()
                    return llm_response["choices"][0]["message"]["content"]
                else:
                    raise Exception(f"LLM API error: {response.status_code}")

        except Exception as e:
            logger.warning(f"LLM overview generation failed: {e}")
            # Fallback to template-based overview
            return f"This dataset contains {stats['documents']['total']} documents covering topics such as {', '.join(topics_analysis['main_topics'][:3])}. The dataset includes {stats['chunks']['total']} searchable text chunks optimized for AI-powered retrieval and question answering."

    async def _generate_search_recommendations(
        self,
        stats: Dict[str, Any],
        topics_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations for optimizing search performance"""
        recommendations = []

        # Vector coverage recommendations
        if not stats["search_readiness"]["has_vectors"]:
            recommendations.append("Generate vector embeddings for all documents to enable semantic search")
        elif stats["search_readiness"]["vector_coverage"] < 1.0:
            recommendations.append("Complete vector embedding generation for optimal search performance")

        # Chunk size recommendations
        avg_tokens = stats["chunks"]["avg_tokens"]
        if avg_tokens < 100:
            recommendations.append("Consider increasing chunk size for better context in search results")
        elif avg_tokens > 600:
            recommendations.append("Consider reducing chunk size for more precise search matches")

        # Topic diversity recommendations
        if topics_analysis["total_unique_topics"] < 3:
            recommendations.append("Dataset may benefit from more diverse content for comprehensive coverage")
        elif topics_analysis["total_unique_topics"] > 50:
            recommendations.append("Consider organizing content into focused sub-datasets for better search precision")

        # Document count recommendations
        doc_count = stats["documents"]["total"]
        if doc_count < 5:
            recommendations.append("Add more documents to improve search quality and coverage")
        elif doc_count > 100:
            recommendations.append("Consider implementing advanced filtering and categorization for better navigation")

        return recommendations[:5]  # Limit to top 5 recommendations

    async def _store_dataset_summary(
        self,
        dataset_id: str,
        summary_data: Dict[str, Any],
        tenant_domain: str,
        user_id: str
    ):
        """Store or update dataset summary in database"""
        async with get_db_session() as session:
            query = """
            UPDATE datasets
            SET
                summary = $1,
                summary_generated_at = $2,
                updated_at = NOW()
            WHERE id = $3
            """

            await execute_command(
                session,
                query,
                json.dumps(summary_data),
                datetime.utcnow(),
                dataset_id
            )

    async def _get_existing_summary(self, dataset_id: str, tenant_domain: str) -> Optional[Dict[str, Any]]:
        """Get existing dataset summary if available"""
        async with get_db_session() as session:
            query = """
            SELECT summary, summary_generated_at
            FROM datasets
            WHERE id = $1 AND summary IS NOT NULL
            """
            result = await fetch_one(session, query, dataset_id)

            if result and result["summary"]:
                return json.loads(result["summary"])
            return None

    def _is_summary_fresh(self, summary: Dict[str, Any], max_age_hours: int = 24) -> bool:
        """Check if summary is recent enough to avoid regeneration"""
        try:
            generated_at = datetime.fromisoformat(summary["metadata"]["generated_at"])
            age_hours = (datetime.utcnow() - generated_at).total_seconds() / 3600
            return age_hours < max_age_hours
        except (KeyError, ValueError):
            return False


# Global instance
dataset_summarizer = DatasetSummarizer()


async def generate_dataset_summary(
    dataset_id: str,
    tenant_domain: str,
    user_id: str,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """Convenience function for dataset summary generation"""
    return await dataset_summarizer.generate_dataset_summary(
        dataset_id, tenant_domain, user_id, force_regenerate
    )


async def get_dataset_summary(dataset_id: str, tenant_domain: str) -> Optional[Dict[str, Any]]:
    """Convenience function for retrieving dataset summary"""
    return await dataset_summarizer._get_existing_summary(dataset_id, tenant_domain)