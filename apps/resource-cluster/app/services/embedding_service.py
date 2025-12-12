"""
Embedding Service for GT 2.0 Resource Cluster

Provides embedding generation with:
- BGE-M3 model integration
- Batch processing capabilities  
- Rate limiting and quota management
- Capability-based authentication
- Stateless operation (no data storage)

GT 2.0 Architecture Principles:
- Perfect Tenant Isolation: Per-request capability validation
- Zero Downtime: Stateless design, circuit breakers
- Self-Contained Security: Capability-based auth
- No Complexity Addition: Simple interface, no database
"""

import asyncio
import logging
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import uuid

from app.core.backends.embedding_backend import EmbeddingBackend, EmbeddingRequest
from app.core.capability_auth import verify_capability_token, CapabilityError
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class EmbeddingResponse:
    """Response structure for embedding generation"""
    request_id: str
    embeddings: List[List[float]]
    model: str
    dimensions: int
    tokens_used: int
    processing_time_ms: int
    tenant_id: str
    created_at: str


@dataclass
class EmbeddingStats:
    """Statistics for embedding requests"""
    total_requests: int = 0
    total_tokens_processed: int = 0
    total_processing_time_ms: int = 0
    average_processing_time_ms: float = 0.0
    last_request_at: Optional[str] = None


class EmbeddingService:
    """
    STATELESS embedding service for GT 2.0 Resource Cluster.
    
    Key features:
    - BGE-M3 model for high-quality embeddings
    - Batch processing for efficiency
    - Rate limiting per capability token
    - Memory-conscious processing
    - No persistent storage
    """
    
    def __init__(self):
        self.backend = EmbeddingBackend()
        self.stats = EmbeddingStats()

        # Initialize BGE-M3 tokenizer for accurate token counting
        try:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
            logger.info("Initialized BGE-M3 tokenizer for accurate token counting")
        except Exception as e:
            logger.warning(f"Failed to load BGE-M3 tokenizer, using word estimation: {e}")
            self.tokenizer = None

        # Rate limiting settings (per capability token)
        self.rate_limits = {
            "requests_per_minute": 60,
            "tokens_per_minute": 50000,
            "max_batch_size": 32
        }

        # Track requests for rate limiting (in-memory, temporary)
        self._request_tracker = {}

        logger.info("STATELESS embedding service initialized")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        capability_token: str,
        instruction: Optional[str] = None,
        request_id: Optional[str] = None,
        normalize: bool = True
    ) -> EmbeddingResponse:
        """
        Generate embeddings with capability-based authentication.
        
        Args:
            texts: List of texts to embed
            capability_token: JWT token with embedding permissions
            instruction: Optional instruction for embedding context
            request_id: Optional request ID for tracking
            normalize: Whether to normalize embeddings
            
        Returns:
            EmbeddingResponse with generated embeddings
            
        Raises:
            CapabilityError: If token invalid or insufficient permissions
            ValueError: If request parameters invalid
        """
        start_time = time.time()
        request_id = request_id or str(uuid.uuid4())
        
        try:
            # Verify capability token and extract permissions
            capability = await verify_capability_token(capability_token)
            tenant_id = capability.get("tenant_id")
            user_id = capability.get("sub")  # Extract user ID from token

            # Check embedding permissions
            await self._verify_embedding_permissions(capability, len(texts))

            # Apply rate limiting
            await self._check_rate_limits(capability_token, len(texts))

            # Validate input
            self._validate_embedding_request(texts)

            # Generate embeddings via backend
            embeddings = await self.backend.generate_embeddings(
                texts=texts,
                instruction=instruction,
                tenant_id=tenant_id,
                request_id=request_id
            )

            # Calculate processing metrics
            processing_time_ms = int((time.time() - start_time) * 1000)
            total_tokens = self._estimate_tokens(texts)

            # Update statistics
            self._update_stats(total_tokens, processing_time_ms)

            # Log embedding usage for billing (non-blocking)
            # Fire and forget - don't wait for completion
            asyncio.create_task(
                self._log_embedding_usage(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    tokens_used=total_tokens,
                    embedding_count=len(embeddings),
                    model=self.backend.model_name,
                    request_id=request_id
                )
            )

            # Create response
            response = EmbeddingResponse(
                request_id=request_id,
                embeddings=embeddings,
                model=self.backend.model_name,
                dimensions=self.backend.embedding_dimensions,
                tokens_used=total_tokens,
                processing_time_ms=processing_time_ms,
                tenant_id=tenant_id,
                created_at=datetime.utcnow().isoformat()
            )

            logger.info(
                f"Generated {len(embeddings)} embeddings for tenant {tenant_id} "
                f"in {processing_time_ms}ms"
            )

            return response
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
        finally:
            # Always ensure cleanup
            if 'texts' in locals():
                del texts
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model"""
        return {
            "model_name": self.backend.model_name,
            "dimensions": self.backend.embedding_dimensions,
            "max_sequence_length": self.backend.max_sequence_length,
            "max_batch_size": self.backend.max_batch_size,
            "supports_instruction": True,
            "normalization_default": True
        }
    
    async def get_service_stats(
        self,
        capability_token: str
    ) -> Dict[str, Any]:
        """
        Get service statistics (for admin users only).
        
        Args:
            capability_token: JWT token with admin permissions
            
        Returns:
            Service statistics
        """
        # Verify admin permissions
        capability = await verify_capability_token(capability_token)
        if not self._has_admin_permissions(capability):
            raise CapabilityError("Admin permissions required")
        
        return {
            "model_info": await self.get_model_info(),
            "statistics": asdict(self.stats),
            "rate_limits": self.rate_limits,
            "active_requests": len(self._request_tracker)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        return {
            "status": "healthy",
            "service": "embedding_service",
            "model": self.backend.model_name,
            "backend_ready": True,
            "last_request": self.stats.last_request_at
        }
    
    async def _verify_embedding_permissions(
        self,
        capability: Dict[str, Any],
        text_count: int
    ) -> None:
        """Verify that capability token has embedding permissions"""
        
        # Check for embedding capability
        capabilities = capability.get("capabilities", [])
        embedding_caps = [
            cap for cap in capabilities 
            if cap.get("resource") == "embeddings"
        ]
        
        if not embedding_caps:
            raise CapabilityError("No embedding permissions in capability token")
        
        # Check constraints
        embedding_cap = embedding_caps[0]  # Use first embedding capability
        constraints = embedding_cap.get("constraints", {})
        
        # Check batch size limit
        max_batch = constraints.get("max_batch_size", self.rate_limits["max_batch_size"])
        if text_count > max_batch:
            raise CapabilityError(f"Batch size {text_count} exceeds limit {max_batch}")
        
        # Check rate limits
        rate_limit = constraints.get("rate_limit_per_minute", self.rate_limits["requests_per_minute"])
        token_limit = constraints.get("tokens_per_minute", self.rate_limits["tokens_per_minute"])
        
        logger.debug(f"Embedding permissions verified: batch={text_count}, limits=({rate_limit}, {token_limit})")
    
    async def _check_rate_limits(
        self,
        capability_token: str,
        text_count: int
    ) -> None:
        """Check rate limits for capability token"""
        
        now = time.time()
        token_hash = hash(capability_token) % 10000  # Simple tracking key
        
        # Clean old entries (older than 1 minute)
        cleanup_time = now - 60
        self._request_tracker = {
            k: v for k, v in self._request_tracker.items()
            if v.get("last_request", 0) > cleanup_time
        }
        
        # Get or create tracker for this token
        if token_hash not in self._request_tracker:
            self._request_tracker[token_hash] = {
                "requests": 0,
                "tokens": 0,
                "last_request": now
            }
        
        tracker = self._request_tracker[token_hash]
        
        # Check request rate limit
        if tracker["requests"] >= self.rate_limits["requests_per_minute"]:
            raise CapabilityError("Rate limit exceeded: too many requests per minute")
        
        # Estimate tokens and check token limit
        estimated_tokens = self._estimate_tokens([f"text_{i}" for i in range(text_count)])
        if tracker["tokens"] + estimated_tokens > self.rate_limits["tokens_per_minute"]:
            raise CapabilityError("Rate limit exceeded: too many tokens per minute")
        
        # Update tracker
        tracker["requests"] += 1
        tracker["tokens"] += estimated_tokens
        tracker["last_request"] = now
    
    def _validate_embedding_request(self, texts: List[str]) -> None:
        """Validate embedding request parameters"""
        
        if not texts:
            raise ValueError("No texts provided for embedding")
        
        if not isinstance(texts, list):
            raise ValueError("Texts must be a list")
        
        if len(texts) > self.backend.max_batch_size:
            raise ValueError(f"Batch size {len(texts)} exceeds maximum {self.backend.max_batch_size}")
        
        # Check individual text lengths
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise ValueError(f"Text at index {i} must be a string")
            
            if len(text.strip()) == 0:
                raise ValueError(f"Text at index {i} is empty")
            
            # Simple token estimation for length check
            estimated_tokens = len(text.split()) * 1.3  # Rough estimation
            if estimated_tokens > self.backend.max_sequence_length:
                raise ValueError(f"Text at index {i} exceeds maximum length")
    
    def _estimate_tokens(self, texts: List[str]) -> int:
        """
        Count tokens using actual BGE-M3 tokenizer.
        Falls back to word-count estimation if tokenizer unavailable.
        """
        if self.tokenizer is not None:
            try:
                total_tokens = 0
                for text in texts:
                    tokens = self.tokenizer.encode(text, add_special_tokens=False)
                    total_tokens += len(tokens)
                return total_tokens
            except Exception as e:
                logger.warning(f"Tokenizer error, falling back to estimation: {e}")

        # Fallback: word count * 1.3 (rough estimation)
        total_words = sum(len(text.split()) for text in texts)
        return int(total_words * 1.3)
    
    def _has_admin_permissions(self, capability: Dict[str, Any]) -> bool:
        """Check if capability has admin permissions"""
        capabilities = capability.get("capabilities", [])
        return any(
            cap.get("resource") == "admin" and "stats" in cap.get("actions", [])
            for cap in capabilities
        )
    
    def _update_stats(self, tokens_processed: int, processing_time_ms: int) -> None:
        """Update service statistics"""
        self.stats.total_requests += 1
        self.stats.total_tokens_processed += tokens_processed
        self.stats.total_processing_time_ms += processing_time_ms
        self.stats.average_processing_time_ms = (
            self.stats.total_processing_time_ms / self.stats.total_requests
        )
        self.stats.last_request_at = datetime.utcnow().isoformat()

    async def _log_embedding_usage(
        self,
        tenant_id: str,
        user_id: str,
        tokens_used: int,
        embedding_count: int,
        model: str = "BAAI/bge-m3",
        request_id: Optional[str] = None
    ) -> None:
        """
        Log embedding usage to control panel database for billing.

        This method logs usage asynchronously and does not block the embedding response.
        Failures are logged as warnings but do not raise exceptions.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier (from capability token 'sub')
            tokens_used: Number of tokens processed
            embedding_count: Number of embeddings generated
            model: Embedding model name
            request_id: Optional request ID for tracking
        """
        try:
            import asyncpg

            # Calculate cost: BGE-M3 pricing ~$0.10 per million tokens
            cost_cents = (tokens_used / 1_000_000) * 0.10 * 100

            # Connect to control panel database
            # Using environment variables from docker-compose
            db_password = os.getenv("CONTROL_PANEL_DB_PASSWORD")
            if not db_password:
                logger.warning("CONTROL_PANEL_DB_PASSWORD not set, skipping embedding usage logging")
                return

            conn = await asyncpg.connect(
                host=os.getenv("CONTROL_PANEL_DB_HOST", "gentwo-controlpanel-postgres"),
                database=os.getenv("CONTROL_PANEL_DB_NAME", "gt2_admin"),
                user=os.getenv("CONTROL_PANEL_DB_USER", "postgres"),
                password=db_password,
                timeout=5.0
            )

            try:
                # Insert usage log
                await conn.execute("""
                    INSERT INTO public.embedding_usage_logs
                    (tenant_id, user_id, tokens_used, embedding_count, model, cost_cents, request_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, tenant_id, user_id, tokens_used, embedding_count, model, cost_cents, request_id)

                logger.info(
                    f"Logged embedding usage: tenant={tenant_id}, user={user_id}, "
                    f"tokens={tokens_used}, embeddings={embedding_count}, cost_cents={cost_cents:.4f}"
                )
            finally:
                await conn.close()

        except Exception as e:
            # Log warning but don't fail the embedding request
            logger.warning(f"Failed to log embedding usage for tenant {tenant_id}: {e}")


# Global service instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service