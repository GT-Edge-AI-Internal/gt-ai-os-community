"""
GT 2.0 API Standards - Capability-Based REST (CB-REST)

A simple, secure API standard designed for GT 2.0's philosophy of
"Elegant Simplicity Through Intelligent Architecture"
"""

from .response import StandardResponse, StandardError, format_response, format_error
from .capability import (
    Capability,
    CapabilityVerifier,
    verify_capability,
    require_capability,
    extract_capability_from_jwt
)
from .errors import ErrorCode, APIError, error_responses
from .middleware import (
    CapabilityMiddleware,
    RequestCorrelationMiddleware,
    TenantIsolationMiddleware
)

__all__ = [
    # Response formatting
    'StandardResponse',
    'StandardError',
    'format_response',
    'format_error',
    
    # Capability verification
    'Capability',
    'CapabilityVerifier',
    'verify_capability',
    'require_capability',
    'extract_capability_from_jwt',
    
    # Error handling
    'ErrorCode',
    'APIError',
    'error_responses',
    
    # Middleware
    'CapabilityMiddleware',
    'RequestCorrelationMiddleware',
    'TenantIsolationMiddleware'
]

__version__ = '1.0.0'