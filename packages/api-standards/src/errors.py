"""
Standard error codes for GT 2.0 CB-REST API

Design principle: Simple, clear error codes that directly indicate the issue
No complex hierarchies, just straightforward categories
"""

from enum import Enum
from typing import Dict, Any, Optional
from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    """
    Standard error codes following GT 2.0 philosophy:
    - Simple and clear
    - Security-focused
    - Tenant-aware
    """
    
    # Capability errors (security by design)
    CAPABILITY_INSUFFICIENT = "CAPABILITY_INSUFFICIENT"
    CAPABILITY_INVALID = "CAPABILITY_INVALID"
    CAPABILITY_EXPIRED = "CAPABILITY_EXPIRED"
    CAPABILITY_SIGNATURE_INVALID = "CAPABILITY_SIGNATURE_INVALID"
    
    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"
    RESOURCE_QUOTA_EXCEEDED = "RESOURCE_QUOTA_EXCEEDED"
    
    # Tenant isolation errors
    TENANT_ISOLATED = "TENANT_ISOLATED"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"
    TENANT_QUOTA_EXCEEDED = "TENANT_QUOTA_EXCEEDED"
    
    # Request errors
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    
    # System errors (minimal, as per GT 2.0 philosophy)
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    
    # File-based database specific errors
    FILE_LOCK_TIMEOUT = "FILE_LOCK_TIMEOUT"
    FILE_CORRUPTION = "FILE_CORRUPTION"
    ENCRYPTION_FAILED = "ENCRYPTION_FAILED"


class APIError(HTTPException):
    """
    Standard API error that integrates with FastAPI
    
    Simplifies error handling while maintaining consistency
    """
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        capability_required: Optional[str] = None,
        capability_provided: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.capability_required = capability_required
        self.capability_provided = capability_provided
        self.details = details or {}
        
        # Create the detail structure for HTTPException
        detail = {
            "code": code.value,
            "message": message,
            "capability_required": capability_required,
            "capability_provided": capability_provided,
            "details": self.details
        }
        
        # Remove None values for cleaner response
        detail = {k: v for k, v in detail.items() if v is not None}
        
        super().__init__(status_code=status_code, detail=detail)


# Pre-defined error responses for common scenarios
error_responses: Dict[ErrorCode, Dict[str, Any]] = {
    ErrorCode.CAPABILITY_INSUFFICIENT: {
        "status_code": status.HTTP_403_FORBIDDEN,
        "description": "User lacks required capability for this operation"
    },
    ErrorCode.CAPABILITY_INVALID: {
        "status_code": status.HTTP_401_UNAUTHORIZED,
        "description": "Invalid capability token"
    },
    ErrorCode.CAPABILITY_EXPIRED: {
        "status_code": status.HTTP_401_UNAUTHORIZED,
        "description": "Capability token has expired"
    },
    ErrorCode.CAPABILITY_SIGNATURE_INVALID: {
        "status_code": status.HTTP_401_UNAUTHORIZED,
        "description": "Capability signature verification failed"
    },
    ErrorCode.RESOURCE_NOT_FOUND: {
        "status_code": status.HTTP_404_NOT_FOUND,
        "description": "Requested resource does not exist"
    },
    ErrorCode.RESOURCE_ALREADY_EXISTS: {
        "status_code": status.HTTP_409_CONFLICT,
        "description": "Resource already exists"
    },
    ErrorCode.RESOURCE_LOCKED: {
        "status_code": status.HTTP_423_LOCKED,
        "description": "Resource is locked"
    },
    ErrorCode.RESOURCE_QUOTA_EXCEEDED: {
        "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        "description": "Resource quota exceeded"
    },
    ErrorCode.TENANT_ISOLATED: {
        "status_code": status.HTTP_403_FORBIDDEN,
        "description": "Cross-tenant access attempted"
    },
    ErrorCode.TENANT_NOT_FOUND: {
        "status_code": status.HTTP_404_NOT_FOUND,
        "description": "Tenant does not exist"
    },
    ErrorCode.TENANT_SUSPENDED: {
        "status_code": status.HTTP_403_FORBIDDEN,
        "description": "Tenant is suspended"
    },
    ErrorCode.TENANT_QUOTA_EXCEEDED: {
        "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        "description": "Tenant quota exceeded"
    },
    ErrorCode.INVALID_REQUEST: {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "description": "Invalid request format"
    },
    ErrorCode.VALIDATION_FAILED: {
        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "description": "Request validation failed"
    },
    ErrorCode.MISSING_REQUIRED_FIELD: {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "description": "Required field is missing"
    },
    ErrorCode.INVALID_FIELD_VALUE: {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "description": "Invalid field value"
    },
    ErrorCode.SYSTEM_ERROR: {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "description": "Internal system error"
    },
    ErrorCode.SERVICE_UNAVAILABLE: {
        "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
        "description": "Service temporarily unavailable"
    },
    ErrorCode.FILE_LOCK_TIMEOUT: {
        "status_code": status.HTTP_423_LOCKED,
        "description": "File database lock timeout"
    },
    ErrorCode.FILE_CORRUPTION: {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "description": "File database corruption detected"
    },
    ErrorCode.ENCRYPTION_FAILED: {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "description": "Encryption operation failed"
    }
}


def raise_api_error(
    code: ErrorCode,
    message: Optional[str] = None,
    **kwargs
) -> None:
    """
    Convenience function to raise a standard API error
    
    Args:
        code: Error code
        message: Optional custom message (uses default if not provided)
        **kwargs: Additional error details
    
    Raises:
        APIError
    """
    error_info = error_responses.get(code, {})
    
    if message is None:
        message = error_info.get("description", "An error occurred")
    
    raise APIError(
        code=code,
        message=message,
        status_code=error_info.get("status_code", status.HTTP_400_BAD_REQUEST),
        **kwargs
    )