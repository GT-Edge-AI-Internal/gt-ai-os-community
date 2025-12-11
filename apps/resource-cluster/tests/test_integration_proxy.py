"""
Unit Tests for Integration Proxy System

Tests secure external service integration, capability-based access control,
sandbox restrictions, and comprehensive audit logging.
"""

import pytest
import tempfile
import json
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from app.services.integration_proxy import (
    IntegrationProxyService, IntegrationConfig, ProxyRequest, ProxyResponse,
    IntegrationType, SandboxLevel, SandboxManager
)


class TestIntegrationConfig:
    """Test IntegrationConfig data structure"""
    
    def test_config_creation(self):
        """Test integration config creation and defaults"""
        config = IntegrationConfig(
            id="test_integration",
            name="Test Integration",
            integration_type=IntegrationType.COMMUNICATION,
            base_url="https://api.example.com",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={"api_key": "test_key"}
        )
        
        assert config.id == "test_integration"
        assert config.name == "Test Integration"
        assert config.integration_type == IntegrationType.COMMUNICATION
        assert config.base_url == "https://api.example.com"
        assert config.authentication_method == "api_key"
        assert config.sandbox_level == SandboxLevel.BASIC
        assert config.auth_config == {"api_key": "test_key"}
        assert config.max_requests_per_hour == 1000
        assert config.timeout_seconds == 30
        assert config.is_active == True
        assert config.allowed_methods == ["GET", "POST"]
    
    def test_config_serialization(self):
        """Test config to/from dict conversion"""
        original = IntegrationConfig(
            id="serialization_test",
            name="Serialization Test",
            integration_type=IntegrationType.DEVELOPMENT,
            base_url="https://api.github.com",
            authentication_method="oauth2",
            sandbox_level=SandboxLevel.RESTRICTED,
            auth_config={"access_token": "token123"},
            allowed_endpoints=["/repos", "/user"],
            blocked_endpoints=["/admin"]
        )
        
        # Convert to dict and back
        config_dict = original.to_dict()
        restored = IntegrationConfig.from_dict(config_dict)
        
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.integration_type == original.integration_type
        assert restored.base_url == original.base_url
        assert restored.sandbox_level == original.sandbox_level
        assert restored.auth_config == original.auth_config
        assert restored.allowed_endpoints == original.allowed_endpoints
        assert restored.blocked_endpoints == original.blocked_endpoints


class TestSandboxManager:
    """Test sandbox restriction management"""
    
    @pytest.fixture
    def sandbox_manager(self):
        """Create sandbox manager for testing"""
        return SandboxManager()
    
    def test_no_sandbox_restrictions(self, sandbox_manager):
        """Test no restrictions for NONE sandbox level"""
        config = IntegrationConfig(
            id="test",
            name="Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.NONE,
            auth_config={}
        )
        
        request = ProxyRequest(
            integration_id="test",
            method="POST",
            endpoint="/api/data",
            timeout_override=120
        )
        
        capability_token = {"constraints": {}}
        
        modified_request, restrictions = sandbox_manager.apply_sandbox_restrictions(
            config, request, capability_token
        )
        
        assert modified_request.timeout_override == 120  # No timeout restriction
        assert len(restrictions) == 0
    
    def test_basic_sandbox_restrictions(self, sandbox_manager):
        """Test basic sandbox restrictions"""
        config = IntegrationConfig(
            id="test",
            name="Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={}
        )
        
        request = ProxyRequest(
            integration_id="test",
            method="POST",
            endpoint="/api/data",
            timeout_override=120,  # Will be limited
            data={"test": "data"}
        )
        
        capability_token = {"constraints": {}}
        
        modified_request, restrictions = sandbox_manager.apply_sandbox_restrictions(
            config, request, capability_token
        )
        
        assert modified_request.timeout_override == 60  # Limited to basic max
        assert "timeout_limited_to_60s" in restrictions
        assert "data_size_validated" in restrictions
    
    def test_strict_sandbox_restrictions(self, sandbox_manager):
        """Test strict sandbox restrictions"""
        config = IntegrationConfig(
            id="test",
            name="Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.STRICT,
            auth_config={},
            allowed_endpoints=["/api/safe"],
            blocked_endpoints=["/api/dangerous"]
        )
        
        # Test allowed endpoint
        request = ProxyRequest(
            integration_id="test",
            method="GET",
            endpoint="/api/safe"
        )
        
        capability_token = {"constraints": {}}
        
        modified_request, restrictions = sandbox_manager.apply_sandbox_restrictions(
            config, request, capability_token
        )
        
        assert "endpoint_validation" in restrictions
        assert "method_restricted" in restrictions
        
        # Test blocked endpoint
        request.endpoint = "/api/dangerous"
        
        with pytest.raises(PermissionError, match="blocked"):
            sandbox_manager.apply_sandbox_restrictions(config, request, capability_token)
        
        # Test forbidden method
        request.method = "DELETE"
        request.endpoint = "/api/safe"
        
        with pytest.raises(PermissionError, match="not allowed"):
            sandbox_manager.apply_sandbox_restrictions(config, request, capability_token)
    
    def test_capability_constraints(self, sandbox_manager):
        """Test capability-based constraints"""
        config = IntegrationConfig(
            id="test",
            name="Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={}
        )
        
        request = ProxyRequest(
            integration_id="test",
            method="GET",
            endpoint="/api/data",
            timeout_override=60
        )
        
        capability_token = {
            "constraints": {
                "integration_timeout_seconds": 20
            }
        }
        
        modified_request, restrictions = sandbox_manager.apply_sandbox_restrictions(
            config, request, capability_token
        )
        
        assert modified_request.timeout_override == 20
        assert "capability_timeout_20s" in restrictions
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, sandbox_manager):
        """Test rate limiting functionality"""
        config = IntegrationConfig(
            id="rate_test",
            name="Rate Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={},
            max_requests_per_hour=2  # Very low limit for testing
        )
        
        # First request should pass
        allowed = await sandbox_manager.check_rate_limits("rate_test", config)
        assert allowed == True
        
        # Second request should pass
        allowed = await sandbox_manager.check_rate_limits("rate_test", config)
        assert allowed == True
        
        # Third request should fail
        allowed = await sandbox_manager.check_rate_limits("rate_test", config)
        assert allowed == False


class TestIntegrationProxyService:
    """Test Integration Proxy Service functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def proxy_service(self, temp_dir):
        """Create proxy service with temporary storage"""
        service = IntegrationProxyService(temp_dir)
        return service
    
    @pytest.fixture
    def mock_capability_token(self):
        """Mock capability token verification"""
        with patch('app.core.security.verify_capability_token') as mock_verify:
            from app.core.security import CapabilityToken, ResourceCapability
            mock_token = CapabilityToken(
                sub="test@example.com",
                tenant_id="test_tenant",
                capabilities=[
                    ResourceCapability(resource="integration:test_integration:*", actions=["execute"])
                ],
                capability_hash="test_hash"
            )
            mock_verify.return_value = mock_token
            yield "mock_token"
    
    @pytest.fixture
    def sample_integration_config(self):
        """Sample integration configuration"""
        return IntegrationConfig(
            id="test_integration",
            name="Test API",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://httpbin.org",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={"api_key": "test_key", "key_header": "X-API-Key"},
            max_requests_per_hour=100,
            timeout_seconds=30
        )
    
    @pytest.mark.asyncio
    async def test_store_and_load_integration_config(self, proxy_service, sample_integration_config):
        """Test storing and loading integration configuration"""
        # Store config
        success = await proxy_service.store_integration_config(sample_integration_config)
        assert success == True
        
        # Load config
        loaded_config = await proxy_service._load_integration_config("test_integration")
        assert loaded_config is not None
        assert loaded_config.id == sample_integration_config.id
        assert loaded_config.name == sample_integration_config.name
        assert loaded_config.integration_type == sample_integration_config.integration_type
        assert loaded_config.base_url == sample_integration_config.base_url
        assert loaded_config.auth_config == sample_integration_config.auth_config
        
        # Test loading non-existent config
        missing_config = await proxy_service._load_integration_config("nonexistent")
        assert missing_config is None
    
    @pytest.mark.asyncio
    async def test_capability_validation(self, proxy_service):
        """Test capability validation"""
        token_data = {
            "capabilities": [
                {"resource": "integration:github:*", "actions": ["execute"]},
                {"resource": "integration:slack:get", "actions": ["execute"]}
            ]
        }
        
        # Test wildcard capability
        assert proxy_service._has_capability(token_data, "integration:github:post") == True
        assert proxy_service._has_capability(token_data, "integration:github:get") == True
        
        # Test specific capability
        assert proxy_service._has_capability(token_data, "integration:slack:get") == True
        assert proxy_service._has_capability(token_data, "integration:slack:post") == False
        
        # Test no capability
        assert proxy_service._has_capability(token_data, "integration:twitter:get") == False
        
        # Test string capabilities
        token_data_simple = {
            "capabilities": ["integration:*", "admin:users"]
        }
        assert proxy_service._has_capability(token_data_simple, "integration:test:action") == True
        assert proxy_service._has_capability(token_data_simple, "admin:users") == True
    
    @pytest.mark.asyncio
    async def test_authentication_headers_api_key(self, proxy_service, sample_integration_config):
        """Test API key authentication header application"""
        headers = {}
        
        await proxy_service._apply_authentication(sample_integration_config, headers)
        
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "Bearer test_key"
    
    @pytest.mark.asyncio
    async def test_authentication_headers_basic_auth(self, proxy_service):
        """Test basic authentication header application"""
        config = IntegrationConfig(
            id="basic_auth_test",
            name="Basic Auth Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="basic_auth",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={
                "username": "testuser",
                "password": "testpass"
            }
        )
        
        headers = {}
        await proxy_service._apply_authentication(config, headers)
        
        assert "Authorization" in headers
        # Basic dGVzdHVzZXI6dGVzdHBhc3M= is base64 for testuser:testpass
        assert headers["Authorization"].startswith("Basic ")
    
    @pytest.mark.asyncio
    async def test_authentication_headers_oauth2(self, proxy_service):
        """Test OAuth2 authentication header application"""
        config = IntegrationConfig(
            id="oauth2_test",
            name="OAuth2 Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://api.test.com",
            authentication_method="oauth2",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={
                "access_token": "oauth_token_123",
                "custom_headers": {"X-Custom": "custom_value"}
            }
        )
        
        headers = {}
        await proxy_service._apply_authentication(config, headers)
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer oauth_token_123"
        assert "X-Custom" in headers
        assert headers["X-Custom"] == "custom_value"
    
    @pytest.mark.asyncio
    async def test_list_integrations_with_capabilities(self, proxy_service, sample_integration_config):
        """Test listing integrations based on capabilities"""
        # Store a test integration
        await proxy_service.store_integration_config(sample_integration_config)
        
        # Create a proper mock for this specific test
        with patch('app.services.integration_proxy.verify_capability_token') as mock_verify:
            from app.core.security import CapabilityToken, ResourceCapability
            mock_token = CapabilityToken(
                sub="test@example.com",
                tenant_id="test_tenant",
                capabilities=[
                    ResourceCapability(resource="integration:test_integration:*", actions=["execute"])
                ],
                capability_hash="test_hash"
            )
            mock_verify.return_value = mock_token
            
            # List integrations (should include the one we stored)
            integrations = await proxy_service.list_integrations("mock_token")
            
            assert len(integrations) == 1
            assert integrations[0].id == "test_integration"
            assert integrations[0].name == "Test API"
    
    @pytest.mark.asyncio
    async def test_usage_logging(self, proxy_service):
        """Test usage logging functionality"""
        await proxy_service._log_usage(
            integration_id="test_integration",
            tenant_id="test_tenant",
            user_id="test@example.com",
            method="GET",
            endpoint="/api/test",
            success=True,
            execution_time_ms=150
        )
        
        # Check log file was created
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage_file = proxy_service.usage_path / f"usage_{date_str}.jsonl"
        assert usage_file.exists()
        
        # Read and verify log record
        with open(usage_file, "r") as f:
            usage_record = json.loads(f.read().strip())
            assert usage_record["integration_id"] == "test_integration"
            assert usage_record["tenant_id"] == "test_tenant"
            assert usage_record["user_id"] == "test@example.com"
            assert usage_record["method"] == "GET"
            assert usage_record["endpoint"] == "/api/test"
            assert usage_record["success"] == True
            assert usage_record["execution_time_ms"] == 150
    
    @pytest.mark.asyncio
    async def test_audit_logging(self, proxy_service):
        """Test audit logging functionality"""
        await proxy_service._audit_log(
            action="integration_executed",
            integration_id="test_integration",
            user_id="test@example.com",
            details={
                "method": "POST",
                "endpoint": "/api/data",
                "restrictions_applied": ["timeout_limited", "data_size_validated"]
            }
        )
        
        # Check audit file was created
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        audit_file = proxy_service.audit_path / f"audit_{date_str}.jsonl"
        assert audit_file.exists()
        
        # Read and verify audit record
        with open(audit_file, "r") as f:
            audit_record = json.loads(f.read().strip())
            assert audit_record["action"] == "integration_executed"
            assert audit_record["integration_id"] == "test_integration"
            assert audit_record["user_id"] == "test@example.com"
            assert audit_record["details"]["method"] == "POST"
            assert "timeout_limited" in audit_record["details"]["restrictions_applied"]
    
    @pytest.mark.asyncio
    async def test_usage_analytics(self, proxy_service):
        """Test usage analytics calculation"""
        # Log some usage records
        for i in range(5):
            await proxy_service._log_usage(
                integration_id="analytics_test",
                tenant_id="test_tenant",
                user_id="test@example.com",
                method="GET",
                endpoint=f"/api/endpoint_{i}",
                success=i < 4,  # 4 successful, 1 failed
                execution_time_ms=100 + i * 10
            )
        
        # Get analytics
        analytics = await proxy_service.get_integration_usage_analytics(
            integration_id="analytics_test",
            days=1
        )
        
        assert analytics["integration_id"] == "analytics_test"
        assert analytics["total_requests"] == 5
        assert analytics["successful_requests"] == 4
        assert analytics["error_count"] == 1
        assert analytics["success_rate"] == 0.8
        assert analytics["avg_execution_time_ms"] == 120  # (100+110+120+130+140)/5
    
    @pytest.mark.asyncio
    async def test_execute_integration_permission_error(self, proxy_service, sample_integration_config):
        """Test integration execution with permission error"""
        # Store config
        await proxy_service.store_integration_config(sample_integration_config)
        
        # Mock capability token verification to return invalid token
        with patch('app.core.security.verify_capability_token') as mock_verify:
            mock_verify.return_value = None
            
            request = ProxyRequest(
                integration_id="test_integration",
                method="GET",
                endpoint="/api/test"
            )
            
            response = await proxy_service.execute_integration(request, "invalid_token")
            
            assert response.success == False
            assert "Invalid capability token" in response.error_message
    
    @pytest.mark.asyncio
    async def test_execute_integration_missing_capability(self, proxy_service, sample_integration_config):
        """Test integration execution with missing capability"""
        # Store config
        await proxy_service.store_integration_config(sample_integration_config)
        
        # Mock capability token verification to return token without required capability
        with patch('app.services.integration_proxy.verify_capability_token') as mock_verify:
            from app.core.security import CapabilityToken
            mock_token = CapabilityToken(
                sub="test@example.com",
                tenant_id="test_tenant",
                capabilities=[],  # No capabilities
                capability_hash="test_hash"
            )
            mock_verify.return_value = mock_token
            
            request = ProxyRequest(
                integration_id="test_integration",
                method="GET",
                endpoint="/api/test"
            )
            
            response = await proxy_service.execute_integration(request, "token_without_capability")
            
            assert response.success == False
            assert "Missing capability" in response.error_message
    
    @pytest.mark.asyncio
    async def test_execute_integration_rate_limit_exceeded(self, proxy_service):
        """Test integration execution with rate limit exceeded"""
        # Create config with very low rate limit
        config = IntegrationConfig(
            id="rate_limit_test",
            name="Rate Limit Test",
            integration_type=IntegrationType.CUSTOM_API,
            base_url="https://httpbin.org",
            authentication_method="api_key",
            sandbox_level=SandboxLevel.BASIC,
            auth_config={"api_key": "test"},
            max_requests_per_hour=1  # Very low limit
        )
        
        await proxy_service.store_integration_config(config)
        
        # Mock capability token
        with patch('app.services.integration_proxy.verify_capability_token') as mock_verify:
            from app.core.security import CapabilityToken, ResourceCapability
            mock_token = CapabilityToken(
                sub="test@example.com",
                tenant_id="test_tenant",
                capabilities=[
                    ResourceCapability(resource="integration:rate_limit_test:*", actions=["execute"])
                ],
                capability_hash="test_hash"
            )
            mock_verify.return_value = mock_token
            
            request = ProxyRequest(
                integration_id="rate_limit_test",
                method="GET",
                endpoint="/api/test"
            )
            
            # First request should work (but we'll skip actual HTTP)
            # Second request should hit rate limit
            
            # Manually trigger rate limit
            proxy_service.sandbox_manager.rate_limiters["rate_limit_test"] = [
                datetime.utcnow()  # Already one request this hour
            ]
            
            response = await proxy_service.execute_integration(request, "valid_token")
            
            assert response.success == False
            assert "Rate limit exceeded" in response.error_message
    
    @pytest.mark.asyncio
    async def test_proxy_request_creation(self):
        """Test ProxyRequest creation and defaults"""
        request = ProxyRequest(
            integration_id="test",
            method="POST",
            endpoint="/api/data"
        )
        
        assert request.integration_id == "test"
        assert request.method == "POST"
        assert request.endpoint == "/api/data"
        assert request.headers == {}
        assert request.data == {}
        assert request.params == {}
        assert request.timeout_override is None
    
    @pytest.mark.asyncio
    async def test_proxy_response_creation(self):
        """Test ProxyResponse creation and defaults"""
        response = ProxyResponse(
            success=True,
            status_code=200,
            data={"result": "success"},
            headers={"content-type": "application/json"},
            execution_time_ms=150,
            sandbox_applied=True,
            restrictions_applied=["timeout_limited"]
        )
        
        assert response.success == True
        assert response.status_code == 200
        assert response.data["result"] == "success"
        assert response.headers["content-type"] == "application/json"
        assert response.execution_time_ms == 150
        assert response.sandbox_applied == True
        assert "timeout_limited" in response.restrictions_applied
        assert response.error_message is None
    
    @pytest.mark.asyncio
    async def test_service_cleanup(self, proxy_service):
        """Test service cleanup and resource management"""
        # Close the service
        await proxy_service.close()
        
        # HTTP client should be closed
        assert proxy_service.http_client is None