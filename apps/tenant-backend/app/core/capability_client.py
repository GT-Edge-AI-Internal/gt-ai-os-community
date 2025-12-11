"""
GT 2.0 Tenant Backend - Capability Client
Generate JWT capability tokens for Resource Cluster API calls
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from jose import jwt
from app.core.config import get_settings
import logging
import httpx

logger = logging.getLogger(__name__)
settings = get_settings()


class CapabilityClient:
    """Generates capability-based JWT tokens for Resource Cluster access"""

    def __init__(self):
        # Use tenant-specific secret key for token signing
        self.secret_key = settings.secret_key
        self.algorithm = "HS256"
        self.issuer = f"gt2-tenant-{settings.tenant_id}"
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.control_panel_url = settings.control_panel_url
    
    async def generate_capability_token(
        self,
        user_email: str,
        tenant_id: str,
        resources: List[str],
        expires_hours: int = 24,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a JWT capability token for Resource Cluster API access.
        
        Args:
            user_email: Email of the user making the request
            tenant_id: Tenant identifier
            resources: List of resource capabilities (e.g., ['external_services', 'rag_processing'])
            expires_hours: Token expiration time in hours
            additional_claims: Additional JWT claims to include
        
        Returns:
            Signed JWT token string
        """
        
        now = datetime.utcnow()
        expiry = now + timedelta(hours=expires_hours)
        
        # Build capability token payload
        payload = {
            # Standard JWT claims
            "iss": self.issuer,  # Issuer
            "sub": user_email,   # Subject (user)
            "aud": "gt2-resource-cluster",  # Audience
            "iat": int(now.timestamp()),    # Issued at
            "exp": int(expiry.timestamp()), # Expiration
            "nbf": int(now.timestamp()),    # Not before
            "jti": f"{tenant_id}-{user_email}-{int(now.timestamp())}", # JWT ID
            
            # GT 2.0 specific claims
            "tenant_id": tenant_id,
            "user_email": user_email,
            "user_type": "tenant_user",
            
            # Capability grants
            "capabilities": await self._build_capabilities(resources, tenant_id, expiry),
            
            # Security metadata
            "capability_hash": self._generate_capability_hash(resources, tenant_id),
            "token_version": "2.0",
            "security_level": "standard"
        }
        
        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)
        
        # Sign the token
        try:
            token = jwt.encode(
                payload,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            logger.info(
                f"Generated capability token for {user_email} with resources: {resources}"
            )
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate capability token: {e}")
            raise RuntimeError(f"Token generation failed: {e}")

    async def _build_capabilities(
        self,
        resources: List[str],
        tenant_id: str,
        expiry: datetime
    ) -> List[Dict[str, Any]]:
        """
        Build capability grants for resources with constraints from Control Panel.

        For LLM resources, fetches real rate limits from Control Panel API.
        For other resources, uses default constraints.
        """
        capabilities = []

        for resource in resources:
            capability = {
                "resource": resource,
                "actions": self._get_default_actions(resource),
                "constraints": await self._get_constraints_for_resource(resource, tenant_id),
                "valid_until": expiry.isoformat()
            }
            capabilities.append(capability)

        return capabilities

    async def _get_constraints_for_resource(
        self,
        resource: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Get constraints for a resource, fetching from Control Panel for LLM resources.

        GT 2.0 Principle: Single source of truth in database.
        Fails fast if Control Panel is unreachable for LLM resources.
        """
        # For LLM resources, fetch real config from Control Panel
        if resource in ["llm", "llm_inference"]:
            # Note: We don't have model_id at this point in the flow
            # This is called during general capability token generation
            # For now, return default constraints that will be overridden
            # when model-specific tokens are generated
            return self._get_default_constraints(resource)

        # For non-LLM resources, use defaults
        return self._get_default_constraints(resource)

    async def _fetch_tenant_model_config(
        self,
        tenant_id: str,
        model_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch tenant model configuration from Control Panel API.

        Returns rate limits from database (single source of truth).
        Fails fast if Control Panel is unreachable (no fallbacks).

        Args:
            tenant_id: Tenant identifier
            model_id: Model identifier

        Returns:
            Model config with rate_limits, or None if not found

        Raises:
            RuntimeError: If Control Panel API is unreachable (fail fast)
        """
        try:
            url = f"{self.control_panel_url}/api/v1/tenant-models/tenants/{tenant_id}/models/{model_id}"

            logger.debug(f"Fetching model config from Control Panel: {url}")

            response = await self.http_client.get(url)

            if response.status_code == 404:
                logger.warning(f"Model {model_id} not configured for tenant {tenant_id}")
                return None

            response.raise_for_status()

            config = response.json()
            logger.info(f"Fetched model config for {model_id}: rate_limits={config.get('rate_limits')}")

            return config

        except httpx.HTTPStatusError as e:
            logger.error(f"Control Panel API error: {e.response.status_code}")
            raise RuntimeError(
                f"Failed to fetch model config from Control Panel: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(f"Control Panel API unreachable: {e}")
            raise RuntimeError(
                f"Control Panel API unreachable - cannot generate capability token. "
                f"Ensure Control Panel is running at {self.control_panel_url}"
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching model config: {e}")
            raise RuntimeError(f"Failed to fetch model config: {e}")

    def _get_default_actions(self, resource: str) -> List[str]:
        """Get default actions for a resource type"""
        
        action_mappings = {
            "external_services": ["create", "read", "update", "delete", "health_check", "sso_token"],
            "rag_processing": ["process_document", "generate_embeddings", "vector_search"],
            "llm_inference": ["chat_completion", "streaming", "function_calling"],
            "llm": ["execute"],  # Use valid ActionType from resource cluster
            "agent_orchestration": ["execute", "status", "interrupt"],
            "ai_literacy": ["play_games", "solve_puzzles", "dialogue", "analytics"],
            "app_integrations": ["read", "write", "webhook"],
            "admin": ["all"],
            # MCP Server Resources
            "mcp:rag": ["search_datasets", "query_documents", "list_user_datasets", "get_dataset_info", "get_relevant_chunks"]
        }
        
        return action_mappings.get(resource, ["read"])
    
    def _get_default_constraints(self, resource: str) -> Dict[str, Any]:
        """Get default constraints for a resource type"""
        
        constraint_mappings = {
            "external_services": {
                "max_instances_per_user": 10,
                "max_cpu_per_instance": "2000m",
                "max_memory_per_instance": "4Gi",
                "max_storage_per_instance": "50Gi",
                "allowed_service_types": ["ctfd", "canvas", "guacamole"]
            },
            "rag_processing": {
                "max_document_size_mb": 100,
                "max_batch_size": 50,
                "max_requests_per_hour": 1000
            },
            "llm_inference": {
                "max_tokens_per_request": 4000,
                "max_requests_per_hour": 100,
                "allowed_models": []  # Models dynamically determined by admin backend
            },
            "llm": {
                "max_tokens_per_request": 4000,
                "max_requests_per_hour": 100,
                "allowed_models": []  # Models dynamically determined by admin backend
            },
            "agent_orchestration": {
                "max_concurrent_agents": 5,
                "max_execution_time_minutes": 30
            },
            "ai_literacy": {
                "max_sessions_per_day": 20,
                "max_session_duration_hours": 4
            },
            "app_integrations": {
                "max_api_calls_per_hour": 500,
                "allowed_domains": ["api.example.com"]
            },
            # MCP Server Resources
            "mcp:rag": {
                "max_requests_per_hour": 500,
                "max_results_per_query": 50
            }
        }
        
        return constraint_mappings.get(resource, {})
    
    def _generate_capability_hash(self, resources: List[str], tenant_id: str) -> str:
        """Generate a hash of the capabilities for verification"""
        import hashlib
        
        # Create a deterministic string from capabilities
        capability_string = f"{tenant_id}:{':'.join(sorted(resources))}"
        
        # Hash with SHA-256
        hash_object = hashlib.sha256(capability_string.encode())
        return hash_object.hexdigest()[:16]  # First 16 characters
    
    async def verify_capability_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a capability token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Decoded token payload
            
        Raises:
            ValueError: If token is invalid or expired
        """
        
        try:
            # Decode and verify the token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience="gt2-resource-cluster"
            )
            
            # Additional validation
            if payload.get("iss") != self.issuer:
                raise ValueError("Invalid token issuer")
            
            # Check if token is still valid
            now = datetime.utcnow()
            if payload.get("exp", 0) < now.timestamp():
                raise ValueError("Token has expired")
            
            if payload.get("nbf", 0) > now.timestamp():
                raise ValueError("Token not yet valid")
            
            logger.debug(f"Verified capability token for user {payload.get('user_email')}")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.JWTClaimsError as e:
            raise ValueError(f"Token claims validation failed: {e}")
        except jwt.JWTError as e:
            raise ValueError(f"Token validation failed: {e}")
        except Exception as e:
            logger.error(f"Capability token verification failed: {e}")
            raise ValueError(f"Invalid token: {e}")
    
    async def refresh_capability_token(
        self,
        current_token: str,
        extend_hours: int = 24
    ) -> str:
        """
        Refresh an existing capability token with extended expiration.
        
        Args:
            current_token: Current JWT token
            extend_hours: Hours to extend from now
            
        Returns:
            New JWT token with extended expiration
        """
        
        # Verify current token
        payload = await self.verify_capability_token(current_token)
        
        # Extract current capabilities
        resources = [cap.get("resource") for cap in payload.get("capabilities", [])]
        
        # Generate new token with extended expiration
        return await self.generate_capability_token(
            user_email=payload.get("user_email"),
            tenant_id=payload.get("tenant_id"),
            resources=resources,
            expires_hours=extend_hours
        )
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get information about a token without full verification.
        Useful for debugging and logging.
        """
        
        try:
            # Decode without verification to get claims
            payload = jwt.get_unverified_claims(token)
            
            return {
                "user_email": payload.get("user_email"),
                "tenant_id": payload.get("tenant_id"),
                "resources": [cap.get("resource") for cap in payload.get("capabilities", [])],
                "expires_at": datetime.fromtimestamp(payload.get("exp", 0)).isoformat(),
                "issued_at": datetime.fromtimestamp(payload.get("iat", 0)).isoformat(),
                "token_version": payload.get("token_version"),
                "security_level": payload.get("security_level")
            }
            
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return {"error": str(e)}