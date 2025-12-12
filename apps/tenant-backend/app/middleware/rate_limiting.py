"""
Rate Limiting Middleware for GT 2.0

Basic rate limiting implementation for tenant protection.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
from typing import Dict, Tuple
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware"""

    # Operational endpoints that don't need rate limiting
    EXEMPT_PATHS = {
        "/health",
        "/ready",
        "/metrics",
        "/api/v1/health"
    }

    def __init__(self, app):
        super().__init__(app)
        self._rate_limits: Dict[str, Tuple[int, float]] = {}  # ip -> (count, window_start)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for operational endpoints
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        if self._is_rate_limited(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip} - Path: {request.url.path}")
            # Return proper JSONResponse instead of raising HTTPException to prevent ASGI violations
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(settings.rate_limit_window_seconds)}
            )

        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded IP first (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client IP is rate limited"""
        current_time = time.time()
        
        if client_ip not in self._rate_limits:
            self._rate_limits[client_ip] = (1, current_time)
            return False
        
        count, window_start = self._rate_limits[client_ip]
        
        # Check if we're still in the same window
        if current_time - window_start < settings.rate_limit_window_seconds:
            if count >= settings.rate_limit_requests:
                return True  # Rate limited
            else:
                self._rate_limits[client_ip] = (count + 1, window_start)
                return False
        else:
            # New window, reset count
            self._rate_limits[client_ip] = (1, current_time)
            return False