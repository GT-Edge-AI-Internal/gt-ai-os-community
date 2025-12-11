"""
Unit tests for API Key Management Service
"""
import pytest
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from cryptography.fernet import Fernet

# Import test fixtures
from tests.test_fixtures import (
    create_mock_tenant,
    create_mock_db_session,
    create_mock_query_result
)

# Set up test environment
os.environ["API_KEY_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app.services.api_key_service import APIKeyService


class TestAPIKeyService:
    """Test API Key Service functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return create_mock_db_session()
    
    @pytest.fixture
    def api_key_service(self, mock_db_session):
        """API Key Service instance"""
        return APIKeyService(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_set_api_key_groq_success(self, api_key_service, mock_db_session):
        """Test setting a Groq API key successfully"""
        # Create mock tenant
        tenant = create_mock_tenant()
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        # Set API key
        result = await api_key_service.set_api_key(
            tenant_id=1,
            provider="groq",
            api_key="gsk_test123456789",
            enabled=True
        )
        
        # Assertions
        assert result["tenant_id"] == 1
        assert result["provider"] == "groq"
        assert result["enabled"] is True
        assert "gsk_test123456789" not in str(tenant.api_keys.get("groq", {}).get("key", ""))
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_set_api_key_invalid_format(self, api_key_service, mock_db_session):
        """Test setting API key with invalid format"""
        tenant = create_mock_tenant()
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Invalid API key format for groq"):
            await api_key_service.set_api_key(
                tenant_id=1,
                provider="groq",
                api_key="invalid_key",
                enabled=True
            )
    
    @pytest.mark.asyncio
    async def test_set_api_key_unsupported_provider(self, api_key_service):
        """Test setting API key for unsupported provider"""
        with pytest.raises(ValueError, match="Unsupported provider: unsupported"):
            await api_key_service.set_api_key(
                tenant_id=1,
                provider="unsupported",
                api_key="test_key"
            )
    
    @pytest.mark.asyncio
    async def test_get_api_keys(self, api_key_service, mock_db_session):
        """Test getting all API keys for a tenant"""
        # Create tenant with encrypted keys
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456").decode()
        
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True,
                    "updated_at": "2024-01-01T00:00:00"
                },
                "openai": {
                    "key": cipher.encrypt(b"sk-test789").decode(),
                    "enabled": False,
                    "updated_at": "2024-01-02T00:00:00"
                }
            }
        )
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.get_api_keys(1)
        
        assert "groq" in result
        assert result["groq"]["configured"] is True
        assert result["groq"]["enabled"] is True
        assert "openai" in result
        assert result["openai"]["enabled"] is False
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key(self, api_key_service, mock_db_session):
        """Test getting decrypted API key"""
        # Create tenant with encrypted key
        cipher = api_key_service.cipher
        original_key = "gsk_test123456789"
        encrypted_key = cipher.encrypt(original_key.encode()).decode()
        
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True,
                    "metadata": {"region": "us-west"}
                }
            }
        )
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.get_decrypted_key(1, "groq")
        
        assert result["provider"] == "groq"
        assert result["api_key"] == original_key
        assert result["enabled"] is True
        assert result["metadata"]["region"] == "us-west"
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_disabled(self, api_key_service, mock_db_session):
        """Test getting decrypted key that is disabled"""
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456").decode()
        
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": False
                }
            }
        )
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="API key for groq is disabled"):
            await api_key_service.get_decrypted_key(1, "groq", require_enabled=True)
    
    @pytest.mark.asyncio
    async def test_disable_api_key(self, api_key_service, mock_db_session):
        """Test disabling an API key"""
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": "encrypted_key",
                    "enabled": True
                }
            }
        )
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.disable_api_key(1, "groq")
        
        assert result is True
        assert tenant.api_keys["groq"]["enabled"] is False
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_remove_api_key(self, api_key_service, mock_db_session):
        """Test removing an API key"""
        api_keys = {
            "groq": {"key": "encrypted_key", "enabled": True},
            "openai": {"key": "another_key", "enabled": True}
        }
        tenant = create_mock_tenant(api_keys=api_keys)
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.remove_api_key(1, "groq")
        
        assert result is True
        assert "groq" not in tenant.api_keys
        assert "openai" in tenant.api_keys
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_test_api_key_groq(self, api_key_service, mock_db_session):
        """Test API key validation for Groq"""
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456789").decode()
        
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True
                }
            }
        )
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": ["llama-3.1-70b"]}
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            result = await api_key_service.test_api_key(1, "groq")
            
            assert result["provider"] == "groq"
            assert result["valid"] is True
            assert result["status_code"] == 200
    
    @pytest.mark.asyncio
    async def test_test_api_key_invalid(self, api_key_service, mock_db_session):
        """Test API key validation with invalid key"""
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_invalid").decode()
        
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True
                }
            }
        )
        
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            result = await api_key_service.test_api_key(1, "groq")
            
            assert result["provider"] == "groq"
            assert result["valid"] is False
            assert result["status_code"] == 401
    
    def test_get_supported_providers(self):
        """Test getting list of supported providers"""
        providers = APIKeyService.get_supported_providers()
        
        assert len(providers) > 0
        
        # Check Groq is included
        groq_provider = next((p for p in providers if p["id"] == "groq"), None)
        assert groq_provider is not None
        assert groq_provider["name"] == "Groq Cloud LLM"
        
        # Check Backblaze requires secret
        backblaze = next((p for p in providers if p["id"] == "backblaze"), None)
        assert backblaze is not None
        assert backblaze["requires_secret"] is True
    
    @pytest.mark.asyncio
    async def test_set_api_key_with_metadata(self, api_key_service, mock_db_session):
        """Test setting API key with metadata"""
        tenant = create_mock_tenant()
        mock_result = create_mock_query_result(tenant, scalar=True)
        mock_db_session.execute.return_value = mock_result
        
        metadata = {"region": "us-west", "model": "llama-3.1-70b"}
        
        result = await api_key_service.set_api_key(
            tenant_id=1,
            provider="groq",
            api_key="gsk_test123456789",
            enabled=True,
            metadata=metadata
        )
        
        assert result["tenant_id"] == 1
        assert result["provider"] == "groq"
        assert tenant.api_keys["groq"]["metadata"] == metadata
    
    @pytest.mark.asyncio
    async def test_get_api_key_usage(self, api_key_service):
        """Test getting API key usage statistics"""
        result = await api_key_service.get_api_key_usage(1, "groq")
        
        assert result["provider"] == "groq"
        assert result["tenant_id"] == 1
        assert "usage" in result
        assert "requests_today" in result["usage"]
        assert "cost_today_cents" in result["usage"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])