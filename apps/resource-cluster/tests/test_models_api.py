"""
Unit tests for Model Management API endpoints
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from httpx import AsyncClient
from faker import Faker

from app.api.v1.models import router
from app.services.model_service import ModelService

fake = Faker()


@pytest.fixture
def mock_model_service():
    """Mock ModelService for API testing"""
    service = Mock(spec=ModelService)
    service.register_model = AsyncMock()
    service.get_model = AsyncMock()
    service.list_models = AsyncMock()
    service.update_model_status = AsyncMock()
    service.retire_model = AsyncMock()
    service.check_model_health = AsyncMock()
    return service


@pytest.fixture
def sample_model_response():
    """Sample model response from service"""
    return {
        "id": "test-llama-70b",
        "name": "Test Llama 70B",
        "version": "1.0.0",
        "provider": "groq",
        "model_type": "llm",
        "description": "Test model for unit testing",
        "capabilities": {"streaming": True, "function_calling": True},
        "parameters": {"temperature": 0.7, "max_tokens": 8000},
        "performance": {
            "max_tokens": 8000,
            "cost_per_1k_tokens": 0.59,
            "latency_p50_ms": 1500.0,
            "latency_p95_ms": 2250.0
        },
        "status": {
            "deployment": "available",
            "health": "healthy",
            "last_health_check": "2024-01-15T10:30:00Z"
        },
        "usage": {
            "request_count": 100,
            "error_count": 2,
            "success_rate": 0.98
        },
        "lifecycle": {
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "retired_at": None
        }
    }


class TestModelsAPI:
    """Test the Models API endpoints"""
    
    @pytest.mark.asyncio
    async def test_register_model_success(self, client, auth_headers, mock_model_service, sample_model_response):
        """Test successful model registration via API"""
        # Mock service response
        mock_model_service.register_model.return_value = sample_model_response
        
        # Request data
        model_data = {
            "model_id": "test-llama-70b",
            "name": "Test Llama 70B",
            "version": "1.0.0",
            "provider": "groq",
            "model_type": "llm",
            "description": "Test model for unit testing",
            "capabilities": {"streaming": True, "function_calling": True},
            "parameters": {"temperature": 0.7, "max_tokens": 8000},
            "endpoint_url": "https://api.groq.com/openai/v1",
            "max_tokens": 8000,
            "cost_per_1k_tokens": 0.59
        }
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.post(
                "/api/v1/models",
                json=model_data,
                headers=auth_headers
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["model"] == sample_model_response
        assert data["message"] == "Model registered successfully"
        
        # Verify service was called with correct data
        mock_model_service.register_model.assert_called_once_with(**model_data)
    
    @pytest.mark.asyncio
    async def test_register_model_validation_error(self, client, auth_headers):
        """Test model registration with validation errors"""
        # Invalid data - missing required fields
        invalid_data = {
            "name": "Test Model"
            # Missing model_id, version, provider, etc.
        }
        
        response = await client.post(
            "/api/v1/models",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data
    
    @pytest.mark.asyncio
    async def test_get_model_success(self, client, auth_headers, mock_model_service, sample_model_response):
        """Test successful model retrieval"""
        # Mock service response
        mock_model_service.get_model.return_value = sample_model_response
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models/test-llama-70b",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data == sample_model_response
        
        # Verify service was called
        mock_model_service.get_model.assert_called_once_with("test-llama-70b")
    
    @pytest.mark.asyncio
    async def test_get_model_not_found(self, client, auth_headers, mock_model_service):
        """Test getting non-existent model"""
        # Mock service response for not found
        mock_model_service.get_model.return_value = None
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models/nonexistent-model",
                headers=auth_headers
            )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["detail"] == "Model not found"
    
    @pytest.mark.asyncio
    async def test_list_models_success(self, client, auth_headers, mock_model_service, sample_model_response):
        """Test successful model listing"""
        # Mock service response
        models_list = [sample_model_response]
        mock_model_service.list_models.return_value = models_list
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == models_list
        assert data["total"] == 1
        
        # Verify service was called without filters
        mock_model_service.list_models.assert_called_once_with(
            provider=None,
            model_type=None,
            deployment_status=None,
            health_status=None
        )
    
    @pytest.mark.asyncio
    async def test_list_models_with_filters(self, client, auth_headers, mock_model_service, sample_model_response):
        """Test model listing with query filters"""
        # Mock service response
        mock_model_service.list_models.return_value = [sample_model_response]
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models?provider=groq&model_type=llm&health_status=healthy",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == [sample_model_response]
        
        # Verify service was called with filters
        mock_model_service.list_models.assert_called_once_with(
            provider="groq",
            model_type="llm",
            deployment_status=None,
            health_status="healthy"
        )
    
    @pytest.mark.asyncio
    async def test_update_model_status_success(self, client, auth_headers, mock_model_service):
        """Test successful model status update"""
        # Mock service response
        mock_model_service.update_model_status.return_value = True
        
        status_update = {
            "deployment_status": "deploying",
            "health_status": "healthy"
        }
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.patch(
                "/api/v1/models/test-llama-70b/status",
                json=status_update,
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Model status updated successfully"
        
        # Verify service was called
        mock_model_service.update_model_status.assert_called_once_with(
            "test-llama-70b",
            deployment_status="deploying",
            health_status="healthy"
        )
    
    @pytest.mark.asyncio
    async def test_update_model_status_not_found(self, client, auth_headers, mock_model_service):
        """Test updating status of non-existent model"""
        # Mock service response for not found
        mock_model_service.update_model_status.return_value = False
        
        status_update = {"deployment_status": "deploying"}
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.patch(
                "/api/v1/models/nonexistent-model/status",
                json=status_update,
                headers=auth_headers
            )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["detail"] == "Model not found"
    
    @pytest.mark.asyncio
    async def test_retire_model_success(self, client, auth_headers, mock_model_service):
        """Test successful model retirement"""
        # Mock service response
        mock_model_service.retire_model.return_value = True
        
        retirement_data = {"reason": "Model outdated"}
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.post(
                "/api/v1/models/test-llama-70b/retire",
                json=retirement_data,
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Model retired successfully"
        
        # Verify service was called
        mock_model_service.retire_model.assert_called_once_with(
            "test-llama-70b",
            reason="Model outdated"
        )
    
    @pytest.mark.asyncio
    async def test_retire_model_not_found(self, client, auth_headers, mock_model_service):
        """Test retiring non-existent model"""
        # Mock service response for not found
        mock_model_service.retire_model.return_value = False
        
        retirement_data = {"reason": "Model outdated"}
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.post(
                "/api/v1/models/nonexistent-model/retire",
                json=retirement_data,
                headers=auth_headers
            )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["detail"] == "Model not found"
    
    @pytest.mark.asyncio
    async def test_check_model_health_success(self, client, auth_headers, mock_model_service):
        """Test successful model health check"""
        # Mock service response
        health_response = {
            "healthy": True,
            "provider": "groq",
            "latency_ms": 1200.0,
            "last_check": "2024-01-15T10:30:00Z",
            "details": "Model responding normally"
        }
        mock_model_service.check_model_health.return_value = health_response
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models/test-llama-70b/health",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data == health_response
        
        # Verify service was called
        mock_model_service.check_model_health.assert_called_once_with("test-llama-70b")
    
    @pytest.mark.asyncio
    async def test_check_model_health_unhealthy(self, client, auth_headers, mock_model_service):
        """Test model health check for unhealthy model"""
        # Mock service response for unhealthy model
        health_response = {
            "healthy": False,
            "error": "Connection timeout",
            "last_check": "2024-01-15T10:30:00Z"
        }
        mock_model_service.check_model_health.return_value = health_response
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models/test-llama-70b/health",
                headers=auth_headers
            )
        
        assert response.status_code == 503  # Service Unavailable
        data = response.json()
        assert data == health_response
    
    @pytest.mark.asyncio
    async def test_check_model_health_not_found(self, client, auth_headers, mock_model_service):
        """Test health check for non-existent model"""
        # Mock service response for not found
        health_response = {
            "healthy": False,
            "error": "Model not found"
        }
        mock_model_service.check_model_health.return_value = health_response
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models/nonexistent-model/health",
                headers=auth_headers
            )
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["detail"] == "Model not found"
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client):
        """Test that endpoints require authentication"""
        # Test without auth headers
        response = await client.get("/api/v1/models")
        assert response.status_code == 401
        
        # Test model registration without auth
        model_data = {"model_id": "test", "name": "Test"}
        response = await client.post("/api/v1/models", json=model_data)
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_capability_validation(self, client, mock_model_service):
        """Test that endpoints validate capabilities"""
        # Mock invalid capability token
        invalid_headers = {"Authorization": "Bearer invalid.token"}
        
        with patch('app.core.security.verify_capability_token') as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")
            
            response = await client.get(
                "/api/v1/models",
                headers=invalid_headers
            )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_error_handling(self, client, auth_headers, mock_model_service):
        """Test API error handling for service exceptions"""
        # Mock service exception
        mock_model_service.list_models.side_effect = Exception("Database connection failed")
        
        with patch('app.api.v1.models.model_service', mock_model_service):
            response = await client.get(
                "/api/v1/models",
                headers=auth_headers
            )
        
        assert response.status_code == 500
        error_data = response.json()
        assert "error" in error_data
        assert "Database connection failed" in error_data["error"]


@pytest.mark.integration
class TestModelsAPIIntegration:
    """Integration tests for Models API with real ModelService"""
    
    @pytest.mark.asyncio
    async def test_full_api_workflow(self, client, auth_headers, temp_db_path, mock_settings):
        """Test complete API workflow with real ModelService"""
        # Create real service for integration test
        service = ModelService()
        service.db_path = temp_db_path
        service._init_database()
        
        model_data = {
            "model_id": "integration-test-model",
            "name": "Integration Test Model",
            "version": "1.0.0",
            "provider": "groq",
            "model_type": "llm",
            "description": "Model for integration testing",
            "max_tokens": 4000,
            "cost_per_1k_tokens": 0.5
        }
        
        with patch('app.api.v1.models.model_service', service):
            # 1. Register model
            response = await client.post(
                "/api/v1/models",
                json=model_data,
                headers=auth_headers
            )
            assert response.status_code == 201
            register_data = response.json()
            assert register_data["model"]["id"] == model_data["model_id"]
            
            # 2. Get model
            response = await client.get(
                f"/api/v1/models/{model_data['model_id']}",
                headers=auth_headers
            )
            assert response.status_code == 200
            get_data = response.json()
            assert get_data["id"] == model_data["model_id"]
            
            # 3. List models
            response = await client.get(
                "/api/v1/models",
                headers=auth_headers
            )
            assert response.status_code == 200
            list_data = response.json()
            assert list_data["total"] == 1
            assert list_data["models"][0]["id"] == model_data["model_id"]
            
            # 4. Update model status
            status_update = {"deployment_status": "available", "health_status": "healthy"}
            response = await client.patch(
                f"/api/v1/models/{model_data['model_id']}/status",
                json=status_update,
                headers=auth_headers
            )
            assert response.status_code == 200
            
            # 5. Verify status update
            response = await client.get(
                f"/api/v1/models/{model_data['model_id']}",
                headers=auth_headers
            )
            updated_model = response.json()
            assert updated_model["status"]["deployment"] == "available"
            assert updated_model["status"]["health"] == "healthy"
            
            # 6. Retire model
            retirement_data = {"reason": "Integration test completed"}
            response = await client.post(
                f"/api/v1/models/{model_data['model_id']}/retire",
                json=retirement_data,
                headers=auth_headers
            )
            assert response.status_code == 200
            
            # 7. Verify retirement
            response = await client.get(
                f"/api/v1/models/{model_data['model_id']}",
                headers=auth_headers
            )
            retired_model = response.json()
            assert retired_model["status"]["deployment"] == "retired"
            assert "Integration test completed" in retired_model["description"]