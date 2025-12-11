"""
Unit tests for Resource Service
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.resource_service import ResourceService
from app.models.ai_resource import AIResource
from app.models.tenant import Tenant, TenantResource
from app.models.usage import UsageRecord


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def resource_service(mock_db_session):
    """Create ResourceService instance with mock database"""
    return ResourceService(mock_db_session)


@pytest.fixture
def sample_resource_data():
    """Sample resource data for testing"""
    return {
        "name": "Test Groq Model",
        "resource_type": "llm",
        "provider": "groq",
        "model_name": "llama2-70b-4096",
        "description": "Test LLM model",
        "max_requests_per_minute": 60,
        "cost_per_1k_tokens": 0.0005
    }


@pytest.fixture
def mock_ai_resource():
    """Create a mock AIResource"""
    resource = Mock(spec=AIResource)
    resource.id = 1
    resource.uuid = "test-uuid-123"
    resource.name = "Test Model"
    resource.provider = "groq"
    resource.model_name = "llama2-70b-4096"
    resource.is_active = True
    resource.health_status = "healthy"
    resource.priority = 100
    resource.created_at = datetime.utcnow()
    resource.updated_at = datetime.utcnow()
    resource.to_dict.return_value = {
        "id": 1,
        "name": "Test Model",
        "provider": "groq",
        "is_active": True
    }
    return resource


@pytest.fixture
def mock_tenant():
    """Create a mock Tenant"""
    tenant = Mock(spec=Tenant)
    tenant.id = 1
    tenant.name = "Test Tenant"
    tenant.domain = "test-tenant"
    return tenant


@pytest.fixture
def mock_tenant_resource():
    """Create a mock TenantResource"""
    tr = Mock(spec=TenantResource)
    tr.id = 1
    tr.tenant_id = 1
    tr.resource_id = 1
    tr.is_enabled = True
    tr.usage_limits = {}
    tr.updated_at = datetime.utcnow()
    return tr


class TestResourceService:
    """Test the ResourceService class"""
    
    @pytest.mark.asyncio
    async def test_create_resource_success(self, resource_service, sample_resource_data):
        """Test successful resource creation"""
        # Mock the database operations
        created_resource = Mock(spec=AIResource)
        created_resource.id = 1
        created_resource.name = sample_resource_data["name"]
        
        resource_service.db.add = Mock()
        resource_service.db.commit = AsyncMock()
        resource_service.db.refresh = AsyncMock()
        
        with patch('app.models.ai_resource.AIResource') as MockResource:
            MockResource.return_value = created_resource
            MockResource.get_groq_defaults.return_value = {
                "provider": "groq",
                "api_endpoints": ["https://api.groq.com/openai/v1"],
                "primary_endpoint": "https://api.groq.com/openai/v1"
            }
            
            result = await resource_service.create_resource(sample_resource_data)
            
            assert result == created_resource
            resource_service.db.add.assert_called_once()
            resource_service.db.commit.assert_called_once()
            resource_service.db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_resource_missing_required_field(self, resource_service):
        """Test resource creation with missing required fields"""
        incomplete_data = {
            "name": "Test Model"
            # Missing required fields
        }
        
        with pytest.raises(ValueError) as exc_info:
            await resource_service.create_resource(incomplete_data)
        
        assert "Missing required field" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_resource_with_groq_defaults(self, resource_service, sample_resource_data):
        """Test resource creation applies Groq defaults"""
        created_resource = Mock(spec=AIResource)
        created_resource.id = 1
        
        resource_service.db.add = Mock()
        resource_service.db.commit = AsyncMock()
        resource_service.db.refresh = AsyncMock()
        
        groq_defaults = {
            "provider": "groq",
            "api_endpoints": ["https://api.groq.com/openai/v1"],
            "primary_endpoint": "https://api.groq.com/openai/v1",
            "health_check_url": "https://api.groq.com/openai/v1/models"
        }
        
        with patch('app.models.ai_resource.AIResource') as MockResource:
            MockResource.return_value = created_resource
            MockResource.get_groq_defaults.return_value = groq_defaults
            
            result = await resource_service.create_resource(sample_resource_data)
            
            # Verify defaults were applied
            create_call_args = MockResource.call_args[1]
            assert "api_endpoints" in create_call_args
            assert "primary_endpoint" in create_call_args
            assert "health_check_url" in create_call_args
    
    @pytest.mark.asyncio
    async def test_get_resource_found(self, resource_service, mock_ai_resource):
        """Test getting existing resource by ID"""
        # Mock database query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_ai_resource
        
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.get_resource(1)
        
        assert result == mock_ai_resource
        resource_service.db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_resource_not_found(self, resource_service):
        """Test getting non-existent resource"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.get_resource(999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_resource_by_uuid(self, resource_service, mock_ai_resource):
        """Test getting resource by UUID"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_ai_resource
        
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.get_resource_by_uuid("test-uuid-123")
        
        assert result == mock_ai_resource
    
    @pytest.mark.asyncio
    async def test_list_resources_no_filters(self, resource_service, mock_ai_resource):
        """Test listing all resources without filters"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_ai_resource]
        
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.list_resources()
        
        assert result == [mock_ai_resource]
    
    @pytest.mark.asyncio
    async def test_list_resources_with_filters(self, resource_service, mock_ai_resource):
        """Test listing resources with filters"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_ai_resource]
        
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.list_resources(
            provider="groq",
            resource_type="llm",
            is_active=True,
            health_status="healthy"
        )
        
        assert result == [mock_ai_resource]
        # Verify that conditions were applied (exact query depends on implementation)
        resource_service.db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_resource_success(self, resource_service, mock_ai_resource):
        """Test successful resource update"""
        # Mock get_resource to return existing resource
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        updates = {
            "name": "Updated Model Name",
            "max_requests_per_minute": 120
        }
        
        result = await resource_service.update_resource(1, updates)
        
        assert result == mock_ai_resource
        # Verify that attributes were updated
        assert mock_ai_resource.name == "Updated Model Name"
        assert mock_ai_resource.max_requests_per_minute == 120
        resource_service.db.commit.assert_called_once()
        resource_service.db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_resource_not_found(self, resource_service):
        """Test updating non-existent resource"""
        resource_service.get_resource = AsyncMock(return_value=None)
        
        result = await resource_service.update_resource(999, {"name": "New Name"})
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_resource_success(self, resource_service, mock_ai_resource):
        """Test successful resource deletion (soft delete)"""
        # Mock get_resource and check for active assignments
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []  # No active assignments
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.delete_resource(1)
        
        assert result is True
        assert mock_ai_resource.is_active is False
        assert mock_ai_resource.health_status == "deleted"
        resource_service.db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_resource_in_use(self, resource_service, mock_ai_resource, mock_tenant_resource):
        """Test deleting resource that's in use by tenants"""
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        # Mock active tenant assignments
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_tenant_resource]
        resource_service.db.execute.return_value = mock_result
        
        with pytest.raises(ValueError) as exc_info:
            await resource_service.delete_resource(1)
        
        assert "Cannot delete resource in use" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_resource_not_found(self, resource_service):
        """Test deleting non-existent resource"""
        resource_service.get_resource = AsyncMock(return_value=None)
        
        result = await resource_service.delete_resource(999)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_assign_resource_to_tenant_success(self, resource_service, mock_ai_resource, mock_tenant):
        """Test successful resource assignment to tenant"""
        # Mock dependencies
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        # Mock tenant query
        tenant_result = Mock()
        tenant_result.scalar_one_or_none.return_value = mock_tenant
        
        # Mock existing assignment query (no existing assignment)
        existing_result = Mock()
        existing_result.scalar_one_or_none.return_value = None
        
        resource_service.db.execute.side_effect = [tenant_result, existing_result]
        
        # Mock new assignment creation
        new_assignment = Mock(spec=TenantResource)
        new_assignment.id = 1
        
        with patch('app.models.tenant.TenantResource', return_value=new_assignment):
            result = await resource_service.assign_resource_to_tenant(1, 1, {"max_requests": 100})
            
            assert result == new_assignment
            resource_service.db.add.assert_called_once()
            resource_service.db.commit.assert_called_once()
            resource_service.db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_assign_resource_to_tenant_update_existing(self, resource_service, mock_ai_resource, mock_tenant, mock_tenant_resource):
        """Test updating existing resource assignment"""
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        # Mock tenant query
        tenant_result = Mock()
        tenant_result.scalar_one_or_none.return_value = mock_tenant
        
        # Mock existing assignment query (existing assignment found)
        existing_result = Mock()
        existing_result.scalar_one_or_none.return_value = mock_tenant_resource
        
        resource_service.db.execute.side_effect = [tenant_result, existing_result]
        
        result = await resource_service.assign_resource_to_tenant(1, 1, {"max_requests": 200})
        
        assert result == mock_tenant_resource
        assert mock_tenant_resource.is_enabled is True
        assert mock_tenant_resource.usage_limits == {"max_requests": 200}
        resource_service.db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_assign_resource_inactive_resource(self, resource_service, mock_ai_resource):
        """Test assigning inactive resource"""
        mock_ai_resource.is_active = False
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        with pytest.raises(ValueError) as exc_info:
            await resource_service.assign_resource_to_tenant(1, 1)
        
        assert "Resource not found or inactive" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_assign_resource_tenant_not_found(self, resource_service, mock_ai_resource):
        """Test assigning resource to non-existent tenant"""
        resource_service.get_resource = AsyncMock(return_value=mock_ai_resource)
        
        # Mock tenant query (not found)
        tenant_result = Mock()
        tenant_result.scalar_one_or_none.return_value = None
        resource_service.db.execute.return_value = tenant_result
        
        with pytest.raises(ValueError) as exc_info:
            await resource_service.assign_resource_to_tenant(1, 999)
        
        assert "Tenant not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_unassign_resource_from_tenant_success(self, resource_service, mock_tenant_resource):
        """Test successful resource unassignment"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_tenant_resource
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.unassign_resource_from_tenant(1, 1)
        
        assert result is True
        assert mock_tenant_resource.is_enabled is False
        resource_service.db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unassign_resource_assignment_not_found(self, resource_service):
        """Test unassigning non-existent assignment"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.unassign_resource_from_tenant(1, 1)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_tenant_resources(self, resource_service, mock_ai_resource):
        """Test getting resources assigned to a tenant"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_ai_resource]
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.get_tenant_resources(1)
        
        assert result == [mock_ai_resource]
    
    @pytest.mark.asyncio
    async def test_health_check_all_resources(self, resource_service):
        """Test health checking all resources"""
        # Mock list_resources
        mock_resource = Mock(spec=AIResource)
        mock_resource.id = 1
        mock_resource.provider = "groq"
        mock_resource.api_key_encrypted = "encrypted_key"
        mock_resource.health_status = "healthy"
        mock_resource.last_health_check = datetime.utcnow()
        mock_resource.update_health_status = Mock()
        
        resource_service.list_resources = AsyncMock(return_value=[mock_resource])
        
        # Mock health check method
        resource_service._health_check_resource = AsyncMock(return_value=True)
        
        result = await resource_service.health_check_all_resources()
        
        assert result["total_resources"] == 1
        assert result["healthy"] == 1
        assert result["unhealthy"] == 0
        assert len(result["details"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_resource_usage_stats(self, resource_service):
        """Test getting resource usage statistics"""
        # Mock usage records
        usage_records = [
            Mock(tokens_used=100, cost_cents=50, created_at=datetime.utcnow()),
            Mock(tokens_used=150, cost_cents=75, created_at=datetime.utcnow()),
            Mock(tokens_used=200, cost_cents=100, created_at=datetime.utcnow())
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = usage_records
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.get_resource_usage_stats(1)
        
        assert result["resource_id"] == 1
        assert result["summary"]["total_requests"] == 3
        assert result["summary"]["total_tokens"] == 450
        assert result["summary"]["total_cost_dollars"] == 2.25  # 225 cents / 100
        assert result["summary"]["avg_tokens_per_request"] == 150.0
    
    @pytest.mark.asyncio
    async def test_get_tenant_usage_stats(self, resource_service):
        """Test getting tenant usage statistics"""
        # Mock usage records with resources
        usage_record = Mock()
        usage_record.tokens_used = 100
        usage_record.cost_cents = 50
        usage_record.created_at = datetime.utcnow()
        
        ai_resource = Mock()
        ai_resource.id = 1
        ai_resource.name = "Test Model"
        ai_resource.provider = "groq"
        ai_resource.model_name = "llama2-70b-4096"
        
        mock_result = Mock()
        mock_result.all.return_value = [(usage_record, ai_resource)]
        resource_service.db.execute.return_value = mock_result
        
        result = await resource_service.get_tenant_usage_stats(1)
        
        assert result["tenant_id"] == 1
        assert result["summary"]["total_requests"] == 1
        assert result["summary"]["total_cost_dollars"] == 0.5
        assert result["summary"]["resources_used"] == 1
        assert 1 in result["by_resource"]
        assert result["by_resource"][1]["resource_name"] == "Test Model"
    
    @pytest.mark.asyncio
    async def test_health_check_resource_groq_success(self, resource_service, mock_ai_resource):
        """Test health checking a Groq resource"""
        mock_ai_resource.provider = "groq"
        
        with patch('app.services.resource_service.groq_service.health_check_resource', return_value=True) as mock_health_check:
            result = await resource_service._health_check_resource(mock_ai_resource, "test-key")
            
            assert result is True
            mock_health_check.assert_called_once_with(mock_ai_resource, "test-key")
    
    @pytest.mark.asyncio
    async def test_health_check_resource_unknown_provider(self, resource_service, mock_ai_resource):
        """Test health checking resource with unknown provider"""
        mock_ai_resource.provider = "unknown_provider"
        mock_ai_resource.update_health_status = Mock()
        
        result = await resource_service._health_check_resource(mock_ai_resource, "test-key")
        
        assert result is False
        mock_ai_resource.update_health_status.assert_called_with("unknown")
    
    @pytest.mark.asyncio
    async def test_health_check_resource_exception(self, resource_service, mock_ai_resource):
        """Test health checking resource with exception"""
        mock_ai_resource.provider = "groq"
        mock_ai_resource.update_health_status = Mock()
        
        with patch('app.services.resource_service.groq_service.health_check_resource', side_effect=Exception("Connection failed")):
            result = await resource_service._health_check_resource(mock_ai_resource, "test-key")
            
            assert result is False
            mock_ai_resource.update_health_status.assert_called_with("unhealthy")