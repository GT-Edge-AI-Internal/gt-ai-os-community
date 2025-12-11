"""
Pure unit tests for API Key Management Service (no SQLAlchemy)
"""
import pytest
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from cryptography.fernet import Fernet

# Set up test environment
os.environ["API_KEY_ENCRYPTION_KEY"] = Fernet.generate_key().decode()


class TestAPIKeyServicePure:
    """Pure unit tests for API Key Service without database dependencies"""
    
    @pytest.mark.asyncio
    async def test_api_key_encryption_decryption(self):
        """Test API key encryption and decryption"""
        from app.services.api_key_service import APIKeyService
        
        # Mock database session
        mock_db = AsyncMock()
        service = APIKeyService(mock_db)
        
        # Test encryption and decryption
        original_key = "gsk_test123456789"
        encrypted = service._encrypt_key(original_key)
        decrypted = service._decrypt_key(encrypted)
        
        assert original_key != encrypted
        assert decrypted == original_key
    
    @pytest.mark.asyncio
    async def test_validate_api_key_format(self):
        """Test API key format validation"""
        from app.services.api_key_service import APIKeyService
        
        mock_db = AsyncMock()
        service = APIKeyService(mock_db)
        
        # Valid formats
        assert service._validate_api_key_format("groq", "gsk_test123456") is True
        assert service._validate_api_key_format("openai", "sk-test123456") is True
        assert service._validate_api_key_format("anthropic", "sk-ant-test123") is True
        assert service._validate_api_key_format("cohere", "test-key-123") is True
        
        # Invalid formats
        assert service._validate_api_key_format("groq", "invalid") is False
        assert service._validate_api_key_format("openai", "invalid") is False
    
    @pytest.mark.asyncio
    async def test_set_api_key_logic(self):
        """Test the core logic of setting an API key"""
        with patch('app.services.api_key_service.select') as mock_select:
            from app.services.api_key_service import APIKeyService
            
            # Create a mock tenant
            mock_tenant = Mock()
            mock_tenant.id = 1
            mock_tenant.api_keys = {}
            
            # Mock database operations
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            service = APIKeyService(mock_db)
            
            # Set API key
            result = await service.set_api_key(
                tenant_id=1,
                provider="groq",
                api_key="gsk_test123456789",
                enabled=True
            )
            
            # Verify results
            assert result["tenant_id"] == 1
            assert result["provider"] == "groq"
            assert result["enabled"] is True
            assert "groq" in mock_tenant.api_keys
            assert mock_tenant.api_keys["groq"]["enabled"] is True
            assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_logic(self):
        """Test getting and decrypting an API key"""
        with patch('app.services.api_key_service.select') as mock_select:
            from app.services.api_key_service import APIKeyService
            
            mock_db = AsyncMock()
            service = APIKeyService(mock_db)
            
            # Encrypt a test key
            original_key = "gsk_test123456789"
            encrypted_key = service._encrypt_key(original_key)
            
            # Create mock tenant with encrypted key
            mock_tenant = Mock()
            mock_tenant.id = 1
            mock_tenant.api_keys = {
                "groq": {
                    "key": encrypted_key,
                    "enabled": True,
                    "metadata": {"region": "us-west"}
                }
            }
            
            # Mock database operations
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            # Get decrypted key
            result = await service.get_decrypted_key(1, "groq")
            
            # Verify results
            assert result["provider"] == "groq"
            assert result["api_key"] == original_key
            assert result["enabled"] is True
            assert result["metadata"]["region"] == "us-west"
    
    @pytest.mark.asyncio
    async def test_test_api_key_groq(self):
        """Test API key validation for Groq"""
        with patch('app.services.api_key_service.select') as mock_select:
            with patch('httpx.AsyncClient') as mock_httpx:
                from app.services.api_key_service import APIKeyService
                
                mock_db = AsyncMock()
                service = APIKeyService(mock_db)
                
                # Encrypt test key
                encrypted_key = service._encrypt_key("gsk_test123456789")
                
                # Create mock tenant
                mock_tenant = Mock()
                mock_tenant.id = 1
                mock_tenant.api_keys = {
                    "groq": {
                        "key": encrypted_key,
                        "enabled": True
                    }
                }
                
                # Mock database
                mock_result = Mock()
                mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
                mock_db.execute = AsyncMock(return_value=mock_result)
                
                # Mock HTTP client
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json = Mock(return_value={"models": ["llama-3.1-70b"]})
                
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                
                # Test API key
                result = await service.test_api_key(1, "groq")
                
                # Verify results
                assert result["provider"] == "groq"
                assert result["valid"] is True
                assert result["status_code"] == 200
    
    @pytest.mark.asyncio
    async def test_disable_api_key_logic(self):
        """Test disabling an API key"""
        with patch('app.services.api_key_service.select') as mock_select:
            from app.services.api_key_service import APIKeyService
            
            # Create mock tenant
            mock_tenant = Mock()
            mock_tenant.id = 1
            mock_tenant.api_keys = {
                "groq": {
                    "key": "encrypted",
                    "enabled": True
                }
            }
            
            # Mock database
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            service = APIKeyService(mock_db)
            
            # Disable key
            result = await service.disable_api_key(1, "groq")
            
            # Verify
            assert result is True
            assert mock_tenant.api_keys["groq"]["enabled"] is False
            assert mock_db.commit.called
    
    @pytest.mark.asyncio
    async def test_remove_api_key_logic(self):
        """Test removing an API key"""
        with patch('app.services.api_key_service.select') as mock_select:
            from app.services.api_key_service import APIKeyService
            
            # Create mock tenant
            mock_tenant = Mock()
            mock_tenant.id = 1
            mock_tenant.api_keys = {
                "groq": {"key": "encrypted", "enabled": True},
                "openai": {"key": "encrypted2", "enabled": True}
            }
            
            # Mock database
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            service = APIKeyService(mock_db)
            
            # Remove key
            result = await service.remove_api_key(1, "groq")
            
            # Verify
            assert result is True
            assert "groq" not in mock_tenant.api_keys
            assert "openai" in mock_tenant.api_keys
            assert mock_db.commit.called
    
    def test_get_supported_providers(self):
        """Test getting supported providers list"""
        from app.services.api_key_service import APIKeyService
        
        providers = APIKeyService.get_supported_providers()
        
        # Check structure
        assert isinstance(providers, list)
        assert len(providers) > 0
        
        # Check specific providers
        provider_ids = [p["id"] for p in providers]
        assert "groq" in provider_ids
        assert "openai" in provider_ids
        assert "anthropic" in provider_ids
        assert "backblaze" in provider_ids
        
        # Check Groq details
        groq = next(p for p in providers if p["id"] == "groq")
        assert groq["name"] == "Groq Cloud LLM"
        assert groq["key_format"] == "gsk_*"
        
        # Check Backblaze has secret requirement
        backblaze = next(p for p in providers if p["id"] == "backblaze")
        assert backblaze["requires_secret"] is True
    
    @pytest.mark.asyncio
    async def test_api_key_usage_stats(self):
        """Test getting API key usage statistics"""
        from app.services.api_key_service import APIKeyService
        
        mock_db = AsyncMock()
        service = APIKeyService(mock_db)
        
        # Get usage (mock implementation returns placeholder data)
        result = await service.get_api_key_usage(1, "groq")
        
        # Verify structure
        assert result["provider"] == "groq"
        assert result["tenant_id"] == 1
        assert "usage" in result
        assert "requests_today" in result["usage"]
        assert "tokens_today" in result["usage"]
        assert "cost_today_cents" in result["usage"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])