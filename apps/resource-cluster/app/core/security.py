"""
GT 2.0 Resource Cluster Security

Capability-based authentication and authorization for resource access.
Implements cryptographically signed JWT tokens with embedded capabilities.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ResourceCapability(BaseModel):
    """Individual resource capability"""
    resource: str  # e.g., "llm:groq", "rag:semantic_search"
    actions: List[str]  # e.g., ["inference", "streaming"]
    limits: Dict[str, Any] = {}  # e.g., {"max_tokens": 4000, "requests_per_minute": 60}
    constraints: Dict[str, Any] = {}  # e.g., {"valid_until": "2024-12-31", "ip_restrictions": []}


class CapabilityToken(BaseModel):
    """Capability-based JWT token payload"""
    sub: str  # User or service identifier
    tenant_id: str  # Tenant identifier
    capabilities: List[ResourceCapability]  # Granted capabilities
    capability_hash: str  # SHA256 hash of capabilities for integrity
    exp: Optional[datetime] = None  # Expiration time
    iat: Optional[datetime] = None  # Issued at time
    jti: Optional[str] = None  # JWT ID for revocation


class CapabilityValidator:
    """Validates and enforces capability-based access control"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def create_capability_token(
        self,
        user_id: str,
        tenant_id: str,
        capabilities: List[Dict[str, Any]],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a cryptographically signed capability token"""
        
        # Convert capabilities to ResourceCapability objects
        capability_objects = [
            ResourceCapability(**cap) for cap in capabilities
        ]
        
        # Generate capability hash for integrity verification
        capability_hash = self._generate_capability_hash(capability_objects)
        
        # Set token expiration
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.settings.capability_token_expire_minutes)
        
        # Create token payload
        token_data = CapabilityToken(
            sub=user_id,
            tenant_id=tenant_id,
            capabilities=[cap.dict() for cap in capability_objects],
            capability_hash=capability_hash,
            exp=expire,
            iat=datetime.utcnow(),
            jti=self._generate_jti()
        )
        
        # Encode JWT token
        encoded_jwt = jwt.encode(
            token_data.dict(),
            self.settings.secret_key,
            algorithm=self.settings.algorithm
        )
        
        return encoded_jwt
    
    def verify_capability_token(self, token: str) -> Optional[CapabilityToken]:
        """Verify and decode a capability token"""
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.algorithm]
            )
            
            # Convert to CapabilityToken object
            capability_token = CapabilityToken(**payload)
            
            # Verify capability hash integrity
            capability_objects = []
            for cap in capability_token.capabilities:
                if isinstance(cap, dict):
                    capability_objects.append(ResourceCapability(**cap))
                else:
                    capability_objects.append(cap)
            
            expected_hash = self._generate_capability_hash(capability_objects)
            
            if capability_token.capability_hash != expected_hash:
                raise ValueError("Capability hash mismatch - token may be tampered")
            
            return capability_token
            
        except (JWTError, ValueError) as e:
            return None
    
    def check_resource_access(
        self,
        token: CapabilityToken,
        resource: str,
        action: str,
        context: Dict[str, Any] = {}
    ) -> bool:
        """Check if token grants access to specific resource and action"""
        
        for capability in token.capabilities:
            # Handle both dict and ResourceCapability object formats
            if isinstance(capability, dict):
                cap_resource = capability["resource"]
                cap_actions = capability.get("actions", [])
                cap_constraints = capability.get("constraints", {})
            else:
                cap_resource = capability.resource
                cap_actions = capability.actions
                cap_constraints = capability.constraints
                
            # Check if capability matches resource
            if self._matches_resource(cap_resource, resource):
                # Check if action is allowed
                if action in cap_actions:
                    # Check additional constraints
                    if self._check_constraints(cap_constraints, context):
                        return True
        
        return False
    
    def get_resource_limits(
        self,
        token: CapabilityToken,
        resource: str
    ) -> Dict[str, Any]:
        """Get resource-specific limits from token"""
        
        for capability in token.capabilities:
            # Handle both dict and ResourceCapability object formats
            if isinstance(capability, dict):
                cap_resource = capability["resource"]
                cap_limits = capability.get("limits", {})
            else:
                cap_resource = capability.resource
                cap_limits = capability.limits
                
            if self._matches_resource(cap_resource, resource):
                return cap_limits
        
        return {}
    
    def _generate_capability_hash(self, capabilities: List[ResourceCapability]) -> str:
        """Generate SHA256 hash of capabilities for integrity verification"""
        # Sort capabilities for consistent hashing
        sorted_caps = sorted(
            [cap.dict() for cap in capabilities],
            key=lambda x: x["resource"]
        )
        
        # Create hash
        cap_string = json.dumps(sorted_caps, sort_keys=True)
        return hashlib.sha256(cap_string.encode()).hexdigest()
    
    def _generate_jti(self) -> str:
        """Generate unique JWT ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _matches_resource(self, pattern: str, resource: str) -> bool:
        """Check if resource pattern matches requested resource"""
        # Handle wildcards (e.g., "llm:*" matches "llm:groq")
        if pattern.endswith(":*"):
            prefix = pattern[:-2]
            return resource.startswith(prefix + ":")
        
        # Handle exact matches
        return pattern == resource
    
    def _check_constraints(self, constraints: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check additional constraints like time validity and IP restrictions"""
        
        # Check time validity
        if "valid_until" in constraints:
            valid_until = datetime.fromisoformat(constraints["valid_until"])
            if datetime.utcnow() > valid_until:
                return False
        
        # Check IP restrictions
        if "ip_restrictions" in constraints and "client_ip" in context:
            allowed_ips = constraints["ip_restrictions"]
            if allowed_ips and context["client_ip"] not in allowed_ips:
                return False
        
        # Check tenant restrictions
        if "allowed_tenants" in constraints and "tenant_id" in context:
            allowed_tenants = constraints["allowed_tenants"]
            if allowed_tenants and context["tenant_id"] not in allowed_tenants:
                return False
        
        return True


# Global validator instance
capability_validator = CapabilityValidator()


def verify_capability_token(token: str) -> Optional[CapabilityToken]:
    """Standalone function for FastAPI dependency injection"""
    return capability_validator.verify_capability_token(token)


def create_resource_capability(
    resource_type: str,
    resource_id: str,
    actions: List[str],
    limits: Dict[str, Any] = {},
    constraints: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """Helper function to create a resource capability"""
    return {
        "resource": f"{resource_type}:{resource_id}",
        "actions": actions,
        "limits": limits,
        "constraints": constraints
    }


def create_assistant_capabilities(assistant_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create capabilities from agent configuration"""
    capabilities = []
    
    # Extract capabilities from agent config
    for cap in assistant_config.get("capabilities", []):
        capabilities.append(cap)
    
    # Add default LLM capability if specified
    if "primary_llm" in assistant_config.get("resource_preferences", {}):
        llm_model = assistant_config["resource_preferences"]["primary_llm"]
        capabilities.append(create_resource_capability(
            "llm",
            llm_model.replace(":", "_"),
            ["inference", "streaming"],
            {
                "max_tokens": assistant_config["resource_preferences"].get("max_tokens", 4000),
                "temperature": assistant_config["resource_preferences"].get("temperature", 0.7)
            }
        ))
    
    return capabilities


# Global capability validator instance
capability_validator = CapabilityValidator()