"""
Authentication and authorization utilities
"""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer()


class JWTHandler:
    """JWT token handler"""
    
    @staticmethod
    def create_access_token(
        user_id: int,
        user_email: str,
        user_type: str,
        current_tenant: Optional[dict] = None,
        available_tenants: Optional[list] = None,
        capabilities: Optional[list] = None,
        # For token refresh: preserve original login time and absolute expiry
        original_iat: Optional[datetime] = None,
        original_absolute_exp: Optional[float] = None,
        # Server-side session token (Issue #264)
        session_token: Optional[str] = None
    ) -> str:
        """Create a JWT access token with tenant context

        NIST/OWASP Compliant Session Management (Issues #242, #264):
        - exp: Idle timeout (4 hours) - refreshable on user activity
        - absolute_exp: Absolute timeout (8 hours) - NOT refreshable, forces re-login
        - iat: Original login time - preserved across token refreshes
        - session_id: Server-side session token for authoritative validation
        """
        now = datetime.now(timezone.utc)

        # Use original iat if refreshing, otherwise current time (new login)
        iat = original_iat if original_iat else now

        # Calculate absolute expiry: iat + absolute timeout hours (only set on initial login)
        if original_absolute_exp is not None:
            absolute_exp = original_absolute_exp
        else:
            absolute_exp = (iat + timedelta(hours=settings.JWT_ABSOLUTE_TIMEOUT_HOURS)).timestamp()

        payload = {
            "sub": str(user_id),
            "email": user_email,
            "user_type": user_type,

            # Current tenant context (most important)
            "current_tenant": current_tenant or {},

            # Available tenants for switching
            "available_tenants": available_tenants or [],

            # Base capabilities (rarely used - tenant-specific capabilities are in current_tenant)
            "capabilities": capabilities or [],

            # NIST/OWASP Session Timeouts (Issues #242, #264)
            # exp: Idle timeout - 4 hours from now (refreshable)
            "exp": now + timedelta(minutes=settings.JWT_EXPIRES_MINUTES),
            # iat: Original login time (preserved across refreshes)
            "iat": iat,
            # absolute_exp: Absolute timeout from original login (NOT refreshable)
            "absolute_exp": absolute_exp,
            # session_id: Server-side session token for authoritative validation (Issue #264)
            # The server-side session is the source of truth - JWT expiry is secondary
            "session_id": session_token
        }
        
        
        # Use RSA keys for consistency with tenant backend
        private_key_pem = """-----BEGIN RSA PRIVATE KEY-----
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
        
        from cryptography.hazmat.primitives import serialization
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), 
            password=None
        )
        return jwt.encode(payload, private_key, algorithm="RS256")
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token"""
        try:
            # Use RSA public key for consistency with tenant backend
            public_key_pem = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAs2EtVywNqwITpULcfp94
tvdYcpwjYqcNdDeJhLASo4J1+bA+C3qnfAXAVcfi1ocwzY+KXtfPDGF6zPynQTJ5
fmhdqepWSJ/RFbUHIwsk1Uuo6ufkPLW3e3QRQL3jpH8sZiSTfH2QqS3WFV2xtZ6l
2+E+z5A/ascWF82iNzI6KuAnfGDCKGCyNy3KoggippF79LxMM0BT8+0eHgvmUNaV
gFaYESwhT0tSCYYU6oWclUK3whgclgTlJkhocqWykcJkp2IGSoHFfgSVOwJsVrhD
hZwkkgKuk1K6n4TzD0vcROlBnYwG4qUQDd36cEWJWXD7NQetdQNMy9YtCyriVItO
uwIDAQAB
-----END PUBLIC KEY-----"""
            
            from cryptography.hazmat.primitives import serialization
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get the current authenticated user"""
    
    token = credentials.credentials
    payload = JWTHandler.decode_token(token)
    
    user_id = int(payload["sub"])
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to be a super admin (control panel access)"""
    if current_user.user_type != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to be a super admin"""
    if current_user.user_type != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user