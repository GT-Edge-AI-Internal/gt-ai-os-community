"""
Tests for Dremio SQL Federation Service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dremio_service import DremioService
from app.models.tenant import Tenant
from app.models.user import User
from app.models.usage import UsageRecord


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def dremio_service(mock_db_session):
    """Dremio Service instance"""
    return DremioService(mock_db_session)


@pytest.fixture
def sample_tenant():
    """Sample tenant for testing"""
    return Tenant(
        id=1,
        name="Test Company",
        domain="testcompany",
        namespace="gt-testcompany",
        status="active",
        api_keys={
            "groq": {
                "key": "encrypted",
                "enabled": True,
                "updated_at": (datetime.utcnow() - timedelta(days=100)).isoformat()
            }
        }
    )


class TestDremioService:
    """Test Dremio Service functionality"""
    
    async def test_authenticate(self, dremio_service):
        """Test Dremio authentication"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"token": "test_token_123"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            token = await dremio_service._authenticate()
            
            assert token == "test_token_123"
            assert dremio_service.auth_token == "test_token_123"
            assert dremio_service.token_expires > datetime.utcnow()
    
    async def test_authenticate_cached_token(self, dremio_service):
        """Test using cached authentication token"""
        # Set cached token
        dremio_service.auth_token = "cached_token"
        dremio_service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        token = await dremio_service._authenticate()
        
        assert token == "cached_token"
    
    async def test_execute_query(self, dremio_service):
        """Test executing SQL query via Dremio"""
        dremio_service.auth_token = "test_token"
        dremio_service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock SQL submission
            submit_response = MagicMock()
            submit_response.status_code = 200
            submit_response.json.return_value = {"id": "job_123"}
            
            # Mock job status check
            status_response = MagicMock()
            status_response.json.return_value = {"jobState": "COMPLETED"}
            
            # Mock results
            results_response = MagicMock()
            results_response.status_code = 200
            results_response.json.return_value = {
                "rows": [
                    {"column1": "value1", "column2": 123},
                    {"column1": "value2", "column2": 456}
                ]
            }
            
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.side_effect = [status_response, results_response]
            
            results = await dremio_service.execute_query("SELECT * FROM test_table")
            
            assert len(results) == 2
            assert results[0]["column1"] == "value1"
            assert results[1]["column2"] == 456
    
    async def test_execute_query_failure(self, dremio_service):
        """Test query execution failure"""
        dremio_service.auth_token = "test_token"
        dremio_service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        with patch('httpx.AsyncClient') as mock_client:
            submit_response = MagicMock()
            submit_response.status_code = 200
            submit_response.json.return_value = {"id": "job_123"}
            
            status_response = MagicMock()
            status_response.json.return_value = {
                "jobState": "FAILED",
                "errorMessage": "Query syntax error"
            }
            
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.return_value = status_response
            
            with pytest.raises(Exception, match="Query failed: Query syntax error"):
                await dremio_service.execute_query("SELECT * FROM invalid")
    
    async def test_get_tenant_dashboard_data(self, dremio_service, mock_db_session, sample_tenant):
        """Test getting comprehensive dashboard data"""
        # Mock tenant query
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = sample_tenant
        
        # Mock user query
        users = [
            User(id=1, email="user1@test.com", tenant_id=1, user_type="admin", 
                 last_login=datetime.utcnow()),
            User(id=2, email="user2@test.com", tenant_id=1, user_type="developer",
                 last_login=datetime.utcnow() - timedelta(days=10))
        ]
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = users
        
        # Mock usage records
        usage_records = [
            UsageRecord(
                id=1, tenant_id=1, operation_type="inference",
                tokens_used=1000, cost_cents=10,
                started_at=datetime.utcnow() - timedelta(days=1)
            )
        ]
        usage_result = MagicMock()
        usage_result.scalars.return_value.all.return_value = usage_records

        # Setup mock returns
        mock_db_session.execute.side_effect = [
            tenant_result,
            users_result,
            usage_result,
            tenant_result  # For security alerts
        ]
        
        # Mock Dremio queries to fail (fallback to local)
        with patch.object(dremio_service, 'execute_query', side_effect=Exception("Dremio unavailable")):
            result = await dremio_service.get_tenant_dashboard_data(1)
        
        assert result["tenant"]["id"] == 1
        assert result["metrics"]["users"]["total_users"] == 2
        assert result["metrics"]["users"]["active_users"] == 1
        assert result["metrics"]["resources"]["total_requests_7d"] == 1
        assert len(result["alerts"]) == 1  # API key rotation warning
    
    async def test_get_user_metrics(self, dremio_service, mock_db_session):
        """Test getting user metrics"""
        users = [
            User(id=1, email="admin@test.com", tenant_id=1, user_type="tenant_admin",
                 last_login=datetime.utcnow()),
            User(id=2, email="dev@test.com", tenant_id=1, user_type="developer",
                 last_login=datetime.utcnow() - timedelta(days=3)),
            User(id=3, email="old@test.com", tenant_id=1, user_type="analyst",
                 last_login=datetime.utcnow() - timedelta(days=30))
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = users
        mock_db_session.execute.return_value = mock_result
        
        result = await dremio_service._get_user_metrics(1)
        
        assert result["total_users"] == 3
        assert result["active_users"] == 2  # Only users logged in within 7 days
        assert result["inactive_users"] == 1
        assert result["by_role"]["admin"] == 1
        assert result["by_role"]["developer"] == 1
        assert result["by_role"]["analyst"] == 1
    
    async def test_get_resource_usage_federated(self, dremio_service):
        """Test getting resource usage via Dremio federation"""
        with patch.object(dremio_service, 'execute_query') as mock_query:
            mock_query.return_value = [
                {
                    "resource_type": "llm",
                    "request_count": 100,
                    "total_tokens": 50000,
                    "total_cost_cents": 250,
                    "avg_latency_ms": 120.5
                },
                {
                    "resource_type": "embedding",
                    "request_count": 50,
                    "total_tokens": 10000,
                    "total_cost_cents": 50,
                    "avg_latency_ms": 45.2
                }
            ]
            
            result = await dremio_service._get_resource_usage_federated(1)
            
            assert result["total_requests_7d"] == 150
            assert result["total_tokens_7d"] == 60000
            assert result["total_cost_cents_7d"] == 300
            assert "llm" in result["by_resource_type"]
            assert result["by_resource_type"]["llm"]["requests"] == 100

    async def test_get_security_alerts(self, dremio_service, mock_db_session, sample_tenant):
        """Test getting security alerts"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_tenant
        mock_db_session.execute.return_value = mock_result
        
        alerts = await dremio_service._get_security_alerts(1)
        
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"
        assert alerts[0]["type"] == "api_key_rotation"
        assert "groq" in alerts[0]["message"]
    
    async def test_create_virtual_datasets(self, dremio_service):
        """Test creating Dremio virtual datasets"""
        dremio_service.auth_token = "test_token"
        dremio_service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await dremio_service.create_virtual_datasets(1)
            
            assert result["tenant_id"] == 1
            assert result["status"] == "success"
            assert len(result["datasets_created"]) == 2
    
    async def test_get_custom_analytics(self, dremio_service):
        """Test running custom analytics queries"""
        with patch.object(dremio_service, 'execute_query') as mock_query:
            mock_query.return_value = [
                {
                    "email": "user1@test.com",
                    "user_type": "developer",
                    "conversations": 10,
                    "total_tokens": 5000,
                    "total_cost_cents": 50
                }
            ]
            
            result = await dremio_service.get_custom_analytics(
                tenant_id=1,
                query_type="user_activity",
                start_date=datetime.utcnow() - timedelta(days=30),
                end_date=datetime.utcnow()
            )
            
            assert len(result) == 1
            assert result[0]["email"] == "user1@test.com"
            assert result[0]["total_tokens"] == 5000
    
    async def test_get_custom_analytics_invalid_type(self, dremio_service):
        """Test custom analytics with invalid query type"""
        with pytest.raises(ValueError, match="Unknown query type: invalid"):
            await dremio_service.get_custom_analytics(
                tenant_id=1,
                query_type="invalid"
            )
    
    async def test_get_performance_metrics(self, dremio_service):
        """Test getting performance metrics"""
        result = await dremio_service._get_performance_metrics(1)
        
        assert "api_latency_p50_ms" in result
        assert "api_latency_p95_ms" in result
        assert "uptime_percentage" in result
        assert "error_rate_percentage" in result
        assert result["uptime_percentage"] == 99.95


if __name__ == "__main__":
    pytest.main([__file__, "-v"])