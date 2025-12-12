"""
Standard response formatting for GT 2.0 CB-REST API

Design principle: Simple, consistent, secure responses with built-in audit trail
"""

from typing import Any, Optional, Dict
from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class StandardError(BaseModel):
    """Standard error structure"""
    code: str = Field(..., description="Error code (e.g., CAPABILITY_INSUFFICIENT)")
    message: str = Field(..., description="Human-readable error message")
    capability_required: Optional[str] = Field(None, description="Required capability for this operation")
    capability_provided: Optional[str] = Field(None, description="Capability that was provided")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class StandardResponse(BaseModel):
    """
    Standard response format for all CB-REST endpoints
    
    Philosophy: Every response has the same structure, reducing ambiguity
    """
    data: Optional[Any] = Field(None, description="Response data (null on error)")
    error: Optional[StandardError] = Field(None, description="Error information (null on success)")
    capability_used: str = Field(..., description="Capability that authorized this request")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request identifier")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


def format_response(
    data: Any,
    capability_used: str,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format a successful response
    
    Args:
        data: The response data
        capability_used: The capability that authorized this request
        request_id: Optional request ID (will be generated if not provided)
    
    Returns:
        Standardized response dictionary
    """
    return StandardResponse(
        data=data,
        error=None,
        capability_used=capability_used,
        request_id=request_id or str(uuid.uuid4())
    ).dict(exclude_none=True)


def format_error(
    code: str,
    message: str,
    capability_used: str = "none",
    capability_required: Optional[str] = None,
    capability_provided: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format an error response
    
    Args:
        code: Error code (e.g., CAPABILITY_INSUFFICIENT)
        message: Human-readable error message
        capability_used: The capability check that failed
        capability_required: The required capability
        capability_provided: The capability that was provided
        details: Additional error details
        request_id: Optional request ID
    
    Returns:
        Standardized error response dictionary
    """
    error = StandardError(
        code=code,
        message=message,
        capability_required=capability_required,
        capability_provided=capability_provided,
        details=details
    )
    
    return StandardResponse(
        data=None,
        error=error,
        capability_used=capability_used,
        request_id=request_id or str(uuid.uuid4())
    ).dict(exclude_none=True)


class BulkOperationResult(BaseModel):
    """Result of a single operation in a bulk request"""
    operation_id: str = Field(..., description="Unique identifier for this operation")
    action: str = Field(..., description="Action performed (create, update, delete)")
    resource_id: Optional[str] = Field(None, description="ID of the affected resource")
    success: bool = Field(..., description="Whether the operation succeeded")
    error: Optional[StandardError] = Field(None, description="Error if operation failed")
    data: Optional[Any] = Field(None, description="Result data if operation succeeded")


class BulkResponse(BaseModel):
    """Response format for bulk operations"""
    operations: list[BulkOperationResult] = Field(..., description="Results of all operations")
    transaction: bool = Field(..., description="Whether all operations were in a transaction")
    total: int = Field(..., description="Total number of operations")
    succeeded: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    capability_used: str = Field(..., description="Capability that authorized this bulk operation")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


def format_bulk_response(
    operations: list[BulkOperationResult],
    transaction: bool,
    capability_used: str,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format a bulk operation response
    
    Args:
        operations: List of operation results
        transaction: Whether operations were transactional
        capability_used: The capability that authorized this request
        request_id: Optional request ID
    
    Returns:
        Standardized bulk response dictionary
    """
    succeeded = sum(1 for op in operations if op.success)
    failed = len(operations) - succeeded
    
    response = BulkResponse(
        operations=operations,
        transaction=transaction,
        total=len(operations),
        succeeded=succeeded,
        failed=failed,
        capability_used=capability_used,
        request_id=request_id or str(uuid.uuid4())
    )
    
    # For bulk responses, we wrap in standard response
    return StandardResponse(
        data=response.dict(exclude_none=True),
        error=None,
        capability_used=capability_used,
        request_id=response.request_id
    ).dict(exclude_none=True)