"""
Resource Cluster Client for GT 2.0 Tenant Backend

Provides stateless access to Resource Cluster services including:
- Document processing
- Embedding generation
- Vector storage (ChromaDB)
- Model inference

Perfect tenant isolation with capability-based authentication.
"""

import logging
import asyncio
import aiohttp
import json
import gc
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from app.core.config import get_settings
from app.core.capability_client import CapabilityClient

logger = logging.getLogger(__name__)


class ResourceClusterClient:
    """
    Client for accessing Resource Cluster services with capability-based auth.
    
    GT 2.0 Security Principles:
    - Capability tokens for fine-grained access control
    - Stateless operations (no data persistence in Resource Cluster)
    - Perfect tenant isolation
    - Immediate memory cleanup
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.capability_client = CapabilityClient()
        
        # Resource Cluster endpoints
        # IMPORTANT: Use Docker service name for stability across container restarts
        # Fixed 2025-09-12: Changed from hardcoded IP to service name for reliability
        self.base_url = getattr(
            self.settings, 
            'resource_cluster_url',  # Matches Pydantic field name (case insensitive)
            'http://gentwo-resource-backend:8000'  # Fallback uses service name, not IP
        )
        
        self.endpoints = {
            'document_processor': f"{self.base_url}/api/v1/process/document",
            'embedding_generator': f"{self.base_url}/api/v1/embeddings/generate",
            'chromadb_backend': f"{self.base_url}/api/v1/vectors",
            'inference': f"{self.base_url}/api/v1/ai/chat/completions"  # Updated to match actual endpoint
        }
        
        # Request timeouts
        self.request_timeout = 300  # seconds - 5 minutes for complex agent operations
        self.upload_timeout = 300   # seconds for large documents
        
        logger.info("Resource Cluster client initialized")
    
    async def _get_capability_token(
        self,
        tenant_id: str,
        user_id: str,
        resources: List[str]
    ) -> str:
        """Generate capability token for Resource Cluster access"""
        try:
            token = await self.capability_client.generate_capability_token(
                user_email=user_id,  # Using user_id as email for now
                tenant_id=tenant_id,
                resources=resources,
                expires_hours=1
            )
            return token
        except Exception as e:
            logger.error(f"Failed to generate capability token: {e}")
            raise
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict[str, Any],
        tenant_id: str,
        user_id: str,
        resources: List[str],
        timeout: int = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Resource Cluster"""
        try:
            # Get capability token
            token = await self._get_capability_token(tenant_id, user_id, resources)
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'X-Tenant-ID': tenant_id,
                'X-User-ID': user_id,
                'X-Request-ID': f"{tenant_id}_{user_id}_{datetime.utcnow().timestamp()}"
            }
            
            # Make request
            timeout_config = aiohttp.ClientTimeout(total=timeout or self.request_timeout)
            
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.request(
                    method=method.upper(),
                    url=endpoint,
                    json=data,
                    headers=headers
                ) as response:
                    
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"Resource Cluster error: {response.status} - {error_text}"
                        )
                    
                    result = await response.json()
                    return result
                    
        except Exception as e:
            logger.error(f"Resource Cluster request failed: {e}")
            raise
    
    # Document Processing
    
    async def process_document(
        self,
        content: bytes,
        document_type: str,
        strategy_type: str = "hybrid",
        tenant_id: str = None,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Process document into chunks via Resource Cluster"""
        try:
            # Convert bytes to base64 for JSON transport
            import base64
            content_b64 = base64.b64encode(content).decode('utf-8')
            
            request_data = {
                "content": content_b64,
                "document_type": document_type,
                "strategy": {
                    "strategy_type": strategy_type,
                    "chunk_size": 512,
                    "chunk_overlap": 128
                }
            }
            
            # Clear original content from memory
            del content
            gc.collect()
            
            result = await self._make_request(
                method='POST',
                endpoint=self.endpoints['document_processor'],
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['document_processing'],
                timeout=self.upload_timeout
            )
            
            chunks = result.get('chunks', [])
            logger.info(f"Processed document into {len(chunks)} chunks")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            gc.collect()
            raise
    
    # Embedding Generation
    
    async def generate_document_embeddings(
        self,
        documents: List[str],
        tenant_id: str,
        user_id: str
    ) -> List[List[float]]:
        """Generate embeddings for documents"""
        try:
            request_data = {
                "texts": documents,
                "model": "BAAI/bge-m3",
                "instruction": None  # Document embeddings don't need instruction
            }
            
            result = await self._make_request(
                method='POST',
                endpoint=self.endpoints['embedding_generator'],
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['embedding_generation']
            )
            
            embeddings = result.get('embeddings', [])
            
            # Clear documents from memory
            del documents
            gc.collect()
            
            logger.info(f"Generated {len(embeddings)} document embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Document embedding generation failed: {e}")
            gc.collect()
            raise
    
    async def generate_query_embeddings(
        self,
        queries: List[str],
        tenant_id: str,
        user_id: str
    ) -> List[List[float]]:
        """Generate embeddings for queries"""
        try:
            request_data = {
                "texts": queries,
                "model": "BAAI/bge-m3",
                "instruction": "Represent this sentence for searching relevant passages: "
            }
            
            result = await self._make_request(
                method='POST',
                endpoint=self.endpoints['embedding_generator'],
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['embedding_generation']
            )
            
            embeddings = result.get('embeddings', [])
            
            # Clear queries from memory
            del queries
            gc.collect()
            
            logger.info(f"Generated {len(embeddings)} query embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Query embedding generation failed: {e}")
            gc.collect()
            raise
    
    # Vector Storage (ChromaDB)
    
    async def create_vector_collection(
        self,
        tenant_id: str,
        user_id: str,
        dataset_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create vector collection in ChromaDB"""
        try:
            request_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "dataset_name": dataset_name,
                "metadata": metadata or {}
            }
            
            result = await self._make_request(
                method='POST',
                endpoint=f"{self.endpoints['chromadb_backend']}/collections",
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['vector_storage']
            )
            
            success = result.get('success', False)
            logger.info(f"Created vector collection for {dataset_name}: {success}")
            
            return success
            
        except Exception as e:
            logger.error(f"Vector collection creation failed: {e}")
            raise
    
    async def store_vectors(
        self,
        tenant_id: str,
        user_id: str,
        dataset_name: str,
        documents: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]] = None,
        ids: List[str] = None
    ) -> bool:
        """Store vectors in ChromaDB"""
        try:
            request_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "dataset_name": dataset_name,
                "documents": documents,
                "embeddings": embeddings,
                "metadata": metadata or [],
                "ids": ids
            }
            
            result = await self._make_request(
                method='POST',
                endpoint=f"{self.endpoints['chromadb_backend']}/store",
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['vector_storage']
            )
            
            # Clear vectors from memory immediately
            del documents, embeddings
            gc.collect()
            
            success = result.get('success', False)
            logger.info(f"Stored vectors in {dataset_name}: {success}")
            
            return success
            
        except Exception as e:
            logger.error(f"Vector storage failed: {e}")
            gc.collect()
            raise
    
    async def search_vectors(
        self,
        tenant_id: str,
        user_id: str,
        dataset_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search vectors in ChromaDB"""
        try:
            request_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "dataset_name": dataset_name,
                "query_embedding": query_embedding,
                "top_k": top_k,
                "filter_metadata": filter_metadata or {}
            }
            
            result = await self._make_request(
                method='POST',
                endpoint=f"{self.endpoints['chromadb_backend']}/search",
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['vector_storage']
            )
            
            # Clear query embedding from memory
            del query_embedding
            gc.collect()
            
            results = result.get('results', [])
            logger.info(f"Found {len(results)} vector search results")
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            gc.collect()
            raise
    
    async def delete_vector_collection(
        self,
        tenant_id: str,
        user_id: str,
        dataset_name: str
    ) -> bool:
        """Delete vector collection from ChromaDB"""
        try:
            request_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "dataset_name": dataset_name
            }
            
            result = await self._make_request(
                method='DELETE',
                endpoint=f"{self.endpoints['chromadb_backend']}/collections",
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['vector_storage']
            )
            
            success = result.get('success', False)
            logger.info(f"Deleted vector collection {dataset_name}: {success}")
            
            return success
            
        except Exception as e:
            logger.error(f"Vector collection deletion failed: {e}")
            raise
    
    # Model Inference
    
    async def inference_with_context(
        self,
        messages: List[Dict[str, str]],
        context: str,
        model: str = "llama-3.1-70b-versatile",
        tenant_id: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Perform inference with RAG context"""
        try:
            # Inject context into system message
            enhanced_messages = []
            system_context = f"Use the following context to answer the user's question:\n\n{context}\n\n"
            
            for msg in messages:
                if msg.get("role") == "system":
                    enhanced_msg = msg.copy()
                    enhanced_msg["content"] = system_context + enhanced_msg["content"]
                    enhanced_messages.append(enhanced_msg)
                else:
                    enhanced_messages.append(msg)
            
            # Add system message if none exists
            if not any(msg.get("role") == "system" for msg in enhanced_messages):
                enhanced_messages.insert(0, {
                    "role": "system",
                    "content": system_context + "You are a helpful AI agent."
                })
            
            request_data = {
                "messages": enhanced_messages,
                "model": model,
                "temperature": 0.7,
                "max_tokens": 4000,
                "user_id": user_id,
                "tenant_id": tenant_id
            }
            
            result = await self._make_request(
                method='POST',
                endpoint=self.endpoints['inference'],
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['llm_inference']
            )
            
            # Clear context from memory
            del context, enhanced_messages
            gc.collect()
            
            return result
            
        except Exception as e:
            logger.error(f"Inference with context failed: {e}")
            gc.collect()
            raise
    
    async def check_health(self) -> Dict[str, Any]:
        """Check Resource Cluster health"""
        try:
            # Test basic connectivity
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        health_data = await response.json()
                        return {
                            "status": "healthy",
                            "resource_cluster": health_data,
                            "endpoints": list(self.endpoints.keys()),
                            "base_url": self.base_url
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "error": f"Health check failed: {response.status}",
                            "base_url": self.base_url
                        }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "base_url": self.base_url
            }
    
    async def call_inference_endpoint(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str = "chat/completions",
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Call AI inference endpoint on Resource Cluster"""
        try:
            # Use the direct inference endpoint
            inference_url = self.endpoints['inference']
            
            # Add tenant/user context to request
            request_data = data.copy() if data else {}
            
            # Make request with capability token
            result = await self._make_request(
                method='POST',
                endpoint=inference_url,
                data=request_data,
                tenant_id=tenant_id,
                user_id=user_id,
                resources=['llm']  # Use valid ResourceType from resource cluster
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Inference endpoint call failed: {e}")
            raise
    
    # Streaming removed for reliability - using non-streaming only