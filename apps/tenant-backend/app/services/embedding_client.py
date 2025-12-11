"""
BGE-M3 Embedding Client for GT 2.0

Simple client for the vLLM BGE-M3 embedding service running on port 8005.
Provides text embedding generation for RAG pipeline.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class BGE_M3_EmbeddingClient:
    """
    Simple client for BGE-M3 embedding service via vLLM.

    Features:
    - Async HTTP client for embeddings
    - Batch processing support
    - Error handling and retries
    - OpenAI-compatible API format
    """

    def __init__(self, base_url: str = None):
        # Determine base URL from environment or configuration
        if base_url is None:
            base_url = self._get_embedding_endpoint()

        self.base_url = base_url
        self.model = "BAAI/bge-m3"
        self.embedding_dimensions = 1024
        self.max_batch_size = 32

        # Initialize BGE-M3 tokenizer for accurate token counting
        try:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
            logger.info("Initialized BGE-M3 tokenizer for accurate token counting")
        except Exception as e:
            logger.warning(f"Failed to load BGE-M3 tokenizer, using word estimation: {e}")
            self.tokenizer = None

    def _get_embedding_endpoint(self) -> str:
        """
        Get the BGE-M3 endpoint based on configuration.
        This should sync with the control panel configuration.
        """
        import os

        # Check environment variables for BGE-M3 configuration
        is_local_mode = os.getenv('BGE_M3_LOCAL_MODE', 'true').lower() == 'true'
        external_endpoint = os.getenv('BGE_M3_EXTERNAL_ENDPOINT')

        if not is_local_mode and external_endpoint:
            return external_endpoint

        # Default to local endpoint
        return os.getenv('EMBEDDING_ENDPOINT', 'http://host.docker.internal:8005')

    def update_endpoint(self, new_endpoint: str):
        """Update the embedding endpoint dynamically"""
        self.base_url = new_endpoint
        logger.info(f"BGE-M3 client endpoint updated to: {new_endpoint}")

    async def health_check(self) -> bool:
        """Check if BGE-M3 service is responding"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                if response.status_code == 200:
                    models = response.json()
                    model_ids = [model['id'] for model in models.get('data', [])]
                    return self.model in model_ids
                return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def generate_embeddings(
        self,
        texts: List[str],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using BGE-M3.

        Args:
            texts: List of text strings to embed
            tenant_id: Tenant ID for usage tracking (optional)
            user_id: User ID for usage tracking (optional)
            request_id: Request ID for tracking (optional)

        Returns:
            List of embedding vectors (each is a list of 1024 floats)

        Raises:
            ValueError: If embedding generation fails
        """
        if not texts:
            return []

        if len(texts) > self.max_batch_size:
            # Process in batches
            all_embeddings = []
            for i in range(0, len(texts), self.max_batch_size):
                batch = texts[i:i + self.max_batch_size]
                batch_embeddings = await self._generate_batch(batch)
                all_embeddings.extend(batch_embeddings)
            embeddings = all_embeddings
        else:
            embeddings = await self._generate_batch(texts)

        # Log usage if tenant context provided (fire and forget)
        if tenant_id and user_id:
            import asyncio
            tokens_used = self._count_tokens(texts)
            asyncio.create_task(
                self._log_embedding_usage(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    tokens_used=tokens_used,
                    embedding_count=len(embeddings),
                    request_id=request_id
                )
            )

        return embeddings

    async def _generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a single batch"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json={
                        "input": texts,
                        "model": self.model
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    # Extract embeddings from OpenAI-compatible response
                    embeddings = []
                    for item in data.get("data", []):
                        embedding = item.get("embedding", [])
                        if len(embedding) != self.embedding_dimensions:
                            raise ValueError(f"Invalid embedding dimensions: {len(embedding)} (expected {self.embedding_dimensions})")
                        embeddings.append(embedding)

                    logger.info(f"Generated {len(embeddings)} embeddings")
                    return embeddings
                else:
                    error_text = response.text
                    logger.error(f"Embedding generation failed: {response.status_code} - {error_text}")
                    raise ValueError(f"Embedding generation failed: {response.status_code}")

        except httpx.TimeoutException:
            logger.error("Embedding generation timed out")
            raise ValueError("Embedding generation timed out")
        except Exception as e:
            logger.error(f"Error calling embedding service: {e}")
            raise ValueError(f"Embedding service error: {str(e)}")

    def _count_tokens(self, texts: List[str]) -> int:
        """Count tokens using actual BGE-M3 tokenizer."""
        if self.tokenizer is not None:
            try:
                total_tokens = 0
                for text in texts:
                    tokens = self.tokenizer.encode(text, add_special_tokens=False)
                    total_tokens += len(tokens)
                return total_tokens
            except Exception as e:
                logger.warning(f"Tokenizer error, falling back to estimation: {e}")

        # Fallback: word count * 1.3
        total_words = sum(len(text.split()) for text in texts)
        return int(total_words * 1.3)

    async def _log_embedding_usage(
        self,
        tenant_id: str,
        user_id: str,
        tokens_used: int,
        embedding_count: int,
        request_id: Optional[str] = None
    ) -> None:
        """Log embedding usage to control panel database for billing."""
        try:
            import asyncpg
            import os

            # Calculate cost: BGE-M3 pricing ~$0.10 per million tokens
            cost_cents = (tokens_used / 1_000_000) * 0.10 * 100

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
                await conn.execute("""
                    INSERT INTO public.embedding_usage_logs
                    (tenant_id, user_id, tokens_used, embedding_count, model, cost_cents, request_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, tenant_id, user_id, tokens_used, embedding_count, self.model, cost_cents, request_id)

                logger.info(
                    f"Logged embedding usage: tenant={tenant_id}, user={user_id}, "
                    f"tokens={tokens_used}, embeddings={embedding_count}, cost_cents={cost_cents:.4f}"
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.warning(f"Failed to log embedding usage: {e}")

    async def generate_single_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector (list of 1024 floats)
        """
        embeddings = await self.generate_embeddings([text])
        return embeddings[0] if embeddings else []


# Global client instance
_embedding_client: Optional[BGE_M3_EmbeddingClient] = None


def get_embedding_client() -> BGE_M3_EmbeddingClient:
    """Get or create global embedding client instance"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = BGE_M3_EmbeddingClient()
    else:
        # Always refresh the endpoint from current configuration
        current_endpoint = _embedding_client._get_embedding_endpoint()
        if _embedding_client.base_url != current_endpoint:
            _embedding_client.base_url = current_endpoint
            logger.info(f"BGE-M3 client endpoint refreshed to: {current_endpoint}")
    return _embedding_client


async def test_embedding_client():
    """Test function for the embedding client"""
    client = get_embedding_client()

    # Test health check
    is_healthy = await client.health_check()
    print(f"BGE-M3 service healthy: {is_healthy}")

    if is_healthy:
        # Test embedding generation
        test_texts = [
            "This is a test document about machine learning.",
            "GT 2.0 is an enterprise AI platform.",
            "Vector embeddings enable semantic search."
        ]

        embeddings = await client.generate_embeddings(test_texts)
        print(f"Generated {len(embeddings)} embeddings")
        print(f"Embedding dimensions: {len(embeddings[0]) if embeddings else 0}")


if __name__ == "__main__":
    asyncio.run(test_embedding_client())