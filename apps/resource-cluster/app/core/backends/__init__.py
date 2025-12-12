"""
Resource backend implementations for GT 2.0

Provides unified interfaces for all resource types:
- LLM inference (Groq, OpenAI, Anthropic)
- Vector databases (PGVector)
- Document processing (Unstructured)
- External services (OAuth2, iframe)
- AI literacy resources
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Registry of available backends
BACKEND_REGISTRY: Dict[str, Any] = {}


def register_backend(name: str, backend_class):
    """Register a resource backend"""
    BACKEND_REGISTRY[name] = backend_class
    logger.info(f"Registered backend: {name}")


def get_backend(name: str):
    """Get a registered backend"""
    if name not in BACKEND_REGISTRY:
        raise ValueError(f"Backend not found: {name}")
    return BACKEND_REGISTRY[name]


async def initialize_backends():
    """Initialize all resource backends"""
    from app.core.backends.groq_proxy import GroqProxyBackend
    from app.core.backends.nvidia_proxy import NvidiaProxyBackend
    from app.core.backends.document_processor import DocumentProcessorBackend
    from app.core.backends.embedding_backend import EmbeddingBackend

    # Register backends
    register_backend("groq_proxy", GroqProxyBackend())
    register_backend("nvidia_proxy", NvidiaProxyBackend())
    register_backend("document_processor", DocumentProcessorBackend())
    register_backend("embedding", EmbeddingBackend())

    logger.info("All resource backends initialized")


def get_embedding_backend():
    """Get the embedding backend instance"""
    return get_backend("embedding")