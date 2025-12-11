"""
RAG Orchestrator Service for GT 2.0

Coordinates RAG operations between chat, MCP tools, and datasets.
Provides intelligent context retrieval and source attribution.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import httpx

from app.services.mcp_integration import MCPIntegrationService, MCPExecutionResult
from app.services.pgvector_search_service import PGVectorSearchService, get_pgvector_search_service
from app.models.agent import Agent
from app.models.assistant_dataset import AssistantDataset

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Context retrieved from RAG operations"""
    chunks: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    search_queries: List[str]
    total_chunks: int
    retrieval_time_ms: float
    datasets_used: List[str]


@dataclass
class RAGSearchParams:
    """Parameters for RAG search operations"""
    query: str
    dataset_ids: Optional[List[str]] = None
    max_chunks: int = 5
    similarity_threshold: float = 0.7
    search_method: str = "hybrid"  # hybrid, vector, text


class RAGOrchestrator:
    """
    Orchestrates RAG operations for enhanced chat responses.

    Coordinates between:
    - Dataset search via MCP RAG server
    - Conversation history via MCP conversation server
    - Direct PGVector search for performance
    - Agent dataset bindings for context filtering
    """

    def __init__(self, tenant_domain: str, user_id: str):
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.mcp_service = MCPIntegrationService()
        self.resource_cluster_url = "http://resource-cluster:8000"

    async def get_rag_context(
        self,
        agent: Agent,
        user_message: str,
        conversation_id: str,
        params: Optional[RAGSearchParams] = None
    ) -> RAGContext:
        """
        Get comprehensive RAG context for a chat message.

        Args:
            agent: Agent instance with dataset bindings
            user_message: User's message/query
            conversation_id: Current conversation ID
            params: Optional search parameters

        Returns:
            RAGContext with relevant chunks and sources
        """
        start_time = datetime.now()

        if params is None:
            params = RAGSearchParams(query=user_message)

        try:
            # Get agent's dataset IDs for search (unchanged)
            agent_dataset_ids = await self._get_agent_datasets(agent)

            # Get conversation files if conversation exists (NEW: simplified approach)
            conversation_files = []
            if conversation_id:
                conversation_files = await self._get_conversation_files(conversation_id)

            # Determine search strategy
            search_dataset_ids = params.dataset_ids or agent_dataset_ids

            # Check if we have any sources to search
            if not search_dataset_ids and not conversation_files:
                logger.info(f"No search sources available - agent {agent.id if agent else 'none'}")
                return RAGContext(
                    chunks=[],
                    sources=[],
                    search_queries=[params.query],
                    total_chunks=0,
                    retrieval_time_ms=0.0,
                    datasets_used=[]
                )

            # Prepare search tasks for dual-source search
            search_tasks = []

            # Task 1: Dataset search via MCP RAG server (unchanged)
            if search_dataset_ids:
                search_tasks.append(
                    self._search_datasets_via_mcp(params.query, search_dataset_ids, params)
                )

            # Task 2: Conversation files search (NEW: direct search)
            if conversation_files:
                search_tasks.append(
                    self._search_conversation_files(params.query, conversation_id)
                )

            # Execute searches in parallel
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Process search results from all sources
            all_chunks = []
            all_sources = []

            result_index = 0

            # Process dataset search results (if performed)
            if search_dataset_ids and result_index < len(search_results):
                dataset_result = search_results[result_index]
                if not isinstance(dataset_result, Exception) and dataset_result.get("success"):
                    dataset_chunks = dataset_result.get("results", [])
                    all_chunks.extend(dataset_chunks)
                    all_sources.extend(self._extract_sources(dataset_chunks))
                result_index += 1

            # Process conversation files search results (if performed)
            if conversation_files and result_index < len(search_results):
                conversation_result = search_results[result_index]
                if not isinstance(conversation_result, Exception):
                    conversation_chunks = conversation_result or []
                    all_chunks.extend(conversation_chunks)
                    all_sources.extend(
                        await self._extract_conversation_file_sources(conversation_chunks, conversation_id)
                    )
                result_index += 1

            # Rank and filter results based on agent preferences (now using all chunks)
            final_chunks = await self._rank_and_filter_chunks(
                all_chunks, agent_dataset_ids, params
            )

            retrieval_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                f"RAG context retrieved: {len(final_chunks)} chunks from "
                f"{len(search_dataset_ids)} datasets + {len(conversation_files)} conversation files "
                f"in {retrieval_time:.1f}ms"
            )

            return RAGContext(
                chunks=final_chunks,
                sources=all_sources,
                search_queries=[params.query],
                total_chunks=len(final_chunks),
                retrieval_time_ms=retrieval_time,
                datasets_used=search_dataset_ids
            )

        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            retrieval_time = (datetime.now() - start_time).total_seconds() * 1000

            # Return empty context on failure
            return RAGContext(
                chunks=[],
                sources=[],
                search_queries=[params.query],
                total_chunks=0,
                retrieval_time_ms=retrieval_time,
                datasets_used=[]
            )

    async def _get_agent_datasets(self, agent: Agent) -> List[str]:
        """Get dataset IDs for an agent (simplified)"""
        try:
            # Get agent configuration from agent service (skip complex table lookup)
            from app.services.agent_service import AgentService
            agent_service = AgentService(self.tenant_domain, self.user_id)
            agent_data = await agent_service.get_agent(agent.id)

            if agent_data and 'selected_dataset_ids' in agent_data and agent_data['selected_dataset_ids'] is not None:
                selected_dataset_ids = agent_data.get('selected_dataset_ids', [])
                logger.info(f"Found {len(selected_dataset_ids)} dataset IDs in agent configuration: {selected_dataset_ids}")
                return selected_dataset_ids
            else:
                logger.info(f"No selected_dataset_ids found in agent {agent.id} configuration: {agent_data.get('selected_dataset_ids') if agent_data else 'no agent_data'}")
                return []

        except Exception as e:
            logger.error(f"Failed to get agent datasets: {e}")
            return []

    async def _get_conversation_files(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation files (NEW: simplified approach)"""
        try:
            from app.services.conversation_file_service import get_conversation_file_service
            file_service = get_conversation_file_service(self.tenant_domain, self.user_id)
            conversation_files = await file_service.list_files(conversation_id)

            # Filter to only completed files
            completed_files = [f for f in conversation_files if f.get('processing_status') == 'completed']

            logger.info(f"Found {len(completed_files)} processed conversation files")
            return completed_files
        except Exception as e:
            logger.error(f"Failed to get conversation files: {e}")
            return []

    async def _search_conversation_files(
        self,
        query: str,
        conversation_id: str
    ) -> List[Dict[str, Any]]:
        """Search conversation files using vector similarity (NEW: direct search)"""
        try:
            from app.services.conversation_file_service import get_conversation_file_service
            file_service = get_conversation_file_service(self.tenant_domain, self.user_id)

            results = await file_service.search_conversation_files(
                conversation_id=conversation_id,
                query=query,
                max_results=5
            )

            logger.info(f"Found {len(results)} matching conversation files")
            return results
        except Exception as e:
            logger.error(f"Failed to search conversation files: {e}")
            return []

    async def _extract_conversation_file_sources(
        self,
        chunks: List[Dict[str, Any]],
        conversation_id: str
    ) -> List[Dict[str, Any]]:
        """Extract unique conversation file sources with rich metadata"""
        sources = {}

        for chunk in chunks:
            file_id = chunk.get("id")
            if file_id and file_id not in sources:
                uploaded_at = chunk.get("uploaded_at")
                if not uploaded_at:
                    logger.warning(f"Missing uploaded_at for file {file_id}")

                file_size = chunk.get("file_size_bytes", 0)
                if file_size == 0:
                    logger.warning(f"Missing file_size_bytes for file {file_id}")

                sources[file_id] = {
                    "document_id": file_id,
                    "dataset_id": None,
                    "document_name": chunk.get("original_filename", "Unknown File"),

                    "source_type": "conversation_file",
                    "access_scope": "conversation",
                    "search_method": "auto_rag",

                    "conversation_id": conversation_id,

                    "uploaded_at": uploaded_at,
                    "file_size_bytes": file_size,
                    "content_type": chunk.get("content_type", "unknown"),
                    "processing_status": chunk.get("processing_status", "unknown"),

                    "chunk_count": 1,
                    "relevance_score": chunk.get("similarity_score", 0.0)
                }
            elif file_id in sources:
                sources[file_id]["chunk_count"] += 1
                current_score = chunk.get("similarity_score", 0.0)
                if current_score > sources[file_id]["relevance_score"]:
                    sources[file_id]["relevance_score"] = current_score

        return list(sources.values())

    # Keep old method for backward compatibility during migration
    async def _get_conversation_datasets(self, conversation_id: str) -> List[str]:
        """Get dataset IDs associated with a conversation (LEGACY: for migration)"""
        try:
            from app.services.conversation_service import ConversationService
            conversation_service = ConversationService(self.tenant_domain, self.user_id)
            conversation_dataset_ids = await conversation_service.get_conversation_datasets(
                conversation_id=conversation_id,
                user_identifier=self.user_id
            )
            logger.info(f"Found {len(conversation_dataset_ids)} legacy conversation datasets: {conversation_dataset_ids}")
            return conversation_dataset_ids
        except Exception as e:
            logger.error(f"Failed to get conversation datasets: {e}")
            return []

    async def _search_datasets_via_mcp(
        self,
        query: str,
        dataset_ids: List[str],
        params: RAGSearchParams
    ) -> Dict[str, Any]:
        """Search datasets using MCP RAG server"""
        try:
            # Prepare MCP tool call
            tool_params = {
                "query": query,
                "dataset_ids": dataset_ids,
                "max_results": params.max_chunks,
                "search_method": params.search_method
            }

            # Create capability token for MCP access
            capability_token = {
                "capabilities": [{"resource": "mcp:rag:*"}],
                "user_id": self.user_id,
                "tenant_domain": self.tenant_domain
            }

            # Execute MCP tool call via resource cluster
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.resource_cluster_url}/api/v1/mcp/execute",
                    json={
                        "server_id": "rag_server",
                        "tool_name": "search_datasets",
                        "parameters": tool_params,
                        "capability_token": capability_token,
                        "tenant_domain": self.tenant_domain,
                        "user_id": self.user_id
                    }
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"MCP RAG search failed: {response.status_code} - {response.text}")
                    return {"success": False, "error": "MCP search failed"}

        except Exception as e:
            logger.error(f"MCP dataset search failed: {e}")
            return {"success": False, "error": str(e)}


    async def _rank_and_filter_chunks(
        self,
        chunks: List[Dict[str, Any]],
        agent_dataset_ids: List[str],
        params: RAGSearchParams
    ) -> List[Dict[str, Any]]:
        """Rank and filter chunks based on agent preferences (simplified)"""
        try:
            if not chunks:
                return []

            # Convert agent dataset list to set for fast lookup
            agent_datasets = set(agent_dataset_ids)

            # Separate conversation files from dataset chunks
            conversation_file_chunks = []
            dataset_chunks = []

            for chunk in chunks:
                if chunk.get("source_type") == "conversation_file":
                    # Conversation files ALWAYS included (user explicitly attached them)
                    chunk["final_score"] = chunk.get("similarity_score", 1.0)
                    chunk["dataset_priority"] = -1  # Highest priority (shown first)
                    conversation_file_chunks.append(chunk)
                else:
                    dataset_chunks.append(chunk)

            # Filter and score dataset chunks using thresholds
            scored_dataset_chunks = []
            for chunk in dataset_chunks:
                dataset_id = chunk.get("dataset_id")
                similarity_score = chunk.get("similarity_score", 0.0)

                # Check if chunk is from agent's configured datasets
                if dataset_id in agent_datasets:
                    # Use agent default threshold
                    if similarity_score >= 0.7:  # Default threshold
                        chunk["final_score"] = similarity_score
                        chunk["dataset_priority"] = 0  # High priority for agent datasets
                        scored_dataset_chunks.append(chunk)
                else:
                    # Use request threshold for other datasets
                    if similarity_score >= params.similarity_threshold:
                        chunk["final_score"] = similarity_score
                        chunk["dataset_priority"] = 999  # Low priority
                        scored_dataset_chunks.append(chunk)

            # Combine: conversation files first, then sorted dataset chunks
            scored_dataset_chunks.sort(key=lambda x: x["final_score"], reverse=True)

            # Limit total results, but always include all conversation files
            final_chunks = conversation_file_chunks + scored_dataset_chunks

            # If we exceed max_chunks, keep all conversation files and trim datasets
            if len(final_chunks) > params.max_chunks:
                dataset_limit = params.max_chunks - len(conversation_file_chunks)
                if dataset_limit > 0:
                    final_chunks = conversation_file_chunks + scored_dataset_chunks[:dataset_limit]
                else:
                    # If conversation files alone exceed limit, keep them all anyway
                    final_chunks = conversation_file_chunks

            logger.info(f"Ranked chunks: {len(conversation_file_chunks)} conversation files (always included) + {len(scored_dataset_chunks)} dataset chunks → {len(final_chunks)} total")

            return final_chunks

        except Exception as e:
            logger.error(f"Chunk ranking failed: {e}")
            return chunks[:params.max_chunks]  # Fallback to simple truncation

    def _extract_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique document sources from dataset chunks with metadata"""
        sources = {}

        for chunk in chunks:
            document_id = chunk.get("document_id")
            if document_id and document_id not in sources:
                sources[document_id] = {
                    "document_id": document_id,
                    "dataset_id": chunk.get("dataset_id"),
                    "document_name": chunk.get("metadata", {}).get("document_name", "Unknown"),

                    "source_type": "dataset",
                    "access_scope": "permanent",
                    "search_method": "mcp_tool",

                    "dataset_name": chunk.get("dataset_name", "Unknown Dataset"),

                    "chunk_count": 1,
                    "relevance_score": chunk.get("similarity_score", 0.0)
                }
            elif document_id in sources:
                sources[document_id]["chunk_count"] += 1
                current_score = chunk.get("similarity_score", 0.0)
                if current_score > sources[document_id]["relevance_score"]:
                    sources[document_id]["relevance_score"] = current_score

        return list(sources.values())

    def format_context_for_llm(self, rag_context: RAGContext) -> str:
        """Format RAG context for inclusion in LLM prompt"""
        if not rag_context.chunks:
            return ""

        context_parts = ["## Relevant Context\n"]

        # Add dataset search results
        if rag_context.chunks:
            context_parts.append("### From Documents:")
            for i, chunk in enumerate(rag_context.chunks[:5], 1):  # Limit to top 5
                document_name = chunk.get("metadata", {}).get("document_name", "Unknown Document")
                content = chunk.get("content", chunk.get("text", ""))

                context_parts.append(f"\n**Source {i}**: {document_name}")
                context_parts.append(f"Content: {content[:500]}...")  # Truncate long content
                context_parts.append("")


        # Add source attribution
        if rag_context.sources:
            context_parts.append("### Sources:")
            for source in rag_context.sources:
                context_parts.append(f"- {source['document_name']} ({source['chunk_count']} relevant sections)")

        return "\n".join(context_parts)

    def format_context_for_agent(
        self,
        rag_context: RAGContext,
        compact_mode: bool = False
    ) -> str:
        """
        Format RAG results with clear source attribution for agent consumption.

        Args:
            rag_context: RAG search results with chunks and sources
            compact_mode: Use compact format for >2 files (~200 tokens vs ~700)

        Returns:
            Formatted context string ready for LLM injection
        """
        if not rag_context.chunks:
            return ""

        dataset_chunks = [
            c for c in rag_context.chunks
            if c.get('source_type') == 'dataset' or c.get('dataset_id')
        ]
        file_chunks = [
            c for c in rag_context.chunks
            if c.get('source_type') == 'conversation_file'
        ]

        context_parts = []
        context_parts.append("=" * 80)
        context_parts.append("📚 KNOWLEDGE BASE CONTEXT - DATASET DOCUMENTS")
        context_parts.append("=" * 80)

        if dataset_chunks:
            context_parts.append("\n📂 FROM AGENT'S PERMANENT DATASETS:")
            context_parts.append("(These are documents from the agent's configured knowledge base)\n")

            for i, chunk in enumerate(dataset_chunks, 1):
                dataset_name = chunk.get('dataset_name', 'Unknown Dataset')
                doc_name = chunk.get('metadata', {}).get('document_name', 'Unknown')
                content = chunk.get('content', chunk.get('text', ''))
                score = chunk.get('similarity_score', 0.0)

                if compact_mode:
                    context_parts.append(f"\n[Dataset: {dataset_name}]\n{content[:400]}...")
                else:
                    context_parts.append(f"\n{'─' * 80}")
                    context_parts.append(f"📚 DATASET EXCERPT {i}")
                    context_parts.append(f"Dataset: {dataset_name} / Document: {doc_name}")
                    context_parts.append(f"Relevance: {score:.2f}")
                    context_parts.append(f"{'─' * 80}")
                    context_parts.append(content[:600] if len(content) > 600 else content)
                    if len(content) > 600:
                        context_parts.append("\n[... excerpt continues ...]")

        if file_chunks:
            context_parts.append(f"\n\n{'=' * 80}")
            context_parts.append("📎 FROM CONVERSATION FILES - USER ATTACHED DOCUMENTS")
            context_parts.append("=" * 80)
            context_parts.append("(These are files the user attached to THIS specific conversation)\n")

            for i, chunk in enumerate(file_chunks, 1):
                filename = chunk.get('document_name', chunk.get('original_filename', 'Unknown'))
                content = chunk.get('content', chunk.get('text', ''))
                score = chunk.get('similarity_score', 0.0)

                if compact_mode:
                    context_parts.append(f"\n[File: {filename}]\n{content[:400]}...")
                else:
                    context_parts.append(f"\n{'─' * 80}")
                    context_parts.append(f"📄 FILE EXCERPT {i}: {filename}")
                    context_parts.append(f"Relevance: {score:.2f}")
                    context_parts.append(f"{'─' * 80}")
                    context_parts.append(content[:600] if len(content) > 600 else content)
                    if len(content) > 600:
                        context_parts.append("\n[... excerpt continues ...]")

        context_text = "\n".join(context_parts)

        formatted_context = f"""{context_text}

{'=' * 80}
⚠️  CONTEXT USAGE INSTRUCTIONS:
1. CONVERSATION FILES (📎) = User's attached files for THIS chat - cite as "In your attached file..."
2. DATASET DOCUMENTS (📂) = Agent's knowledge base - cite as "According to the dataset..."
3. Always prioritize conversation files when both sources have relevant information
4. Be explicit about which source you're referencing in your answer
{'=' * 80}"""

        return formatted_context


# Global instance factory
def get_rag_orchestrator(tenant_domain: str, user_id: str) -> RAGOrchestrator:
    """Get RAG orchestrator instance for tenant and user"""
    return RAGOrchestrator(tenant_domain, user_id)