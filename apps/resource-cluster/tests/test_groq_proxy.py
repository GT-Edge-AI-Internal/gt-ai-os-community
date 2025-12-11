"""
Unit tests for Groq Proxy Backend with HAProxy Integration
"""
import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import httpx
from faker import Faker

from app.core.backends.groq_proxy import GroqProxyBackend

fake = Faker()


@pytest.fixture
def groq_proxy(mock_settings):
    """Create GroqProxyBackend instance with mocked settings"""
    with patch('app.core.backends.groq_proxy.get_settings', return_value=mock_settings):
        proxy = GroqProxyBackend()
        return proxy


@pytest.fixture
def mock_groq_client():
    """Mock AsyncGroq client"""
    client = Mock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def mock_model_service():
    """Mock model service for groq proxy tests"""
    service = Mock()
    service.get_model = AsyncMock()
    service.track_model_usage = AsyncMock()
    return service


@pytest.fixture
def sample_groq_response():
    """Sample Groq API response"""
    return Mock(
        choices=[Mock(message=Mock(content="This is a test response"))],
        usage=Mock(
            prompt_tokens=10,
            completion_tokens=15,
            total_tokens=25
        ),
        model="llama-3.1-70b-versatile"
    )


class TestGroqProxyBackend:
    """Test the GroqProxyBackend class"""
    
    def test_initialization_with_haproxy(self, mock_settings):
        """Test GroqProxyBackend initialization with HAProxy configuration"""
        mock_settings.groq_api_key = "test-api-key"
        mock_settings.haproxy_groq_endpoint = "http://test-haproxy:8000"
        mock_settings.haproxy_enabled = True
        
        with patch('app.core.backends.groq_proxy.get_settings', return_value=mock_settings), \
             patch('groq.AsyncGroq') as mock_groq_class:
            
            proxy = GroqProxyBackend()
            
            # Verify AsyncGroq was initialized with HAProxy endpoint
            mock_groq_class.assert_called_once_with(
                api_key="test-api-key",
                base_url="http://test-haproxy:8000",
                timeout=httpx.Timeout(30.0),
                max_retries=1
            )
            
            # Verify circuit breaker initialization
            assert proxy.circuit_breaker_status["state"] == "closed"
            assert proxy.circuit_breaker_status["failure_count"] == 0
            assert proxy.circuit_breaker_status["failure_threshold"] == 5
            assert proxy.circuit_breaker_status["recovery_timeout"] == 60
    
    def test_initialization_without_api_key(self, mock_settings):
        """Test initialization when Groq API key is not provided"""
        mock_settings.groq_api_key = None
        
        with patch('app.core.backends.groq_proxy.get_settings', return_value=mock_settings):
            proxy = GroqProxyBackend()
            assert proxy.client is None
    
    @pytest.mark.asyncio
    async def test_execute_inference_success(self, groq_proxy, sample_groq_response, mock_model_service):
        """Test successful LLM inference execution"""
        # Mock the client and model service
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(return_value=sample_groq_response)
        
        with patch('app.core.backends.groq_proxy.model_service', mock_model_service):
            mock_model_service.get_model.return_value = None  # Use built-in config
            
            result = await groq_proxy.execute_inference(
                prompt="Hello, how are you?",
                model="llama-3.1-70b-versatile",
                temperature=0.7,
                max_tokens=4000,
                user_id="test-user",
                tenant_id="test-tenant"
            )
        
        assert result["content"] == "This is a test response"
        assert result["model"] == "llama-3.1-70b-versatile"
        assert result["usage"]["total_tokens"] == 25
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 15
        assert result["load_balanced"] is True
        assert result["haproxy_backend"] == "groq_general_backend"
        assert "latency_ms" in result
        assert "cost_cents" in result["usage"]
        
        # Verify model usage tracking was called
        mock_model_service.track_model_usage.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_inference_with_model_service_config(self, groq_proxy, sample_groq_response, mock_model_service):
        """Test inference with model configuration from model service"""
        # Mock model service returning model info
        mock_model_info = {
            "performance": {
                "max_tokens": 8000,
                "cost_per_1k_tokens": 0.59
            },
            "capabilities": {"streaming": True}
        }
        mock_model_service.get_model.return_value = mock_model_info
        
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(return_value=sample_groq_response)
        
        with patch('app.core.backends.groq_proxy.model_service', mock_model_service):
            result = await groq_proxy.execute_inference(
                prompt="Test prompt",
                model="custom-model",
                max_tokens=10000,  # Should be limited by model config
                user_id="test-user",
                tenant_id="test-tenant"
            )
        
        # Verify max_tokens was limited by model configuration
        call_args = groq_proxy.client.chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 8000  # Limited by model config
    
    @pytest.mark.asyncio
    async def test_execute_inference_circuit_breaker_open(self, groq_proxy):
        """Test inference when circuit breaker is open"""
        # Set circuit breaker to open state
        groq_proxy.circuit_breaker_status["state"] = "open"
        groq_proxy.circuit_breaker_status["failure_count"] = 5
        groq_proxy.circuit_breaker_status["last_failure_time"] = datetime.utcnow()
        
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await groq_proxy.execute_inference(
                prompt="Test prompt",
                model="llama-3.1-70b-versatile"
            )
    
    @pytest.mark.asyncio
    async def test_execute_inference_circuit_breaker_recovery(self, groq_proxy, sample_groq_response):
        """Test circuit breaker recovery after timeout"""
        # Set circuit breaker to open state but with old failure time
        groq_proxy.circuit_breaker_status["state"] = "open"
        groq_proxy.circuit_breaker_status["failure_count"] = 5
        groq_proxy.circuit_breaker_status["last_failure_time"] = datetime.utcnow() - timedelta(minutes=2)
        
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(return_value=sample_groq_response)
        
        with patch('app.core.backends.groq_proxy.model_service'):
            result = await groq_proxy.execute_inference(
                prompt="Test prompt",
                model="llama-3.1-70b-versatile"
            )
        
        # Circuit should have moved to half-open and then closed on success
        assert groq_proxy.circuit_breaker_status["state"] == "closed"
        assert groq_proxy.circuit_breaker_status["failure_count"] == 0
        assert result["content"] == "This is a test response"
    
    @pytest.mark.asyncio
    async def test_execute_inference_failure_tracking(self, groq_proxy, mock_model_service):
        """Test failure tracking and circuit breaker logic"""
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(side_effect=Exception("Connection failed"))
        
        with patch('app.core.backends.groq_proxy.model_service', mock_model_service):
            with pytest.raises(Exception, match="Groq inference failed"):
                await groq_proxy.execute_inference(
                    prompt="Test prompt",
                    model="llama-3.1-70b-versatile"
                )
        
        # Verify failure was tracked
        assert groq_proxy.circuit_breaker_status["failure_count"] == 1
        assert groq_proxy.circuit_breaker_status["last_failure_time"] is not None
        
        # Verify model service was called to track failure
        mock_model_service.track_model_usage.assert_called_once_with(
            model_id="llama-3.1-70b-versatile",
            success=False
        )
    
    @pytest.mark.asyncio
    async def test_execute_inference_multiple_failures_open_circuit(self, groq_proxy, mock_model_service):
        """Test that multiple failures open the circuit breaker"""
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(side_effect=Exception("Connection failed"))
        
        with patch('app.core.backends.groq_proxy.model_service', mock_model_service):
            # Trigger multiple failures
            for i in range(5):
                with pytest.raises(Exception):
                    await groq_proxy.execute_inference(
                        prompt="Test prompt",
                        model="llama-3.1-70b-versatile"
                    )
        
        # Circuit breaker should be open after threshold failures
        assert groq_proxy.circuit_breaker_status["state"] == "open"
        assert groq_proxy.circuit_breaker_status["failure_count"] == 5
    
    @pytest.mark.asyncio
    async def test_stream_inference(self, groq_proxy):
        """Test streaming inference functionality"""
        # Mock streaming response
        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock(delta=Mock(content="Hello "))]
        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock(delta=Mock(content="world!"))]
        mock_chunk3 = Mock()
        mock_chunk3.choices = [Mock(delta=Mock(content=None))]  # End of stream
        
        async def mock_stream():
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                yield chunk
        
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(return_value=mock_stream())
        
        # Collect streaming results
        results = []
        async for chunk in groq_proxy.execute_inference(
            prompt="Test prompt",
            model="llama-3.1-70b-versatile",
            stream=True,
            user_id="test-user",
            tenant_id="test-tenant"
        ):
            results.append(chunk)
        
        # Verify streaming output
        assert len(results) >= 2  # Should have content chunks plus completion signal
        assert "Hello " in results[0]
        assert "world!" in results[1]
    
    @pytest.mark.asyncio
    async def test_check_health_success(self, groq_proxy, mock_settings):
        """Test successful health check via HAProxy stats"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "groq_general_backend,groq-primary-1,UP,100,1,0"
        
        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__.return_value = mock_client
            
            health = await groq_proxy.check_health()
        
        assert health["haproxy_load_balancer"]["healthy"] is True
        assert health["haproxy_load_balancer"]["stats_accessible"] is True
        assert health["circuit_breaker"]["state"] == "closed"
        assert health["groq_endpoints"]["managed_by"] == "haproxy"
        assert "last_check" in health["haproxy_load_balancer"]
    
    @pytest.mark.asyncio
    async def test_check_health_haproxy_failure(self, groq_proxy, mock_settings):
        """Test health check when HAProxy stats are unavailable"""
        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = Mock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_httpx.return_value.__aenter__.return_value = mock_client
            
            health = await groq_proxy.check_health()
        
        assert health["haproxy_load_balancer"]["healthy"] is False
        assert "Connection refused" in health["haproxy_load_balancer"]["error"]
        assert health["circuit_breaker"]["state"] == "closed"
    
    @pytest.mark.asyncio
    async def test_check_health_stats_endpoint_error(self, groq_proxy, mock_settings):
        """Test health check when HAProxy stats return HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 503
        
        with patch('httpx.AsyncClient') as mock_httpx:
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__.return_value = mock_client
            
            health = await groq_proxy.check_health()
        
        assert health["haproxy_load_balancer"]["healthy"] is False
        assert "Stats endpoint returned 503" in health["haproxy_load_balancer"]["error"]
    
    def test_circuit_breaker_state_transitions(self, groq_proxy):
        """Test circuit breaker state transitions"""
        # Initial state should be closed
        assert groq_proxy.circuit_breaker_status["state"] == "closed"
        
        # Record failures to open circuit
        for i in range(5):
            asyncio.run(groq_proxy._record_failure())
        
        assert groq_proxy.circuit_breaker_status["state"] == "open"
        assert groq_proxy.circuit_breaker_status["failure_count"] == 5
        
        # Move to half-open after timeout
        groq_proxy.circuit_breaker_status["last_failure_time"] = datetime.utcnow() - timedelta(minutes=2)
        is_closed = asyncio.run(groq_proxy._is_circuit_closed())
        assert is_closed is True
        assert groq_proxy.circuit_breaker_status["state"] == "half_open"
        
        # Success in half-open should close circuit
        asyncio.run(groq_proxy._record_success())
        assert groq_proxy.circuit_breaker_status["state"] == "closed"
        assert groq_proxy.circuit_breaker_status["failure_count"] == 0
    
    def test_usage_tracking(self, groq_proxy):
        """Test usage metrics tracking"""
        # Track some usage
        asyncio.run(groq_proxy._track_usage(
            user_id="user1",
            tenant_id="tenant1", 
            model="llama-3.1-70b",
            tokens=100,
            latency=1500.0,
            cost_per_1k=0.59
        ))
        
        usage_key = "tenant1:user1:llama-3.1-70b"
        metrics = groq_proxy.usage_metrics[usage_key]
        
        assert metrics["total_tokens"] == 100
        assert metrics["total_requests"] == 1
        assert metrics["total_cost_cents"] == 5  # 100/1000 * 0.59 * 100
        assert metrics["average_latency"] == 1500.0
        
        # Track more usage
        asyncio.run(groq_proxy._track_usage(
            user_id="user1",
            tenant_id="tenant1",
            model="llama-3.1-70b", 
            tokens=200,
            latency=1200.0,
            cost_per_1k=0.59
        ))
        
        metrics = groq_proxy.usage_metrics[usage_key]
        assert metrics["total_tokens"] == 300
        assert metrics["total_requests"] == 2
        assert metrics["total_cost_cents"] == 17  # (100+200)/1000 * 0.59 * 100
        assert metrics["average_latency"] == 1350.0  # (1500 + 1200) / 2
    
    def test_cost_calculation(self, groq_proxy):
        """Test cost calculation accuracy"""
        # Test cost calculation
        cost = groq_proxy._calculate_cost(1000, 0.59)
        assert cost == 59  # 1000/1000 * 0.59 * 100
        
        cost = groq_proxy._calculate_cost(500, 1.20)
        assert cost == 60  # 500/1000 * 1.20 * 100
        
        cost = groq_proxy._calculate_cost(1500, 0.30)
        assert cost == 45  # 1500/1000 * 0.30 * 100
    
    @pytest.mark.asyncio
    async def test_get_available_models(self, groq_proxy):
        """Test getting available Groq models"""
        models = await groq_proxy.get_available_models()
        
        assert len(models) > 0
        
        # Check model structure
        for model in models:
            assert "id" in model
            assert "name" in model
            assert "provider" in model
            assert model["provider"] == "groq"
            assert "max_tokens" in model
            assert "cost_per_1k_tokens" in model
            assert "supports_streaming" in model
            assert "supports_function_calling" in model
    
    @pytest.mark.asyncio
    async def test_invalid_model_handling(self, groq_proxy, mock_model_service):
        """Test handling of invalid model requests"""
        groq_proxy.client = Mock()
        mock_model_service.get_model.return_value = None
        
        with patch('app.core.backends.groq_proxy.model_service', mock_model_service):
            with pytest.raises(ValueError, match="Unsupported model"):
                await groq_proxy.execute_inference(
                    prompt="Test prompt",
                    model="nonexistent-model"
                )
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, groq_proxy, sample_groq_response, mock_model_service):
        """Test handling concurrent inference requests"""
        groq_proxy.client = Mock()
        groq_proxy.client.chat.completions.create = AsyncMock(return_value=sample_groq_response)
        
        async def make_request(request_id):
            with patch('app.core.backends.groq_proxy.model_service', mock_model_service):
                return await groq_proxy.execute_inference(
                    prompt=f"Request {request_id}",
                    model="llama-3.1-70b-versatile",
                    user_id=f"user-{request_id}",
                    tenant_id="test-tenant"
                )
        
        # Make 10 concurrent requests
        tasks = [make_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert len(results) == 10
        for result in results:
            assert result["content"] == "This is a test response"
            assert result["load_balanced"] is True
        
        # Usage tracking should have been called for each request
        assert mock_model_service.track_model_usage.call_count == 10


@pytest.mark.integration
class TestGroqProxyIntegration:
    """Integration tests for GroqProxyBackend"""
    
    @pytest.mark.asyncio
    async def test_full_inference_workflow(self, mock_settings):
        """Test complete inference workflow with HAProxy integration"""
        mock_settings.groq_api_key = "test-api-key"
        mock_settings.haproxy_groq_endpoint = "http://test-haproxy:8000"
        
        # Mock successful Groq response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Integration test response"))]
        mock_response.usage = Mock(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        mock_response.model = "llama-3.1-70b-versatile"
        
        with patch('app.core.backends.groq_proxy.get_settings', return_value=mock_settings), \
             patch('groq.AsyncGroq') as mock_groq_class, \
             patch('app.core.backends.groq_proxy.model_service') as mock_model_service:
            
            # Setup mocks
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_groq_class.return_value = mock_client
            mock_model_service.get_model.return_value = None
            mock_model_service.track_model_usage = AsyncMock()
            
            # Create proxy and execute inference
            proxy = GroqProxyBackend()
            result = await proxy.execute_inference(
                prompt="Integration test prompt",
                model="llama-3.1-70b-versatile",
                temperature=0.7,
                max_tokens=4000,
                user_id="integration-user",
                tenant_id="integration-tenant"
            )
            
            # Verify results
            assert result["content"] == "Integration test response"
            assert result["model"] == "llama-3.1-70b-versatile"
            assert result["usage"]["total_tokens"] == 15
            assert result["load_balanced"] is True
            assert result["haproxy_backend"] == "groq_general_backend"
            
            # Verify HAProxy configuration was used
            mock_groq_class.assert_called_once_with(
                api_key="test-api-key",
                base_url="http://test-haproxy:8000",
                timeout=httpx.Timeout(30.0),
                max_retries=1
            )
            
            # Verify usage tracking
            mock_model_service.track_model_usage.assert_called_once_with(
                model_id="llama-3.1-70b-versatile",
                success=True,
                latency_ms=pytest.approx(0, abs=5000)  # Allow reasonable latency range
            )