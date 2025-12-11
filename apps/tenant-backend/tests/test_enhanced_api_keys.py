"""
Unit Tests for Enhanced API Keys System

Tests API key management, capability tokens, and constraint enforcement
with tenant isolation and comprehensive audit logging.
"""

import pytest
import tempfile
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from app.services.enhanced_api_keys import (
    EnhancedAPIKeyService, APIKeyConfig, APIKeyStatus, APIKeyScope, APIKeyUsage
)


class TestAPIKeyUsage:
    """Test API key usage tracking"""
    
    def test_usage_creation(self):
        """Test usage tracking creation and updates"""
        usage = APIKeyUsage()
        
        assert usage.requests_count == 0
        assert usage.last_used is None
        assert usage.bytes_transferred == 0
        assert usage.errors_count == 0
        assert usage.rate_limit_hits == 0
    
    def test_usage_serialization(self):
        """Test usage to/from dict conversion"""
        original = APIKeyUsage(
            requests_count=100,
            last_used=datetime.utcnow(),
            bytes_transferred=1024000,
            errors_count=5,
            rate_limit_hits=2
        )
        
        # Convert to dict and back
        usage_dict = original.to_dict()
        restored = APIKeyUsage.from_dict(usage_dict)
        
        assert restored.requests_count == original.requests_count
        assert restored.last_used == original.last_used
        assert restored.bytes_transferred == original.bytes_transferred
        assert restored.errors_count == original.errors_count
        assert restored.rate_limit_hits == original.rate_limit_hits


class TestAPIKeyConfig:
    """Test API key configuration"""
    
    def test_config_creation(self):
        """Test API key config creation"""
        config = APIKeyConfig(
            name="Test API Key",
            owner_id="user@example.com",
            key_hash="abc123",
            capabilities=["llm:gpt-4", "rag:search"],
            scope=APIKeyScope.USER
        )
        
        assert config.name == "Test API Key"
        assert config.owner_id == "user@example.com"
        assert config.scope == APIKeyScope.USER
        assert len(config.capabilities) == 2
        assert config.status == APIKeyStatus.ACTIVE
        assert config.rate_limit_per_hour == 1000  # Default for user scope
    
    def test_config_serialization(self):
        """Test config to/from dict conversion"""
        original = APIKeyConfig(
            name="Serialization Test",
            owner_id="test@example.com",
            key_hash="hash123",
            capabilities=["test:capability"],
            scope=APIKeyScope.TENANT,
            expires_at=datetime.utcnow() + timedelta(days=90)
        )
        
        # Convert to dict and back
        config_dict = original.to_dict()
        restored = APIKeyConfig.from_dict(config_dict)
        
        assert restored.name == original.name
        assert restored.owner_id == original.owner_id
        assert restored.key_hash == original.key_hash
        assert restored.capabilities == original.capabilities
        assert restored.scope == original.scope
        assert restored.expires_at == original.expires_at
        assert restored.status == original.status


class TestEnhancedAPIKeyService:
    """Test Enhanced API Key Service functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def api_key_service(self, temp_dir):
        """Create API key service with temporary storage"""
        service = EnhancedAPIKeyService("test.com", "test_signing_key")
        service.base_path = temp_dir
        service.keys_path = temp_dir / "keys"
        service.usage_path = temp_dir / "usage"
        service.audit_path = temp_dir / "audit"
        service._ensure_directories()
        return service
    
    @pytest.fixture
    def mock_capability_token(self):
        """Mock capability token verification"""
        with patch('app.services.enhanced_api_keys.verify_capability_token') as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "test.com",
                "sub": "admin@example.com",
                "capabilities": ["admin:api_keys"]
            }
            yield "mock_token"
    
    @pytest.mark.asyncio
    async def test_create_api_key_user_scope(self, api_key_service, mock_capability_token):
        """Test creating user-scope API key"""
        api_key, raw_key = await api_key_service.create_api_key(
            name="User Test Key",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4", "rag:search"],
            scope=APIKeyScope.USER,
            expires_in_days=30,
            capability_token=mock_capability_token
        )
        
        assert api_key.name == "User Test Key"
        assert api_key.owner_id == "user@example.com"
        assert api_key.scope == APIKeyScope.USER
        assert api_key.capabilities == ["llm:gpt-4", "rag:search"]
        assert api_key.status == APIKeyStatus.ACTIVE
        assert api_key.rate_limit_per_hour == 1000  # User scope default
        assert api_key.expires_at is not None
        
        # Verify raw key format
        assert raw_key.startswith("gt2_test.com_")
        assert len(raw_key) > 20
        
        # Verify key hash
        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert api_key.key_hash == expected_hash
        
        # Check file was created
        key_file = api_key_service.keys_path / f"{api_key.id}.json"
        assert key_file.exists()
    
    @pytest.mark.asyncio
    async def test_create_api_key_tenant_scope(self, api_key_service, mock_capability_token):
        """Test creating tenant-scope API key"""
        api_key, raw_key = await api_key_service.create_api_key(
            name="Tenant Test Key",
            owner_id="admin@example.com",
            capabilities=["admin:tenant_settings", "automation:create"],
            scope=APIKeyScope.TENANT,
            capability_token=mock_capability_token
        )
        
        assert api_key.scope == APIKeyScope.TENANT
        assert api_key.rate_limit_per_hour == 5000  # Tenant scope default
        assert api_key.daily_quota == 50000
        assert api_key.cost_limit_cents == 5000
    
    @pytest.mark.asyncio
    async def test_create_api_key_admin_scope(self, api_key_service, mock_capability_token):
        """Test creating admin-scope API key"""
        api_key, raw_key = await api_key_service.create_api_key(
            name="Admin Test Key",
            owner_id="admin@example.com",
            capabilities=["admin:user_management", "admin:tenant_settings"],
            scope=APIKeyScope.ADMIN,
            capability_token=mock_capability_token
        )
        
        assert api_key.scope == APIKeyScope.ADMIN
        assert api_key.rate_limit_per_hour == 10000  # Admin scope default
        assert api_key.daily_quota == 100000
        assert api_key.cost_limit_cents == 10000
    
    @pytest.mark.asyncio
    async def test_create_api_key_with_constraints(self, api_key_service, mock_capability_token):
        """Test creating API key with custom constraints"""
        custom_constraints = {
            "max_automation_chain_depth": 10,
            "mcp_memory_limit_mb": 1024,
            "enable_premium_features": True
        }
        
        api_key, raw_key = await api_key_service.create_api_key(
            name="Constrained Key",
            owner_id="user@example.com",
            capabilities=["automation:create"],
            constraints=custom_constraints,
            capability_token=mock_capability_token
        )
        
        assert api_key.tenant_constraints["max_automation_chain_depth"] == 10
        assert api_key.tenant_constraints["mcp_memory_limit_mb"] == 1024
        assert api_key.tenant_constraints["enable_premium_features"] == True
        
        # Should also have defaults applied
        assert "allowed_file_types" in api_key.tenant_constraints
    
    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, api_key_service, mock_capability_token):
        """Test successful API key validation"""
        # Create API key
        api_key, raw_key = await api_key_service.create_api_key(
            name="Validation Test",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        # Validate the key
        valid, loaded_key, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/chat",
            client_ip="192.168.1.100"
        )
        
        assert valid == True
        assert loaded_key is not None
        assert loaded_key.id == api_key.id
        assert error is None
        
        # Check usage was updated
        updated_key = await api_key_service._load_api_key(api_key.id)
        assert updated_key.usage.requests_count == 1
        assert updated_key.usage.last_used is not None
    
    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self, api_key_service):
        """Test validation of invalid API key"""
        invalid_key = "invalid_key_format"
        
        valid, api_key, error = await api_key_service.validate_api_key(
            raw_key=invalid_key,
            endpoint="/api/v1/chat"
        )
        
        assert valid == False
        assert api_key is None
        assert error == "Invalid API key"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_expired(self, api_key_service, mock_capability_token):
        """Test validation of expired API key"""
        # Create API key with very short expiration
        api_key, raw_key = await api_key_service.create_api_key(
            name="Expiry Test",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            expires_in_days=0,  # Expires immediately
            capability_token=mock_capability_token
        )
        
        # Manually set expiration to past
        api_key.expires_at = datetime.utcnow() - timedelta(hours=1)
        await api_key_service._store_api_key(api_key)
        
        # Validate the expired key
        valid, loaded_key, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/chat"
        )
        
        assert valid == False
        assert error == "API key has expired"
        
        # Check key status was updated to expired
        updated_key = await api_key_service._load_api_key(api_key.id)
        assert updated_key.status == APIKeyStatus.EXPIRED
    
    @pytest.mark.asyncio
    async def test_validate_api_key_endpoint_restrictions(self, api_key_service, mock_capability_token):
        """Test API key endpoint restrictions"""
        # Create API key with endpoint restrictions
        api_key, raw_key = await api_key_service.create_api_key(
            name="Restricted Key",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        # Set endpoint restrictions
        api_key.allowed_endpoints = ["/api/v1/chat", "/api/v1/embeddings"]
        api_key.blocked_endpoints = ["/api/v1/admin"]
        await api_key_service._store_api_key(api_key)
        
        # Test allowed endpoint
        valid, _, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/chat"
        )
        assert valid == True
        assert error is None
        
        # Test disallowed endpoint
        valid, _, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/documents"
        )
        assert valid == False
        assert "not allowed" in error
        
        # Test blocked endpoint
        valid, _, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/admin"
        )
        assert valid == False
        assert "is blocked" in error
    
    @pytest.mark.asyncio
    async def test_validate_api_key_ip_restrictions(self, api_key_service, mock_capability_token):
        """Test API key IP restrictions"""
        # Create API key with IP restrictions
        api_key, raw_key = await api_key_service.create_api_key(
            name="IP Restricted Key",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        # Set IP restrictions
        api_key.allowed_ips = ["192.168.1.100", "10.0.0.1"]
        await api_key_service._store_api_key(api_key)
        
        # Test allowed IP
        valid, _, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/chat",
            client_ip="192.168.1.100"
        )
        assert valid == True
        assert error is None
        
        # Test disallowed IP
        valid, _, error = await api_key_service.validate_api_key(
            raw_key=raw_key,
            endpoint="/api/v1/chat",
            client_ip="172.16.0.1"
        )
        assert valid == False
        assert "not allowed" in error
    
    @pytest.mark.asyncio
    async def test_generate_capability_token(self, api_key_service, mock_capability_token):
        """Test capability token generation"""
        # Create API key
        api_key, raw_key = await api_key_service.create_api_key(
            name="Token Test",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4", "rag:search"],
            capability_token=mock_capability_token
        )
        
        # Generate capability token
        token = await api_key_service.generate_capability_token(api_key)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are quite long
        
        # Token should be valid JWT format (has 3 parts separated by dots)
        parts = token.split('.')
        assert len(parts) == 3
    
    @pytest.mark.asyncio
    async def test_rotate_api_key(self, api_key_service, mock_capability_token):
        """Test API key rotation"""
        # Create API key
        api_key, original_key = await api_key_service.create_api_key(
            name="Rotation Test",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        original_hash = api_key.key_hash
        
        # Rotate the key
        rotated_key, new_raw_key = await api_key_service.rotate_api_key(
            key_id=api_key.id,
            owner_id="user@example.com",
            capability_token=mock_capability_token
        )
        
        # Verify rotation
        assert rotated_key.id == api_key.id  # Same key ID
        assert rotated_key.key_hash != original_hash  # Different hash
        assert rotated_key.last_rotated is not None
        assert new_raw_key != original_key  # Different raw key
        assert new_raw_key.startswith("gt2_test.com_")
        
        # Verify new hash matches new key
        expected_hash = hashlib.sha256(new_raw_key.encode()).hexdigest()
        assert rotated_key.key_hash == expected_hash
        
        # Old key should no longer validate
        valid, _, _ = await api_key_service.validate_api_key(original_key)
        assert valid == False
        
        # New key should validate
        valid, _, _ = await api_key_service.validate_api_key(new_raw_key)
        assert valid == True
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, api_key_service, mock_capability_token):
        """Test API key revocation"""
        # Create API key
        api_key, raw_key = await api_key_service.create_api_key(
            name="Revocation Test",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        # Revoke the key
        success = await api_key_service.revoke_api_key(
            key_id=api_key.id,
            owner_id="user@example.com",
            capability_token=mock_capability_token
        )
        
        assert success == True
        
        # Verify key status was updated
        revoked_key = await api_key_service._load_api_key(api_key.id)
        assert revoked_key.status == APIKeyStatus.REVOKED
        
        # Key should no longer validate
        valid, loaded_key, error = await api_key_service.validate_api_key(raw_key)
        assert valid == False
        assert error == "API key is revoked"
    
    @pytest.mark.asyncio
    async def test_list_user_api_keys(self, api_key_service, mock_capability_token):
        """Test listing user API keys"""
        # Create multiple API keys for user
        user_id = "user@example.com"
        
        keys_created = []
        for i in range(3):
            api_key, _ = await api_key_service.create_api_key(
                name=f"User Key {i+1}",
                owner_id=user_id,
                capabilities=["llm:gpt-4"],
                capability_token=mock_capability_token
            )
            keys_created.append(api_key)
        
        # Create key for different user
        await api_key_service.create_api_key(
            name="Other User Key",
            owner_id="other@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        # List keys for original user
        user_keys = await api_key_service.list_user_api_keys(
            owner_id=user_id,
            capability_token=mock_capability_token,
            include_usage=True
        )
        
        # Should only return keys for the user
        assert len(user_keys) == 3
        for key in user_keys:
            assert key.owner_id == user_id
        
        # Check keys are sorted by creation time (newest first)
        for i in range(len(user_keys) - 1):
            assert user_keys[i].created_at >= user_keys[i + 1].created_at
    
    @pytest.mark.asyncio
    async def test_get_usage_analytics(self, api_key_service, mock_capability_token):
        """Test usage analytics collection"""
        # Create API key with some usage
        api_key, raw_key = await api_key_service.create_api_key(
            name="Analytics Test",
            owner_id="user@example.com",
            capabilities=["llm:gpt-4"],
            capability_token=mock_capability_token
        )
        
        # Simulate some usage
        api_key.usage.requests_count = 100
        api_key.usage.errors_count = 5
        api_key.usage.rate_limit_hits = 2
        await api_key_service._store_api_key(api_key)
        
        # Get analytics
        analytics = await api_key_service.get_usage_analytics(
            owner_id="user@example.com",
            key_id=api_key.id,
            days=30
        )
        
        assert analytics["total_requests"] == 100
        assert analytics["total_errors"] == 5
        assert analytics["rate_limit_hits"] == 2
        assert analytics["keys_analyzed"] == 1
        assert analytics["avg_requests_per_day"] == 100 / 30
        assert "date_range" in analytics
    
    @pytest.mark.asyncio
    async def test_usage_logging(self, api_key_service):
        """Test detailed usage logging"""
        # Log usage record
        await api_key_service._log_usage(
            key_id="test_key_123",
            endpoint="/api/v1/chat",
            client_ip="192.168.1.100"
        )
        
        # Check usage file was created
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage_file = api_key_service.usage_path / f"usage_{date_str}.jsonl"
        assert usage_file.exists()
        
        # Read and verify usage record
        with open(usage_file, "r") as f:
            usage_record = json.loads(f.read().strip())
            assert usage_record["key_id"] == "test_key_123"
            assert usage_record["endpoint"] == "/api/v1/chat"
            assert usage_record["client_ip"] == "192.168.1.100"
            assert usage_record["tenant"] == "test.com"
    
    @pytest.mark.asyncio
    async def test_audit_logging(self, api_key_service):
        """Test audit logging for key management actions"""
        # Log audit record
        await api_key_service._audit_log(
            action="api_key_created",
            user_id="admin@example.com",
            details={"key_id": "test_123", "name": "Test Key"}
        )
        
        # Check audit file was created
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        audit_file = api_key_service.audit_path / f"audit_{date_str}.jsonl"
        assert audit_file.exists()
        
        # Read and verify audit record
        with open(audit_file, "r") as f:
            audit_record = json.loads(f.read().strip())
            assert audit_record["action"] == "api_key_created"
            assert audit_record["user_id"] == "admin@example.com"
            assert audit_record["details"]["key_id"] == "test_123"
            assert audit_record["tenant"] == "test.com"
    
    @pytest.mark.asyncio
    async def test_constraint_application(self, api_key_service):
        """Test tenant constraint application"""
        # Test default constraints
        defaults = api_key_service._apply_tenant_defaults({})
        
        assert "max_automation_chain_depth" in defaults
        assert "mcp_memory_limit_mb" in defaults
        assert "allowed_file_types" in defaults
        assert defaults["max_automation_chain_depth"] == 5
        assert defaults["enable_premium_features"] == False
        
        # Test custom constraints override defaults
        custom = {"max_automation_chain_depth": 10, "custom_setting": "test"}
        applied = api_key_service._apply_tenant_defaults(custom)
        
        assert applied["max_automation_chain_depth"] == 10  # Override
        assert applied["custom_setting"] == "test"  # Custom
        assert applied["mcp_memory_limit_mb"] == 512  # Default preserved
    
    @pytest.mark.asyncio
    async def test_scope_defaults_application(self, api_key_service):
        """Test scope-based default application"""
        # Test user scope defaults
        user_key = APIKeyConfig()
        api_key_service._apply_scope_defaults(user_key, APIKeyScope.USER)
        
        assert user_key.rate_limit_per_hour == 1000
        assert user_key.daily_quota == 10000
        assert user_key.cost_limit_cents == 1000
        
        # Test tenant scope defaults
        tenant_key = APIKeyConfig()
        api_key_service._apply_scope_defaults(tenant_key, APIKeyScope.TENANT)
        
        assert tenant_key.rate_limit_per_hour == 5000
        assert tenant_key.daily_quota == 50000
        assert tenant_key.cost_limit_cents == 5000
        
        # Test admin scope defaults
        admin_key = APIKeyConfig()
        api_key_service._apply_scope_defaults(admin_key, APIKeyScope.ADMIN)
        
        assert admin_key.rate_limit_per_hour == 10000
        assert admin_key.daily_quota == 100000
        assert admin_key.cost_limit_cents == 10000
    
    @pytest.mark.asyncio
    async def test_permission_errors(self, api_key_service):
        """Test permission errors for key operations"""
        # Test invalid capability token
        with patch('app.services.enhanced_api_keys.verify_capability_token') as mock_verify:
            mock_verify.return_value = None
            
            with pytest.raises(PermissionError):
                await api_key_service.create_api_key(
                    name="Test",
                    owner_id="user@example.com",
                    capabilities=["llm:gpt-4"],
                    capability_token="invalid_token"
                )
        
        # Test wrong tenant in token
        with patch('app.services.enhanced_api_keys.verify_capability_token') as mock_verify:
            mock_verify.return_value = {"tenant_id": "wrong_tenant"}
            
            with pytest.raises(PermissionError):
                await api_key_service.create_api_key(
                    name="Test",
                    owner_id="user@example.com",
                    capabilities=["llm:gpt-4"],
                    capability_token="wrong_tenant_token"
                )
    
    @pytest.mark.asyncio
    async def test_key_storage_and_loading(self, api_key_service):
        """Test key storage and loading persistence"""
        key_config = APIKeyConfig(
            name="Storage Test",
            owner_id="user@example.com",
            key_hash="test_hash_123",
            capabilities=["llm:gpt-4", "rag:search"],
            scope=APIKeyScope.TENANT,
            allowed_endpoints=["/api/v1/chat"],
            expires_at=datetime.utcnow() + timedelta(days=90)
        )
        
        # Store key
        await api_key_service._store_api_key(key_config)
        
        # Load key
        loaded_key = await api_key_service._load_api_key(key_config.id)
        
        assert loaded_key is not None
        assert loaded_key.name == key_config.name
        assert loaded_key.owner_id == key_config.owner_id
        assert loaded_key.key_hash == key_config.key_hash
        assert loaded_key.capabilities == key_config.capabilities
        assert loaded_key.scope == key_config.scope
        assert loaded_key.allowed_endpoints == key_config.allowed_endpoints
        assert loaded_key.expires_at == key_config.expires_at
        
        # Test loading by hash
        loaded_by_hash = await api_key_service._load_api_key_by_hash("test_hash_123")
        assert loaded_by_hash is not None
        assert loaded_by_hash.id == key_config.id
        
        # Test loading non-existent key
        missing_key = await api_key_service._load_api_key("nonexistent")
        assert missing_key is None