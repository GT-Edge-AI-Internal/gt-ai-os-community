"""
Capability-based access control for GT 2.0 CB-REST API

Design principle: Security through cryptographic capabilities embedded in JWT tokens
Perfect tenant isolation through capability scoping
"""

import hashlib
import hmac
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import jwt
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .errors import ErrorCode, APIError


# Security scheme for FastAPI
security = HTTPBearer()


class Capability(BaseModel):
    """
    A single capability grant
    
    Format: resource:id:action
    Example: tenant:customer1:read
    """
    resource: str = Field(..., description="Resource type (tenant, user, resource, etc.)")
    resource_id: str = Field(..., description="Specific resource ID or wildcard (*)")
    action: str = Field(..., description="Action allowed (read, write, create, delete, admin)")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Additional constraints")
    expires_at: Optional[datetime] = Field(None, description="Expiration time for this capability")
    
    def matches(self, required_resource: str, required_id: str, required_action: str) -> bool:
        """
        Check if this capability matches the required permission
        
        Supports wildcards (*) for resource_id and action
        """
        # Check resource type
        if self.resource != required_resource and self.resource != "*":
            return False
        
        # Check resource ID (supports wildcards)
        if self.resource_id != required_id and self.resource_id != "*":
            return False
        
        # Check action (supports wildcards and hierarchical permissions)
        if self.action == "*" or self.action == "admin":
            return True  # Admin has all permissions
        
        if self.action == required_action:
            return True
        
        # Hierarchical permissions: write includes read, delete includes write
        action_hierarchy = {
            "delete": ["write", "read"],
            "write": ["read"],
            "create": ["read"]
        }
        
        if required_action in action_hierarchy.get(self.action, []):
            return True
        
        return False
    
    def to_string(self) -> str:
        """Convert capability to string format"""
        return f"{self.resource}:{self.resource_id}:{self.action}"
    
    @classmethod
    def from_string(cls, capability_str: str) -> "Capability":
        """Parse capability from string format"""
        parts = capability_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid capability format: {capability_str}")
        
        return cls(
            resource=parts[0],
            resource_id=parts[1],
            action=parts[2]
        )


class CapabilityToken(BaseModel):
    """
    JWT token payload with embedded capabilities
    """
    sub: str = Field(..., description="Subject (user email or ID)")
    tenant_id: str = Field(..., description="Tenant ID for isolation")
    user_type: str = Field(..., description="User type (super_admin, gt_admin, tenant_admin, tenant_user)")
    capabilities: List[Dict[str, Any]] = Field(..., description="List of granted capabilities")
    iat: int = Field(..., description="Issued at timestamp")
    exp: int = Field(..., description="Expiration timestamp")
    jti: Optional[str] = Field(None, description="JWT ID for revocation")
    
    def get_capabilities(self) -> List[Capability]:
        """Convert capability dicts to Capability objects"""
        return [Capability(**cap) for cap in self.capabilities]
    
    def has_capability(self, resource: str, resource_id: str, action: str) -> bool:
        """Check if token has a specific capability"""
        for cap in self.get_capabilities():
            if cap.matches(resource, resource_id, action):
                # Check expiration if set
                if cap.expires_at and cap.expires_at < datetime.utcnow():
                    continue
                return True
        return False


class CapabilityVerifier:
    """
    Verifies capabilities and signatures
    """
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def verify_token(self, token: str) -> CapabilityToken:
        """
        Verify and decode a JWT capability token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded CapabilityToken
        
        Raises:
            APIError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return CapabilityToken(**payload)
        except jwt.ExpiredSignatureError:
            raise APIError(
                code=ErrorCode.CAPABILITY_EXPIRED,
                message="Capability token has expired",
                status_code=401
            )
        except jwt.InvalidTokenError as e:
            raise APIError(
                code=ErrorCode.CAPABILITY_INVALID,
                message=f"Invalid capability token: {str(e)}",
                status_code=401
            )
    
    def verify_signature(self, token: str, signature: str) -> bool:
        """
        Verify HMAC signature of capability
        
        Args:
            token: JWT token string
            signature: HMAC signature to verify
        
        Returns:
            True if signature is valid
        """
        expected_signature = hmac.new(
            self.secret_key.encode(),
            token.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def create_token(
        self,
        user_email: str,
        tenant_id: str,
        user_type: str,
        capabilities: List[Capability],
        expires_in: timedelta = timedelta(hours=24)
    ) -> str:
        """
        Create a new capability token
        
        Args:
            user_email: User's email address
            tenant_id: Tenant ID for isolation
            user_type: Type of user
            capabilities: List of capabilities to grant
            expires_in: Token expiration time
        
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        exp = now + expires_in
        
        payload = CapabilityToken(
            sub=user_email,
            tenant_id=tenant_id,
            user_type=user_type,
            capabilities=[cap.dict(exclude_none=True) for cap in capabilities],
            iat=int(now.timestamp()),
            exp=int(exp.timestamp())
        )
        
        return jwt.encode(
            payload.dict(exclude_none=True),
            self.secret_key,
            algorithm=self.algorithm
        )


# Global verifier instance (initialized by application)
_verifier: Optional[CapabilityVerifier] = None


def init_capability_verifier(secret_key: str, algorithm: str = "HS256"):
    """Initialize the global capability verifier"""
    global _verifier
    _verifier = CapabilityVerifier(secret_key, algorithm)


def get_verifier() -> CapabilityVerifier:
    """Get the global capability verifier"""
    if _verifier is None:
        raise RuntimeError("Capability verifier not initialized. Call init_capability_verifier first.")
    return _verifier


async def verify_capability(
    credentials: HTTPAuthorizationCredentials = Security(security),
    request: Request = None
) -> CapabilityToken:
    """
    FastAPI dependency to verify capability token
    
    Args:
        credentials: Bearer token from Authorization header
        request: Optional request object for additional context
    
    Returns:
        Verified CapabilityToken
    
    Raises:
        HTTPException: If token is invalid
    """
    verifier = get_verifier()
    
    # Check for signature header if request provided
    signature = None
    if request:
        signature = request.headers.get("X-Capability-Signature")
        if signature and not verifier.verify_signature(credentials.credentials, signature):
            raise APIError(
                code=ErrorCode.CAPABILITY_SIGNATURE_INVALID,
                message="Capability signature verification failed",
                status_code=401
            )
    
    return verifier.verify_token(credentials.credentials)


def require_capability(
    resource: str,
    resource_id: str,
    action: str
):
    """
    Create a FastAPI dependency that requires a specific capability
    
    Args:
        resource: Resource type
        resource_id: Resource ID (can be "*" for wildcard)
        action: Required action
    
    Returns:
        FastAPI dependency function
    """
    async def capability_checker(
        token: CapabilityToken = Depends(verify_capability)
    ) -> CapabilityToken:
        """Check if the token has the required capability"""
        
        # Super admins bypass all checks (GT 2.0 admin efficiency)
        if token.user_type == "super_admin":
            return token
        
        # GT admins can access all tenants but not system resources
        if token.user_type == "gt_admin" and resource in ["tenant", "user", "resource"]:
            return token
        
        # Check specific capability
        if not token.has_capability(resource, resource_id, action):
            capability_required = f"{resource}:{resource_id}:{action}"
            
            # Find what capabilities the user has for this resource
            user_caps = [
                cap.to_string() 
                for cap in token.get_capabilities() 
                if cap.resource == resource
            ]
            
            raise APIError(
                code=ErrorCode.CAPABILITY_INSUFFICIENT,
                message=f"Insufficient capability for {resource} {action}",
                status_code=403,
                capability_required=capability_required,
                capability_provided=", ".join(user_caps) if user_caps else "none"
            )
        
        return token
    
    return capability_checker


def extract_capability_from_jwt(token_str: str) -> Optional[CapabilityToken]:
    """
    Extract capability token without verification (for logging/debugging)
    
    WARNING: This does not verify the token! Use only for non-security purposes.
    
    Args:
        token_str: JWT token string
    
    Returns:
        CapabilityToken if decodable, None otherwise
    """
    try:
        # Decode without verification
        payload = jwt.decode(token_str, options={"verify_signature": False})
        return CapabilityToken(**payload)
    except Exception:
        return None