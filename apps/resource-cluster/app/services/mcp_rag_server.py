"""
GT 2.0 MCP RAG Server

Provides RAG (Retrieval-Augmented Generation) capabilities as an MCP server.
Agents can use this server to search datasets, query documents, and retrieve
relevant context for user queries.

Tools provided:
- search_datasets: Search across user's accessible datasets
- query_documents: Query specific documents for relevant chunks
- get_relevant_chunks: Get relevant text chunks based on similarity
- list_user_datasets: List all datasets accessible to the user
- get_dataset_info: Get detailed information about a dataset
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass
import httpx
import json

from app.core.security import verify_capability_token
from app.services.mcp_server import MCPServerResource, MCPServerConfig

logger = logging.getLogger(__name__)


@dataclass
class RAGSearchParams:
    """Parameters for RAG search operations"""
    query: str
    dataset_ids: Optional[List[str]] = None
    search_method: str = "hybrid"  # hybrid, vector, text
    max_results: int = 10
    similarity_threshold: float = 0.7
    include_metadata: bool = True


@dataclass
class RAGSearchResult:
    """Result from RAG search operation"""
    chunk_id: str
    document_id: str
    dataset_id: str
    dataset_name: str
    document_name: str
    content: str
    similarity_score: float
    chunk_index: int
    metadata: Dict[str, Any]


class MCPRAGServer:
    """
    MCP server for RAG operations in GT 2.0.

    Provides secure, tenant-isolated access to document search capabilities
    through standardized MCP tool interfaces.
    """

    def __init__(self, tenant_backend_url: str = "http://tenant-backend:8000"):
        self.tenant_backend_url = tenant_backend_url
        self.server_name = "rag_server"
        self.server_type = "rag"

        # Define available tools (streamlined for simplicity)
        self.available_tools = [
            "search_datasets"
        ]

        # Tool schemas for MCP protocol (enhanced with flexible parameters)
        self.tool_schemas = {
            "search_datasets": {
                "name": "search_datasets",
                "description": "Search through datasets containing uploaded documents, PDFs, and files. Use when users ask about documentation, reference materials, checking files, looking up information, need data from uploaded content, want to know what's in the dataset, search our data, check if we have something, or look through files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for in the datasets"
                        },
                        "dataset_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "(Optional) List of specific dataset IDs to search within"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "(Optional) File pattern filter (e.g., '*.pdf', '*.txt')"
                        },
                        "search_all": {
                            "type": "boolean",
                            "default": False,
                            "description": "(Optional) Search across all accessible datasets (ignores dataset_ids)"
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "description": "(Optional) Number of results to return (default: 10)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    async def handle_tool_call(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        tenant_domain: str,
        user_id: str,
        agent_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle MCP tool call with tenant isolation and user context.

        Args:
            tool_name: Name of the tool being called
            parameters: Tool parameters from the LLM
            tenant_domain: Tenant domain for isolation
            user_id: User making the request

        Returns:
            Tool execution result or error
        """
        logger.info(f"🚀 MCP RAG Server: handle_tool_call called - tool={tool_name}, tenant={tenant_domain}, user={user_id}")
        logger.info(f"📝 MCP RAG Server: parameters={parameters}")
        try:
            # Validate tool exists
            if tool_name not in self.available_tools:
                return {
                    "error": f"Unknown tool: {tool_name}",
                    "tool_name": tool_name
                }

            # Route to appropriate handler
            if tool_name == "search_datasets":
                return await self._search_datasets(parameters, tenant_domain, user_id, agent_context)
            else:
                return {
                    "error": f"Tool handler not implemented: {tool_name}",
                    "tool_name": tool_name
                }

        except Exception as e:
            logger.error(f"Error handling tool call {tool_name}: {e}")
            return {
                "error": f"Tool execution failed: {str(e)}",
                "tool_name": tool_name
            }

    def _verify_user_access(self, user_id: str, tenant_domain: str) -> bool:
        """Verify user has access to tenant resources (simplified check)"""
        # In a real system, this would query the database to verify
        # that the user has access to the tenant's resources
        # For now, we trust that the tenant backend has already verified this
        return bool(user_id and tenant_domain)

    async def _search_datasets(
        self,
        parameters: Dict[str, Any],
        tenant_domain: str,
        user_id: str,
        agent_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search across user's datasets"""
        logger.info(f"🔍 RAG Server: search_datasets called for user {user_id} in tenant {tenant_domain}")
        logger.info(f"📝 RAG Server: search parameters = {parameters}")
        logger.info(f"📝 RAG Server: parameter types: {[(k, type(v)) for k, v in parameters.items()]}")

        try:
            query = parameters.get("query", "").strip()
            list_mode = parameters.get("list_mode", False)

            # Handle list mode - list available datasets instead of searching
            if list_mode:
                logger.info(f"🔍 RAG Server: List mode activated - fetching available datasets")

                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(
                        f"{self.tenant_backend_url}/api/v1/datasets/internal/list",
                        headers={
                            "X-Tenant-Domain": tenant_domain,
                            "X-User-ID": user_id
                        }
                    )

                    if response.status_code == 200:
                        datasets = response.json()
                        logger.info(f"✅ RAG Server: Successfully listed {len(datasets)} datasets")
                        return {
                            "success": True,
                            "datasets": datasets,
                            "total_count": len(datasets),
                            "list_mode": True
                        }
                    else:
                        logger.error(f"❌ RAG Server: Failed to list datasets: {response.status_code} - {response.text}")
                        return {"error": f"Failed to list datasets: {response.status_code}"}

            # Normal search mode
            if not query:
                logger.error("❌ RAG Server: Query parameter is required")
                return {"error": "Query parameter is required"}

            # Prepare search request with enhanced parameters
            dataset_ids = parameters.get("dataset_ids")
            file_pattern = parameters.get("file_pattern")
            search_all = parameters.get("search_all", False)

            # Handle legacy dataset_id parameter (backwards compatibility)
            if dataset_ids is None and parameters.get("dataset_id"):
                dataset_ids = [parameters.get("dataset_id")]

            # Ensure dataset_ids is properly formatted
            if dataset_ids is None:
                dataset_ids = []
            elif isinstance(dataset_ids, str):
                dataset_ids = [dataset_ids]

            # If search_all is True, ignore dataset_ids filter
            if search_all:
                dataset_ids = []

            # AGENT-AWARE: If no datasets specified, use agent's configured datasets
            if not dataset_ids and not search_all and agent_context:
                agent_dataset_ids = agent_context.get('selected_dataset_ids', [])
                if agent_dataset_ids:
                    dataset_ids = agent_dataset_ids
                    agent_name = agent_context.get('agent_name', 'Unknown')
                    logger.info(f"✅ RAG Server: Using agent '{agent_name}' datasets: {dataset_ids}")
                else:
                    logger.warning(f"⚠️ RAG Server: Agent context available but no datasets configured")
            elif not dataset_ids and not search_all:
                logger.warning(f"⚠️ RAG Server: No dataset_ids provided and no agent context available")

            search_request = {
                "query": query,
                "search_type": parameters.get("search_method", "hybrid"),
                "max_results": parameters.get("max_results", 10),  # No arbitrary cap
                "dataset_ids": dataset_ids,
                "min_similarity": 0.3
            }

            # Add file_pattern if provided
            if file_pattern:
                search_request["file_pattern"] = file_pattern

            logger.info(f"🎯 RAG Server: prepared search request = {search_request}")

            # Call tenant backend search API
            logger.info(f"🌐 RAG Server: calling tenant backend at {self.tenant_backend_url}/api/v1/search/")
            logger.info(f"🌐 RAG Server: request headers: X-Tenant-Domain='{tenant_domain}', X-User-ID='{user_id}'")
            logger.info(f"🌐 RAG Server: request body: {search_request}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.tenant_backend_url}/api/v1/search/",
                    json=search_request,
                    headers={
                        "X-Tenant-Domain": tenant_domain,
                        "X-User-ID": user_id,
                        "Content-Type": "application/json"
                    }
                )

                logger.info(f"📊 RAG Server: tenant backend response: {response.status_code}")
                if response.status_code != 200:
                    logger.error(f"📊 RAG Server: error response body: {response.text}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ RAG Server: search successful, got {len(data.get('results', []))} results")

                    # Format results for MCP response
                    results = []
                    for result in data.get("results", []):
                        results.append({
                            "chunk_id": result.get("chunk_id"),
                            "document_id": result.get("document_id"),
                            "dataset_id": result.get("dataset_id"),
                            "content": result.get("text", ""),
                            "similarity_score": result.get("hybrid_score", 0.0),
                            "metadata": result.get("metadata", {})
                        })

                    return {
                        "success": True,
                        "query": query,
                        "results_count": len(results),
                        "results": results,
                        "search_method": data.get("search_type", "hybrid")
                    }
                else:
                    error_text = response.text
                    logger.error(f"❌ RAG Server: search failed: {response.status_code} - {error_text}")
                    return {
                        "error": f"Search failed: {response.status_code} - {error_text}",
                        "query": query
                    }

        except Exception as e:
            logger.error(f"Dataset search error: {e}")
            return {
                "error": f"Search operation failed: {str(e)}",
                "query": parameters.get("query", "")
            }

    async def _query_documents(
        self,
        parameters: Dict[str, Any],
        tenant_domain: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Query specific documents for relevant chunks"""
        try:
            query = parameters.get("query", "").strip()
            document_ids = parameters.get("document_ids", [])

            if not query or not document_ids:
                return {"error": "Both query and document_ids are required"}

            # Use search API with document ID filter
            search_request = {
                "query": query,
                "search_type": "hybrid",
                "max_results": parameters.get("max_results", 5),
                "document_ids": document_ids
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.tenant_backend_url}/api/v1/search/documents",
                    json=search_request,
                    headers={
                        "X-Tenant-Domain": tenant_domain,
                        "X-User-ID": user_id,
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "query": query,
                        "document_ids": document_ids,
                        "results": data.get("results", [])
                    }
                else:
                    return {
                        "error": f"Document query failed: {response.status_code}",
                        "query": query,
                        "document_ids": document_ids
                    }

        except Exception as e:
            return {
                "error": f"Document query failed: {str(e)}",
                "query": parameters.get("query", "")
            }

    async def _list_user_datasets(
        self,
        parameters: Dict[str, Any],
        tenant_domain: str,
        user_id: str
    ) -> Dict[str, Any]:
        """List user's accessible datasets"""
        try:
            include_stats = parameters.get("include_stats", True)

            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {"include_stats": include_stats}
                response = await client.get(
                    f"{self.tenant_backend_url}/api/v1/datasets",
                    params=params,
                    headers={
                        "X-Tenant-Domain": tenant_domain,
                        "X-User-ID": user_id
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    datasets = data.get("data", []) if isinstance(data, dict) else data

                    # Format for MCP response
                    formatted_datasets = []
                    for dataset in datasets:
                        formatted_datasets.append({
                            "id": dataset.get("id"),
                            "name": dataset.get("name"),
                            "description": dataset.get("description"),
                            "document_count": dataset.get("document_count", 0),
                            "chunk_count": dataset.get("chunk_count", 0),
                            "created_at": dataset.get("created_at"),
                            "access_group": dataset.get("access_group", "individual")
                        })

                    return {
                        "success": True,
                        "datasets": formatted_datasets,
                        "total_count": len(formatted_datasets)
                    }
                else:
                    return {
                        "error": f"Failed to list datasets: {response.status_code}"
                    }

        except Exception as e:
            return {
                "error": f"Failed to list datasets: {str(e)}"
            }

    async def _get_dataset_info(
        self,
        parameters: Dict[str, Any],
        tenant_domain: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get detailed information about a dataset"""
        try:
            dataset_id = parameters.get("dataset_id")
            if not dataset_id:
                return {"error": "dataset_id parameter is required"}

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.tenant_backend_url}/api/v1/datasets/{dataset_id}",
                    headers={
                        "X-Tenant-Domain": tenant_domain,
                        "X-User-ID": user_id
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    dataset = data.get("data", data)

                    return {
                        "success": True,
                        "dataset": {
                            "id": dataset.get("id"),
                            "name": dataset.get("name"),
                            "description": dataset.get("description"),
                            "document_count": dataset.get("document_count", 0),
                            "chunk_count": dataset.get("chunk_count", 0),
                            "vector_count": dataset.get("vector_count", 0),
                            "storage_size_mb": dataset.get("storage_size_mb", 0),
                            "created_at": dataset.get("created_at"),
                            "updated_at": dataset.get("updated_at"),
                            "access_group": dataset.get("access_group"),
                            "tags": dataset.get("tags", [])
                        }
                    }
                elif response.status_code == 404:
                    return {
                        "error": f"Dataset not found: {dataset_id}"
                    }
                else:
                    return {
                        "error": f"Failed to get dataset info: {response.status_code}"
                    }

        except Exception as e:
            return {
                "error": f"Failed to get dataset info: {str(e)}"
            }

    async def _get_user_agent_datasets(self, tenant_domain: str, user_id: str) -> List[str]:
        """Auto-detect agent datasets for the current user"""
        try:
            # Get user's agents and their configured datasets
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.tenant_backend_url}/api/v1/agents",
                    headers={
                        "X-Tenant-Domain": tenant_domain,
                        "X-User-ID": user_id
                    }
                )

                if response.status_code == 200:
                    agents_data = response.json()
                    agents = agents_data.get("data", []) if isinstance(agents_data, dict) else agents_data

                    # Collect all dataset IDs from all user's agents
                    all_dataset_ids = set()
                    for agent in agents:
                        agent_dataset_ids = agent.get("selected_dataset_ids", [])
                        if agent_dataset_ids:
                            all_dataset_ids.update(agent_dataset_ids)
                            logger.info(f"🔍 RAG Server: Agent {agent.get('name', 'unknown')} has datasets: {agent_dataset_ids}")

                    return list(all_dataset_ids)
                else:
                    logger.warning(f"⚠️ RAG Server: Failed to get agents: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"❌ RAG Server: Error getting user agent datasets: {e}")
            return []

    async def _get_relevant_chunks(
        self,
        parameters: Dict[str, Any],
        tenant_domain: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get most relevant chunks for a query"""
        try:
            query = parameters.get("query", "").strip()
            if not query:
                return {"error": "query parameter is required"}

            chunk_count = min(parameters.get("chunk_count", 3), 10)  # Cap at 10
            min_similarity = parameters.get("min_similarity", 0.6)
            dataset_ids = parameters.get("dataset_ids")

            search_request = {
                "query": query,
                "search_type": "vector",  # Use vector search for relevance
                "max_results": chunk_count,
                "min_similarity": min_similarity,
                "dataset_ids": dataset_ids
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.tenant_backend_url}/api/v1/search",
                    json=search_request,
                    headers={
                        "X-Tenant-Domain": tenant_domain,
                        "X-User-ID": user_id,
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    chunks = []

                    for result in data.get("results", []):
                        chunks.append({
                            "chunk_id": result.get("chunk_id"),
                            "document_id": result.get("document_id"),
                            "dataset_id": result.get("dataset_id"),
                            "content": result.get("text", ""),
                            "similarity_score": result.get("vector_similarity", 0.0),
                            "chunk_index": result.get("rank", 0),
                            "metadata": result.get("metadata", {})
                        })

                    return {
                        "success": True,
                        "query": query,
                        "chunks": chunks,
                        "chunk_count": len(chunks),
                        "min_similarity": min_similarity
                    }
                else:
                    return {
                        "error": f"Chunk retrieval failed: {response.status_code}"
                    }

        except Exception as e:
            return {
                "error": f"Failed to get relevant chunks: {str(e)}"
            }

    def get_server_config(self) -> MCPServerConfig:
        """Get MCP server configuration"""
        return MCPServerConfig(
            server_name=self.server_name,
            server_url="internal://mcp-rag-server",
            server_type=self.server_type,
            available_tools=self.available_tools,
            required_capabilities=["mcp:rag:*"],
            sandbox_mode=True,
            max_memory_mb=256,
            max_cpu_percent=25,
            timeout_seconds=30,
            network_isolation=False,  # Needs to access tenant backend
            max_requests_per_minute=120,
            max_concurrent_requests=10
        )

    def get_tool_schemas(self) -> Dict[str, Any]:
        """Get MCP tool schemas for this server"""
        return self.tool_schemas


# Global instance
mcp_rag_server = MCPRAGServer()