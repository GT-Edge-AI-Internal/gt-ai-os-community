"""
Unit tests for Groq service
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import httpx

from app.services.groq_service import GroqClient, GroqService, GroqAPIError, groq_service
from app.models.ai_resource import AIResource


@pytest.fixture
def mock_ai_resource():
    """Create a mock AI resource for testing"""
    resource = Mock(spec=AIResource)
    resource.id = 1
    resource.name = "Test Groq Model"
    resource.provider = "groq"
    resource.model_name = "llama2-70b-4096"
    resource.api_endpoints = ["https://api.groq.com/openai/v1"]
    resource.primary_endpoint = "https://api.groq.com/openai/v1"
    resource.failover_endpoints = ["https://backup.groq.com/openai/v1"]
    resource.health_check_url = "https://api.groq.com/openai/v1/models"
    resource.latency_sla_ms = 3000
    resource.cost_per_1k_tokens = 0.0005
    resource.configuration = {"temperature": 0.7, "max_tokens": 4000}
    resource.get_available_endpoints.return_value = [
        "https://api.groq.com/openai/v1",
        "https://backup.groq.com/openai/v1"
    ]
    resource.merge_config.return_value = {
        "temperature": 0.7,
        "max_tokens": 4000,
        "top_p": 1.0
    }
    resource.calculate_cost.return_value = 50  # 50 cents for 1000 tokens
    resource.update_health_status = Mock()
    return resource


@pytest.fixture
def api_key():
    """Test API key"""
    return "test-api-key-12345"


class TestGroqClient:
    """Test the GroqClient class"""
    
    @pytest.mark.asyncio
    async def test_init(self, mock_ai_resource, api_key):
        """Test GroqClient initialization"""
        client = GroqClient(mock_ai_resource, api_key)
        
        assert client.resource == mock_ai_resource
        assert client.api_key == api_key
        assert client._current_endpoint_index == 0
        assert client._endpoint_failures == {}
        assert client._rate_limit_reset is None
        
        # Cleanup
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_get_next_endpoint_healthy(self, mock_ai_resource, api_key):
        """Test getting next endpoint when all are healthy"""
        client = GroqClient(mock_ai_resource, api_key)
        
        endpoint = client._get_next_endpoint()
        assert endpoint == "https://api.groq.com/openai/v1"
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_get_next_endpoint_with_failures(self, mock_ai_resource, api_key):
        """Test getting next endpoint when primary has failed"""
        client = GroqClient(mock_ai_resource, api_key)
        
        # Mark primary endpoint as failed
        client._mark_endpoint_failed("https://api.groq.com/openai/v1")
        
        endpoint = client._get_next_endpoint()
        assert endpoint == "https://backup.groq.com/openai/v1"
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_mark_endpoint_failed_exponential_backoff(self, mock_ai_resource, api_key):
        """Test endpoint failure tracking with exponential backoff"""
        client = GroqClient(mock_ai_resource, api_key)
        endpoint = "https://api.groq.com/openai/v1"
        
        # First failure - 5 minute backoff
        client._mark_endpoint_failed(endpoint, 1)  # Use 1 minute for faster testing
        assert endpoint in client._endpoint_failures
        assert client._endpoint_failures[endpoint]["count"] == 1
        
        # Second failure - 2 minute backoff
        client._mark_endpoint_failed(endpoint, 1)
        assert client._endpoint_failures[endpoint]["count"] == 2
        
        # Third failure - 4 minute backoff
        client._mark_endpoint_failed(endpoint, 1)
        assert client._endpoint_failures[endpoint]["count"] == 3
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_reset_endpoint_failures(self, mock_ai_resource, api_key):
        """Test resetting endpoint failures on success"""
        client = GroqClient(mock_ai_resource, api_key)
        endpoint = "https://api.groq.com/openai/v1"
        
        # Mark as failed
        client._mark_endpoint_failed(endpoint)
        assert endpoint in client._endpoint_failures
        
        # Reset on success
        client._reset_endpoint_failures(endpoint)
        assert endpoint not in client._endpoint_failures
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_ai_resource, api_key):
        """Test successful health check"""
        with patch.object(GroqClient, '_make_request') as mock_request:
            mock_request.return_value = {"data": [{"id": "llama2-70b-4096"}]}
            
            client = GroqClient(mock_ai_resource, api_key)
            result = await client.health_check()
            
            assert result is True
            mock_request.assert_called_once_with("GET", "models")
            
            await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_ai_resource, api_key):
        """Test failed health check"""
        with patch.object(GroqClient, '_make_request') as mock_request:
            mock_request.side_effect = GroqAPIError("Connection failed")
            
            client = GroqClient(mock_ai_resource, api_key)
            result = await client.health_check()
            
            assert result is False
            
            await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_chat_completion_success(self, mock_ai_resource, api_key):
        """Test successful chat completion"""
        mock_response = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hello! How can I help you?"}}],
            "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10},
            "model": "llama2-70b-4096"
        }
        
        with patch.object(GroqClient, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            client = GroqClient(mock_ai_resource, api_key)
            
            messages = [{"role": "user", "content": "Hello"}]
            result = await client.chat_completion(messages)
            
            assert "id" in result
            assert "choices" in result
            assert "usage" in result
            assert "_metadata" in result
            assert "latency_ms" in result["_metadata"]
            
            # Verify request payload
            expected_payload = {
                "model": "llama2-70b-4096",
                "messages": messages,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 4000,
                "top_p": 1.0
            }
            mock_request.assert_called_once_with("POST", "chat/completions", json=expected_payload)
            
            await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_chat_completion_with_custom_config(self, mock_ai_resource, api_key):
        """Test chat completion with custom configuration"""
        mock_response = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"total_tokens": 15},
            "model": "llama2-70b-4096"
        }
        
        with patch.object(GroqClient, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            client = GroqClient(mock_ai_resource, api_key)
            
            messages = [{"role": "user", "content": "Test"}]
            result = await client.chat_completion(
                messages,
                model="custom-model",
                temperature=0.9,
                max_tokens=2000
            )
            
            # Verify custom config was used
            call_args = mock_request.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "custom-model"
            # Temperature from custom config should override resource config
            # (exact behavior depends on merge_config implementation)
            
            await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_make_request_with_failover(self, mock_ai_resource, api_key):
        """Test HTTP request with automatic failover"""
        async def mock_request_side_effect(method, url, **kwargs):
            if "api.groq.com" in url:
                # Primary endpoint fails
                raise httpx.RequestError("Connection failed")
            else:
                # Backup endpoint succeeds
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"success": True}
                return mock_response
        
        client = GroqClient(mock_ai_resource, api_key)
        
        with patch.object(client.client, 'request', side_effect=mock_request_side_effect):
            result = await client._make_request("GET", "test")
            assert result == {"success": True}
            
            # Primary endpoint should be marked as failed
            assert "https://api.groq.com/openai/v1" in client._endpoint_failures
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_make_request_rate_limit(self, mock_ai_resource, api_key):
        """Test handling of rate limit response"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "60"}
        
        client = GroqClient(mock_ai_resource, api_key)
        
        with patch.object(client.client, 'request', return_value=mock_response):
            with pytest.raises(GroqAPIError) as exc_info:
                await client._make_request("GET", "test")
            
            assert "Rate limited" in str(exc_info.value)
            assert exc_info.value.status_code == 429
            assert client._rate_limit_reset is not None
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_make_request_server_error_with_failover(self, mock_ai_resource, api_key):
        """Test server error handling with failover"""
        responses = [
            Mock(status_code=500, text="Server Error"),  # Primary fails
            Mock(status_code=200, json=lambda: {"success": True})  # Backup succeeds
        ]
        
        client = GroqClient(mock_ai_resource, api_key)
        
        with patch.object(client.client, 'request', side_effect=responses):
            result = await client._make_request("GET", "test")
            assert result == {"success": True}
        
        await client.client.aclose()
    
    @pytest.mark.asyncio
    async def test_make_request_all_endpoints_fail(self, mock_ai_resource, api_key):
        """Test when all endpoints fail"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        
        client = GroqClient(mock_ai_resource, api_key)
        
        with patch.object(client.client, 'request', return_value=mock_response):
            with pytest.raises(GroqAPIError) as exc_info:
                await client._make_request("GET", "test")
            
            assert "No healthy endpoints available" in str(exc_info.value)


class TestGroqService:
    """Test the GroqService class"""
    
    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self, mock_ai_resource, api_key):
        """Test that get_client creates a new client for new resource"""
        service = GroqService()
        
        async with service.get_client(mock_ai_resource, api_key) as client:
            assert isinstance(client, GroqClient)
            assert client.resource == mock_ai_resource
            assert client.api_key == api_key
        
        # Client should be cached
        assert mock_ai_resource.id in service._clients
    
    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_client(self, mock_ai_resource, api_key):
        """Test that get_client reuses existing client"""
        service = GroqService()
        
        # First call creates client
        async with service.get_client(mock_ai_resource, api_key) as client1:
            client_id_1 = id(client1)
        
        # Second call should reuse same client
        async with service.get_client(mock_ai_resource, api_key) as client2:
            client_id_2 = id(client2)
        
        assert client_id_1 == client_id_2
    
    @pytest.mark.asyncio
    async def test_health_check_resource_success(self, mock_ai_resource, api_key):
        """Test successful resource health check"""
        service = GroqService()
        
        with patch.object(GroqClient, 'health_check', return_value=True):
            result = await service.health_check_resource(mock_ai_resource, api_key)
            
            assert result is True
            mock_ai_resource.update_health_status.assert_called_with("healthy")
    
    @pytest.mark.asyncio
    async def test_health_check_resource_failure(self, mock_ai_resource, api_key):
        """Test failed resource health check"""
        service = GroqService()
        
        with patch.object(GroqClient, 'health_check', side_effect=Exception("Connection failed")):
            result = await service.health_check_resource(mock_ai_resource, api_key)
            
            assert result is False
            mock_ai_resource.update_health_status.assert_called_with("unhealthy")
    
    @pytest.mark.asyncio
    async def test_chat_completion_with_usage_tracking(self, mock_ai_resource, api_key):
        """Test chat completion with usage tracking"""
        service = GroqService()
        
        mock_response = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"total_tokens": 100},
            "_metadata": {
                "model_used": "llama2-70b-4096",
                "latency_ms": 500
            }
        }
        
        with patch.object(GroqClient, 'chat_completion', return_value=mock_response):
            result = await service.chat_completion(
                mock_ai_resource,
                api_key,
                [{"role": "user", "content": "Hello"}],
                "user@example.com",
                1
            )
            
            assert "_usage_record" in result
            usage_record = result["_usage_record"]
            assert usage_record["tenant_id"] == 1
            assert usage_record["resource_id"] == 1
            assert usage_record["user_email"] == "user@example.com"
            assert usage_record["tokens_used"] == 100
            assert usage_record["cost_cents"] == 50  # Based on mock calculate_cost
    
    @pytest.mark.asyncio
    async def test_cleanup_clients(self):
        """Test client cleanup"""
        service = GroqService()
        
        # Add some mock clients
        mock_client1 = Mock()
        mock_client1.client.aclose = AsyncMock()
        mock_client2 = Mock()
        mock_client2.client.aclose = AsyncMock()
        
        service._clients[1] = mock_client1
        service._clients[2] = mock_client2
        
        await service.cleanup_clients()
        
        # All clients should be closed and removed
        assert len(service._clients) == 0
        mock_client1.client.aclose.assert_called_once()
        mock_client2.client.aclose.assert_called_once()


class TestGroqAPIError:
    """Test the GroqAPIError exception"""
    
    def test_groq_api_error_init(self):
        """Test GroqAPIError initialization"""
        error = GroqAPIError("Test error", 400, "Bad request")
        
        assert str(error) == "Test error"
        assert error.status_code == 400
        assert error.response_body == "Bad request"
    
    def test_groq_api_error_without_optional_params(self):
        """Test GroqAPIError with only message"""
        error = GroqAPIError("Test error")
        
        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.response_body is None


@pytest.mark.integration
class TestGroqServiceIntegration:
    """Integration tests for Groq service (require actual API or better mocking)"""
    
    @pytest.mark.asyncio
    async def test_full_chat_completion_flow(self, mock_ai_resource, api_key):
        """Test full chat completion flow with mocked HTTP responses"""
        # Mock the entire HTTP request/response cycle
        mock_response_data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "llama2-70b-4096",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "agent",
                    "content": "Hello! I'm a helpful agent. How can I help you today?"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }
        
        async def mock_request(method, url, **kwargs):
            response = Mock()
            response.status_code = 200
            response.json.return_value = mock_response_data
            return response
        
        with patch('httpx.AsyncClient.request', side_effect=mock_request):
            service = GroqService()
            
            result = await service.chat_completion(
                mock_ai_resource,
                api_key,
                [{"role": "user", "content": "Hello"}],
                "user@example.com",
                tenant_id=1
            )
            
            # Verify response structure
            assert result["id"] == "chatcmpl-123"
            assert result["model"] == "llama2-70b-4096"
            assert result["usage"]["total_tokens"] == 25
            assert "_usage_record" in result
            assert "_metadata" in result
            
            # Verify usage tracking
            usage = result["_usage_record"]
            assert usage["tokens_used"] == 25
            assert usage["tenant_id"] == 1
            assert usage["user_email"] == "user@example.com"