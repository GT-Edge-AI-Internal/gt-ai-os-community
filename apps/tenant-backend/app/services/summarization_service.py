"""
GT 2.0 Summarization Service

Provides AI-powered summarization capabilities for documents and datasets.
Uses the same pattern as conversation title generation with Llama 3.1 8B.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.postgresql_client import get_postgresql_client
from app.core.resource_client import ResourceClusterClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SummarizationService:
    """
    Service for generating AI summaries of documents and datasets.

    Uses the same approach as conversation title generation:
    - Llama 3.1 8B instant model
    - Low temperature for consistency
    - Resource cluster for AI responses
    """

    def __init__(self, tenant_domain: str, user_id: str):
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.resource_client = ResourceClusterClient()
        self.summarization_model = "llama-3.1-8b-instant"
        self.settings = get_settings()

    async def generate_document_summary(
        self,
        document_id: str,
        document_content: str,
        document_name: str
    ) -> Optional[str]:
        """
        Generate AI summary for a document using Llama 3.1 8B.

        Args:
            document_id: UUID of the document
            document_content: Full text content of the document
            document_name: Original filename/name of the document

        Returns:
            Generated summary string or None if failed
        """
        try:
            # Truncate content to first 3000 chars (like conversation title generation)
            content_preview = document_content[:3000]

            # Create summarization prompt
            prompt = f"""Summarize this document '{document_name}' in 2-3 sentences.
Focus on the main topics, key information, and purpose of the document.

Document content:
{content_preview}

Summary:"""

            logger.info(f"Generating summary for document {document_id} ({document_name})")

            # Call Resource Cluster with same pattern as conversation titles
            summary = await self._call_ai_for_summary(
                prompt=prompt,
                context_type="document",
                max_tokens=150
            )

            if summary:
                # Store summary in database
                await self._store_document_summary(document_id, summary)
                logger.info(f"Generated summary for document {document_id}: {summary[:100]}...")
                return summary
            else:
                logger.warning(f"Failed to generate summary for document {document_id}")
                return None

        except Exception as e:
            logger.error(f"Error generating document summary for {document_id}: {e}")
            return None

    async def generate_dataset_summary(self, dataset_id: str) -> Optional[str]:
        """
        Generate AI summary for a dataset based on its document summaries.

        Args:
            dataset_id: UUID of the dataset

        Returns:
            Generated dataset summary or None if failed
        """
        try:
            # Get all document summaries in this dataset
            document_summaries = await self._get_document_summaries_for_dataset(dataset_id)

            if not document_summaries:
                logger.info(f"No document summaries found for dataset {dataset_id}")
                return None

            # Get dataset name for context
            dataset_info = await self._get_dataset_info(dataset_id)
            dataset_name = dataset_info.get('name', 'Unknown Dataset') if dataset_info else 'Unknown Dataset'

            # Combine summaries for LLM context
            combined_summaries = "\n".join([
                f"- {doc['filename']}: {doc['summary']}"
                for doc in document_summaries
                if doc['summary']  # Only include docs that have summaries
            ])

            if not combined_summaries.strip():
                logger.info(f"No valid document summaries for dataset {dataset_id}")
                return None

            # Create dataset summarization prompt
            prompt = f"""Based on these document summaries, create a comprehensive 3-4 sentence summary describing what the dataset '{dataset_name}' contains and its purpose:

Documents in dataset:
{combined_summaries}

Dataset summary:"""

            logger.info(f"Generating summary for dataset {dataset_id} ({dataset_name})")

            # Call AI for dataset summary
            summary = await self._call_ai_for_summary(
                prompt=prompt,
                context_type="dataset",
                max_tokens=200
            )

            if summary:
                # Store dataset summary in database
                await self._store_dataset_summary(dataset_id, summary)
                logger.info(f"Generated dataset summary for {dataset_id}: {summary[:100]}...")
                return summary
            else:
                logger.warning(f"Failed to generate summary for dataset {dataset_id}")
                return None

        except Exception as e:
            logger.error(f"Error generating dataset summary for {dataset_id}: {e}")
            return None

    async def update_dataset_summary_on_change(self, dataset_id: str) -> bool:
        """
        Regenerate dataset summary when documents are added/removed.

        Args:
            dataset_id: UUID of the dataset to update

        Returns:
            True if summary was updated successfully
        """
        try:
            summary = await self.generate_dataset_summary(dataset_id)
            return summary is not None
        except Exception as e:
            logger.error(f"Error updating dataset summary for {dataset_id}: {e}")
            return False

    async def _call_ai_for_summary(
        self,
        prompt: str,
        context_type: str,
        max_tokens: int = 150
    ) -> Optional[str]:
        """
        Call Resource Cluster for AI summary generation.
        Uses ResourceClusterClient for consistent service discovery.

        Args:
            prompt: The summarization prompt
            context_type: Type of summary (document, dataset)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated summary text or None if failed
        """
        try:
            # Prepare request payload (same format as conversation service)
            request_data = {
                "model": self.summarization_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,  # Lower temperature for consistent summaries
                "max_tokens": max_tokens,
                "top_p": 1.0
            }

            logger.info(f"Calling Resource Cluster for {context_type} summary generation")

            # Use ResourceClusterClient for consistent service discovery and auth
            result = await self.resource_client.call_inference_endpoint(
                tenant_id=self.tenant_domain,
                user_id=self.user_id,
                endpoint="chat/completions",
                data=request_data
            )

            if result and "choices" in result and len(result["choices"]) > 0:
                summary = result["choices"][0]["message"]["content"].strip()
                logger.info(f"✅ AI {context_type} summary generated successfully: {summary[:50]}...")
                return summary
            else:
                logger.error(f"❌ Invalid AI response format for {context_type} summary: {result}")
                return None

        except Exception as e:
            logger.error(f"❌ Error calling Resource Cluster for {context_type} summary: {e}", exc_info=True)
            return None

    async def _store_document_summary(self, document_id: str, summary: str) -> None:
        """Store document summary in database"""
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = self.settings.postgres_schema

                await conn.execute(f"""
                    UPDATE {schema_name}.documents
                    SET summary = $1,
                        summary_generated_at = $2,
                        summary_model = $3
                    WHERE id = $4
                """, summary, datetime.now(), self.summarization_model, document_id)

        except Exception as e:
            logger.error(f"Error storing document summary for {document_id}: {e}")
            raise

    async def _store_dataset_summary(self, dataset_id: str, summary: str) -> None:
        """Store dataset summary in database"""
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = self.settings.postgres_schema

                await conn.execute(f"""
                    UPDATE {schema_name}.datasets
                    SET summary = $1,
                        summary_generated_at = $2,
                        summary_model = $3
                    WHERE id = $4
                """, summary, datetime.now(), self.summarization_model, dataset_id)

        except Exception as e:
            logger.error(f"Error storing dataset summary for {dataset_id}: {e}")
            raise

    async def _get_document_summaries_for_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Get all document summaries for a dataset"""
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = self.settings.postgres_schema

                rows = await conn.fetch(f"""
                    SELECT id, filename, original_filename, summary, summary_generated_at
                    FROM {schema_name}.documents
                    WHERE dataset_id = $1
                    AND summary IS NOT NULL
                    AND summary != ''
                    ORDER BY created_at ASC
                """, dataset_id)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting document summaries for dataset {dataset_id}: {e}")
            return []

    async def _get_dataset_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get basic dataset information"""
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = self.settings.postgres_schema

                row = await conn.fetchrow(f"""
                    SELECT id, name, description
                    FROM {schema_name}.datasets
                    WHERE id = $1
                """, dataset_id)

                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting dataset info for {dataset_id}: {e}")
            return None

    async def get_datasets_with_summaries(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all user-accessible datasets with their summaries.
        Used for context injection in chat.

        Args:
            user_id: UUID of the user

        Returns:
            List of datasets with summaries
        """
        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = self.settings.postgres_schema

                rows = await conn.fetch(f"""
                    SELECT id, name, description, summary, summary_generated_at,
                           document_count, total_size_bytes
                    FROM {schema_name}.datasets
                    WHERE (created_by = $1::uuid
                           OR access_group IN ('team', 'organization'))
                    AND is_active = true
                    ORDER BY name ASC
                """, user_id)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting datasets with summaries for user {user_id}: {e}")
            return []

    async def get_filtered_datasets_with_summaries(
        self,
        user_id: str,
        allowed_dataset_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get datasets with summaries filtered by allowed dataset IDs.
        Used for agent-aware context injection in chat.

        Args:
            user_id: User UUID string
            allowed_dataset_ids: List of dataset IDs the agent/user should see

        Returns:
            List of dataset dictionaries with summaries, filtered by allowed IDs
        """
        if not allowed_dataset_ids:
            logger.info(f"No allowed dataset IDs provided for user {user_id} - returning empty list")
            return []

        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = self.settings.postgres_schema

                # Convert dataset IDs to UUID format for query
                placeholders = ",".join(f"${i+2}::uuid" for i in range(len(allowed_dataset_ids)))

                query = f"""
                    SELECT id, name, description, summary, summary_generated_at,
                           document_count, total_size_bytes
                    FROM {schema_name}.datasets
                    WHERE (created_by = $1::uuid
                           OR access_group IN ('team', 'organization'))
                    AND is_active = true
                    AND id = ANY(ARRAY[{placeholders}])
                    ORDER BY name ASC
                """

                params = [user_id] + allowed_dataset_ids
                rows = await conn.fetch(query, *params)

                filtered_datasets = [dict(row) for row in rows]
                logger.info(f"Filtered datasets for user {user_id}: {len(filtered_datasets)} out of {len(allowed_dataset_ids)} requested")

                return filtered_datasets

        except Exception as e:
            logger.error(f"Error getting filtered datasets with summaries for user {user_id}: {e}")
            return []


# Factory function for dependency injection
def get_summarization_service(tenant_domain: str, user_id: str) -> SummarizationService:
    """Factory function to create SummarizationService instance"""
    return SummarizationService(tenant_domain, user_id)