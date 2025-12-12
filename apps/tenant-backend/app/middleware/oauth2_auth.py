"""
OAuth2 Authentication Middleware for GT 2.0 Tenant Backend

Handles OAuth2 authentication headers from OAuth2 Proxy and extracts
user information for tenant isolation and access control.
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict, Any
import logging
import json
import base64
from urllib.parse import unquote

logger = logging.getLogger(__name__)


class OAuth2AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle OAuth2 authentication from OAuth2 Proxy.
    
    Extracts user information from OAuth2 Proxy headers and sets
    user context for downstream handlers.
    """
    
    # Routes that don't require authentication
    EXEMPT_PATHS = {
        "/health",
        "/metrics", 
        "/docs",
        "/openapi.json",
        "/api/v1/health",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout"
    }
    
    def __init__(self, app, require_auth: bool = True):
        super().__init__(app)
        self.require_auth = require_auth
    
    async def dispatch(self, request: Request, call_next):
        """Process OAuth2 authentication headers"""
        
        # Skip authentication for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Try OAuth2 headers first, then fallback to JWT token authentication
        user_info = self._extract_oauth2_headers(request)
        
        # If no OAuth2 headers found, try JWT token authentication
        if not user_info:
            user_info = await self._extract_jwt_user(request)
        
        if self.require_auth and not user_info:
            logger.warning(f"Authentication required but no valid OAuth2 headers found for {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Set user context in request state
        if user_info:
            request.state.user = user_info
            request.state.authenticated = True
            logger.info(f"Authenticated user: {user_info.get('email', 'unknown')} for {request.url.path}")
        else:
            request.state.user = None
            request.state.authenticated = False
        
        # Continue with request processing
        response = await call_next(request)
        
        # Add authentication-related headers to response
        if user_info:
            response.headers["X-Authenticated-User"] = user_info.get("email", "unknown")
            response.headers["X-Auth-Source"] = user_info.get("auth_source", "oauth2-proxy")
        
        return response
    
    def _extract_oauth2_headers(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Extract user information from OAuth2 Proxy headers.
        
        OAuth2 Proxy sets the following headers:
        - X-Auth-Request-User: Username/email
        - X-Auth-Request-Email: User email
        - X-Auth-Request-Access-Token: Access token
        - Authorization: Bearer token (if configured)
        """
        
        # Extract user information from OAuth2 Proxy headers
        user_email = request.headers.get("X-Auth-Request-Email")
        user_name = request.headers.get("X-Auth-Request-User") 
        access_token = request.headers.get("X-Auth-Request-Access-Token")
        
        # Also check Authorization header for bearer token
        auth_header = request.headers.get("Authorization")
        bearer_token = None
        if auth_header and auth_header.startswith("Bearer "):
            bearer_token = auth_header[7:]  # Remove "Bearer " prefix
        
        if not user_email and not user_name:
            logger.debug("No OAuth2 authentication headers found")
            return None
        
        user_info = {
            "email": user_email,
            "username": user_name or user_email,
            "access_token": access_token,
            "bearer_token": bearer_token,
            "auth_source": "oauth2-proxy",
            "authenticated_at": request.headers.get("X-Auth-Request-Timestamp"),
        }
        
        # Extract additional user attributes if present
        if groups_header := request.headers.get("X-Auth-Request-Groups"):
            try:
                # Groups might be base64 encoded or comma-separated
                if self._is_base64(groups_header):
                    groups_decoded = base64.b64decode(groups_header).decode('utf-8')
                    user_info["groups"] = json.loads(groups_decoded)
                else:
                    user_info["groups"] = groups_header.split(",")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to decode groups header: {e}")
                user_info["groups"] = []
        
        # Extract user roles if present
        if roles_header := request.headers.get("X-Auth-Request-Roles"):
            try:
                if self._is_base64(roles_header):
                    roles_decoded = base64.b64decode(roles_header).decode('utf-8')
                    user_info["roles"] = json.loads(roles_decoded)
                else:
                    user_info["roles"] = roles_header.split(",")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to decode roles header: {e}")
                user_info["roles"] = []
        
        # Extract tenant information from headers or JWT token
        tenant_id = self._extract_tenant_info(request, user_info)
        if tenant_id:
            user_info["tenant_id"] = tenant_id
        
        return user_info
    
    def _extract_tenant_info(self, request: Request, user_info: Dict[str, Any]) -> Optional[str]:
        """
        Extract tenant information from request headers or JWT token.
        
        Tenant information can come from:
        1. X-Tenant-ID header (set by load balancer based on domain)
        2. JWT token claims
        3. Domain name parsing
        """
        
        # Check for explicit tenant header
        if tenant_header := request.headers.get("X-Tenant-ID"):
            return tenant_header
        
        # Extract tenant from domain name
        host = request.headers.get("Host", "")
        if host and "." in host:
            # Assume format: tenant.gt2.com
            potential_tenant = host.split(".")[0]
            if potential_tenant != "www" and potential_tenant != "api":
                return potential_tenant
        
        # Try to extract from JWT token if present
        if bearer_token := user_info.get("bearer_token"):
            tenant_from_jwt = self._extract_tenant_from_jwt(bearer_token)
            if tenant_from_jwt:
                return tenant_from_jwt
        
        logger.warning(f"Could not determine tenant for user {user_info.get('email', 'unknown')}")
        return None
    
    def _extract_tenant_from_jwt(self, token: str) -> Optional[str]:
        """
        Extract tenant information from JWT token without verifying signature.
        
        Note: This is just for extracting claims, not for security validation.
        Security validation should be done by OAuth2 Proxy.
        """
        try:
            # Split JWT token (header.payload.signature)
            parts = token.split(".")
            if len(parts) != 3:
                return None
            
            # Decode payload (add padding if needed)
            payload = parts[1]
            # Add padding if needed for base64 decoding
            payload += "=" * (4 - len(payload) % 4)
            
            decoded_payload = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded_payload)
            
            # Look for tenant in various claim fields
            tenant_claims = ["tenant_id", "tenant", "org_id", "organization"]
            for claim in tenant_claims:
                if claim in claims:
                    return str(claims[claim])
            
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            logger.debug(f"Failed to decode JWT payload: {e}")
        
        return None
    
    def _is_base64(self, s: str) -> bool:
        """Check if a string is base64 encoded"""
        try:
            if isinstance(s, str):
                s = s.encode('ascii')
            return base64.b64encode(base64.b64decode(s)) == s
        except Exception:
            return False
    
    async def _extract_jwt_user(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Extract user information from JWT token in Authorization header.
        
        This provides fallback authentication when OAuth2 proxy headers are not present.
        """
        from app.core.security import get_current_user
        
        try:
            # Get Authorization header
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return None
            
            # Use the security module to validate and extract user info
            user_data = await get_current_user(auth_header)
            
            # Convert security module format to middleware format
            if user_data:
                return {
                    "email": user_data.get("email", user_data.get("user_id", "unknown")),
                    "username": user_data.get("tenant_display_name", user_data.get("email", "unknown")),
                    "tenant_id": user_data.get("tenant_id", "1"),
                    "tenant_domain": user_data.get("tenant_domain", "default"),
                    "tenant_name": user_data.get("tenant_name", "Default Tenant"),
                    "tenant_role": user_data.get("tenant_role", "tenant_user"),
                    "user_type": user_data.get("user_type", "tenant_user"),
                    "capabilities": user_data.get("capabilities", []),
                    "resource_limits": user_data.get("resource_limits", {}),
                    "auth_source": "jwt-token",
                    "bearer_token": auth_header[7:],  # Remove "Bearer " prefix
                    "authenticated_at": None,
                    "is_primary_tenant": user_data.get("is_primary_tenant", False)
                }
            
        except Exception as e:
            logger.debug(f"Failed to authenticate via JWT token: {e}")
            return None
        
        return None


class OAuth2SecurityDependency:
    """
    FastAPI dependency to get current authenticated user from OAuth2 context.
    
    Usage:
        @app.get("/api/v1/user/profile")
        async def get_profile(user: dict = Depends(get_current_user)):
            return {"user": user}
    """
    
    def __call__(self, request: Request) -> Dict[str, Any]:
        """Get current authenticated user from request state"""
        
        if not hasattr(request.state, "authenticated") or not request.state.authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return request.state.user


# Singleton instance for dependency injection
get_current_user = OAuth2SecurityDependency()


def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user (optional - doesn't raise exception if not authenticated).
    
    Usage:
        @app.get("/api/v1/public/info")
        async def get_info(user: Optional[dict] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user['email']}"}
            return {"message": "Hello anonymous user"}
    """
    
    if hasattr(request.state, "authenticated") and request.state.authenticated:
        return request.state.user
    
    return None


def require_tenant_access(required_tenant: Optional[str] = None):
    """
    Dependency to ensure user has access to specified tenant.
    
    Usage:
        @app.get("/api/v1/tenant/{tenant_id}/data")
        async def get_tenant_data(
            tenant_id: str,
            user: dict = Depends(get_current_user),
            _: None = Depends(require_tenant_access)
        ):
            # User is guaranteed to have access to tenant_id
            return {"data": "tenant specific data"}
    """
    
    def dependency(request: Request, user: Dict[str, Any] = Depends(get_current_user)) -> None:
        """Check tenant access for current user"""
        
        user_tenant = user.get("tenant_id")
        
        # If no required tenant specified, use the one from user context
        target_tenant = required_tenant or user_tenant
        
        if not target_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant information not available"
            )
        
        # Check if user has access to the required tenant
        if user_tenant != target_tenant:
            logger.warning(
                f"User {user.get('email', 'unknown')} attempted to access tenant {target_tenant} "
                f"but belongs to tenant {user_tenant}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: insufficient tenant permissions"
            )
    
    return dependency


def require_roles(*required_roles: str):
    """
    Dependency to ensure user has one of the required roles.
    
    Usage:
        @app.delete("/api/v1/admin/users/{user_id}")
        async def delete_user(
            user_id: str,
            user: dict = Depends(get_current_user),
            _: None = Depends(require_roles("admin", "user_manager"))
        ):
            # User has admin or user_manager role
            return {"deleted": user_id}
    """
    
    def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> None:
        """Check role requirements for current user"""
        
        user_roles = set(user.get("roles", []))
        required_roles_set = set(required_roles)
        
        if not user_roles.intersection(required_roles_set):
            logger.warning(
                f"User {user.get('email', 'unknown')} with roles {list(user_roles)} "
                f"attempted to access endpoint requiring roles {list(required_roles_set)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: requires one of roles: {', '.join(required_roles)}"
            )
    
    return dependency