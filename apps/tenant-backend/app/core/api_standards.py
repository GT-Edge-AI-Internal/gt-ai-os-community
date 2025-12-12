"""
GT 2.0 Tenant Backend - CB-REST API Standards Integration

This module integrates the CB-REST standards into the Tenant backend
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
        TENANT_ISOLATION_VIOLATION = "TENANT_ISOLATION_VIOLATION"
    
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


def setup_api_standards(app, secret_key: str, tenant_id: str):
    """
    Setup CB-REST API standards for the tenant application
    
    Args:
        app: FastAPI application instance
        secret_key: Secret key for JWT signing
        tenant_id: Tenant identifier for isolation
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
            requests_per_minute=100  # Per-tenant rate limiting
        )
    
    if 'TenantIsolationMiddleware' in globals():
        app.add_middleware(
            TenantIsolationMiddleware,
            tenant_id=tenant_id,
            enforce_isolation=True
        )
    
    if 'CapabilityMiddleware' in globals():
        app.add_middleware(
            CapabilityMiddleware,
            exclude_paths=["/health", "/ready", "/metrics", "/api/v1/auth/login"]
        )