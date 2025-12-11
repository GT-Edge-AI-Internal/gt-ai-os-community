"""
Security module for GT 2.0 Tenant Backend

Provides JWT capability token verification and user authentication.
"""

import os
import jwt
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization
from fastapi import Header
import logging

logger = logging.getLogger(__name__)

def get_jwt_keys():
    """Get production JWT keys from environment variables"""
    # For development, use default keys if environment vars not set
    default_private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAs2EtVywNqwITpULcfp94tvdYcpwjYqcNdDeJhLASo4J1+bA+
C3qnfAXAVcfi1ocwzY+KXtfPDGF6zPynQTJ5fmhdqepWSJ/RFbUHIwsk1Uuo6ufk
PLW3e3QRQL3jpH8sZiSTfH2QqS3WFV2xtZ6l2+E+z5A/ascWF82iNzI6KuAnfGDC
KGCyNy3KoggippF79LxMM0BT8+0eHgvmUNaVgFaYESwhT0tSCYYU6oWclUK3whgc
lgTlJkhocqWykcJkp2IGSoHFfgSVOwJsVrhDhZwkkgKuk1K6n4TzD0vcROlBnYwG
4qUQDd36cEWJWXD7NQetdQNMy9YtCyriVItOuwIDAQABAoIBAAIZbg1qH5LTyGUT
vj7hIOmLRYa52xQpflfQ2pQp913ghf7xGBjMS6+A5bpbR4VZObH+LxFjFzI+5dAG
WPLDY3aeRBJcAryA2lKVtsqrM7gnVYfCRQKM4ePY/Oa0Ejj3oA5l+S/ozEuelLXV
TeIhRDGpljGZr5RRVinbJz3cIaAk0G1BP9wCsdgWyh5Suv5arP5NlrKWKXguQ5re
u1u4KPosp+y/h85VTsvh5fpC8P/Op+W/QVoiI79LkgK/5+pkD+JJHLQZll/J+nsw
+U6jNK3tY0xMK/V0Xjes+aRXWwfkEPbJoznZ0ffUudrwxqKQ99KDd/RX9PfT+9Ek
pBcnZ4kCgYEA2aVKXCKPW2m3aAyBITP2cE4BvoFSVKM5m67ZI3ZTLp+hBQM3Zyha
s80aVeXMKWKYZ1516K8bWumqc4H09yz1XqYsvrnqkfAFKBCLXPyjlSeiuB3+OnT3
VqPXIfA4Pj3lELmx0+GIdToopC3cFENu1brXDzJtn0lePqxkpRyXf38CgYEA0v2U
MN3qFh+xDxrATtqEkSpfb0N/1dBKHEGxhEnRmtV7zKlXAPTWNQkfXCt38cekEiyC
y6L+RgDEPO1haC+9PqEVk0JkT3cvEKfPV5NRUjPlp/gIX4y5n2EUguoCIx5ZBDbC
f0YvsKNqAphQO5BMx9yN6sFyMcDmMWpNq8OizsUCgYABJHT3dtb5y9xCl4419mfc
vwwTS+p6t0CeKJTLMtvM6tmVhSbNS9DuEK2KteIUdYgHQt+rkP+7wm46nPwEMCA5
lvW1KpSon3Hne+6/VjQlnEemX8Ht3J9PvRxr+S7SZNDG/bKJQi3NL7j246a8FH6I
cKqgUctxgpkUCyOcGkJRUQKBgEj7F6BTkl32tlsAKNbdtQ81de9ZjMVbl9bwTkPw
+MSy5XCkfojBJ7sOnb9W9dU29iSnKtLfXU6/gyGEBrZwFOit9XWLeIEYO7pqIUks
lut1MhIItHTAi5B6lwq1gOm+3JGdk2dM0sAptkiRgOcpgbV8L8atBR/6lmUvXRB1
ykH1AoGBAMXus6Ndv/z5rN9zrfN3lggDimd6O6i9h8wgtB/3Dgh42uII3mkZv9Cq
twPpNSKKjLnDF/hD6zi+RvX/XZa2ANdAtchccce7bZ867yeIE96qEjErWCLp6ZTu
RPPKFpbF/qdkGLZftFEqRYkhsEHXAQtJ5sS/mQKnB4R6yv4d6iN2
-----END RSA PRIVATE KEY-----"""

    default_public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAs2EtVywNqwITpULcfp94
tvdYcpwjYqcNdDeJhLASo4J1+bA+C3qnfAXAVcfi1ocwzY+KXtfPDGF6zPynQTJ5
fmhdqepWSJ/RFbUHIwsk1Uuo6ufkPLW3e3QRQL3jpH8sZiSTfH2QqS3WFV2xtZ6l
2+E+z5A/ascWF82iNzI6KuAnfGDCKGCyNy3KoggippF79LxMM0BT8+0eHgvmUNaV
gFaYESwhT0tSCYYU6oWclUK3whgclgTlJkhocqWykcJkp2IGSoHFfgSVOwJsVrhD
hZwkkgKuk1K6n4TzD0vcROlBnYwG4qUQDd36cEWJWXD7NQetdQNMy9YtCyriVItO
uwIDAQAB
-----END PUBLIC KEY-----"""

    # Get keys from environment or use defaults for development
    private_key_pem = os.environ.get('JWT_PRIVATE_KEY', default_private_key)
    public_key_pem = os.environ.get('JWT_PUBLIC_KEY', default_public_key)
    
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), 
            password=None
        )
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        
        return private_key, public_key
    except Exception as e:
        logger.error(f"Failed to load JWT keys: {e}")
        raise ValueError("Invalid JWT keys configuration")


def verify_capability_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify JWT capability token using RSA public key
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload if valid, None otherwise
    """
    try:
        private_key, public_key = get_jwt_keys()
        
        # Verify token with RSA public key
        payload = jwt.decode(token, public_key, algorithms=["RS256"])
        
        # Check expiration
        if "exp" in payload:
            if datetime.utcnow().timestamp() > payload["exp"]:
                logger.warning("Token expired")
                return None
        
        return payload
        
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def create_capability_token(
    user_id: str,
    tenant_id: str,
    capabilities: list,
    expires_hours: int = 4
) -> str:
    """
    Create JWT capability token using RSA private key
    
    Args:
        user_id: User identifier
        tenant_id: Tenant domain
        capabilities: List of capability objects
        expires_hours: Token expiration in hours
        
    Returns:
        JWT token string
    """
    try:
        private_key, public_key = get_jwt_keys()
        
        payload = {
            "sub": user_id,
            "email": user_id,
            "user_type": "tenant_user",
            
            # Current tenant context (primary structure)
            "current_tenant": {
                "id": tenant_id,
                "domain": tenant_id,
                "name": f"Tenant {tenant_id}",
                "role": "tenant_user",
                "display_name": user_id,
                "email": user_id,
                "is_primary": True,
                "capabilities": capabilities
            },
            
            # Available tenants for tenant switching
            "available_tenants": [{
                "id": tenant_id,
                "domain": tenant_id,
                "name": f"Tenant {tenant_id}",
                "role": "tenant_user"
            }],
            
            # Standard JWT fields
            "iat": datetime.utcnow().timestamp(),
            "exp": (datetime.utcnow() + timedelta(hours=expires_hours)).timestamp()
        }
        
        return jwt.encode(payload, private_key, algorithm="RS256")
    except Exception as e:
        logger.error(f"Failed to create capability token: {e}")
        raise ValueError("Failed to create capability token")


async def get_current_user(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Get current user from authorization header - REQUIRED for all endpoints
    Raises 401 if authentication fails - following GT 2.0 security principles
    """
    from fastapi import HTTPException, status
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    # Extract token
    token = authorization.replace("Bearer ", "")
    payload = verify_capability_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract tenant context from new JWT structure
    current_tenant = payload.get('current_tenant', {})
    available_tenants = payload.get('available_tenants', [])
    user_type = payload.get('user_type', 'tenant_user')
    
    # For admin users, allow access to any tenant backend
    if user_type == 'super_admin' and current_tenant.get('domain') == 'admin':
        # Admin users accessing tenant backends - create tenant context for the current backend
        from app.core.config import get_settings
        settings = get_settings()
        
        # Override the admin context with the current tenant backend's context
        current_tenant = {
            'id': settings.tenant_id,
            'domain': settings.tenant_domain,
            'name': f'Tenant {settings.tenant_domain}',
            'role': 'super_admin',
            'display_name': payload.get('email', 'Admin User'),
            'email': payload.get('email'),
            'is_primary': True,
            'capabilities': [
                {'resource': '*', 'actions': ['*'], 'constraints': {}},
            ]
        }
        logger.info(f"Admin user {payload.get('email')} accessing tenant backend {settings.tenant_domain}")
    
    # Validate tenant context exists
    if not current_tenant or not current_tenant.get('id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid tenant context in token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Return user dict with clean tenant context structure
    return {
        'sub': payload.get('sub'),
        'email': payload.get('email'),
        'user_id': payload.get('sub'),
        'user_type': payload.get('user_type', 'tenant_user'),
        
        # Current tenant context (primary structure)
        'tenant_id': str(current_tenant.get('id')),
        'tenant_domain': current_tenant.get('domain'),
        'tenant_name': current_tenant.get('name'),
        'tenant_role': current_tenant.get('role'),
        'tenant_display_name': current_tenant.get('display_name'),
        'tenant_email': current_tenant.get('email'),
        'is_primary_tenant': current_tenant.get('is_primary', False),
        
        # Tenant-specific capabilities  
        'capabilities': current_tenant.get('capabilities', []),
        
        # Available tenants for tenant switching
        'available_tenants': available_tenants
    }


def get_current_user_email(authorization: str) -> str:
    """
    Extract user email from authorization header
    """
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = verify_capability_token(token)
        if payload:
            current_tenant = payload.get('current_tenant', {})
            # Prefer tenant-specific email, fallback to user email, then sub
            return (current_tenant.get('email') or 
                   payload.get('email') or 
                   payload.get('sub', 'test@example.com'))
    
    return 'anonymous@example.com'


def get_tenant_info(authorization: str) -> Dict[str, str]:
    """
    Extract tenant information from authorization header
    """
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = verify_capability_token(token)
        if payload:
            current_tenant = payload.get('current_tenant', {})
            if current_tenant:
                return {
                    'tenant_id': str(current_tenant.get('id')),
                    'tenant_domain': current_tenant.get('domain'),
                    'tenant_name': current_tenant.get('name'),
                    'tenant_role': current_tenant.get('role')
                }
    
    return {
        'tenant_id': 'default',
        'tenant_domain': 'default',
        'tenant_name': 'Default Tenant',
        'tenant_role': 'tenant_user'
    }


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify JWT token - alias for verify_capability_token
    """
    return verify_capability_token(token)


async def get_user_context_unified(
    authorization: Optional[str] = Header(None),
    x_tenant_domain: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Unified authentication for both JWT (user requests) and header-based (service requests).

    Supports two auth modes:
    1. JWT Authentication: Authorization header with Bearer token (for direct user requests)
    2. Header Authentication: X-Tenant-Domain + X-User-ID headers (for internal service requests)

    Returns user context with tenant information for both modes.
    """
    from fastapi import HTTPException, status

    # Mode 1: Header-based authentication (for internal services like MCP)
    if x_tenant_domain and x_user_id:
        logger.info(f"Using header auth: tenant={x_tenant_domain}, user={x_user_id}")
        return {
            "tenant_domain": x_tenant_domain,
            "tenant_id": x_tenant_domain,
            "id": x_user_id,
            "sub": x_user_id,
            "email": x_user_id,
            "user_id": x_user_id,
            "user_type": "internal_service",
            "tenant_role": "tenant_user"
        }

    # Mode 2: JWT authentication (for direct user requests)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = verify_capability_token(token)

        if payload:
            logger.info(f"Using JWT auth: user={payload.get('sub')}")
            # Extract tenant context from JWT structure
            current_tenant = payload.get('current_tenant', {})
            return {
                'sub': payload.get('sub'),
                'email': payload.get('email'),
                'user_id': payload.get('sub'),
                'id': payload.get('sub'),
                'user_type': payload.get('user_type', 'tenant_user'),
                'tenant_id': str(current_tenant.get('id', 'default')),
                'tenant_domain': current_tenant.get('domain', 'default'),
                'tenant_name': current_tenant.get('name', 'Default Tenant'),
                'tenant_role': current_tenant.get('role', 'tenant_user'),
                'capabilities': current_tenant.get('capabilities', [])
            }

    # No valid authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication: provide either Authorization header or X-Tenant-Domain + X-User-ID headers"
    )