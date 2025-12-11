"""
Pure unit tests for Dremio SQL Federation Service (no SQLAlchemy)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch


class TestDremioServicePure:
    """Pure unit tests for Dremio Service without database dependencies"""
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful Dremio authentication"""
        with patch('httpx.AsyncClient') as mock_httpx:
            from app.services.dremio_service import DremioService
            
            # Mock HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={"token": "test_token_123"})
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            
            # Create service
            mock_db = AsyncMock()
            service = DremioService(mock_db)
            
            # Authenticate
            token = await service._authenticate()
            
            # Verify
            assert token == "test_token_123"
            assert service.auth_token == "test_token_123"
            assert service.token_expires > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_authenticate_cached_token(self):
        """Test using cached authentication token"""
        from app.services.dremio_service import DremioService
        
        mock_db = AsyncMock()
        service = DremioService(mock_db)
        
        # Set cached token
        service.auth_token = "cached_token"
        service.token_expires = datetime.utcnow() + timedelta(hours=1)
        
        # Authenticate (should use cache)
        token = await service._authenticate()
        
        # Verify cached token is returned
        assert token == "cached_token"
    
    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        """Test successful query execution"""
        with patch('httpx.AsyncClient') as mock_httpx:
            from app.services.dremio_service import DremioService
            
            # Mock responses
            submit_response = Mock()
            submit_response.status_code = 200
            submit_response.json = Mock(return_value={"id": "job_123"})
            
            status_response = Mock()
            status_response.json = Mock(return_value={"jobState": "COMPLETED"})
            
            results_response = Mock()
            results_response.status_code = 200
            results_response.json = Mock(return_value={
                "rows": [
                    {"column1": "value1", "column2": 123},
                    {"column1": "value2", "column2": 456}
                ]
            })
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=submit_response)
            mock_client.get = AsyncMock(side_effect=[status_response, results_response])
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            
            # Create service with auth token
            mock_db = AsyncMock()
            service = DremioService(mock_db)
            service.auth_token = "test_token"
            service.token_expires = datetime.utcnow() + timedelta(hours=1)
            
            # Execute query
            results = await service.execute_query("SELECT * FROM test_table")
            
            # Verify
            assert len(results) == 2
            assert results[0]["column1"] == "value1"
            assert results[1]["column2"] == 456
    
    @pytest.mark.asyncio
    async def test_execute_query_failure(self):
        """Test query execution failure"""
        with patch('httpx.AsyncClient') as mock_httpx:
            from app.services.dremio_service import DremioService
            
            # Mock responses
            submit_response = Mock()
            submit_response.status_code = 200
            submit_response.json = Mock(return_value={"id": "job_123"})
            
            status_response = Mock()
            status_response.json = Mock(return_value={
                "jobState": "FAILED",
                "errorMessage": "Query syntax error"
            })
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=submit_response)
            mock_client.get = AsyncMock(return_value=status_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            
            # Create service
            mock_db = AsyncMock()
            service = DremioService(mock_db)
            service.auth_token = "test_token"
            service.token_expires = datetime.utcnow() + timedelta(hours=1)
            
            # Execute query and expect failure
            with pytest.raises(Exception, match="Query failed: Query syntax error"):
                await service.execute_query("SELECT * FROM invalid")
    
    @pytest.mark.asyncio
    async def test_get_user_metrics(self):
        """Test calculating user metrics"""
        with patch('app.services.dremio_service.select') as mock_select:
            from app.services.dremio_service import DremioService
            
            # Create mock users
            users = [
                Mock(user_type="tenant_admin", last_login=datetime.utcnow()),
                Mock(user_type="developer", last_login=datetime.utcnow() - timedelta(days=3)),
                Mock(user_type="analyst", last_login=datetime.utcnow() - timedelta(days=30))
            ]
            
            # Mock database
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_scalars = Mock()
            mock_scalars.all = Mock(return_value=users)
            mock_result.scalars = Mock(return_value=mock_scalars)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            service = DremioService(mock_db)
            
            # Get metrics
            result = await service._get_user_metrics(1)
            
            # Verify
            assert result["total_users"] == 3
            assert result["active_users"] == 2  # Only users logged in within 7 days
            assert result["inactive_users"] == 1
            assert result["by_role"]["admin"] == 1
            assert result["by_role"]["developer"] == 1
            assert result["by_role"]["analyst"] == 1
    
    @pytest.mark.asyncio
    async def test_get_billing_analytics(self):
        """Test calculating billing analytics"""
        with patch('app.services.dremio_service.select') as mock_select:
            from app.services.dremio_service import DremioService
            
            # Create mock billing records
            billing1 = Mock(
                total_cost_cents=300,
                compute_cost_cents=120,
                storage_cost_cents=80,
                api_cost_cents=70,
                transfer_cost_cents=30,
                billing_date=datetime.utcnow().replace(day=1)
            )
            billing2 = Mock(
                total_cost_cents=200,
                compute_cost_cents=80,
                storage_cost_cents=60,
                api_cost_cents=40,
                transfer_cost_cents=20,
                billing_date=datetime.utcnow().replace(day=2)
            )
            
            # Mock database
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_scalars = Mock()
            mock_scalars.all = Mock(return_value=[billing1, billing2])
            mock_result.scalars = Mock(return_value=mock_scalars)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            service = DremioService(mock_db)
            
            # Get analytics
            result = await service._get_billing_analytics(1)
            
            # Verify
            assert result["current_month_cost_cents"] == 500
            assert result["cost_breakdown"]["compute"] == 200
            assert result["cost_breakdown"]["storage"] == 140
            assert result["cost_breakdown"]["api_calls"] == 110
            assert result["cost_breakdown"]["data_transfer"] == 50
            assert "projected_month_cost_cents" in result
    
    @pytest.mark.asyncio
    async def test_get_security_alerts(self):
        """Test generating security alerts"""
        with patch('app.services.dremio_service.select') as mock_select:
            from app.services.dremio_service import DremioService
            
            # Create mock tenant with old API key
            mock_tenant = Mock()
            mock_tenant.api_keys = {
                "groq": {
                    "key": "encrypted",
                    "enabled": True,
                    "updated_at": (datetime.utcnow() - timedelta(days=100)).isoformat()
                }
            }
            
            # Mock database
            mock_db = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            service = DremioService(mock_db)
            
            # Get alerts
            alerts = await service._get_security_alerts(1)
            
            # Verify
            assert len(alerts) == 1
            assert alerts[0]["severity"] == "warning"
            assert alerts[0]["type"] == "api_key_rotation"
            assert "groq" in alerts[0]["message"]
    
    @pytest.mark.asyncio
    async def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        from app.services.dremio_service import DremioService
        
        mock_db = AsyncMock()
        service = DremioService(mock_db)
        
        # Get metrics (uses mock data)
        result = await service._get_performance_metrics(1)
        
        # Verify structure
        assert "api_latency_p50_ms" in result
        assert "api_latency_p95_ms" in result
        assert "api_latency_p99_ms" in result
        assert "uptime_percentage" in result
        assert "error_rate_percentage" in result
        assert result["uptime_percentage"] == 99.95
    
    @pytest.mark.asyncio
    async def test_create_virtual_datasets(self):
        """Test creating virtual datasets in Dremio"""
        with patch('httpx.AsyncClient') as mock_httpx:
            from app.services.dremio_service import DremioService
            
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 201
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            
            # Create service
            mock_db = AsyncMock()
            service = DremioService(mock_db)
            service.auth_token = "test_token"
            service.token_expires = datetime.utcnow() + timedelta(hours=1)
            
            # Create datasets
            result = await service.create_virtual_datasets(1)
            
            # Verify
            assert result["tenant_id"] == 1
            assert result["status"] == "success"
            assert len(result["datasets_created"]) == 2
            assert "tenant_1_dashboard" in result["datasets_created"]
            assert "tenant_1_analytics" in result["datasets_created"]
    
    @pytest.mark.asyncio
    async def test_get_custom_analytics_user_activity(self):
        """Test custom analytics for user activity"""
        from app.services.dremio_service import DremioService
        
        # Mock query results
        query_results = [
            {
                "email": "user1@test.com",
                "user_type": "developer",
                "conversations": 10,
                "total_tokens": 5000,
                "total_cost_cents": 50
            }
        ]
        
        mock_db = AsyncMock()
        service = DremioService(mock_db)
        
        with patch.object(service, 'execute_query', return_value=query_results):
            result = await service.get_custom_analytics(
                tenant_id=1,
                query_type="user_activity",
                start_date=datetime.utcnow() - timedelta(days=30),
                end_date=datetime.utcnow()
            )
            
            # Verify
            assert len(result) == 1
            assert result[0]["email"] == "user1@test.com"
            assert result[0]["total_tokens"] == 5000
    
    @pytest.mark.asyncio
    async def test_get_custom_analytics_invalid_type(self):
        """Test custom analytics with invalid query type"""
        from app.services.dremio_service import DremioService
        
        mock_db = AsyncMock()
        service = DremioService(mock_db)
        
        with pytest.raises(ValueError, match="Unknown query type: invalid"):
            await service.get_custom_analytics(
                tenant_id=1,
                query_type="invalid"
            )
    
    @pytest.mark.asyncio
    async def test_dashboard_data_fallback_to_local(self):
        """Test dashboard data fallback when Dremio is unavailable"""
        with patch('app.services.dremio_service.select') as mock_select:
            from app.services.dremio_service import DremioService
            
            # Create mock data
            mock_tenant = Mock()
            mock_tenant.id = 1
            mock_tenant.name = "Test Company"
            mock_tenant.domain = "testcompany"
            mock_tenant.api_keys = {}
            
            mock_users = [Mock(), Mock()]  # 2 users
            mock_usage = [Mock()]  # 1 usage record
            mock_billing = [Mock(total_cost_cents=500)]
            
            # Mock database results
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(side_effect=[
                Mock(scalar_one_or_none=Mock(return_value=mock_tenant)),
                Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=mock_users)))),
                Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=mock_usage)))),
                Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=mock_billing)))),
                Mock(scalar_one_or_none=Mock(return_value=mock_tenant))
            ])
            
            service = DremioService(mock_db)
            
            # Mock Dremio to fail
            with patch.object(service, 'execute_query', side_effect=Exception("Dremio down")):
                result = await service.get_tenant_dashboard_data(1)
            
            # Verify fallback data
            assert result["tenant"]["id"] == 1
            assert result["data_source"] == "local"
            assert "metrics" in result
            assert "analytics" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])