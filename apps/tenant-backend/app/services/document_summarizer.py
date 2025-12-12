"""
Document Summarization Service for GT 2.0

Generates AI-powered summaries for uploaded documents using the Resource Cluster.
Provides both quick summaries and detailed analysis for RAG visualization.
"""

import logging
import asyncio
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.database import get_db_session, execute_command, fetch_one

logger = logging.getLogger(__name__)


class DocumentSummarizer:
    """
    Service for generating document summaries using Resource Cluster LLM.

    Features:
    - Quick document summaries (2-3 sentences)
    - Detailed analysis with key topics and themes
    - Metadata extraction (document type, language, etc.)
    - Integration with document processor workflow
    """

    def __init__(self):
        self.resource_cluster_url = "http://gentwo-resource-backend:8000"
        self.max_content_length = 4000  # Max chars to send for summarization

    async def generate_document_summary(
        self,
        document_id: str,
        content: str,
        filename: str,
        tenant_domain: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary for a document.

        Args:
            document_id: Document ID in the database
            content: Document text content
            filename: Original filename
            tenant_domain: Tenant domain for context
            user_id: User who uploaded the document

        Returns:
            Dictionary with summary data including quick_summary, detailed_analysis,
            topics, metadata, and confidence scores
        """
        try:
            # Truncate content if too long
            truncated_content = content[:self.max_content_length]
            if len(content) > self.max_content_length:
                truncated_content += "... [content truncated]"

            # Generate summary using Resource Cluster LLM
            summary_data = await self._call_llm_for_summary(
                content=truncated_content,
                filename=filename,
                document_type=self._detect_document_type(filename)
            )

            # Store summary in database
            await self._store_document_summary(
                document_id=document_id,
                summary_data=summary_data,
                tenant_domain=tenant_domain,
                user_id=user_id
            )

            logger.info(f"Generated summary for document {document_id}: {filename}")
            return summary_data

        except Exception as e:
            logger.error(f"Failed to generate summary for document {document_id}: {e}")
            # Return basic fallback summary
            return {
                "quick_summary": f"Document: {filename}",
                "detailed_analysis": "Summary generation failed",
                "topics": [],
                "metadata": {
                    "document_type": self._detect_document_type(filename),
                    "estimated_read_time": len(content) // 200,  # ~200 words per minute
                    "character_count": len(content),
                    "language": "unknown"
                },
                "confidence": 0.0,
                "error": str(e)
            }

    async def _call_llm_for_summary(
        self,
        content: str,
        filename: str,
        document_type: str
    ) -> Dict[str, Any]:
        """Call Resource Cluster LLM to generate document summary"""

        prompt = f"""Analyze this {document_type} document and provide a comprehensive summary.

Document: {filename}
Content:
{content}

Please provide:
1. A concise 2-3 sentence summary
2. Key topics and themes (list)
3. Document analysis including tone, purpose, and target audience
4. Estimated language and reading level

Format your response as JSON with these keys:
- quick_summary: Brief 2-3 sentence overview
- detailed_analysis: Paragraph with deeper insights
- topics: Array of key topics/themes
- metadata: Object with language, tone, purpose, target_audience
- confidence: Float 0-1 indicating analysis confidence"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.resource_cluster_url}/api/v1/ai/chat/completions",
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a document analysis expert. Provide accurate, concise summaries in valid JSON format."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    },
                    headers={
                        "X-Tenant-ID": "default",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    llm_response = response.json()
                    content_text = llm_response["choices"][0]["message"]["content"]

                    # Try to parse JSON response
                    try:
                        import json
                        summary_data = json.loads(content_text)

                        # Validate required fields and add defaults if missing
                        return {
                            "quick_summary": summary_data.get("quick_summary", f"Analysis of {filename}"),
                            "detailed_analysis": summary_data.get("detailed_analysis", "Detailed analysis not available"),
                            "topics": summary_data.get("topics", []),
                            "metadata": {
                                **summary_data.get("metadata", {}),
                                "document_type": document_type,
                                "generated_at": datetime.utcnow().isoformat()
                            },
                            "confidence": min(1.0, max(0.0, summary_data.get("confidence", 0.7)))
                        }

                    except json.JSONDecodeError:
                        # Fallback if LLM doesn't return valid JSON
                        return {
                            "quick_summary": content_text[:200] + "..." if len(content_text) > 200 else content_text,
                            "detailed_analysis": content_text,
                            "topics": [],
                            "metadata": {
                                "document_type": document_type,
                                "generated_at": datetime.utcnow().isoformat(),
                                "note": "Summary extracted from free-form LLM response"
                            },
                            "confidence": 0.5
                        }
                else:
                    raise Exception(f"Resource Cluster API error: {response.status_code}")

        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            raise

    async def _store_document_summary(
        self,
        document_id: str,
        summary_data: Dict[str, Any],
        tenant_domain: str,
        user_id: str
    ):
        """Store generated summary in database"""

        # Use the same database session pattern as document processor
        async with get_db_session(tenant_domain) as session:
            try:
                # Insert or update document summary
                query = """
                INSERT INTO document_summaries (
                    document_id, user_id, quick_summary, detailed_analysis,
                    topics, metadata, confidence, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (document_id)
                DO UPDATE SET
                    quick_summary = EXCLUDED.quick_summary,
                    detailed_analysis = EXCLUDED.detailed_analysis,
                    topics = EXCLUDED.topics,
                    metadata = EXCLUDED.metadata,
                    confidence = EXCLUDED.confidence,
                    updated_at = EXCLUDED.updated_at
                """

                import json
                await execute_command(
                    session,
                    query,
                    document_id,
                    user_id,
                    summary_data["quick_summary"],
                    summary_data["detailed_analysis"],
                    json.dumps(summary_data["topics"]),
                    json.dumps(summary_data["metadata"]),
                    summary_data["confidence"],
                    datetime.utcnow(),
                    datetime.utcnow()
                )

                logger.info(f"Stored summary for document {document_id}")

            except Exception as e:
                logger.error(f"Failed to store document summary: {e}")
                raise

    def _detect_document_type(self, filename: str) -> str:
        """Detect document type from filename extension"""
        import pathlib

        extension = pathlib.Path(filename).suffix.lower()

        type_mapping = {
            '.pdf': 'PDF document',
            '.docx': 'Word document',
            '.doc': 'Word document',
            '.txt': 'Text file',
            '.md': 'Markdown document',
            '.csv': 'CSV data file',
            '.json': 'JSON data file',
            '.html': 'HTML document',
            '.htm': 'HTML document',
            '.rtf': 'Rich text document'
        }

        return type_mapping.get(extension, 'Unknown document type')

    async def get_document_summary(
        self,
        document_id: str,
        tenant_domain: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve stored document summary"""

        async with get_db_session(tenant_domain) as session:
            try:
                query = """
                SELECT quick_summary, detailed_analysis, topics, metadata,
                       confidence, created_at, updated_at
                FROM document_summaries
                WHERE document_id = $1
                """

                result = await fetch_one(session, query, document_id)

                if result:
                    import json
                    return {
                        "quick_summary": result["quick_summary"],
                        "detailed_analysis": result["detailed_analysis"],
                        "topics": json.loads(result["topics"]) if result["topics"] else [],
                        "metadata": json.loads(result["metadata"]) if result["metadata"] else {},
                        "confidence": result["confidence"],
                        "created_at": result["created_at"].isoformat(),
                        "updated_at": result["updated_at"].isoformat()
                    }

                return None

            except Exception as e:
                logger.error(f"Failed to retrieve document summary: {e}")
                return None


# Global instance
document_summarizer = DocumentSummarizer()


async def generate_document_summary(
    document_id: str,
    content: str,
    filename: str,
    tenant_domain: str,
    user_id: str
) -> Dict[str, Any]:
    """Convenience function for document summary generation"""
    return await document_summarizer.generate_document_summary(
        document_id, content, filename, tenant_domain, user_id
    )


async def get_document_summary(document_id: str, tenant_domain: str) -> Optional[Dict[str, Any]]:
    """Convenience function for retrieving document summary"""
    return await document_summarizer.get_document_summary(document_id, tenant_domain)