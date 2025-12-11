"""
Unit tests for Consul Service Registry Integration
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from faker import Faker

from app.core.backends.consul_registry import ConsulServiceRegistry

fake = Faker()


@pytest.fixture
def consul_registry(mock_settings):
    """Create ConsulServiceRegistry instance with mocked settings"""
    with patch('app.core.backends.consul_registry.get_settings', return_value=mock_settings):
        registry = ConsulServiceRegistry()
        return registry


@pytest.fixture
def mock_consul_client():
    """Mock Consul client"""
    client = Mock()
    client.agent.service.register = AsyncMock()
    client.agent.service.deregister = AsyncMock()
    client.health.service = AsyncMock()
    client.kv.put = AsyncMock()
    client.kv.get = AsyncMock()
    client.catalog.service = AsyncMock()
    return client


@pytest.fixture
def sample_service_data():
    """Sample service registration data"""
    return {
        "service_id": "test-groq-proxy-1",
        "service_name": "groq-proxy",
        "address": "192.168.1.100",
        "port": 8000,
        "tags": ["groq", "llm", "proxy"],
        "meta": {
            "version": "1.0.0",
            "cluster": "resource",
            "environment": "test"
        },
        "check": {
            "http": "http://192.168.1.100:8000/health",
            "interval": "10s",
            "timeout": "5s"
        }
    }


class TestConsulServiceRegistry:
    """Test the ConsulServiceRegistry class"""
    
    def test_initialization(self, mock_settings):
        """Test ConsulServiceRegistry initialization"""
        mock_settings.consul_host = "test-consul"
        mock_settings.consul_port = 8500
        mock_settings.consul_token = "test-token"
        
        with patch('app.core.backends.consul_registry.get_settings', return_value=mock_settings), \
             patch('consul.Consul') as mock_consul_class:
            
            registry = ConsulServiceRegistry()
            
            # Verify Consul client was initialized with correct parameters
            mock_consul_class.assert_called_once_with(
                host="test-consul",
                port=8500,
                token="test-token"
            )
            
            # Verify instance attributes
            assert registry.health_check_interval == 30
            assert registry.service_ttl == 60
            assert registry.discovery_cache == {}
    
    @pytest.mark.asyncio
    async def test_register_service_success(self, consul_registry, mock_consul_client, sample_service_data):
        """Test successful service registration"""
        # Mock consul client
        consul_registry.consul = mock_consul_client
        mock_consul_client.agent.service.register.return_value = True
        
        result = await consul_registry.register_service(**sample_service_data)
        
        assert result is True
        
        # Verify consul registration was called with correct data
        expected_registration = {
            "service_id": sample_service_data["service_id"],
            "name": sample_service_data["service_name"],
            "address": sample_service_data["address"],
            "port": sample_service_data["port"],
            "tags": sample_service_data["tags"],
            "meta": sample_service_data["meta"],
            "check": sample_service_data["check"]
        }
        
        mock_consul_client.agent.service.register.assert_called_once_with(**expected_registration)
    
    @pytest.mark.asyncio
    async def test_register_service_failure(self, consul_registry, mock_consul_client, sample_service_data):
        """Test service registration failure handling"""
        # Mock consul client to raise exception
        consul_registry.consul = mock_consul_client
        mock_consul_client.agent.service.register.side_effect = Exception("Consul connection failed")
        
        result = await consul_registry.register_service(**sample_service_data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_deregister_service_success(self, consul_registry, mock_consul_client):
        """Test successful service deregistration"""
        consul_registry.consul = mock_consul_client
        mock_consul_client.agent.service.deregister.return_value = True
        
        result = await consul_registry.deregister_service("test-service-1")
        
        assert result is True
        mock_consul_client.agent.service.deregister.assert_called_once_with("test-service-1")
    
    @pytest.mark.asyncio
    async def test_deregister_service_failure(self, consul_registry, mock_consul_client):
        """Test service deregistration failure handling"""
        consul_registry.consul = mock_consul_client
        mock_consul_client.agent.service.deregister.side_effect = Exception("Service not found")
        
        result = await consul_registry.deregister_service("nonexistent-service")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_discover_services_success(self, consul_registry, mock_consul_client):
        """Test successful service discovery"""
        # Mock consul health check response
        mock_services = [
            {
                "Service": {
                    "ID": "groq-proxy-1",
                    "Service": "groq-proxy",
                    "Address": "192.168.1.100",
                    "Port": 8000,
                    "Tags": ["groq", "llm"],
                    "Meta": {"version": "1.0.0"}
                },
                "Checks": [
                    {"Status": "passing", "CheckID": "service:groq-proxy-1"}
                ]
            },
            {
                "Service": {
                    "ID": "groq-proxy-2",
                    "Service": "groq-proxy",
                    "Address": "192.168.1.101",
                    "Port": 8000,
                    "Tags": ["groq", "llm"],
                    "Meta": {"version": "1.0.0"}
                },
                "Checks": [
                    {"Status": "passing", "CheckID": "service:groq-proxy-2"}
                ]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        services = await consul_registry.discover_services("groq-proxy")
        
        assert len(services) == 2
        assert services[0]["id"] == "groq-proxy-1"
        assert services[0]["address"] == "192.168.1.100"
        assert services[0]["port"] == 8000
        assert services[0]["health"] == "passing"
        assert services[0]["tags"] == ["groq", "llm"]
        
        # Verify consul was called correctly
        mock_consul_client.health.service.assert_called_once_with("groq-proxy", passing=True)
    
    @pytest.mark.asyncio
    async def test_discover_services_empty_result(self, consul_registry, mock_consul_client):
        """Test service discovery with no results"""
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, [])
        
        services = await consul_registry.discover_services("nonexistent-service")
        
        assert services == []
    
    @pytest.mark.asyncio
    async def test_discover_services_with_caching(self, consul_registry, mock_consul_client):
        """Test service discovery caching mechanism"""
        mock_services = [
            {
                "Service": {
                    "ID": "test-service-1",
                    "Service": "test-service",
                    "Address": "192.168.1.100",
                    "Port": 8000,
                    "Tags": [],
                    "Meta": {}
                },
                "Checks": [{"Status": "passing"}]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        # First call should hit consul
        services1 = await consul_registry.discover_services("test-service")
        assert len(services1) == 1
        
        # Second call within cache TTL should use cache
        services2 = await consul_registry.discover_services("test-service")
        assert len(services2) == 1
        
        # Consul should only be called once due to caching
        assert mock_consul_client.health.service.call_count == 1
    
    @pytest.mark.asyncio
    async def test_discover_services_cache_expiry(self, consul_registry, mock_consul_client):
        """Test service discovery cache expiry"""
        mock_services = [
            {
                "Service": {
                    "ID": "test-service-1",
                    "Service": "test-service",
                    "Address": "192.168.1.100",
                    "Port": 8000,
                    "Tags": [],
                    "Meta": {}
                },
                "Checks": [{"Status": "passing"}]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        # Set very short cache TTL for testing
        consul_registry.cache_ttl = 0.1  # 100ms
        
        # First call
        services1 = await consul_registry.discover_services("test-service")
        assert len(services1) == 1
        
        # Wait for cache to expire
        await asyncio.sleep(0.2)
        
        # Second call should hit consul again
        services2 = await consul_registry.discover_services("test-service")
        assert len(services2) == 1
        
        # Consul should be called twice due to cache expiry
        assert mock_consul_client.health.service.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_healthy_endpoints(self, consul_registry, mock_consul_client):
        """Test getting healthy service endpoints"""
        mock_services = [
            {
                "Service": {
                    "ID": "groq-proxy-1",
                    "Service": "groq-proxy",
                    "Address": "192.168.1.100",
                    "Port": 8000,
                    "Tags": ["primary"],
                    "Meta": {"weight": "100"}
                },
                "Checks": [{"Status": "passing"}]
            },
            {
                "Service": {
                    "ID": "groq-proxy-2",
                    "Service": "groq-proxy",
                    "Address": "192.168.1.101",
                    "Port": 8000,
                    "Tags": ["secondary"],
                    "Meta": {"weight": "50"}
                },
                "Checks": [{"Status": "passing"}]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        endpoints = await consul_registry.get_healthy_endpoints("groq-proxy")
        
        assert len(endpoints) == 2
        assert endpoints[0] == "http://192.168.1.100:8000"
        assert endpoints[1] == "http://192.168.1.101:8000"
    
    @pytest.mark.asyncio
    async def test_get_healthy_endpoints_with_weights(self, consul_registry, mock_consul_client):
        """Test getting healthy endpoints with weight-based ordering"""
        mock_services = [
            {
                "Service": {
                    "ID": "groq-proxy-1",
                    "Service": "groq-proxy",
                    "Address": "192.168.1.100",
                    "Port": 8000,
                    "Tags": [],
                    "Meta": {"weight": "50"}
                },
                "Checks": [{"Status": "passing"}]
            },
            {
                "Service": {
                    "ID": "groq-proxy-2",
                    "Service": "groq-proxy",
                    "Address": "192.168.1.101",
                    "Port": 8000,
                    "Tags": [],
                    "Meta": {"weight": "100"}
                },
                "Checks": [{"Status": "passing"}]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        endpoints = await consul_registry.get_healthy_endpoints("groq-proxy", sort_by_weight=True)
        
        # Should be sorted by weight (highest first)
        assert len(endpoints) == 2
        assert endpoints[0] == "http://192.168.1.101:8000"  # weight 100
        assert endpoints[1] == "http://192.168.1.100:8000"  # weight 50
    
    @pytest.mark.asyncio
    async def test_set_key_value(self, consul_registry, mock_consul_client):
        """Test setting key-value pairs in Consul KV store"""
        consul_registry.consul = mock_consul_client
        mock_consul_client.kv.put.return_value = True
        
        result = await consul_registry.set_key_value("config/groq/api_key", "secret-key-123")
        
        assert result is True
        mock_consul_client.kv.put.assert_called_once_with("config/groq/api_key", "secret-key-123")
    
    @pytest.mark.asyncio
    async def test_get_key_value(self, consul_registry, mock_consul_client):
        """Test getting key-value pairs from Consul KV store"""
        # Mock consul response format: (index, value)
        mock_response = (123, {"Value": b"secret-key-123"})
        consul_registry.consul = mock_consul_client
        mock_consul_client.kv.get.return_value = mock_response
        
        value = await consul_registry.get_key_value("config/groq/api_key")
        
        assert value == "secret-key-123"
        mock_consul_client.kv.get.assert_called_once_with("config/groq/api_key")
    
    @pytest.mark.asyncio
    async def test_get_key_value_not_found(self, consul_registry, mock_consul_client):
        """Test getting non-existent key returns None"""
        consul_registry.consul = mock_consul_client
        mock_consul_client.kv.get.return_value = (None, None)
        
        value = await consul_registry.get_key_value("nonexistent/key")
        
        assert value is None
    
    @pytest.mark.asyncio
    async def test_check_service_health(self, consul_registry, mock_consul_client):
        """Test checking health of a specific service"""
        mock_services = [
            {
                "Service": {"ID": "test-service-1"},
                "Checks": [
                    {"Status": "passing", "Output": "HTTP 200 OK"},
                    {"Status": "passing", "Output": "Service ready"}
                ]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        health = await consul_registry.check_service_health("test-service")
        
        assert health["healthy"] is True
        assert health["total_instances"] == 1
        assert health["healthy_instances"] == 1
        assert health["unhealthy_instances"] == 0
        assert "checks" in health
    
    @pytest.mark.asyncio
    async def test_check_service_health_mixed_status(self, consul_registry, mock_consul_client):
        """Test checking health with mixed healthy/unhealthy instances"""
        mock_services = [
            {
                "Service": {"ID": "test-service-1"},
                "Checks": [{"Status": "passing"}]
            },
            {
                "Service": {"ID": "test-service-2"},
                "Checks": [{"Status": "critical", "Output": "Connection failed"}]
            },
            {
                "Service": {"ID": "test-service-3"},
                "Checks": [{"Status": "warning", "Output": "High latency"}]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.return_value = (None, mock_services)
        
        health = await consul_registry.check_service_health("test-service")
        
        assert health["healthy"] is False  # Not all instances healthy
        assert health["total_instances"] == 3
        assert health["healthy_instances"] == 1
        assert health["unhealthy_instances"] == 2
    
    @pytest.mark.asyncio
    async def test_watch_service_changes(self, consul_registry, mock_consul_client):
        """Test watching for service changes"""
        # Mock initial service list
        initial_services = [
            {
                "Service": {
                    "ID": "service-1",
                    "Service": "test-service",
                    "Address": "192.168.1.100",
                    "Port": 8000
                },
                "Checks": [{"Status": "passing"}]
            }
        ]
        
        # Mock updated service list (new service added)
        updated_services = initial_services + [
            {
                "Service": {
                    "ID": "service-2",
                    "Service": "test-service",
                    "Address": "192.168.1.101",
                    "Port": 8000
                },
                "Checks": [{"Status": "passing"}]
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.health.service.side_effect = [
            (None, initial_services),
            (None, updated_services)
        ]
        
        # Callback to track changes
        changes = []
        
        def on_change(service_name, services):
            changes.append((service_name, len(services)))
        
        # Start watching (with short interval for testing)
        watch_task = asyncio.create_task(
            consul_registry.watch_service_changes("test-service", on_change, interval=0.1)
        )
        
        # Wait for initial discovery and one update
        await asyncio.sleep(0.3)
        
        # Stop watching
        watch_task.cancel()
        
        # Verify changes were detected
        assert len(changes) >= 1
        assert changes[0] == ("test-service", 1)  # Initial state
        if len(changes) > 1:
            assert changes[1] == ("test-service", 2)  # Updated state
    
    @pytest.mark.asyncio
    async def test_get_service_catalog(self, consul_registry, mock_consul_client):
        """Test getting service catalog information"""
        mock_catalog = [
            {
                "ServiceName": "groq-proxy",
                "ServiceTags": ["groq", "llm"],
                "ServiceAddress": "192.168.1.100",
                "ServicePort": 8000,
                "ServiceMeta": {"version": "1.0.0"}
            },
            {
                "ServiceName": "model-service",
                "ServiceTags": ["models", "registry"],
                "ServiceAddress": "192.168.1.200",
                "ServicePort": 8001,
                "ServiceMeta": {"version": "1.0.0"}
            }
        ]
        
        consul_registry.consul = mock_consul_client
        mock_consul_client.catalog.service.side_effect = [
            (None, [mock_catalog[0]]),  # groq-proxy
            (None, [mock_catalog[1]])   # model-service
        ]
        
        catalog = await consul_registry.get_service_catalog()
        
        assert len(catalog) >= 2  # Should include services from discovery
        
        # Verify catalog format
        service_names = [service["name"] for service in catalog]
        assert "groq-proxy" in service_names
        assert "model-service" in service_names
    
    def test_format_service_endpoint(self, consul_registry):
        """Test endpoint formatting utility"""
        service = {
            "address": "192.168.1.100",
            "port": 8000
        }
        
        endpoint = consul_registry._format_service_endpoint(service)
        assert endpoint == "http://192.168.1.100:8000"
        
        # Test with HTTPS
        endpoint_https = consul_registry._format_service_endpoint(service, use_https=True)
        assert endpoint_https == "https://192.168.1.100:8000"
    
    def test_is_service_healthy(self, consul_registry):
        """Test service health status checking"""
        # Healthy service
        healthy_checks = [
            {"Status": "passing"},
            {"Status": "passing"}
        ]
        assert consul_registry._is_service_healthy(healthy_checks) is True
        
        # Unhealthy service
        unhealthy_checks = [
            {"Status": "passing"},
            {"Status": "critical"}
        ]
        assert consul_registry._is_service_healthy(unhealthy_checks) is False
        
        # Warning service (should be considered unhealthy)
        warning_checks = [
            {"Status": "warning"}
        ]
        assert consul_registry._is_service_healthy(warning_checks) is False
        
        # No checks (assume unhealthy)
        assert consul_registry._is_service_healthy([]) is False
    
    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, consul_registry, mock_consul_client):
        """Test concurrent service registration and discovery operations"""
        consul_registry.consul = mock_consul_client
        mock_consul_client.agent.service.register.return_value = True
        mock_consul_client.health.service.return_value = (None, [])
        
        # Create multiple service registration tasks
        async def register_service(service_id):
            return await consul_registry.register_service(
                service_id=service_id,
                service_name="test-service",
                address="192.168.1.100",
                port=8000
            )
        
        # Run concurrent operations
        tasks = [register_service(f"service-{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)
        assert mock_consul_client.agent.service.register.call_count == 5
    
    @pytest.mark.asyncio
    async def test_error_handling_consul_unavailable(self, consul_registry):
        """Test error handling when Consul is unavailable"""
        # Don't set consul client to simulate unavailable Consul
        consul_registry.consul = None
        
        # All operations should handle the missing client gracefully
        result = await consul_registry.register_service(
            service_id="test", service_name="test", address="127.0.0.1", port=8000
        )
        assert result is False
        
        services = await consul_registry.discover_services("test")
        assert services == []
        
        health = await consul_registry.check_service_health("test")
        assert health["healthy"] is False
        assert "Consul client not available" in health.get("error", "")


@pytest.mark.integration
class TestConsulServiceRegistryIntegration:
    """Integration tests for ConsulServiceRegistry"""
    
    @pytest.mark.asyncio
    async def test_full_service_lifecycle(self, mock_settings):
        """Test complete service lifecycle with Consul integration"""
        mock_settings.consul_host = "localhost"
        mock_settings.consul_port = 8500
        
        # Mock consul responses for full lifecycle
        with patch('consul.Consul') as mock_consul_class:
            mock_consul = Mock()
            mock_consul.agent.service.register = AsyncMock(return_value=True)
            mock_consul.agent.service.deregister = AsyncMock(return_value=True)
            mock_consul.health.service = AsyncMock(return_value=(None, [{
                "Service": {
                    "ID": "integration-test-service",
                    "Service": "integration-test",
                    "Address": "192.168.1.100",
                    "Port": 8000,
                    "Tags": ["test"],
                    "Meta": {"version": "1.0.0"}
                },
                "Checks": [{"Status": "passing"}]
            }]))
            mock_consul_class.return_value = mock_consul
            
            # Create registry
            registry = ConsulServiceRegistry()
            
            # 1. Register service
            result = await registry.register_service(
                service_id="integration-test-service",
                service_name="integration-test",
                address="192.168.1.100",
                port=8000,
                tags=["test"],
                meta={"version": "1.0.0"}
            )
            assert result is True
            
            # 2. Discover services
            services = await registry.discover_services("integration-test")
            assert len(services) == 1
            assert services[0]["id"] == "integration-test-service"
            
            # 3. Check health
            health = await registry.check_service_health("integration-test")
            assert health["healthy"] is True
            assert health["total_instances"] == 1
            
            # 4. Get healthy endpoints
            endpoints = await registry.get_healthy_endpoints("integration-test")
            assert len(endpoints) == 1
            assert endpoints[0] == "http://192.168.1.100:8000"
            
            # 5. Deregister service
            result = await registry.deregister_service("integration-test-service")
            assert result is True
            
            # Verify all consul operations were called
            mock_consul.agent.service.register.assert_called_once()
            mock_consul.agent.service.deregister.assert_called_once_with("integration-test-service")
            mock_consul.health.service.assert_called()