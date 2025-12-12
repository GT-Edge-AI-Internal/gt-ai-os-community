"""
API Key Management Service for tenant-specific external API keys
"""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm.attributes import flag_modified

from app.models.tenant import Tenant
from app.models.audit import AuditLog
from app.core.config import settings


class APIKeyService:
    """Service for managing tenant-specific API keys"""
    
    # Supported API key providers - NVIDIA, Groq, and Backblaze
    SUPPORTED_PROVIDERS = {
        'nvidia': {
            'name': 'NVIDIA NIM',
            'description': 'GPU-accelerated inference on DGX Cloud via build.nvidia.com',
            'required_format': 'nvapi-*',
            'test_endpoint': 'https://integrate.api.nvidia.com/v1/models'
        },
        'groq': {
            'name': 'Groq Cloud LLM',
            'description': 'High-performance LLM inference',
            'required_format': 'gsk_*',
            'test_endpoint': 'https://api.groq.com/openai/v1/models'
        },
        'backblaze': {
            'name': 'Backblaze B2',
            'description': 'S3-compatible backup storage',
            'required_format': None,  # Key ID and Application Key
            'test_endpoint': None
        }
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # Use environment variable or generate a key for encryption
        encryption_key = os.getenv('API_KEY_ENCRYPTION_KEY')
        if not encryption_key:
            # In production, this should be stored securely
            encryption_key = Fernet.generate_key().decode()
            os.environ['API_KEY_ENCRYPTION_KEY'] = encryption_key
        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
    
    async def set_api_key(
        self,
        tenant_id: int,
        provider: str,
        api_key: str,
        api_secret: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set or update an API key for a tenant"""
        
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Validate key format if required
        provider_info = self.SUPPORTED_PROVIDERS[provider]
        if provider_info['required_format'] and not api_key.startswith(provider_info['required_format'].replace('*', '')):
            raise ValueError(f"Invalid API key format for {provider}")
        
        # Get tenant
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Encrypt API key
        encrypted_key = self.cipher.encrypt(api_key.encode()).decode()
        encrypted_secret = None
        if api_secret:
            encrypted_secret = self.cipher.encrypt(api_secret.encode()).decode()
        
        # Update tenant's API keys
        api_keys = tenant.api_keys or {}
        api_keys[provider] = {
            'key': encrypted_key,
            'secret': encrypted_secret,
            'enabled': enabled,
            'metadata': metadata or {},
            'updated_at': datetime.utcnow().isoformat(),
            'updated_by': 'admin'  # Should come from auth context
        }
        
        tenant.api_keys = api_keys
        flag_modified(tenant, "api_keys")
        await self.db.commit()

        # Log the action
        audit_log = AuditLog(
            tenant_id=tenant_id,
            action='api_key_updated',
            resource_type='api_key',
            resource_id=provider,
            details={'provider': provider, 'enabled': enabled}
        )
        self.db.add(audit_log)
        await self.db.commit()

        # Invalidate Resource Cluster cache so it picks up the new key
        await self._invalidate_resource_cluster_cache(tenant.domain, provider)

        return {
            'tenant_id': tenant_id,
            'provider': provider,
            'enabled': enabled,
            'updated_at': api_keys[provider]['updated_at']
        }
    
    async def get_api_keys(self, tenant_id: int) -> Dict[str, Any]:
        """Get all API keys for a tenant (without decryption)"""
        
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        api_keys = tenant.api_keys or {}
        
        # Return key status without actual keys
        return {
            provider: {
                'configured': True,
                'enabled': info.get('enabled', False),
                'updated_at': info.get('updated_at'),
                'metadata': info.get('metadata', {})
            }
            for provider, info in api_keys.items()
        }
    
    async def get_decrypted_key(
        self,
        tenant_id: int,
        provider: str,
        require_enabled: bool = True
    ) -> Dict[str, Any]:
        """Get decrypted API key for a specific provider"""
        
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        api_keys = tenant.api_keys or {}
        if provider not in api_keys:
            raise ValueError(f"API key for {provider} not configured for tenant {tenant_id}")
        
        key_info = api_keys[provider]
        if require_enabled and not key_info.get('enabled', False):
            raise ValueError(f"API key for {provider} is disabled for tenant {tenant_id}")
        
        # Decrypt the key
        decrypted_key = self.cipher.decrypt(key_info['key'].encode()).decode()
        decrypted_secret = None
        if key_info.get('secret'):
            decrypted_secret = self.cipher.decrypt(key_info['secret'].encode()).decode()
        
        return {
            'provider': provider,
            'api_key': decrypted_key,
            'api_secret': decrypted_secret,
            'metadata': key_info.get('metadata', {}),
            'enabled': key_info.get('enabled', False)
        }
    
    async def disable_api_key(self, tenant_id: int, provider: str) -> bool:
        """Disable an API key without removing it"""

        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        api_keys = tenant.api_keys or {}
        if provider not in api_keys:
            raise ValueError(f"API key for {provider} not configured")

        api_keys[provider]['enabled'] = False
        api_keys[provider]['updated_at'] = datetime.utcnow().isoformat()

        tenant.api_keys = api_keys
        flag_modified(tenant, "api_keys")
        await self.db.commit()

        # Log the action
        audit_log = AuditLog(
            tenant_id=tenant_id,
            action='api_key_disabled',
            resource_type='api_key',
            resource_id=provider,
            details={'provider': provider}
        )
        self.db.add(audit_log)
        await self.db.commit()

        # Invalidate Resource Cluster cache
        await self._invalidate_resource_cluster_cache(tenant.domain, provider)

        return True
    
    async def remove_api_key(self, tenant_id: int, provider: str) -> bool:
        """Completely remove an API key"""

        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        api_keys = tenant.api_keys or {}
        if provider in api_keys:
            del api_keys[provider]
            tenant.api_keys = api_keys
            flag_modified(tenant, "api_keys")
            await self.db.commit()

            # Log the action
            audit_log = AuditLog(
                tenant_id=tenant_id,
                action='api_key_removed',
                resource_type='api_key',
                resource_id=provider,
                details={'provider': provider}
            )
            self.db.add(audit_log)
            await self.db.commit()

            # Invalidate Resource Cluster cache
            await self._invalidate_resource_cluster_cache(tenant.domain, provider)

            return True

        return False
    
    async def test_api_key(self, tenant_id: int, provider: str) -> Dict[str, Any]:
        """Test if an API key is valid by making a test request with detailed error mapping"""

        import httpx

        # Get decrypted key
        key_info = await self.get_decrypted_key(tenant_id, provider)
        provider_info = self.SUPPORTED_PROVIDERS[provider]

        if not provider_info.get('test_endpoint'):
            return {
                'provider': provider,
                'testable': False,
                'valid': False,
                'message': 'No test endpoint available for this provider',
                'error_type': 'not_testable'
            }

        # Validate key format before making request
        api_key = key_info['api_key']
        if provider == 'nvidia' and not api_key.startswith('nvapi-'):
            return {
                'provider': provider,
                'valid': False,
                'message': 'Invalid key format (should start with nvapi-)',
                'error_type': 'invalid_format'
            }
        if provider == 'groq' and not api_key.startswith('gsk_'):
            return {
                'provider': provider,
                'valid': False,
                'message': 'Invalid key format (should start with gsk_)',
                'error_type': 'invalid_format'
            }

        # Build authorization headers based on provider
        headers = self._get_auth_headers(provider, api_key)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    provider_info['test_endpoint'],
                    headers=headers,
                    timeout=10.0
                )

                # Extract rate limit headers
                rate_limit_remaining = None
                rate_limit_reset = None
                if 'x-ratelimit-remaining' in response.headers:
                    try:
                        rate_limit_remaining = int(response.headers['x-ratelimit-remaining'])
                    except (ValueError, TypeError):
                        pass
                if 'x-ratelimit-reset' in response.headers:
                    rate_limit_reset = response.headers['x-ratelimit-reset']

                # Count available models if response is successful
                models_available = None
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if 'data' in data and isinstance(data['data'], list):
                            models_available = len(data['data'])
                    except Exception:
                        pass

                # Detailed error mapping
                if response.status_code == 200:
                    return {
                        'provider': provider,
                        'valid': True,
                        'message': 'API key is valid',
                        'status_code': response.status_code,
                        'rate_limit_remaining': rate_limit_remaining,
                        'rate_limit_reset': rate_limit_reset,
                        'models_available': models_available
                    }
                elif response.status_code == 401:
                    return {
                        'provider': provider,
                        'valid': False,
                        'message': 'Invalid or expired API key',
                        'status_code': response.status_code,
                        'error_type': 'auth_failed',
                        'rate_limit_remaining': rate_limit_remaining,
                        'rate_limit_reset': rate_limit_reset
                    }
                elif response.status_code == 403:
                    return {
                        'provider': provider,
                        'valid': False,
                        'message': 'Insufficient permissions for this API key',
                        'status_code': response.status_code,
                        'error_type': 'insufficient_permissions',
                        'rate_limit_remaining': rate_limit_remaining,
                        'rate_limit_reset': rate_limit_reset
                    }
                elif response.status_code == 429:
                    return {
                        'provider': provider,
                        'valid': True,  # Key is valid, just rate limited
                        'message': 'Rate limit exceeded - key is valid but currently limited',
                        'status_code': response.status_code,
                        'error_type': 'rate_limited',
                        'rate_limit_remaining': rate_limit_remaining,
                        'rate_limit_reset': rate_limit_reset
                    }
                else:
                    return {
                        'provider': provider,
                        'valid': False,
                        'message': f'Test failed with HTTP {response.status_code}',
                        'status_code': response.status_code,
                        'error_type': 'server_error' if response.status_code >= 500 else 'unknown',
                        'rate_limit_remaining': rate_limit_remaining,
                        'rate_limit_reset': rate_limit_reset
                    }

        except httpx.ConnectError:
            return {
                'provider': provider,
                'valid': False,
                'message': f"Connection failed: Unable to reach {provider_info['test_endpoint']}",
                'error_type': 'connection_error'
            }
        except httpx.TimeoutException:
            return {
                'provider': provider,
                'valid': False,
                'message': 'Connection timed out after 10 seconds',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'provider': provider,
                'valid': False,
                'error': str(e),
                'message': f"Test failed: {str(e)}",
                'error_type': 'unknown'
            }

    def _get_auth_headers(self, provider: str, api_key: str) -> Dict[str, str]:
        """Build authorization headers based on provider"""
        if provider in ('nvidia', 'groq', 'openai', 'cohere', 'huggingface'):
            return {'Authorization': f"Bearer {api_key}"}
        elif provider == 'anthropic':
            return {'x-api-key': api_key}
        else:
            return {'Authorization': f"Bearer {api_key}"}
    
    async def get_api_key_usage(self, tenant_id: int, provider: str) -> Dict[str, Any]:
        """Get usage statistics for an API key"""
        
        # This would query usage records for the specific provider
        # For now, return mock data
        return {
            'provider': provider,
            'tenant_id': tenant_id,
            'usage': {
                'requests_today': 1234,
                'tokens_today': 456789,
                'cost_today_cents': 234,
                'requests_month': 45678,
                'tokens_month': 12345678,
                'cost_month_cents': 8901
            }
        }
    
    async def _invalidate_resource_cluster_cache(
        self,
        tenant_domain: str,
        provider: str
    ) -> None:
        """
        Notify Resource Cluster to invalidate its API key cache.

        This is called after API keys are modified, disabled, or removed
        to ensure the Resource Cluster doesn't use stale cached keys.

        Non-critical: If this fails, the cache will expire naturally after TTL.
        """
        try:
            from app.clients.resource_cluster_client import get_resource_cluster_client

            client = get_resource_cluster_client()
            await client.invalidate_api_key_cache(
                tenant_domain=tenant_domain,
                provider=provider
            )
        except Exception as e:
            # Log but don't fail the main operation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to invalidate Resource Cluster cache (non-critical): {e}")

    @classmethod
    def get_supported_providers(cls) -> List[Dict[str, Any]]:
        """Get list of supported API key providers"""
        return [
            {
                'id': provider_id,
                'name': info['name'],
                'description': info['description'],
                'requires_secret': provider_id == 'backblaze'
            }
            for provider_id, info in cls.SUPPORTED_PROVIDERS.items()
        ]