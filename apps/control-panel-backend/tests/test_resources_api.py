"""
Unit tests for Resource Management API
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json

from app.main import app
from app.api.resources import get_current_user
from app.models.user import User
from app.models.ai_resource import AIResource
from app.models.tenant import TenantResource


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def async_client():
    """Create async test client"""
    return AsyncClient(app=app, base_url="http://test")


@pytest.fixture
def mock_user():
    """Create a mock user with admin capabilities"""
    user = Mock(spec=User)
    user.id = 1
    user.email = "admin@gt2.dev"
    user.user_type = "super_admin"
    user.capabilities = [
        {
            "resource": "resource:*",
            "actions": ["read", "write", "admin"]
        },
        {
            "resource": "tenant:*",
            "actions": ["read", "write", "admin"]
        }
    ]
    return user


@pytest.fixture
def auth_headers():
    """Create authentication headers"""
    return {"Authorization": "Bearer test-jwt-token"}


@pytest.fixture
def sample_resource_data():
    """Sample resource creation data"""
    return {
        "name": "Test Groq Model",
        "description": "Test LLM model for unit testing",
        "resource_type": "llm",
        "provider": "groq",
        "model_name": "llama2-70b-4096",
        "primary_endpoint": "https://api.groq.com/openai/v1",
        "api_endpoints": ["https://api.groq.com/openai/v1"],
        "health_check_url": "https://api.groq.com/openai/v1/models",
        "max_requests_per_minute": 60,
        "max_tokens_per_request": 4000,
        "cost_per_1k_tokens": 0.0005,
        "latency_sla_ms": 3000,
        "priority": 100,
        "configuration": {
            "temperature": 0.7,
            "max_tokens": 4000
        }
    }


@pytest.fixture
def mock_resource():
    """Create a mock AIResource"""
    resource = Mock(spec=AIResource)
    resource.id = 1
    resource.uuid = "test-uuid-123"
    resource.name = "Test Model"
    resource.description = "Test description"
    resource.resource_type = "llm"
    resource.provider = "groq"
    resource.model_name = "llama2-70b-4096"
    resource.health_status = "healthy"
    resource.is_active = True
    resource.created_at = datetime.utcnow()
    resource.updated_at = datetime.utcnow()
    resource.to_dict.return_value = {
        "id": 1,
        "uuid": "test-uuid-123",
        "name": "Test Model",
        "description": "Test description",
        "resource_type": "llm",
        "provider": "groq",
        "model_name": "llama2-70b-4096",
        "health_status": "healthy",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    return resource


class TestResourceAPI:
    """Test the Resource Management API endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_resource_success(self, async_client, sample_resource_data, auth_headers, mock_user, mock_resource):
        """Test successful resource creation"""
        # Mock dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.create_resource = AsyncMock(return_value=mock_resource)
            
            response = await async_client.post(
                "/api/v1/resources/",
                json=sample_resource_data,
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "Test Model"
            assert data["provider"] == "groq"
        
        # Cleanup
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_create_resource_validation_error(self, async_client, auth_headers, mock_user):
        """Test resource creation with validation errors"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        invalid_data = {
            "name": "Test Model"
            # Missing required fields
        }
        
        response = await async_client.post(
            "/api/v1/resources/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_create_resource_invalid_resource_type(self, async_client, sample_resource_data, auth_headers, mock_user):
        """Test resource creation with invalid resource type"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        invalid_data = sample_resource_data.copy()
        invalid_data["resource_type"] = "invalid_type"
        
        response = await async_client.post(
            "/api/v1/resources/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_create_resource_unauthorized(self, async_client, sample_resource_data):
        """Test resource creation without authentication"""
        response = await async_client.post(
            "/api/v1/resources/",
            json=sample_resource_data
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_list_resources_success(self, async_client, auth_headers, mock_user, mock_resource):
        """Test successful resource listing"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.list_resources = AsyncMock(return_value=[mock_resource])
            
            response = await async_client.get(
                "/api/v1/resources/",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == 1
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_list_resources_with_filters(self, async_client, auth_headers, mock_user, mock_resource):
        """Test resource listing with filters"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.list_resources = AsyncMock(return_value=[mock_resource])
            
            response = await async_client.get(
                "/api/v1/resources/?provider=groq&resource_type=llm&is_active=true",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            
            # Verify filters were passed to service
            mock_service.list_resources.assert_called_once_with(
                provider="groq",
                resource_type="llm",
                is_active=True,
                health_status=None
            )
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_get_resource_success(self, async_client, auth_headers, mock_user, mock_resource):
        """Test successful resource retrieval"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_resource = AsyncMock(return_value=mock_resource)
            
            response = await async_client.get(
                "/api/v1/resources/1",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "Test Model"
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_get_resource_not_found(self, async_client, auth_headers, mock_user):
        """Test resource retrieval when resource doesn't exist"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_resource = AsyncMock(return_value=None)
            
            response = await async_client.get(
                "/api/v1/resources/999",
                headers=auth_headers
            )
            
            assert response.status_code == 404
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_update_resource_success(self, async_client, auth_headers, mock_user, mock_resource):
        """Test successful resource update"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        updated_resource = mock_resource
        updated_resource.name = "Updated Model Name"
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.update_resource = AsyncMock(return_value=updated_resource)
            
            update_data = {
                "name": "Updated Model Name",
                "max_requests_per_minute": 120
            }
            
            response = await async_client.put(
                "/api/v1/resources/1",
                json=update_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            
            # Verify update was called with correct data
            mock_service.update_resource.assert_called_once_with(1, update_data)
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_update_resource_not_found(self, async_client, auth_headers, mock_user):
        """Test updating non-existent resource"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.update_resource = AsyncMock(return_value=None)
            
            response = await async_client.put(
                "/api/v1/resources/999",
                json={"name": "New Name"},
                headers=auth_headers
            )
            
            assert response.status_code == 404
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_delete_resource_success(self, async_client, auth_headers, mock_user):
        """Test successful resource deletion"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.delete_resource = AsyncMock(return_value=True)
            
            response = await async_client.delete(
                "/api/v1/resources/1",
                headers=auth_headers
            )
            
            assert response.status_code == 204
            mock_service.delete_resource.assert_called_once_with(1)
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_delete_resource_not_found(self, async_client, auth_headers, mock_user):
        """Test deleting non-existent resource"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.delete_resource = AsyncMock(return_value=False)
            
            response = await async_client.delete(
                "/api/v1/resources/999",
                headers=auth_headers
            )
            
            assert response.status_code == 404
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_delete_resource_in_use(self, async_client, auth_headers, mock_user):
        """Test deleting resource that's in use"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.delete_resource = AsyncMock(side_effect=ValueError("Cannot delete resource in use by 2 tenants"))
            
            response = await async_client.delete(
                "/api/v1/resources/1",
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "Cannot delete resource in use" in data["detail"]
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_assign_resource_to_tenant_success(self, async_client, auth_headers, mock_user):
        """Test successful resource assignment to tenant"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        mock_assignment = Mock(spec=TenantResource)
        mock_assignment.id = 1
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.assign_resource_to_tenant = AsyncMock(return_value=mock_assignment)
            
            assignment_data = {
                "tenant_id": 1,
                "usage_limits": {
                    "max_requests_per_hour": 100
                }
            }
            
            response = await async_client.post(
                "/api/v1/resources/1/assign",
                json=assignment_data,
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["message"] == "Resource assigned successfully"
            assert data["assignment_id"] == 1
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_unassign_resource_from_tenant_success(self, async_client, auth_headers, mock_user):
        """Test successful resource unassignment"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.unassign_resource_from_tenant = AsyncMock(return_value=True)
            
            response = await async_client.delete(
                "/api/v1/resources/1/assign/1",
                headers=auth_headers
            )
            
            assert response.status_code == 204
            mock_service.unassign_resource_from_tenant.assert_called_once_with(1, 1)
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_unassign_resource_assignment_not_found(self, async_client, auth_headers, mock_user):
        """Test unassigning non-existent assignment"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.unassign_resource_from_tenant = AsyncMock(return_value=False)
            
            response = await async_client.delete(
                "/api/v1/resources/1/assign/999",
                headers=auth_headers
            )
            
            assert response.status_code == 404
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_get_resource_usage_stats(self, async_client, auth_headers, mock_user):
        """Test getting resource usage statistics"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        mock_stats = {
            "resource_id": 1,
            "period": {
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-01-31T23:59:59"
            },
            "summary": {
                "total_requests": 100,
                "total_tokens": 10000,
                "total_cost_dollars": 5.0,
                "avg_tokens_per_request": 100.0,
                "avg_cost_per_request_cents": 5.0
            },
            "daily_stats": {}
        }
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_resource_usage_stats = AsyncMock(return_value=mock_stats)
            
            response = await async_client.get(
                "/api/v1/resources/1/usage",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["resource_id"] == 1
            assert data["summary"]["total_requests"] == 100
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_health_check_all_resources(self, async_client, auth_headers, mock_user):
        """Test health check for all resources"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        mock_health_results = {
            "total_resources": 2,
            "healthy": 1,
            "unhealthy": 1,
            "unknown": 0,
            "details": [
                {
                    "id": 1,
                    "name": "Resource 1",
                    "provider": "groq",
                    "health_status": "healthy",
                    "last_check": datetime.utcnow().isoformat()
                },
                {
                    "id": 2,
                    "name": "Resource 2",
                    "provider": "groq",
                    "health_status": "unhealthy",
                    "last_check": datetime.utcnow().isoformat()
                }
            ]
        }
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.health_check_all_resources = AsyncMock(return_value=mock_health_results)
            
            response = await async_client.post(
                "/api/v1/resources/health-check",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_resources"] == 2
            assert data["healthy"] == 1
            assert data["unhealthy"] == 1
            assert len(data["details"]) == 2
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_health_check_single_resource(self, async_client, auth_headers, mock_user, mock_resource):
        """Test health check for a single resource"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_resource = AsyncMock(return_value=mock_resource)
            mock_service._health_check_resource = AsyncMock(return_value=True)
            
            response = await async_client.get(
                "/api/v1/resources/1/health",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["resource_id"] == 1
            assert data["is_healthy"] is True
            assert "health_status" in data
            assert "last_check" in data
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_get_tenant_resources(self, async_client, auth_headers, mock_user, mock_resource):
        """Test getting resources assigned to a tenant"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_tenant_resources = AsyncMock(return_value=[mock_resource])
            
            response = await async_client.get(
                "/api/v1/resources/tenant/1",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == 1
            
            mock_service.get_tenant_resources.assert_called_once_with(1)
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_get_tenant_usage_stats(self, async_client, auth_headers, mock_user):
        """Test getting tenant usage statistics"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        mock_stats = {
            "tenant_id": 1,
            "period": {
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-01-31T23:59:59"
            },
            "summary": {
                "total_requests": 150,
                "total_cost_dollars": 7.5,
                "resources_used": 2
            },
            "by_resource": {
                "1": {
                    "resource_name": "Resource 1",
                    "provider": "groq",
                    "model_name": "llama2-70b-4096",
                    "requests": 100,
                    "tokens": 10000,
                    "cost_cents": 500
                }
            }
        }
        
        with patch('app.api.resources.ResourceService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_tenant_usage_stats = AsyncMock(return_value=mock_stats)
            
            response = await async_client.get(
                "/api/v1/resources/tenant/1/usage",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == 1
            assert data["summary"]["total_requests"] == 150
            assert "by_resource" in data
        
        app.dependency_overrides.clear()


class TestResourceAPIValidation:
    """Test request validation for Resource API"""
    
    @pytest.mark.asyncio
    async def test_create_resource_invalid_cost_negative(self, async_client, sample_resource_data, auth_headers, mock_user):
        """Test resource creation with negative cost"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        invalid_data = sample_resource_data.copy()
        invalid_data["cost_per_1k_tokens"] = -0.001  # Negative cost
        
        response = await async_client.post(
            "/api/v1/resources/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_create_resource_invalid_latency_sla(self, async_client, sample_resource_data, auth_headers, mock_user):
        """Test resource creation with invalid latency SLA"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        invalid_data = sample_resource_data.copy()
        invalid_data["latency_sla_ms"] = 50  # Below minimum
        
        response = await async_client.post(
            "/api/v1/resources/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        
        app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_create_resource_invalid_provider(self, async_client, sample_resource_data, auth_headers, mock_user):
        """Test resource creation with invalid provider"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        invalid_data = sample_resource_data.copy()
        invalid_data["provider"] = "invalid_provider"
        
        response = await async_client.post(
            "/api/v1/resources/",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422
        
        app.dependency_overrides.clear()


class TestResourceAPIPermissions:
    """Test permission checking for Resource API"""
    
    @pytest.fixture
    def limited_user(self):
        """Create a user with limited permissions"""
        user = Mock(spec=User)
        user.id = 2
        user.email = "user@gt2.dev"
        user.user_type = "tenant_user"
        user.capabilities = [
            {
                "resource": "resource:1",
                "actions": ["read"]
            }
        ]
        return user
    
    @pytest.mark.asyncio
    async def test_create_resource_insufficient_permissions(self, async_client, sample_resource_data, auth_headers, limited_user):
        """Test resource creation with insufficient permissions"""
        app.dependency_overrides[get_current_user] = lambda: limited_user
        
        with patch('app.api.resources.require_capability') as mock_require:
            mock_require.side_effect = Exception("Insufficient permissions")
            
            response = await async_client.post(
                "/api/v1/resources/",
                json=sample_resource_data,
                headers=auth_headers
            )
            
            # Should fail before reaching the service layer
            assert response.status_code == 500  # Internal error due to exception
        
        app.dependency_overrides.clear()