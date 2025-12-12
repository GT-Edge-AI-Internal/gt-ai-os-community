"""
GT 2.0 Resource Cluster - API Standards Integration

This module integrates CB-REST standards for non-AI endpoints while
maintaining OpenAI compatibility for AI inference endpoints.
"""

import os
import sys
from pathlib import Path

# Add the api-standards package to the path
api_standards_path = Path(__file__).parent.parent.parent.parent.parent / "packages" / "api-standards" / "src"
if api_standards_path.exists():
    sys.path.insert(0, str(api_standards_path))

# Import CB-REST standards
try:
    from response import StandardResponse, format_response, format_error
    from capability import (
        init_capability_verifier,
        verify_capability,
        require_capability,
        Capability,
        CapabilityToken
    )
    from errors import ErrorCode, APIError, raise_api_error
    from middleware import (
        RequestCorrelationMiddleware,
        CapabilityMiddleware,
        TenantIsolationMiddleware,
        RateLimitMiddleware
    )
except ImportError as e:
    # Fallback for development - create minimal implementations
    print(f"Warning: Could not import api-standards package: {e}")
    
    # Create minimal implementations for development
    class StandardResponse:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    
    def format_response(data, capability_used, request_id=None):
        return {
            "data": data,
            "error": None,
            "capability_used": capability_used,
            "request_id": request_id or "dev-mode"
        }
    
    def format_error(code, message, capability_used="none", **kwargs):
        return {
            "data": None,
            "error": {
                "code": code,
                "message": message,
                **kwargs
            },
            "capability_used": capability_used,
            "request_id": kwargs.get("request_id", "dev-mode")
        }
    
    class ErrorCode:
        CAPABILITY_INSUFFICIENT = "CAPABILITY_INSUFFICIENT"
        RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
        INVALID_REQUEST = "INVALID_REQUEST"
        SYSTEM_ERROR = "SYSTEM_ERROR"
        RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    class APIError(Exception):
        def __init__(self, code, message, **kwargs):
            self.code = code
            self.message = message
            self.kwargs = kwargs
            super().__init__(message)


# Export all CB-REST components
__all__ = [
    'StandardResponse',
    'format_response',
    'format_error',
    'init_capability_verifier',
    'verify_capability',
    'require_capability',
    'Capability',
    'CapabilityToken',
    'ErrorCode',
    'APIError',
    'raise_api_error',
    'RequestCorrelationMiddleware',
    'CapabilityMiddleware',
    'TenantIsolationMiddleware',
    'RateLimitMiddleware'
]


def setup_api_standards(app, secret_key: str):
    """
    Setup API standards for the Resource Cluster
    
    IMPORTANT: This only applies CB-REST to non-AI endpoints.
    AI inference endpoints maintain OpenAI compatibility.
    
    Args:
        app: FastAPI application instance
        secret_key: Secret key for JWT signing
    """
    # Initialize capability verifier
    if 'init_capability_verifier' in globals():
        init_capability_verifier(secret_key)
    
    # Add middleware in correct order
    if 'RequestCorrelationMiddleware' in globals():
        app.add_middleware(RequestCorrelationMiddleware)
    
    if 'RateLimitMiddleware' in globals():
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=1000  # Higher limit for resource cluster
        )
    
    # Note: No TenantIsolationMiddleware for Resource Cluster
    # as it serves multiple tenants with capability-based access
    
    if 'CapabilityMiddleware' in globals():
        # Exclude AI inference endpoints from CB-REST middleware
        # to maintain OpenAI compatibility
        app.add_middleware(
            CapabilityMiddleware,
            exclude_paths=[
                "/health",
                "/ready",
                "/metrics",
                "/ai/chat/completions",  # OpenAI compatible
                "/ai/embeddings",        # OpenAI compatible
                "/ai/images/generations", # OpenAI compatible
                "/ai/models"             # OpenAI compatible
            ]
        )