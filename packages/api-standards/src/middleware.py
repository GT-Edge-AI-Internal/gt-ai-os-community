"""
Standard middleware for GT 2.0 CB-REST API

Design principle: Cross-cutting concerns handled simply and consistently
"""

import uuid
import time
import logging
from typing import Optional, Dict, Any, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .capability import verify_capability, CapabilityToken, get_verifier
from .response import format_error
from .errors import ErrorCode


logger = logging.getLogger(__name__)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Add request correlation ID to all requests for distributed tracing
    
    GT 2.0 Philosophy: Simple observability through request tracking
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate request ID
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in request state for access by handlers
        request.state.request_id = request_id
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Add headers to response
        response.headers[self.header_name] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        # Log request completion
        logger.info(
            f"Request {request_id} completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration": duration
            }
        )
        
        return response


class CapabilityMiddleware(BaseHTTPMiddleware):
    """
    Verify capabilities for all protected endpoints
    
    GT 2.0 Philosophy: Security by design, not configuration
    """
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list[str]] = None,
        audit_logger: Optional[logging.Logger] = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/metrics", "/docs", "/redoc"]
        self.audit_logger = audit_logger or logger
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip capability check for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Extract and verify token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                content=format_error(
                    code=ErrorCode.CAPABILITY_INVALID.value,
                    message="Missing or invalid authorization header",
                    capability_used="none",
                    request_id=getattr(request.state, "request_id", str(uuid.uuid4()))
                ),
                status_code=401,
                media_type="application/json"
            )
        
        try:
            # Verify token
            token = auth_header.replace("Bearer ", "")
            verifier = get_verifier()
            capability_token = verifier.verify_token(token)
            
            # Store in request state for access by handlers
            request.state.capability_token = capability_token
            request.state.tenant_id = capability_token.tenant_id
            request.state.user_email = capability_token.sub
            
            # Check signature if provided
            signature = request.headers.get("X-Capability-Signature")
            if signature and not verifier.verify_signature(token, signature):
                return Response(
                    content=format_error(
                        code=ErrorCode.CAPABILITY_SIGNATURE_INVALID.value,
                        message="Invalid capability signature",
                        capability_used="none",
                        request_id=getattr(request.state, "request_id", str(uuid.uuid4()))
                    ),
                    status_code=401,
                    media_type="application/json"
                )
            
            # Process request
            response = await call_next(request)
            
            # Audit log successful capability usage
            self.audit_logger.info(
                f"Capability used: {request.method} {request.url.path}",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "tenant_id": capability_token.tenant_id,
                    "user": capability_token.sub,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Capability verification failed: {e}")
            return Response(
                content=format_error(
                    code=ErrorCode.CAPABILITY_INVALID.value,
                    message=str(e),
                    capability_used="none",
                    request_id=getattr(request.state, "request_id", str(uuid.uuid4()))
                ),
                status_code=401,
                media_type="application/json"
            )


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Ensure perfect tenant isolation for all requests
    
    GT 2.0 Philosophy: Security through architectural design
    """
    
    def __init__(
        self,
        app: ASGIApp,
        enforce_isolation: bool = True
    ):
        super().__init__(app)
        self.enforce_isolation = enforce_isolation
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for non-tenant paths
        if not self.enforce_isolation or request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get tenant from capability token (set by CapabilityMiddleware)
        capability_token: Optional[CapabilityToken] = getattr(request.state, "capability_token", None)
        if not capability_token:
            return await call_next(request)  # Let other middleware handle auth
        
        # Extract tenant from path if present
        path_parts = request.url.path.strip("/").split("/")
        path_tenant = None
        
        # Look for tenant ID in common patterns
        if "tenants" in path_parts:
            idx = path_parts.index("tenants")
            if idx + 1 < len(path_parts):
                path_tenant = path_parts[idx + 1]
        
        # Check tenant isolation
        if path_tenant and capability_token.tenant_id != path_tenant:
            # Only super_admin and gt_admin can access other tenants
            if capability_token.user_type not in ["super_admin", "gt_admin"]:
                logger.warning(
                    f"Tenant isolation violation attempted",
                    extra={
                        "request_id": getattr(request.state, "request_id", "unknown"),
                        "user_tenant": capability_token.tenant_id,
                        "requested_tenant": path_tenant,
                        "user": capability_token.sub,
                        "path": request.url.path
                    }
                )
                
                return Response(
                    content=format_error(
                        code=ErrorCode.TENANT_ISOLATED.value,
                        message="Cross-tenant access not allowed",
                        capability_used=f"tenant:{capability_token.tenant_id}:*",
                        capability_required=f"tenant:{path_tenant}:*",
                        request_id=getattr(request.state, "request_id", str(uuid.uuid4()))
                    ),
                    status_code=403,
                    media_type="application/json"
                )
        
        # Add tenant context to request
        request.state.tenant_context = {
            "tenant_id": capability_token.tenant_id,
            "requested_tenant": path_tenant,
            "user_type": capability_token.user_type,
            "isolation_enforced": True
        }
        
        return await call_next(request)


class FileSystemIsolationMiddleware(BaseHTTPMiddleware):
    """
    Ensure file system access is properly isolated per tenant
    
    GT 2.0 Philosophy: File-based databases with perfect isolation
    """
    
    def __init__(
        self,
        app: ASGIApp,
        base_path: str = "/data"
    ):
        super().__init__(app)
        self.base_path = base_path
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get tenant from request state
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            # Set allowed file paths for this tenant
            request.state.allowed_paths = [
                f"{self.base_path}/{tenant_id}",
                f"{self.base_path}/shared"  # Shared read-only resources
            ]
            
            # Set file encryption key reference
            request.state.encryption_key_id = f"{tenant_id}-key-{time.strftime('%Y-%m')}"
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting per capability
    
    GT 2.0 Philosophy: Resource protection through simple limits
    """
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        cache: Optional[Dict[str, list[float]]] = None
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.cache = cache or {}  # In production, use Redis
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get user identifier from capability token
        capability_token: Optional[CapabilityToken] = getattr(request.state, "capability_token", None)
        if not capability_token:
            return await call_next(request)
        
        # Create rate limit key
        key = f"{capability_token.tenant_id}:{capability_token.sub}"
        
        # Check rate limit
        now = time.time()
        minute_ago = now - 60
        
        # Get request times for this key
        request_times = self.cache.get(key, [])
        
        # Remove old entries
        request_times = [t for t in request_times if t > minute_ago]
        
        # Check if limit exceeded
        if len(request_times) >= self.requests_per_minute:
            return Response(
                content=format_error(
                    code=ErrorCode.RESOURCE_QUOTA_EXCEEDED.value,
                    message=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                    capability_used=f"tenant:{capability_token.tenant_id}:*",
                    details={"retry_after": 60 - (now - request_times[0])},
                    request_id=getattr(request.state, "request_id", str(uuid.uuid4()))
                ),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(int(60 - (now - request_times[0])))}
            )
        
        # Add current request time
        request_times.append(now)
        self.cache[key] = request_times
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(self.requests_per_minute - len(request_times))
        response.headers["X-RateLimit-Reset"] = str(int(minute_ago + 60))
        
        return response