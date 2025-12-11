"""
Tests for API Key Management Service
"""
import pytest
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet

from app.services.api_key_service import APIKeyService
from app.models.tenant import Tenant
from app.models.audit import AuditLog


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def api_key_service(mock_db_session):
    """API Key Service instance"""
    return APIKeyService(mock_db_session)


@pytest.fixture
def sample_tenant():
    """Sample tenant for testing"""
    tenant = Tenant(
        id=1,
        name="Test Company",
        domain="testcompany",
        api_keys={}
    )
    return tenant


class TestAPIKeyService:
    """Test API Key Service functionality"""
    
    async def test_set_api_key_groq(self, api_key_service, mock_db_session, sample_tenant):
        """Test setting a Groq API key"""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_tenant
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.set_api_key(
            tenant_id=1,
            provider="groq",
            api_key="gsk_test123456",
            enabled=True
        )
        
        assert result["tenant_id"] == 1
        assert result["provider"] == "groq"
        assert result["enabled"] is True
        
        # Verify API key was encrypted
        assert "gsk_test123456" not in str(sample_tenant.api_keys["groq"]["key"])
        assert sample_tenant.api_keys["groq"]["enabled"] is True
        
        # Verify audit log was created
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()
    
    async def test_set_api_key_invalid_format(self, api_key_service, mock_db_session, sample_tenant):
        """Test setting API key with invalid format"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_tenant
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Invalid API key format for groq"):
            await api_key_service.set_api_key(
                tenant_id=1,
                provider="groq",
                api_key="invalid_key_format",
                enabled=True
            )
    
    async def test_set_api_key_unsupported_provider(self, api_key_service):
        """Test setting API key for unsupported provider"""
        with pytest.raises(ValueError, match="Unsupported provider: unsupported"):
            await api_key_service.set_api_key(
                tenant_id=1,
                provider="unsupported",
                api_key="test_key"
            )
    
    async def test_set_api_key_tenant_not_found(self, api_key_service, mock_db_session):
        """Test setting API key for non-existent tenant"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Tenant 999 not found"):
            await api_key_service.set_api_key(
                tenant_id=999,
                provider="groq",
                api_key="gsk_test123456"
            )
    
    async def test_get_api_keys(self, api_key_service, mock_db_session):
        """Test getting all API keys for a tenant"""
        # Create tenant with encrypted keys
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456").decode()
        
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
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
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.get_api_keys(1)
        
        assert "groq" in result
        assert result["groq"]["configured"] is True
        assert result["groq"]["enabled"] is True
        assert "openai" in result
        assert result["openai"]["enabled"] is False
    
    async def test_get_decrypted_key(self, api_key_service, mock_db_session):
        """Test getting decrypted API key"""
        # Create tenant with encrypted key
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456").decode()
        
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True,
                    "metadata": {"region": "us-west"}
                }
            }
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.get_decrypted_key(1, "groq")
        
        assert result["provider"] == "groq"
        assert result["api_key"] == "gsk_test123456"
        assert result["enabled"] is True
        assert result["metadata"]["region"] == "us-west"
    
    async def test_get_decrypted_key_disabled(self, api_key_service, mock_db_session):
        """Test getting decrypted key that is disabled"""
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456").decode()
        
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": False
                }
            }
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="API key for groq is disabled"):
            await api_key_service.get_decrypted_key(1, "groq", require_enabled=True)
    
    async def test_disable_api_key(self, api_key_service, mock_db_session):
        """Test disabling an API key"""
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
            api_keys={
                "groq": {
                    "key": "encrypted_key",
                    "enabled": True
                }
            }
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.disable_api_key(1, "groq")
        
        assert result is True
        assert tenant.api_keys["groq"]["enabled"] is False
        mock_db_session.commit.assert_called()
    
    async def test_remove_api_key(self, api_key_service, mock_db_session):
        """Test removing an API key"""
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
            api_keys={
                "groq": {
                    "key": "encrypted_key",
                    "enabled": True
                },
                "openai": {
                    "key": "another_key",
                    "enabled": True
                }
            }
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        result = await api_key_service.remove_api_key(1, "groq")
        
        assert result is True
        assert "groq" not in tenant.api_keys
        assert "openai" in tenant.api_keys  # Other keys remain
        mock_db_session.commit.assert_called()
    
    async def test_test_api_key_groq(self, api_key_service, mock_db_session):
        """Test API key validation for Groq"""
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_test123456").decode()
        
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True
                }
            }
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await api_key_service.test_api_key(1, "groq")
            
            assert result["provider"] == "groq"
            assert result["valid"] is True
            assert result["status_code"] == 200
    
    async def test_test_api_key_invalid(self, api_key_service, mock_db_session):
        """Test API key validation with invalid key"""
        cipher = api_key_service.cipher
        encrypted_key = cipher.encrypt(b"gsk_invalid").decode()
        
        tenant = Tenant(
            id=1,
            name="Test Company",
            domain="testcompany",
            api_keys={
                "groq": {
                    "key": encrypted_key,
                    "enabled": True
                }
            }
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant
        mock_db_session.execute.return_value = mock_result
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await api_key_service.test_api_key(1, "groq")
            
            assert result["provider"] == "groq"
            assert result["valid"] is False
            assert result["status_code"] == 401
    
    async def test_get_api_key_usage(self, api_key_service):
        """Test getting API key usage statistics"""
        result = await api_key_service.get_api_key_usage(1, "groq")
        
        assert result["provider"] == "groq"
        assert result["tenant_id"] == 1
        assert "usage" in result
        assert "requests_today" in result["usage"]
        assert "cost_today_cents" in result["usage"]
    
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
    
    async def test_encryption_key_generation(self):
        """Test that encryption key is properly generated"""
        # Clear environment variable
        if 'API_KEY_ENCRYPTION_KEY' in os.environ:
            del os.environ['API_KEY_ENCRYPTION_KEY']
        
        # Create service (should generate key)
        mock_session = AsyncMock(spec=AsyncSession)
        service = APIKeyService(mock_session)
        
        # Verify key was generated and stored
        assert 'API_KEY_ENCRYPTION_KEY' in os.environ
        assert len(os.environ['API_KEY_ENCRYPTION_KEY']) > 0
        
        # Verify cipher works
        test_data = b"test_data"
        encrypted = service.cipher.encrypt(test_data)
        decrypted = service.cipher.decrypt(encrypted)
        assert decrypted == test_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])