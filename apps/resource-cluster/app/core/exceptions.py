"""
GT 2.0 Resource Cluster Exceptions

Custom exceptions for the resource cluster.
"""


class ResourceClusterError(Exception):
    """Base exception for resource cluster errors"""
    pass


class ProviderError(ResourceClusterError):
    """Error from AI model provider"""
    pass


class ModelNotFoundError(ResourceClusterError):
    """Requested model not found"""
    pass


class CapabilityError(ResourceClusterError):
    """Capability token validation error"""
    pass


class MCPError(ResourceClusterError):
    """MCP service error"""
    pass


class DocumentProcessingError(ResourceClusterError):
    """Document processing error"""
    pass


class RateLimitError(ResourceClusterError):
    """Rate limit exceeded"""
    pass


class CircuitBreakerError(ProviderError):
    """Circuit breaker is open"""
    pass