"""
Integration Proxy Service for GT 2.0

Secure proxy service for external integrations with capability-based access control,
sandbox restrictions, and comprehensive audit logging. All external calls are routed
through this service in the Resource Cluster for security and monitoring.
"""

import asyncio
import json
import httpx
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from contextlib import asynccontextmanager

from app.core.security import verify_capability_token
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class IntegrationType(Enum):
    """Types of external integrations"""
    COMMUNICATION = "communication"      # Slack, Teams, Discord
    DEVELOPMENT = "development"          # GitHub, GitLab, Jira
    PROJECT_MANAGEMENT = "project_management"  # Asana, Monday.com
    DATABASE = "database"                # PostgreSQL, MySQL, MongoDB
    CUSTOM_API = "custom_api"            # Custom REST/GraphQL APIs
    WEBHOOK = "webhook"                  # Outbound webhook calls


class SandboxLevel(Enum):
    """Sandbox restriction levels"""
    NONE = "none"                       # No restrictions (trusted)
    BASIC = "basic"                     # Basic timeout and size limits
    RESTRICTED = "restricted"           # Limited API calls and data access
    STRICT = "strict"                   # Maximum restrictions


@dataclass
class IntegrationConfig:
    """Configuration for external integration"""
    id: str
    name: str
    integration_type: IntegrationType
    base_url: str
    authentication_method: str  # oauth2, api_key, basic_auth, certificate
    sandbox_level: SandboxLevel
    
    # Authentication details (encrypted)
    auth_config: Dict[str, Any]
    
    # Rate limits and constraints
    max_requests_per_hour: int = 1000
    max_response_size_bytes: int = 10 * 1024 * 1024  # 10MB
    timeout_seconds: int = 30
    
    # Allowed operations
    allowed_methods: List[str] = None
    allowed_endpoints: List[str] = None
    blocked_endpoints: List[str] = None
    
    # Network restrictions
    allowed_domains: List[str] = None
    
    # Created metadata
    created_at: datetime = None
    created_by: str = ""
    is_active: bool = True
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.allowed_methods is None:
            self.allowed_methods = ["GET", "POST"]
        if self.allowed_endpoints is None:
            self.allowed_endpoints = []
        if self.blocked_endpoints is None:
            self.blocked_endpoints = []
        if self.allowed_domains is None:
            self.allowed_domains = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data["integration_type"] = self.integration_type.value
        data["sandbox_level"] = self.sandbox_level.value
        data["created_at"] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntegrationConfig":
        """Create from dictionary"""
        data["integration_type"] = IntegrationType(data["integration_type"])
        data["sandbox_level"] = SandboxLevel(data["sandbox_level"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class ProxyRequest:
    """Request to proxy to external service"""
    integration_id: str
    method: str
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    data: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, str]] = None
    timeout_override: Optional[int] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.data is None:
            self.data = {}
        if self.params is None:
            self.params = {}


@dataclass
class ProxyResponse:
    """Response from proxied external service"""
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]]
    headers: Dict[str, str]
    execution_time_ms: int
    sandbox_applied: bool
    restrictions_applied: List[str]
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.restrictions_applied is None:
            self.restrictions_applied = []


class SandboxManager:
    """Manages sandbox restrictions for external integrations"""
    
    def __init__(self):
        self.active_requests: Dict[str, datetime] = {}
        self.rate_limiters: Dict[str, List[datetime]] = {}
    
    def apply_sandbox_restrictions(
        self, 
        config: IntegrationConfig, 
        request: ProxyRequest,
        capability_token: Dict[str, Any]
    ) -> Tuple[ProxyRequest, List[str]]:
        """Apply sandbox restrictions to request"""
        restrictions_applied = []
        
        if config.sandbox_level == SandboxLevel.NONE:
            return request, restrictions_applied
        
        # Apply timeout restrictions
        if config.sandbox_level in [SandboxLevel.BASIC, SandboxLevel.RESTRICTED, SandboxLevel.STRICT]:
            max_timeout = self._get_max_timeout(config.sandbox_level)
            if request.timeout_override is None or request.timeout_override > max_timeout:
                request.timeout_override = max_timeout
                restrictions_applied.append(f"timeout_limited_to_{max_timeout}s")
        
        # Apply endpoint restrictions
        if config.sandbox_level in [SandboxLevel.RESTRICTED, SandboxLevel.STRICT]:
            # Check blocked endpoints first
            if request.endpoint in config.blocked_endpoints:
                raise PermissionError(f"Endpoint {request.endpoint} is blocked")
            
            # Then check allowed endpoints if specified
            if config.allowed_endpoints and request.endpoint not in config.allowed_endpoints:
                raise PermissionError(f"Endpoint {request.endpoint} not allowed")
            
            restrictions_applied.append("endpoint_validation")
        
        # Apply method restrictions
        if config.sandbox_level == SandboxLevel.STRICT:
            allowed_methods = config.allowed_methods or ["GET", "POST"]
            if request.method not in allowed_methods:
                raise PermissionError(f"HTTP method {request.method} not allowed in strict mode")
            restrictions_applied.append("method_restricted")
        
        # Apply data size restrictions
        if request.data:
            data_size = len(json.dumps(request.data).encode())
            max_size = self._get_max_data_size(config.sandbox_level)
            if data_size > max_size:
                raise ValueError(f"Request data size {data_size} exceeds limit {max_size}")
            restrictions_applied.append("data_size_validated")
        
        # Apply capability-based restrictions
        constraints = capability_token.get("constraints", {})
        if "integration_timeout_seconds" in constraints:
            max_cap_timeout = constraints["integration_timeout_seconds"]
            if request.timeout_override > max_cap_timeout:
                request.timeout_override = max_cap_timeout
                restrictions_applied.append(f"capability_timeout_{max_cap_timeout}s")
        
        return request, restrictions_applied
    
    def _get_max_timeout(self, sandbox_level: SandboxLevel) -> int:
        """Get maximum timeout for sandbox level"""
        timeouts = {
            SandboxLevel.BASIC: 60,
            SandboxLevel.RESTRICTED: 30,
            SandboxLevel.STRICT: 15
        }
        return timeouts.get(sandbox_level, 30)
    
    def _get_max_data_size(self, sandbox_level: SandboxLevel) -> int:
        """Get maximum data size for sandbox level"""
        sizes = {
            SandboxLevel.BASIC: 1024 * 1024,      # 1MB
            SandboxLevel.RESTRICTED: 512 * 1024,  # 512KB
            SandboxLevel.STRICT: 256 * 1024       # 256KB
        }
        return sizes.get(sandbox_level, 512 * 1024)
    
    async def check_rate_limits(self, integration_id: str, config: IntegrationConfig) -> bool:
        """Check if request is within rate limits"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Initialize or clean rate limiter
        if integration_id not in self.rate_limiters:
            self.rate_limiters[integration_id] = []
        
        # Remove old requests
        self.rate_limiters[integration_id] = [
            req_time for req_time in self.rate_limiters[integration_id]
            if req_time > hour_ago
        ]
        
        # Check rate limit
        if len(self.rate_limiters[integration_id]) >= config.max_requests_per_hour:
            return False
        
        # Record this request
        self.rate_limiters[integration_id].append(now)
        return True


class IntegrationProxyService:
    """
    Integration Proxy Service for secure external API access.
    
    Features:
    - Capability-based access control
    - Sandbox restrictions based on trust level
    - Rate limiting and usage tracking
    - Comprehensive audit logging
    - Response sanitization and size limits
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path("/data/resource-cluster/integrations")
        self.configs_path = self.base_path / "configs"
        self.usage_path = self.base_path / "usage"
        self.audit_path = self.base_path / "audit"
        
        self.sandbox_manager = SandboxManager()
        self.http_client = None
        
        # Ensure directories exist with proper permissions
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure storage directories exist with proper permissions"""
        for path in [self.configs_path, self.usage_path, self.audit_path]:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
    
    @asynccontextmanager
    async def get_http_client(self):
        """Get HTTP client with proper configuration"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
        try:
            yield self.http_client
        finally:
            # Client stays open for reuse
            pass
    
    async def execute_integration(
        self,
        request: ProxyRequest,
        capability_token: str
    ) -> ProxyResponse:
        """Execute integration request with security and sandbox restrictions"""
        start_time = datetime.utcnow()
        
        try:
            # Verify capability token
            token_obj = verify_capability_token(capability_token)
            if not token_obj:
                raise PermissionError("Invalid capability token")
            
            # Convert token object to dict for compatibility
            token_data = {
                "tenant_id": token_obj.tenant_id,
                "sub": token_obj.sub,
                "capabilities": [cap.dict() if hasattr(cap, 'dict') else cap for cap in token_obj.capabilities],
                "constraints": {}
            }
            
            # Load integration configuration
            config = await self._load_integration_config(request.integration_id)
            if not config or not config.is_active:
                raise ValueError(f"Integration {request.integration_id} not found or inactive")
            
            # Validate capability for this integration
            required_capability = f"integration:{request.integration_id}:{request.method.lower()}"
            if not self._has_capability(token_data, required_capability):
                raise PermissionError(f"Missing capability: {required_capability}")
            
            # Check rate limits
            if not await self.sandbox_manager.check_rate_limits(request.integration_id, config):
                raise PermissionError("Rate limit exceeded")
            
            # Apply sandbox restrictions
            sandboxed_request, restrictions = self.sandbox_manager.apply_sandbox_restrictions(
                config, request, token_data
            )
            
            # Execute the request
            response = await self._execute_proxied_request(config, sandboxed_request)
            response.sandbox_applied = len(restrictions) > 0
            response.restrictions_applied = restrictions
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            response.execution_time_ms = int(execution_time)
            
            # Log usage
            await self._log_usage(
                integration_id=request.integration_id,
                tenant_id=token_data.get("tenant_id"),
                user_id=token_data.get("sub"),
                method=request.method,
                endpoint=request.endpoint,
                success=response.success,
                execution_time_ms=response.execution_time_ms
            )
            
            # Audit log
            await self._audit_log(
                action="integration_executed",
                integration_id=request.integration_id,
                user_id=token_data.get("sub"),
                details={
                    "method": request.method,
                    "endpoint": request.endpoint,
                    "success": response.success,
                    "restrictions_applied": restrictions
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Integration execution failed: {e}")
            
            # Log error
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self._log_usage(
                integration_id=request.integration_id,
                tenant_id=token_data.get("tenant_id") if 'token_data' in locals() else "unknown",
                user_id=token_data.get("sub") if 'token_data' in locals() else "unknown",
                method=request.method,
                endpoint=request.endpoint,
                success=False,
                execution_time_ms=int(execution_time),
                error=str(e)
            )
            
            return ProxyResponse(
                success=False,
                status_code=500,
                data=None,
                headers={},
                execution_time_ms=int(execution_time),
                sandbox_applied=False,
                restrictions_applied=[],
                error_message=str(e)
            )
    
    async def _execute_proxied_request(
        self, 
        config: IntegrationConfig, 
        request: ProxyRequest
    ) -> ProxyResponse:
        """Execute the actual HTTP request to external service"""
        
        # Build URL
        if request.endpoint.startswith('http'):
            url = request.endpoint
        else:
            url = f"{config.base_url.rstrip('/')}/{request.endpoint.lstrip('/')}"
        
        # Apply authentication
        headers = request.headers.copy()
        await self._apply_authentication(config, headers)
        
        # Set timeout
        timeout = request.timeout_override or config.timeout_seconds
        
        try:
            async with self.get_http_client() as client:
                # Execute request
                if request.method.upper() == "GET":
                    response = await client.get(
                        url, 
                        headers=headers, 
                        params=request.params,
                        timeout=timeout
                    )
                elif request.method.upper() == "POST":
                    response = await client.post(
                        url, 
                        headers=headers, 
                        json=request.data,
                        params=request.params,
                        timeout=timeout
                    )
                elif request.method.upper() == "PUT":
                    response = await client.put(
                        url, 
                        headers=headers, 
                        json=request.data,
                        params=request.params,
                        timeout=timeout
                    )
                elif request.method.upper() == "DELETE":
                    response = await client.delete(
                        url, 
                        headers=headers,
                        params=request.params,
                        timeout=timeout
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {request.method}")
                
                # Check response size
                if len(response.content) > config.max_response_size_bytes:
                    raise ValueError(f"Response size exceeds limit: {len(response.content)}")
                
                # Parse response
                try:
                    data = response.json() if response.content else {}
                except json.JSONDecodeError:
                    data = {"raw_content": response.text}
                
                return ProxyResponse(
                    success=200 <= response.status_code < 300,
                    status_code=response.status_code,
                    data=data,
                    headers=dict(response.headers),
                    execution_time_ms=0,  # Will be set by caller
                    sandbox_applied=False  # Will be set by caller
                )
                
        except httpx.TimeoutException:
            return ProxyResponse(
                success=False,
                status_code=408,
                data=None,
                headers={},
                execution_time_ms=timeout * 1000,
                sandbox_applied=False,
                restrictions_applied=[],
                error_message="Request timeout"
            )
        except Exception as e:
            return ProxyResponse(
                success=False,
                status_code=500,
                data=None,
                headers={},
                execution_time_ms=0,
                sandbox_applied=False,
                restrictions_applied=[],
                error_message=str(e)
            )
    
    async def _apply_authentication(self, config: IntegrationConfig, headers: Dict[str, str]):
        """Apply authentication to request headers"""
        auth_config = config.auth_config
        
        if config.authentication_method == "api_key":
            api_key = auth_config.get("api_key")
            key_header = auth_config.get("key_header", "Authorization")
            key_prefix = auth_config.get("key_prefix", "Bearer")
            
            if api_key:
                headers[key_header] = f"{key_prefix} {api_key}"
        
        elif config.authentication_method == "basic_auth":
            username = auth_config.get("username")
            password = auth_config.get("password")
            
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"
        
        elif config.authentication_method == "oauth2":
            access_token = auth_config.get("access_token")
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
        
        # Add custom headers
        custom_headers = auth_config.get("custom_headers", {})
        headers.update(custom_headers)
    
    def _has_capability(self, token_data: Dict[str, Any], required_capability: str) -> bool:
        """Check if token has required capability"""
        capabilities = token_data.get("capabilities", [])
        
        for capability in capabilities:
            if isinstance(capability, dict):
                resource = capability.get("resource", "")
                # Handle wildcard matching
                if resource == required_capability:
                    return True
                if resource.endswith("*"):
                    prefix = resource[:-1]  # Remove the *
                    if required_capability.startswith(prefix):
                        return True
            elif isinstance(capability, str):
                # Handle wildcard matching for string capabilities
                if capability == required_capability:
                    return True
                if capability.endswith("*"):
                    prefix = capability[:-1]  # Remove the *
                    if required_capability.startswith(prefix):
                        return True
        
        return False
    
    async def _load_integration_config(self, integration_id: str) -> Optional[IntegrationConfig]:
        """Load integration configuration from storage"""
        config_file = self.configs_path / f"{integration_id}.json"
        
        if not config_file.exists():
            return None
        
        try:
            with open(config_file, "r") as f:
                data = json.load(f)
            return IntegrationConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load integration config {integration_id}: {e}")
            return None
    
    async def store_integration_config(self, config: IntegrationConfig) -> bool:
        """Store integration configuration"""
        config_file = self.configs_path / f"{config.id}.json"
        
        try:
            with open(config_file, "w") as f:
                json.dump(config.to_dict(), f, indent=2)
            
            # Set secure permissions
            config_file.chmod(0o600)
            return True
            
        except Exception as e:
            logger.error(f"Failed to store integration config {config.id}: {e}")
            return False
    
    async def _log_usage(
        self,
        integration_id: str,
        tenant_id: str,
        user_id: str,
        method: str,
        endpoint: str,
        success: bool,
        execution_time_ms: int,
        error: Optional[str] = None
    ):
        """Log integration usage for analytics"""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage_file = self.usage_path / f"usage_{date_str}.jsonl"
        
        usage_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "method": method,
            "endpoint": endpoint,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "error": error
        }
        
        try:
            with open(usage_file, "a") as f:
                f.write(json.dumps(usage_record) + "\n")
            
            # Set secure permissions on file
            usage_file.chmod(0o600)
                
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
    
    async def _audit_log(
        self,
        action: str,
        integration_id: str,
        user_id: str,
        details: Dict[str, Any]
    ):
        """Log audit trail for integration actions"""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        audit_file = self.audit_path / f"audit_{date_str}.jsonl"
        
        audit_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "integration_id": integration_id,
            "user_id": user_id,
            "details": details
        }
        
        try:
            with open(audit_file, "a") as f:
                f.write(json.dumps(audit_record) + "\n")
            
            # Set secure permissions on file
            audit_file.chmod(0o600)
                
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
    
    async def list_integrations(self, capability_token: str) -> List[IntegrationConfig]:
        """List available integrations based on capabilities"""
        token_obj = verify_capability_token(capability_token)
        if not token_obj:
            raise PermissionError("Invalid capability token")
        
        # Convert token object to dict for compatibility
        token_data = {
            "tenant_id": token_obj.tenant_id,
            "sub": token_obj.sub,
            "capabilities": [cap.dict() if hasattr(cap, 'dict') else cap for cap in token_obj.capabilities],
            "constraints": {}
        }
        
        integrations = []
        
        for config_file in self.configs_path.glob("*.json"):
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                config = IntegrationConfig.from_dict(data)
                
                # Check if user has capability for this integration
                required_capability = f"integration:{config.id}:*"
                if self._has_capability(token_data, required_capability):
                    integrations.append(config)
                    
            except Exception as e:
                logger.warning(f"Failed to load integration config {config_file}: {e}")
        
        return integrations
    
    async def get_integration_usage_analytics(
        self,
        integration_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage analytics for integration"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days-1)  # Include today in the range
        
        total_requests = 0
        successful_requests = 0
        total_execution_time = 0
        error_count = 0
        
        # Process usage logs
        for day_offset in range(days):
            date = start_date + timedelta(days=day_offset)
            date_str = date.strftime("%Y-%m-%d")
            usage_file = self.usage_path / f"usage_{date_str}.jsonl"
            
            if usage_file.exists():
                try:
                    with open(usage_file, "r") as f:
                        for line in f:
                            record = json.loads(line.strip())
                            if record["integration_id"] == integration_id:
                                total_requests += 1
                                if record["success"]:
                                    successful_requests += 1
                                else:
                                    error_count += 1
                                total_execution_time += record["execution_time_ms"]
                except Exception as e:
                    logger.warning(f"Failed to process usage file {usage_file}: {e}")
        
        return {
            "integration_id": integration_id,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_count": error_count,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "avg_execution_time_ms": total_execution_time / total_requests if total_requests > 0 else 0,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    
    async def close(self):
        """Close HTTP client and cleanup resources"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None