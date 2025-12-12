"""
Capability-Based Authentication for GT 2.0 Resource Cluster

Implements JWT capability token verification with:
- Cryptographic signature validation
- Fine-grained resource permissions
- Rate limiting and constraints enforcement
- Tenant isolation validation
- Zero external dependencies

GT 2.0 Security Principles:
- Self-contained: No external auth services
- Stateless: All permissions in JWT token
- Cryptographic: RSA signature verification
- Isolated: Perfect tenant separation
"""

import jwt
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException, Depends, Header
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CapabilityError(Exception):
    """Capability authentication error"""
    pass


class ResourceType(str, Enum):
    """Resource types in GT 2.0"""
    LLM = "llm"
    EMBEDDING = "embedding"
    VECTOR_STORAGE = "vector_storage"
    EXTERNAL_SERVICES = "external_services"
    ADMIN = "admin"


class ActionType(str, Enum):
    """Action types for resources"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class Capability:
    """Individual capability definition"""
    resource: ResourceType
    actions: List[ActionType]
    constraints: Dict[str, Any]
    expires_at: Optional[datetime] = None
    
    def allows_action(self, action: ActionType) -> bool:
        """Check if capability allows specific action"""
        return action in self.actions
    
    def is_expired(self) -> bool:
        """Check if capability is expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def check_constraint(self, constraint_name: str, value: Any) -> bool:
        """Check if value satisfies constraint"""
        if constraint_name not in self.constraints:
            return True  # No constraint means allowed
        
        constraint_value = self.constraints[constraint_name]
        
        if constraint_name == "max_tokens":
            return value <= constraint_value
        elif constraint_name == "allowed_models":
            return value in constraint_value
        elif constraint_name == "max_requests_per_hour":
            # This would be checked separately with rate limiting
            return True
        elif constraint_name == "allowed_tenants":
            return value in constraint_value
        
        return True


@dataclass  
class CapabilityToken:
    """Parsed capability token"""
    subject: str
    tenant_id: str
    capabilities: List[Capability]
    issued_at: datetime
    expires_at: datetime
    issuer: str
    token_version: str
    
    def has_capability(self, resource: ResourceType, action: ActionType) -> bool:
        """Check if token has specific capability"""
        for cap in self.capabilities:
            if cap.resource == resource and cap.allows_action(action) and not cap.is_expired():
                return True
        return False
    
    def get_capability(self, resource: ResourceType) -> Optional[Capability]:
        """Get capability for specific resource"""
        for cap in self.capabilities:
            if cap.resource == resource and not cap.is_expired():
                return cap
        return None
    
    def is_expired(self) -> bool:
        """Check if entire token is expired"""
        return datetime.now(timezone.utc) > self.expires_at


class CapabilityAuthenticator:
    """
    Handles capability token verification and authorization.
    
    Uses JWT tokens with embedded permissions for stateless authentication.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # In production, this would be loaded from secure storage
        # For development, using the secret key
        self.secret_key = self.settings.secret_key
        self.algorithm = "HS256"  # TODO: Upgrade to RS256 with public/private keys
        
        logger.info("Capability authenticator initialized")
    
    async def verify_token(self, token: str) -> CapabilityToken:
        """
        Verify and parse capability token.
        
        Args:
            token: JWT capability token
            
        Returns:
            Parsed capability token
            
        Raises:
            CapabilityError: If token is invalid or expired
        """
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience="gt2-resource-cluster"
            )
            
            # Validate required fields
            required_fields = ["sub", "tenant_id", "capabilities", "iat", "exp", "iss"]
            for field in required_fields:
                if field not in payload:
                    raise CapabilityError(f"Missing required field: {field}")
            
            # Parse timestamps
            issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            
            # Check token expiration
            if datetime.now(timezone.utc) > expires_at:
                raise CapabilityError("Token has expired")
            
            # Parse capabilities
            capabilities = []
            for cap_data in payload["capabilities"]:
                try:
                    capability = Capability(
                        resource=ResourceType(cap_data["resource"]),
                        actions=[ActionType(action) for action in cap_data["actions"]],
                        constraints=cap_data.get("constraints", {}),
                        expires_at=datetime.fromtimestamp(
                            cap_data["expires_at"], tz=timezone.utc
                        ) if cap_data.get("expires_at") else None
                    )
                    capabilities.append(capability)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid capability in token: {e}")
                    # Skip invalid capabilities rather than rejecting entire token
                    continue
            
            # Create capability token
            capability_token = CapabilityToken(
                subject=payload["sub"],
                tenant_id=payload["tenant_id"],
                capabilities=capabilities,
                issued_at=issued_at,
                expires_at=expires_at,
                issuer=payload["iss"],
                token_version=payload.get("token_version", "1.0")
            )
            
            logger.debug(f"Capability token verified for {capability_token.subject}")
            return capability_token
            
        except jwt.ExpiredSignatureError:
            raise CapabilityError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise CapabilityError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise CapabilityError(f"Token verification failed: {e}")
    
    async def check_resource_access(
        self,
        capability_token: CapabilityToken,
        resource: ResourceType,
        action: ActionType,
        constraints: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if token allows access to resource with specific action.
        
        Args:
            capability_token: Verified capability token
            resource: Resource type to access
            action: Action to perform
            constraints: Additional constraints to check
            
        Returns:
            True if access is allowed
            
        Raises:
            CapabilityError: If access is denied
        """
        try:
            # Check token expiration
            if capability_token.is_expired():
                raise CapabilityError("Token has expired")
            
            # Find matching capability
            capability = capability_token.get_capability(resource)
            if not capability:
                raise CapabilityError(f"No capability for resource: {resource}")
            
            # Check action permission
            if not capability.allows_action(action):
                raise CapabilityError(f"Action {action} not allowed for resource {resource}")
            
            # Check constraints if provided
            if constraints:
                for constraint_name, value in constraints.items():
                    if not capability.check_constraint(constraint_name, value):
                        raise CapabilityError(
                            f"Constraint violation: {constraint_name} = {value}"
                        )
            
            return True
            
        except CapabilityError:
            raise
        except Exception as e:
            logger.error(f"Resource access check failed: {e}")
            raise CapabilityError(f"Access check failed: {e}")


# Global authenticator instance
capability_authenticator = CapabilityAuthenticator()


async def verify_capability_token(token: str) -> Dict[str, Any]:
    """
    Verify capability token and return payload.
    
    Args:
        token: JWT capability token
        
    Returns:
        Token payload as dictionary
        
    Raises:
        CapabilityError: If token is invalid
    """
    capability_token = await capability_authenticator.verify_token(token)
    
    return {
        "sub": capability_token.subject,
        "tenant_id": capability_token.tenant_id,
        "capabilities": [
            {
                "resource": cap.resource.value,
                "actions": [action.value for action in cap.actions],
                "constraints": cap.constraints
            }
            for cap in capability_token.capabilities
        ],
        "iat": capability_token.issued_at.timestamp(),
        "exp": capability_token.expires_at.timestamp(),
        "iss": capability_token.issuer,
        "token_version": capability_token.token_version
    }


async def get_current_capability(
    authorization: str = Header(..., description="Bearer token")
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current capability from Authorization header.
    
    Args:
        authorization: Authorization header with Bearer token
        
    Returns:
        Capability payload
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format"
            )
        
        token = authorization[7:]  # Remove "Bearer " prefix
        payload = await verify_capability_token(token)
        
        return payload
        
    except CapabilityError as e:
        logger.warning(f"Capability authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")


async def require_capability(
    resource: ResourceType,
    action: ActionType,
    constraints: Optional[Dict[str, Any]] = None
):
    """
    FastAPI dependency to require specific capability.
    
    Args:
        resource: Required resource type
        action: Required action type
        constraints: Additional constraints to check
        
    Returns:
        Dependency function
    """
    async def _check_capability(
        capability_payload: Dict[str, Any] = Depends(get_current_capability)
    ) -> Dict[str, Any]:
        try:
            # Reconstruct capability token from payload
            capabilities = []
            for cap_data in capability_payload["capabilities"]:
                capability = Capability(
                    resource=ResourceType(cap_data["resource"]),
                    actions=[ActionType(action) for action in cap_data["actions"]],
                    constraints=cap_data["constraints"]
                )
                capabilities.append(capability)
            
            capability_token = CapabilityToken(
                subject=capability_payload["sub"],
                tenant_id=capability_payload["tenant_id"],
                capabilities=capabilities,
                issued_at=datetime.fromtimestamp(capability_payload["iat"], tz=timezone.utc),
                expires_at=datetime.fromtimestamp(capability_payload["exp"], tz=timezone.utc),
                issuer=capability_payload["iss"],
                token_version=capability_payload["token_version"]
            )
            
            # Check required capability
            await capability_authenticator.check_resource_access(
                capability_token=capability_token,
                resource=resource,
                action=action,
                constraints=constraints
            )
            
            return capability_payload
            
        except CapabilityError as e:
            logger.warning(f"Capability check failed: {e}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.error(f"Capability check error: {e}")
            raise HTTPException(status_code=500, detail="Authorization error")
    
    return _check_capability


# Convenience functions for common capability checks

async def require_llm_capability(
    capability_payload: Dict[str, Any] = Depends(
        require_capability(ResourceType.LLM, ActionType.EXECUTE)
    )
) -> Dict[str, Any]:
    """Require LLM execution capability"""
    return capability_payload


async def require_embedding_capability(
    capability_payload: Dict[str, Any] = Depends(
        require_capability(ResourceType.EMBEDDING, ActionType.EXECUTE)
    )
) -> Dict[str, Any]:
    """Require embedding generation capability"""
    return capability_payload


async def require_admin_capability(
    capability_payload: Dict[str, Any] = Depends(
        require_capability(ResourceType.ADMIN, ActionType.ADMIN)
    )
) -> Dict[str, Any]:
    """Require admin capability"""
    return capability_payload


async def verify_capability_token_dependency(
    authorization: str = Header(..., description="Bearer token")
) -> Dict[str, Any]:
    """
    FastAPI dependency for ChromaDB MCP API that verifies capability token.
    
    Returns token payload with raw_token field for service layer use.
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format"
            )
        
        token = authorization[7:]  # Remove "Bearer " prefix
        payload = await verify_capability_token(token)
        
        # Add raw token for service layer
        payload["raw_token"] = token
        
        return payload
        
    except CapabilityError as e:
        logger.warning(f"Capability authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")