"""
Unit tests for Dremio SQL Federation Service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Import test fixtures
from tests.test_fixtures import (
    create_mock_tenant,
    create_mock_user,
    create_mock_usage_record,
    create_mock_billing_usage,
    create_mock_db_session,
    create_mock_query_result
)

from app.services.dremio_service import DremioService


class TestDremioService:
    """Test Dremio Service functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return create_mock_db_session()
    
    @pytest.fixture
    def dremio_service(self, mock_db_session):
        """Dremio Service instance"""
        return DremioService(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_authenticate(self, dremio_service):
        """Test Dremio authentication"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"token": "test_token_123"}
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            token = await dremio_service._authenticate()
            
            assert token == "test_token_123"
            assert dremio_service.auth_token == "test_token_123"
            assert dremio_service.token_expires > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_authenticate_cached_token(self, dremio_service):
        """Test using cached authentication token"""
        # Set cached token
        dremio_service.auth_token = "cached_token"
        dremio_service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        token = await dremio_service._authenticate()
        
        assert token == "cached_token"
    
    @pytest.mark.asyncio
    async def test_execute_query_success(self, dremio_service):
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
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.side_effect = [status_response, results_response]
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            results = await dremio_service.execute_query("SELECT * FROM test_table")
            
            assert len(results) == 2
            assert results[0]["column1"] == "value1"
            assert results[1]["column2"] == 456
    
    @pytest.mark.asyncio
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
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = submit_response
            mock_client_instance.get.return_value = status_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            with pytest.raises(Exception, match="Query failed: Query syntax error"):
                await dremio_service.execute_query("SELECT * FROM invalid")
    
    @pytest.mark.asyncio
    async def test_get_tenant_dashboard_data(self, dremio_service, mock_db_session):
        """Test getting comprehensive dashboard data"""
        # Create mock data
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": "encrypted",
                    "enabled": True,
                    "updated_at": (datetime.utcnow() - timedelta(days=100)).isoformat()
                }
            }
        )
        
        users = [
            create_mock_user(id=1, email="user1@test.com", user_type="admin"),
            create_mock_user(id=2, email="user2@test.com", user_type="developer",
                           last_login=datetime.utcnow() - timedelta(days=10))
        ]
        
        usage_records = [
            create_mock_usage_record(id=1, tokens_used=1000, cost_cents=10)
        ]
        
        billing_records = [
            create_mock_billing_usage(id=1, total_cost_cents=500)
        ]
        
        # Setup mock returns
        mock_db_session.execute.side_effect = [
            create_mock_query_result(tenant, scalar=True),  # tenant query
            create_mock_query_result(users),  # users query
            create_mock_query_result(usage_records),  # usage query
            create_mock_query_result(billing_records),  # billing query
            create_mock_query_result(tenant, scalar=True),  # security alerts query
        ]
        
        # Mock Dremio queries to fail (fallback to local)
        with patch.object(dremio_service, 'execute_query', side_effect=Exception("Dremio unavailable")):
            result = await dremio_service.get_tenant_dashboard_data(1)
        
        assert result["tenant"]["id"] == 1
        assert result["metrics"]["users"]["total_users"] == 2
        assert result["metrics"]["users"]["active_users"] == 1
        assert result["metrics"]["resources"]["total_requests_7d"] == 1
        assert result["analytics"]["billing"]["current_month_cost_cents"] == 500
        assert len(result["alerts"]) == 1  # API key rotation warning
    
    @pytest.mark.asyncio
    async def test_get_user_metrics(self, dremio_service, mock_db_session):
        """Test getting user metrics"""
        users = [
            create_mock_user(id=1, email="admin@test.com", user_type="tenant_admin",
                           last_login=datetime.utcnow()),
            create_mock_user(id=2, email="dev@test.com", user_type="developer",
                           last_login=datetime.utcnow() - timedelta(days=3)),
            create_mock_user(id=3, email="old@test.com", user_type="analyst",
                           last_login=datetime.utcnow() - timedelta(days=30))
        ]
        
        mock_db_session.execute.return_value = create_mock_query_result(users)
        
        result = await dremio_service._get_user_metrics(1)
        
        assert result["total_users"] == 3
        assert result["active_users"] == 2  # Only users logged in within 7 days
        assert result["inactive_users"] == 1
        assert result["by_role"]["admin"] == 1
        assert result["by_role"]["developer"] == 1
        assert result["by_role"]["analyst"] == 1
    
    @pytest.mark.asyncio
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
    
    @pytest.mark.asyncio
    async def test_get_billing_analytics(self, dremio_service, mock_db_session):
        """Test getting billing analytics"""
        billing_records = [
            create_mock_billing_usage(id=1, total_cost_cents=300,
                                     billing_date=datetime.utcnow().replace(day=1)),
            create_mock_billing_usage(id=2, total_cost_cents=200,
                                     billing_date=datetime.utcnow().replace(day=2))
        ]
        
        # Manually set the cost breakdown for accurate testing
        billing_records[0].compute_cost_cents = 120
        billing_records[0].storage_cost_cents = 80
        billing_records[0].api_cost_cents = 70
        billing_records[0].transfer_cost_cents = 30
        
        billing_records[1].compute_cost_cents = 80
        billing_records[1].storage_cost_cents = 60
        billing_records[1].api_cost_cents = 40
        billing_records[1].transfer_cost_cents = 20
        
        mock_db_session.execute.return_value = create_mock_query_result(billing_records)
        
        result = await dremio_service._get_billing_analytics(1)
        
        assert result["current_month_cost_cents"] == 500
        assert result["cost_breakdown"]["compute"] == 200
        assert result["cost_breakdown"]["storage"] == 140
        assert result["cost_breakdown"]["api_calls"] == 110
        assert result["cost_breakdown"]["data_transfer"] == 50
        assert "projected_month_cost_cents" in result
    
    @pytest.mark.asyncio
    async def test_get_security_alerts(self, dremio_service, mock_db_session):
        """Test getting security alerts"""
        tenant = create_mock_tenant(
            api_keys={
                "groq": {
                    "key": "encrypted",
                    "enabled": True,
                    "updated_at": (datetime.utcnow() - timedelta(days=100)).isoformat()
                }
            }
        )
        
        mock_db_session.execute.return_value = create_mock_query_result(tenant, scalar=True)
        
        alerts = await dremio_service._get_security_alerts(1)
        
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"
        assert alerts[0]["type"] == "api_key_rotation"
        assert "groq" in alerts[0]["message"]
    
    @pytest.mark.asyncio
    async def test_create_virtual_datasets(self, dremio_service):
        """Test creating Dremio virtual datasets"""
        dremio_service.auth_token = "test_token"
        dremio_service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 201
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            result = await dremio_service.create_virtual_datasets(1)
            
            assert result["tenant_id"] == 1
            assert result["status"] == "success"
            assert len(result["datasets_created"]) == 2
    
    @pytest.mark.asyncio
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
    
    @pytest.mark.asyncio
    async def test_get_custom_analytics_invalid_type(self, dremio_service):
        """Test custom analytics with invalid query type"""
        with pytest.raises(ValueError, match="Unknown query type: invalid"):
            await dremio_service.get_custom_analytics(
                tenant_id=1,
                query_type="invalid"
            )
    
    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, dremio_service):
        """Test getting performance metrics"""
        result = await dremio_service._get_performance_metrics(1)
        
        assert "api_latency_p50_ms" in result
        assert "api_latency_p95_ms" in result
        assert "uptime_percentage" in result
        assert "error_rate_percentage" in result
        assert result["uptime_percentage"] == 99.95
    
    @pytest.mark.asyncio
    async def test_dashboard_data_with_dremio(self, dremio_service, mock_db_session):
        """Test dashboard data fetching with Dremio available"""
        tenant = create_mock_tenant()
        
        mock_db_session.execute.side_effect = [
            create_mock_query_result(tenant, scalar=True),  # tenant query
            create_mock_query_result(tenant, scalar=True),  # security alerts
        ]
        
        # Mock successful Dremio queries
        with patch.object(dremio_service, 'execute_query') as mock_query:
            mock_query.side_effect = [
                # User metrics query
                [{"total": 5, "active": 3, "role": "admin", "count": 2}],
                # Resource usage query
                [{"resource_type": "llm", "request_count": 100, "total_tokens": 50000}],
                # Billing query
                [{"total_cost": 1000, "compute": 400, "storage": 300}],
                # Performance query
                [{"p50": 100, "p95": 500, "uptime": 99.9}]
            ]
            
            result = await dremio_service.get_tenant_dashboard_data(1)
            
            assert result["tenant"]["id"] == 1
            assert result["data_source"] == "dremio"
            assert "metrics" in result
            assert "analytics" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])