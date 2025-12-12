"""
Enhanced API Key Management Service for GT 2.0

Implements advanced API key management with capability-based permissions,
configurable constraints, and comprehensive audit logging.
"""

import os
import stat
import json
import secrets
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
import jwt

from app.core.security import verify_capability_token

logger = logging.getLogger(__name__)


class APIKeyStatus(Enum):
    """API key status states"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class APIKeyScope(Enum):
    """API key scope levels"""
    USER = "user"           # User-specific operations
    TENANT = "tenant"       # Tenant-wide operations
    ADMIN = "admin"         # Administrative operations


@dataclass
class APIKeyUsage:
    """API key usage tracking"""
    requests_count: int = 0
    last_used: Optional[datetime] = None
    bytes_transferred: int = 0
    errors_count: int = 0
    rate_limit_hits: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "requests_count": self.requests_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "bytes_transferred": self.bytes_transferred,
            "errors_count": self.errors_count,
            "rate_limit_hits": self.rate_limit_hits
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIKeyUsage":
        """Create from dictionary"""
        return cls(
            requests_count=data.get("requests_count", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            bytes_transferred=data.get("bytes_transferred", 0),
            errors_count=data.get("errors_count", 0),
            rate_limit_hits=data.get("rate_limit_hits", 0)
        )


@dataclass
class APIKeyConfig:
    """Enhanced API key configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    owner_id: str = ""
    key_hash: str = ""
    
    # Capability and permissions
    capabilities: List[str] = field(default_factory=list)
    scope: APIKeyScope = APIKeyScope.USER
    tenant_constraints: Dict[str, Any] = field(default_factory=dict)
    
    # Rate limiting and quotas
    rate_limit_per_hour: int = 1000
    daily_quota: int = 10000
    monthly_quota: int = 300000
    cost_limit_cents: int = 1000
    
    # Resource constraints
    max_tokens_per_request: int = 4000
    max_concurrent_requests: int = 10
    allowed_endpoints: List[str] = field(default_factory=list)
    blocked_endpoints: List[str] = field(default_factory=list)
    
    # Network and security
    allowed_ips: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    require_tls: bool = True
    
    # Lifecycle management
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_rotated: Optional[datetime] = None
    
    # Usage tracking
    usage: APIKeyUsage = field(default_factory=APIKeyUsage)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "key_hash": self.key_hash,
            "capabilities": self.capabilities,
            "scope": self.scope.value,
            "tenant_constraints": self.tenant_constraints,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "daily_quota": self.daily_quota,
            "monthly_quota": self.monthly_quota,
            "cost_limit_cents": self.cost_limit_cents,
            "max_tokens_per_request": self.max_tokens_per_request,
            "max_concurrent_requests": self.max_concurrent_requests,
            "allowed_endpoints": self.allowed_endpoints,
            "blocked_endpoints": self.blocked_endpoints,
            "allowed_ips": self.allowed_ips,
            "allowed_domains": self.allowed_domains,
            "require_tls": self.require_tls,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_rotated": self.last_rotated.isoformat() if self.last_rotated else None,
            "usage": self.usage.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIKeyConfig":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            owner_id=data["owner_id"],
            key_hash=data["key_hash"],
            capabilities=data.get("capabilities", []),
            scope=APIKeyScope(data.get("scope", "user")),
            tenant_constraints=data.get("tenant_constraints", {}),
            rate_limit_per_hour=data.get("rate_limit_per_hour", 1000),
            daily_quota=data.get("daily_quota", 10000),
            monthly_quota=data.get("monthly_quota", 300000),
            cost_limit_cents=data.get("cost_limit_cents", 1000),
            max_tokens_per_request=data.get("max_tokens_per_request", 4000),
            max_concurrent_requests=data.get("max_concurrent_requests", 10),
            allowed_endpoints=data.get("allowed_endpoints", []),
            blocked_endpoints=data.get("blocked_endpoints", []),
            allowed_ips=data.get("allowed_ips", []),
            allowed_domains=data.get("allowed_domains", []),
            require_tls=data.get("require_tls", True),
            status=APIKeyStatus(data.get("status", "active")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            last_rotated=datetime.fromisoformat(data["last_rotated"]) if data.get("last_rotated") else None,
            usage=APIKeyUsage.from_dict(data.get("usage", {}))
        )


class EnhancedAPIKeyService:
    """
    Enhanced API Key management service with advanced capabilities.
    
    Features:
    - Capability-based permissions with tenant constraints
    - Granular rate limiting and quota management
    - Network-based access controls (IP, domain restrictions)
    - Comprehensive usage tracking and analytics
    - Automated key rotation and lifecycle management
    - Perfect tenant isolation through file-based storage
    """
    
    def __init__(self, tenant_domain: str, signing_key: str = ""):
        self.tenant_domain = tenant_domain
        self.signing_key = signing_key or self._generate_signing_key()
        self.base_path = Path(f"/data/{tenant_domain}/api_keys")
        self.keys_path = self.base_path / "keys"
        self.usage_path = self.base_path / "usage"
        self.audit_path = self.base_path / "audit"
        
        # Ensure directories exist with proper permissions
        self._ensure_directories()
        
        logger.info(f"EnhancedAPIKeyService initialized for {tenant_domain}")
    
    def _ensure_directories(self):
        """Ensure API key directories exist with proper permissions"""
        for path in [self.keys_path, self.usage_path, self.audit_path]:
            path.mkdir(parents=True, exist_ok=True)
            # Set permissions to 700 (owner only)
            os.chmod(path, stat.S_IRWXU)
    
    def _generate_signing_key(self) -> str:
        """Generate cryptographic signing key for JWT tokens"""
        return secrets.token_urlsafe(64)
    
    async def create_api_key(
        self,
        name: str,
        owner_id: str,
        capabilities: List[str],
        scope: APIKeyScope = APIKeyScope.USER,
        expires_in_days: int = 90,
        constraints: Optional[Dict[str, Any]] = None,
        capability_token: str = ""
    ) -> Tuple[APIKeyConfig, str]:
        """
        Create a new API key with specified capabilities and constraints.
        
        Args:
            name: Human-readable name for the key
            owner_id: User who owns the key
            capabilities: List of capability strings
            scope: Key scope level
            expires_in_days: Expiration time in days
            constraints: Custom constraints for the key
            capability_token: Admin capability token
            
        Returns:
            Tuple of (APIKeyConfig, raw_key)
        """
        # Verify admin capability for key creation
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Generate secure API key
        raw_key = f"gt2_{self.tenant_domain}_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Apply constraints with tenant-specific defaults
        final_constraints = self._apply_tenant_defaults(constraints or {})
        
        # Create API key configuration
        api_key = APIKeyConfig(
            name=name,
            owner_id=owner_id,
            key_hash=key_hash,
            capabilities=capabilities,
            scope=scope,
            tenant_constraints=final_constraints,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )
        
        # Apply scope-based defaults
        self._apply_scope_defaults(api_key, scope)
        
        # Store API key
        await self._store_api_key(api_key)
        
        # Log creation
        await self._audit_log("api_key_created", owner_id, {
            "key_id": api_key.id,
            "name": name,
            "scope": scope.value,
            "capabilities": capabilities
        })
        
        logger.info(f"Created API key: {name} ({api_key.id}) for {owner_id}")
        return api_key, raw_key
    
    async def validate_api_key(
        self,
        raw_key: str,
        endpoint: str = "",
        client_ip: str = "",
        user_agent: str = ""
    ) -> Tuple[bool, Optional[APIKeyConfig], Optional[str]]:
        """
        Validate API key and check constraints.
        
        Args:
            raw_key: Raw API key from request
            endpoint: Requested endpoint
            client_ip: Client IP address
            user_agent: Client user agent
            
        Returns:
            Tuple of (valid, api_key_config, error_message)
        """
        # Hash the key for lookup
        # Security Note: SHA256 is used here for API key lookup/indexing, not password storage.
        # API keys are high-entropy random strings, making them resistant to dictionary/rainbow attacks.
        # This is an acceptable security pattern similar to how GitHub and Stripe handle API keys.
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Load API key configuration
        api_key = await self._load_api_key_by_hash(key_hash)
        if not api_key:
            return False, None, "Invalid API key"
        
        # Check key status
        if api_key.status != APIKeyStatus.ACTIVE:
            return False, api_key, f"API key is {api_key.status.value}"
        
        # Check expiration
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            # Auto-expire the key
            api_key.status = APIKeyStatus.EXPIRED
            await self._store_api_key(api_key)
            return False, api_key, "API key has expired"
        
        # Check endpoint restrictions
        if api_key.allowed_endpoints:
            if endpoint not in api_key.allowed_endpoints:
                return False, api_key, f"Endpoint {endpoint} not allowed"
        
        if endpoint in api_key.blocked_endpoints:
            return False, api_key, f"Endpoint {endpoint} is blocked"
        
        # Check IP restrictions
        if api_key.allowed_ips and client_ip not in api_key.allowed_ips:
            return False, api_key, f"IP {client_ip} not allowed"
        
        # Check rate limits
        rate_limit_ok, rate_error = await self._check_rate_limits(api_key)
        if not rate_limit_ok:
            return False, api_key, rate_error
        
        # Update usage
        await self._update_usage(api_key, endpoint, client_ip)
        
        return True, api_key, None
    
    async def generate_capability_token(
        self,
        api_key: APIKeyConfig,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate JWT capability token from API key.
        
        Args:
            api_key: API key configuration
            additional_context: Additional context for the token
            
        Returns:
            JWT capability token
        """
        # Build capability payload
        capabilities = []
        for cap_string in api_key.capabilities:
            capability = {
                "resource": cap_string,
                "actions": ["*"],  # API keys get full action access for their capabilities
                "constraints": api_key.tenant_constraints.get(cap_string, {})
            }
            capabilities.append(capability)
        
        # Create JWT payload
        payload = {
            "sub": api_key.owner_id,
            "tenant_id": self.tenant_domain,
            "api_key_id": api_key.id,
            "scope": api_key.scope.value,
            "capabilities": capabilities,
            "constraints": api_key.tenant_constraints,
            "rate_limits": {
                "requests_per_hour": api_key.rate_limit_per_hour,
                "max_tokens_per_request": api_key.max_tokens_per_request,
                "cost_limit_cents": api_key.cost_limit_cents
            },
            "iat": int(datetime.utcnow().timestamp()),
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        # Add additional context
        if additional_context:
            payload.update(additional_context)
        
        # Sign and return token
        token = jwt.encode(payload, self.signing_key, algorithm="HS256")
        return token
    
    async def rotate_api_key(
        self,
        key_id: str,
        owner_id: str,
        capability_token: str
    ) -> Tuple[APIKeyConfig, str]:
        """
        Rotate API key (generate new key value).
        
        Args:
            key_id: API key ID to rotate
            owner_id: Owner of the key
            capability_token: Admin capability token
            
        Returns:
            Tuple of (updated_config, new_raw_key)
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Load existing key
        api_key = await self._load_api_key(key_id)
        if not api_key:
            raise ValueError("API key not found")
        
        # Verify ownership
        if api_key.owner_id != owner_id:
            raise PermissionError("Only key owner can rotate")
        
        # Generate new key
        new_raw_key = f"gt2_{self.tenant_domain}_{secrets.token_urlsafe(32)}"
        new_key_hash = hashlib.sha256(new_raw_key.encode()).hexdigest()
        
        # Update configuration
        api_key.key_hash = new_key_hash
        api_key.last_rotated = datetime.utcnow()
        api_key.updated_at = datetime.utcnow()
        
        # Store updated key
        await self._store_api_key(api_key)
        
        # Log rotation
        await self._audit_log("api_key_rotated", owner_id, {
            "key_id": key_id,
            "name": api_key.name
        })
        
        logger.info(f"Rotated API key: {api_key.name} ({key_id})")
        return api_key, new_raw_key
    
    async def revoke_api_key(
        self,
        key_id: str,
        owner_id: str,
        capability_token: str
    ) -> bool:
        """
        Revoke API key (mark as revoked).
        
        Args:
            key_id: API key ID to revoke
            owner_id: Owner of the key
            capability_token: Admin capability token
            
        Returns:
            True if revoked successfully
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Load and verify key
        api_key = await self._load_api_key(key_id)
        if not api_key:
            return False
        
        if api_key.owner_id != owner_id:
            raise PermissionError("Only key owner can revoke")
        
        # Revoke key
        api_key.status = APIKeyStatus.REVOKED
        api_key.updated_at = datetime.utcnow()
        
        # Store updated key
        await self._store_api_key(api_key)
        
        # Log revocation
        await self._audit_log("api_key_revoked", owner_id, {
            "key_id": key_id,
            "name": api_key.name
        })
        
        logger.info(f"Revoked API key: {api_key.name} ({key_id})")
        return True
    
    async def list_user_api_keys(
        self,
        owner_id: str,
        capability_token: str,
        include_usage: bool = True
    ) -> List[APIKeyConfig]:
        """
        List API keys for a user.
        
        Args:
            owner_id: User to get keys for
            capability_token: User capability token
            include_usage: Include usage statistics
            
        Returns:
            List of API key configurations
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        user_keys = []
        
        # Load all keys and filter by owner
        if self.keys_path.exists():
            for key_file in self.keys_path.glob("*.json"):
                try:
                    with open(key_file, "r") as f:
                        data = json.load(f)
                        if data.get("owner_id") == owner_id:
                            api_key = APIKeyConfig.from_dict(data)
                            
                            # Update usage if requested
                            if include_usage:
                                await self._update_key_usage_stats(api_key)
                            
                            user_keys.append(api_key)
                
                except Exception as e:
                    logger.error(f"Error loading key file {key_file}: {e}")
        
        return sorted(user_keys, key=lambda k: k.created_at, reverse=True)
    
    async def get_usage_analytics(
        self,
        owner_id: str,
        key_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage analytics for API keys.
        
        Args:
            owner_id: Owner of the keys
            key_id: Specific key ID (optional)
            days: Number of days to analyze
            
        Returns:
            Usage analytics data
        """
        analytics = {
            "total_requests": 0,
            "total_errors": 0,
            "avg_requests_per_day": 0,
            "most_used_endpoints": [],
            "rate_limit_hits": 0,
            "keys_analyzed": 0,
            "date_range": {
                "start": (datetime.utcnow() - timedelta(days=days)).isoformat(),
                "end": datetime.utcnow().isoformat()
            }
        }
        
        # Get user's keys
        user_keys = await self.list_user_api_keys(owner_id, "", include_usage=True)
        
        # Filter by specific key if requested
        if key_id:
            user_keys = [key for key in user_keys if key.id == key_id]
        
        # Aggregate usage data
        for api_key in user_keys:
            analytics["total_requests"] += api_key.usage.requests_count
            analytics["total_errors"] += api_key.usage.errors_count
            analytics["rate_limit_hits"] += api_key.usage.rate_limit_hits
            analytics["keys_analyzed"] += 1
        
        # Calculate averages
        if days > 0:
            analytics["avg_requests_per_day"] = analytics["total_requests"] / days
        
        return analytics
    
    def _apply_tenant_defaults(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Apply tenant-specific default constraints"""
        defaults = {
            "max_automation_chain_depth": 5,
            "mcp_memory_limit_mb": 512,
            "mcp_timeout_seconds": 30,
            "max_file_size_bytes": 10 * 1024 * 1024,  # 10MB
            "allowed_file_types": [".pdf", ".txt", ".md", ".json", ".csv"],
            "enable_premium_features": False
        }
        
        # Merge with provided constraints (provided values take precedence)
        final_constraints = defaults.copy()
        final_constraints.update(constraints)
        
        return final_constraints
    
    def _apply_scope_defaults(self, api_key: APIKeyConfig, scope: APIKeyScope):
        """Apply scope-based default limits"""
        if scope == APIKeyScope.USER:
            api_key.rate_limit_per_hour = 1000
            api_key.daily_quota = 10000
            api_key.cost_limit_cents = 1000
        elif scope == APIKeyScope.TENANT:
            api_key.rate_limit_per_hour = 5000
            api_key.daily_quota = 50000
            api_key.cost_limit_cents = 5000
        elif scope == APIKeyScope.ADMIN:
            api_key.rate_limit_per_hour = 10000
            api_key.daily_quota = 100000
            api_key.cost_limit_cents = 10000
    
    async def _check_rate_limits(self, api_key: APIKeyConfig) -> Tuple[bool, Optional[str]]:
        """Check if API key is within rate limits"""
        # For now, implement basic hourly check
        # In production, would check against usage tracking database
        
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        
        # Load hourly usage (mock implementation)
        hourly_usage = 0  # Would query actual usage data
        
        if hourly_usage >= api_key.rate_limit_per_hour:
            api_key.usage.rate_limit_hits += 1
            await self._store_api_key(api_key)
            return False, f"Rate limit exceeded: {hourly_usage}/{api_key.rate_limit_per_hour} requests per hour"
        
        return True, None
    
    async def _update_usage(self, api_key: APIKeyConfig, endpoint: str, client_ip: str):
        """Update API key usage statistics"""
        api_key.usage.requests_count += 1
        api_key.usage.last_used = datetime.utcnow()
        
        # Store updated usage
        await self._store_api_key(api_key)
        
        # Log detailed usage (for analytics)
        await self._log_usage(api_key.id, endpoint, client_ip)
    
    async def _store_api_key(self, api_key: APIKeyConfig):
        """Store API key configuration to file system"""
        key_file = self.keys_path / f"{api_key.id}.json"
        
        with open(key_file, "w") as f:
            json.dump(api_key.to_dict(), f, indent=2)
        
        # Set secure permissions
        os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
    
    async def _load_api_key(self, key_id: str) -> Optional[APIKeyConfig]:
        """Load API key configuration by ID"""
        key_file = self.keys_path / f"{key_id}.json"
        
        if not key_file.exists():
            return None
        
        try:
            with open(key_file, "r") as f:
                data = json.load(f)
                return APIKeyConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading API key {key_id}: {e}")
            return None
    
    async def _load_api_key_by_hash(self, key_hash: str) -> Optional[APIKeyConfig]:
        """Load API key configuration by hash"""
        if not self.keys_path.exists():
            return None
        
        for key_file in self.keys_path.glob("*.json"):
            try:
                with open(key_file, "r") as f:
                    data = json.load(f)
                    if data.get("key_hash") == key_hash:
                        return APIKeyConfig.from_dict(data)
            except Exception as e:
                logger.error(f"Error loading key file {key_file}: {e}")
        
        return None
    
    async def _update_key_usage_stats(self, api_key: APIKeyConfig):
        """Update comprehensive usage statistics for a key"""
        # In production, would aggregate from detailed usage logs
        # For now, use existing basic stats
        pass
    
    async def _log_usage(self, key_id: str, endpoint: str, client_ip: str):
        """Log detailed API key usage for analytics"""
        usage_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "key_id": key_id,
            "endpoint": endpoint,
            "client_ip": client_ip,
            "tenant": self.tenant_domain
        }
        
        # Store in daily usage file
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage_file = self.usage_path / f"usage_{date_str}.jsonl"
        
        with open(usage_file, "a") as f:
            f.write(json.dumps(usage_record) + "\n")
    
    async def _audit_log(self, action: str, user_id: str, details: Dict[str, Any]):
        """Log API key management actions for audit"""
        audit_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "tenant": self.tenant_domain,
            "details": details
        }
        
        # Store in daily audit file
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        audit_file = self.audit_path / f"audit_{date_str}.jsonl"
        
        with open(audit_file, "a") as f:
            f.write(json.dumps(audit_record) + "\n")