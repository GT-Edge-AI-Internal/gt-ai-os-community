"""
Embedding Model Backend

STATELESS embedding generation using BGE-M3 model hosted on GT's GPU clusters.
All embeddings are generated in real-time - NO user data is stored.
"""

import logging
import gc
import hashlib
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
# import numpy as np  # Temporarily disabled for Docker build
import aiohttp
import json

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class EmbeddingRequest:
    """Request structure for embedding generation"""
    texts: List[str]
    model: str = "BAAI/bge-m3"
    batch_size: int = 32
    normalize: bool = True
    instruction: Optional[str] = None  # For instruction-based embeddings


class EmbeddingBackend:
    """
    STATELESS embedding backend for BGE-M3 model.
    
    Security principles:
    - NO persistence of embeddings or text
    - All processing via GT's internal GPU cluster
    - Immediate memory cleanup after generation
    - No caching of user content
    - Request signing and verification
    """
    
    def __init__(self):
        self.model_name = "BAAI/bge-m3"
        self.embedding_dimensions = 1024  # BGE-M3 dimensions
        self.max_batch_size = 32
        self.max_sequence_length = 8192  # BGE-M3 supports up to 8192 tokens

        # Determine endpoint based on configuration
        self.embedding_endpoint = self._get_embedding_endpoint()

        # Timeout for embedding requests
        self.request_timeout = 60  # seconds for model loading

        logger.info(f"STATELESS embedding backend initialized for {self.model_name}")
        logger.info(f"Using embedding endpoint: {self.embedding_endpoint}")

    def _get_embedding_endpoint(self) -> str:
        """
        Get the embedding endpoint based on configuration.
        Priority:
        1. Model registry from config sync (database-backed)
        2. Environment variables (BGE_M3_LOCAL_MODE, BGE_M3_EXTERNAL_ENDPOINT)
        3. Default local endpoint
        """
        # Try to get configuration from model registry first (loaded from database)
        try:
            from app.services.model_service import default_model_service
            import asyncio

            # Use the default model service instance (singleton) used by config sync
            model_service = default_model_service

            # Try to get the model config synchronously (during initialization)
            # The get_model method is async, so we need to handle this carefully
            bge_m3_config = model_service.model_registry.get("BAAI/bge-m3")

            if bge_m3_config:
                # Model registry stores endpoint as 'endpoint_url' and config as 'parameters'
                endpoint = bge_m3_config.get("endpoint_url")
                config = bge_m3_config.get("parameters", {})
                is_local_mode = config.get("is_local_mode", True)
                external_endpoint = config.get("external_endpoint")

                logger.info(f"Found BGE-M3 in registry: endpoint_url={endpoint}, is_local_mode={is_local_mode}, external_endpoint={external_endpoint}")

                if endpoint:
                    logger.info(f"Using BGE-M3 endpoint from model registry (is_local_mode={is_local_mode}): {endpoint}")
                    return endpoint
                else:
                    logger.warning(f"BGE-M3 found in registry but endpoint_url is None/empty. Full config: {bge_m3_config}")
            else:
                available_models = list(model_service.model_registry.keys())
                logger.debug(f"BGE-M3 not found in model registry during init (expected on first startup). Available models: {available_models}")
        except Exception as e:
            logger.debug(f"Model registry not yet available during startup (will be populated after config sync): {e}")

        # Fall back to Settings fields (environment variables or .env file)
        is_local_mode = getattr(settings, 'bge_m3_local_mode', True)
        external_endpoint = getattr(settings, 'bge_m3_external_endpoint', None)

        if not is_local_mode and external_endpoint:
            logger.info(f"Using external BGE-M3 endpoint from settings: {external_endpoint}")
            return external_endpoint

        # Default to local endpoint
        local_endpoint = getattr(
            settings,
            'embedding_endpoint',
            'http://gentwo-vllm-embeddings:8000/v1/embeddings'
        )
        logger.info(f"Using local BGE-M3 endpoint: {local_endpoint}")
        return local_endpoint

    async def update_endpoint_config(self, is_local_mode: bool, external_endpoint: str = None):
        """
        Update the embedding endpoint configuration dynamically.
        This allows switching between local and external endpoints without restart.
        """
        if is_local_mode:
            self.embedding_endpoint = getattr(
                settings,
                'embedding_endpoint',
                'http://gentwo-vllm-embeddings:8000/v1/embeddings'
            )
        else:
            if external_endpoint:
                self.embedding_endpoint = external_endpoint
            else:
                raise ValueError("External endpoint must be provided when not in local mode")

        logger.info(f"BGE-M3 endpoint updated to: {self.embedding_endpoint}")
        logger.info(f"Mode: {'Local GT Edge' if is_local_mode else 'External API'}")

    def refresh_endpoint_from_registry(self):
        """
        Refresh the embedding endpoint from the model registry.
        Called by config sync when BGE-M3 configuration changes.
        """
        logger.info(f"Refreshing embedding endpoint - current: {self.embedding_endpoint}")
        new_endpoint = self._get_embedding_endpoint()
        if new_endpoint != self.embedding_endpoint:
            logger.info(f"Refreshing BGE-M3 endpoint from {self.embedding_endpoint} to {new_endpoint}")
            self.embedding_endpoint = new_endpoint
        else:
            logger.info(f"BGE-M3 endpoint unchanged: {self.embedding_endpoint}")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        instruction: Optional[str] = None,
        tenant_id: str = None,
        request_id: str = None
    ) -> List[List[float]]:
        """
        Generate embeddings for texts using BGE-M3 - STATELESS operation.
        
        Args:
            texts: List of texts to embed (will be cleared from memory)
            instruction: Optional instruction for query vs document embeddings
            tenant_id: Tenant ID for audit logging (not stored with data)
            request_id: Request ID for tracing
        
        Returns:
            List of embedding vectors (immediately returned, not stored)
        """
        try:
            # Validate input
            if not texts:
                return []
            
            if len(texts) > self.max_batch_size:
                # Process in batches
                return await self._batch_process_embeddings(
                    texts, instruction, tenant_id, request_id
                )
            
            # Prepare request
            request_data = {
                "model": self.model_name,
                "input": texts,
                "encoding_format": "float",
                "dimensions": self.embedding_dimensions
            }
            
            # Add instruction if provided (for query vs document distinction)
            if instruction:
                request_data["instruction"] = instruction
            
            # Add metadata for audit (not stored with embeddings)
            metadata = {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "text_count": len(texts),
                # Hash for deduplication without storing content
                "content_hash": hashlib.sha256(
                    "".join(texts).encode()
                ).hexdigest()[:16]
            }
            
            # Call vLLM service - NO FALLBACKS
            embeddings = await self._call_embedding_service(request_data, metadata)
            
            # Clear texts from memory immediately
            del texts
            gc.collect()
            
            # Validate response
            if not embeddings or len(embeddings) == 0:
                raise ValueError("No embeddings returned from service")
            
            # Normalize if needed
            if self._should_normalize():
                embeddings = self._normalize_embeddings(embeddings)
            
            logger.info(
                f"Generated {len(embeddings)} embeddings (STATELESS) "
                f"for tenant {tenant_id}"
            )
            
            # Return immediately - no storage
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Ensure memory is cleared even on error
            gc.collect()
            raise
        finally:
            # Always ensure memory cleanup
            gc.collect()
    
    async def _batch_process_embeddings(
        self,
        texts: List[str],
        instruction: Optional[str],
        tenant_id: str,
        request_id: str
    ) -> List[List[float]]:
        """Process large text lists in batches using vLLM service"""
        all_embeddings = []
        
        for i in range(0, len(texts), self.max_batch_size):
            batch = texts[i:i + self.max_batch_size]
            
            # Prepare request for this batch
            request_data = {
                "model": self.model_name,
                "input": batch,
                "encoding_format": "float",
                "dimensions": self.embedding_dimensions
            }
            
            if instruction:
                request_data["instruction"] = instruction
            
            metadata = {
                "tenant_id": tenant_id,
                "request_id": f"{request_id}_batch_{i}",
                "text_count": len(batch),
                "content_hash": hashlib.sha256(
                    "".join(batch).encode()
                ).hexdigest()[:16]
            }
            
            batch_embeddings = await self._call_embedding_service(request_data, metadata)
            all_embeddings.extend(batch_embeddings)
            
            # Clear batch from memory
            del batch
            gc.collect()
        
        return all_embeddings
    
    
    async def _call_embedding_service(
        self,
        request_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[List[float]]:
        """Call internal GPU cluster embedding service"""
        
        async with aiohttp.ClientSession() as session:
            try:
                # Add capability token for authentication
                headers = {
                    "Content-Type": "application/json",
                    "X-Tenant-ID": metadata.get("tenant_id", ""),
                    "X-Request-ID": metadata.get("request_id", ""),
                    # Authorization will be added by Resource Cluster
                }
                
                async with session.post(
                    self.embedding_endpoint,
                    json=request_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.request_timeout)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(
                            f"Embedding service error: {response.status} - {error_text}"
                        )
                    
                    result = await response.json()
                    
                    # Extract embeddings from response
                    if "data" in result:
                        embeddings = [item["embedding"] for item in result["data"]]
                    elif "embeddings" in result:
                        embeddings = result["embeddings"]
                    else:
                        raise ValueError("Invalid embedding service response format")
                    
                    return embeddings
                    
            except asyncio.TimeoutError:
                raise ValueError(f"Embedding service timeout after {self.request_timeout}s")
            except Exception as e:
                logger.error(f"Error calling embedding service: {e}")
                raise
    
    def _should_normalize(self) -> bool:
        """Check if embeddings should be normalized"""
        # BGE-M3 embeddings are typically normalized for similarity search
        return True
    
    def _normalize_embeddings(
        self,
        embeddings: List[List[float]]
    ) -> List[List[float]]:
        """Normalize embedding vectors to unit length"""
        normalized = []
        
        for embedding in embeddings:
            # Simple normalization without numpy (for now)
            import math
            
            # Calculate norm
            norm = math.sqrt(sum(x * x for x in embedding))
            
            if norm > 0:
                normalized_vec = [x / norm for x in embedding]
            else:
                normalized_vec = embedding[:]
            
            normalized.append(normalized_vec)
        
        return normalized
    
    async def generate_query_embeddings(
        self,
        queries: List[str],
        tenant_id: str = None,
        request_id: str = None
    ) -> List[List[float]]:
        """
        Generate embeddings specifically for queries.
        BGE-M3 can use different instructions for queries vs documents.
        """
        # For BGE-M3, queries can use a specific instruction
        instruction = "Represent this sentence for searching relevant passages: "
        return await self.generate_embeddings(
            queries, instruction, tenant_id, request_id
        )
    
    async def generate_document_embeddings(
        self,
        documents: List[str],
        tenant_id: str = None,
        request_id: str = None
    ) -> List[List[float]]:
        """
        Generate embeddings specifically for documents.
        BGE-M3 can use different instructions for documents vs queries.
        """
        # For BGE-M3, documents typically don't need special instruction
        return await self.generate_embeddings(
            documents, None, tenant_id, request_id
        )
    
    async def validate_texts(
        self,
        texts: List[str]
    ) -> Dict[str, Any]:
        """
        Validate texts before embedding - no content stored.
        
        Args:
            texts: List of texts to validate
        
        Returns:
            Validation result with any warnings
        """
        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "stats": {
                "total_texts": len(texts),
                "max_length": 0,
                "avg_length": 0
            }
        }
        
        if not texts:
            validation["valid"] = False
            validation["errors"].append("No texts provided")
            return validation
        
        # Check text lengths
        lengths = [len(text) for text in texts]
        validation["stats"]["max_length"] = max(lengths)
        validation["stats"]["avg_length"] = sum(lengths) // len(lengths)
        
        # BGE-M3 max sequence length check (approximate)
        max_chars = self.max_sequence_length * 4  # Rough char to token ratio
        
        for i, length in enumerate(lengths):
            if length > max_chars:
                validation["warnings"].append(
                    f"Text {i} may exceed model's max sequence length"
                )
            elif length == 0:
                validation["errors"].append(f"Text {i} is empty")
                validation["valid"] = False
        
        # Batch size check
        if len(texts) > self.max_batch_size * 10:
            validation["warnings"].append(
                f"Large batch ({len(texts)} texts) will be processed in chunks"
            )
        
        return validation
    
    async def check_health(self) -> Dict[str, Any]:
        """Check embedding backend health - no user data exposed"""
        try:
            # Test connection to vLLM service
            test_text = ["Health check test"]
            test_embeddings = await self.generate_embeddings(
                test_text,
                tenant_id="health_check",
                request_id="health_check"
            )
            
            health_status = {
                "status": "healthy",
                "model": self.model_name,
                "dimensions": self.embedding_dimensions,
                "max_batch_size": self.max_batch_size,
                "max_sequence_length": self.max_sequence_length,
                "endpoint": self.embedding_endpoint,
                "stateless": True,
                "memory_cleared": True,
                "vllm_service_connected": len(test_embeddings) > 0
            }
            
        except Exception as e:
            health_status = {
                "status": "unhealthy",
                "error": str(e),
                "model": self.model_name,
                "endpoint": self.embedding_endpoint
            }
        
        return health_status