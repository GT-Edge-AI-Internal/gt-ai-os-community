"""
External Services Integration Unit Tests

Tests the ExternalServiceManager for tenant-based external web service management.
Includes service instance lifecycle, Resource Cluster integration, SSO token generation,
access control, analytics, and service template management.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.services.external_service import ExternalServiceManager
from app.models.external_service import ExternalServiceInstance, ServiceAccessLog, ServiceTemplate


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def external_service_manager(mock_db_session):
    """ExternalServiceManager instance with mocked dependencies"""
    manager = ExternalServiceManager(mock_db_session)
    manager.capability_token = "test-capability-token"
    return manager


@pytest.fixture
def sample_service_instance():
    """Sample external service instance"""
    return ExternalServiceInstance(
        id="service-123",
        service_type="ctfd",
        service_name="Test CTFd Instance",
        description="Test CTFd for cybersecurity training",
        resource_instance_id="resource-456",
        endpoint_url="https://ctfd.test.gt2.com",
        status="running",
        service_config={"challenges_enabled": True, "team_mode": False},
        created_by="user@example.com",
        allowed_users=["user@example.com"],
        access_level="private",
        health_status="healthy",
        restart_count=0
    )


@pytest.fixture
def sample_service_template():
    """Sample service template"""
    return ServiceTemplate(
        id="template-123",
        template_name="CTFd Cybersecurity Lab",
        service_type="ctfd",
        description="Pre-configured CTFd instance for cybersecurity training",
        category="cybersecurity",
        default_config={
            "challenges_enabled": True,
            "team_mode": False,
            "auto_start": True,
            "backup_enabled": True
        },
        resource_requirements={
            "cpu": "500m",
            "memory": "1Gi",
            "storage": "5Gi"
        },
        created_by="admin@example.com",
        is_active=True,
        is_public=True
    )


class TestExternalServiceManager:
    """Test ExternalServiceManager functionality"""

    async def test_create_service_instance_success(self, external_service_manager):
        """Test successful service instance creation"""
        # Mock Resource Cluster response
        resource_response = {
            "instance_id": "resource-456",
            "endpoint_url": "https://ctfd.test.gt2.com",
            "status": "running"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = resource_response
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            external_service_manager.db.commit = AsyncMock()
            external_service_manager.db.refresh = AsyncMock()
            
            result = await external_service_manager.create_service_instance(
                service_type="ctfd",
                service_name="Test CTFd",
                user_email="user@example.com",
                config_overrides={"team_mode": True}
            )
            
            assert result.service_type == "ctfd"
            assert result.service_name == "Test CTFd"
            assert result.created_by == "user@example.com"
            assert result.resource_instance_id == "resource-456"
            assert result.endpoint_url == "https://ctfd.test.gt2.com"
            assert result.status == "running"
            
            external_service_manager.db.add.assert_called_once()
            external_service_manager.db.commit.assert_called_once()

    async def test_create_service_instance_unsupported_type(self, external_service_manager):
        """Test creating service with unsupported type"""
        with pytest.raises(ValueError, match="Unsupported service type: unsupported"):
            await external_service_manager.create_service_instance(
                service_type="unsupported",
                service_name="Test Service",
                user_email="user@example.com"
            )

    async def test_create_service_instance_with_template(self, external_service_manager, sample_service_template):
        """Test creating service instance with template"""
        # Mock template retrieval
        external_service_manager.get_service_template = AsyncMock(return_value=sample_service_template)
        
        # Mock Resource Cluster response
        resource_response = {
            "instance_id": "resource-456",
            "endpoint_url": "https://ctfd.test.gt2.com",
            "status": "running"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = resource_response
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            external_service_manager.db.commit = AsyncMock()
            external_service_manager.db.refresh = AsyncMock()
            
            result = await external_service_manager.create_service_instance(
                service_type="ctfd",
                service_name="Template CTFd",
                user_email="user@example.com",
                template_id="template-123"
            )
            
            # Verify template config was applied
            assert result.service_config["challenges_enabled"] is True
            assert result.resource_limits == sample_service_template.resource_requirements

    async def test_create_service_instance_template_not_found(self, external_service_manager):
        """Test creating service with non-existent template"""
        external_service_manager.get_service_template = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="Template template-456 not found"):
            await external_service_manager.create_service_instance(
                service_type="ctfd",
                service_name="Test Service",
                user_email="user@example.com",
                template_id="template-456"
            )

    async def test_create_service_instance_resource_cluster_error(self, external_service_manager):
        """Test Resource Cluster API error during service creation"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"detail": "Internal server error"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with pytest.raises(RuntimeError, match="Failed to create service instance: Internal server error"):
                await external_service_manager.create_service_instance(
                    service_type="ctfd",
                    service_name="Test CTFd",
                    user_email="user@example.com"
                )

    async def test_create_service_instance_no_capability_token(self, external_service_manager):
        """Test service creation without capability token"""
        external_service_manager.capability_token = None
        
        with pytest.raises(ValueError, match="Capability token not set"):
            await external_service_manager.create_service_instance(
                service_type="ctfd",
                service_name="Test CTFd",
                user_email="user@example.com"
            )

    async def test_get_service_instance_success(self, external_service_manager, sample_service_instance):
        """Test retrieving service instance with access control"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_service_instance
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.get_service_instance(
            "service-123", 
            "user@example.com"
        )
        
        assert result is not None
        assert result.id == "service-123"
        assert result.service_type == "ctfd"
        external_service_manager.db.execute.assert_called_once()

    async def test_get_service_instance_access_denied(self, external_service_manager):
        """Test access denied when user not in allowed_users"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.get_service_instance(
            "service-123", 
            "unauthorized@example.com"
        )
        
        assert result is None

    async def test_list_user_services_success(self, external_service_manager):
        """Test listing user's accessible services"""
        mock_services = [
            ExternalServiceInstance(
                id="service-1",
                service_type="ctfd",
                service_name="CTFd Lab 1",
                status="running",
                created_by="user@example.com",
                allowed_users=["user@example.com"]
            ),
            ExternalServiceInstance(
                id="service-2",
                service_type="canvas",
                service_name="Canvas Course",
                status="running",
                created_by="admin@example.com",
                allowed_users=["user@example.com", "admin@example.com"]
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_services
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.list_user_services("user@example.com")
        
        assert len(result) == 2
        assert result[0].service_type == "ctfd"
        assert result[1].service_type == "canvas"

    async def test_list_user_services_with_filters(self, external_service_manager):
        """Test listing services with type and status filters"""
        mock_services = [
            ExternalServiceInstance(
                id="service-1",
                service_type="ctfd",
                service_name="CTFd Lab 1",
                status="running",
                created_by="user@example.com",
                allowed_users=["user@example.com"]
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_services
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.list_user_services(
            "user@example.com",
            service_type="ctfd",
            status="running"
        )
        
        assert len(result) == 1
        assert result[0].service_type == "ctfd"
        assert result[0].status == "running"

    async def test_stop_service_instance_success(self, external_service_manager, sample_service_instance):
        """Test successful service instance stopping"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.delete.return_value = mock_response
            
            external_service_manager.db.commit = AsyncMock()
            
            result = await external_service_manager.stop_service_instance(
                "service-123",
                "user@example.com"
            )
            
            assert result is True
            assert sample_service_instance.status == "stopped"
            external_service_manager.db.commit.assert_called_once()

    async def test_stop_service_instance_not_found(self, external_service_manager):
        """Test stopping non-existent service instance"""
        external_service_manager.get_service_instance = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="Service instance service-123 not found or access denied"):
            await external_service_manager.stop_service_instance(
                "service-123",
                "user@example.com"
            )

    async def test_stop_service_instance_resource_cluster_failure(self, external_service_manager, sample_service_instance):
        """Test Resource Cluster failure during service stopping"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.delete.return_value = mock_response
            
            result = await external_service_manager.stop_service_instance(
                "service-123",
                "user@example.com"
            )
            
            assert result is False

    async def test_get_service_health_success(self, external_service_manager, sample_service_instance):
        """Test getting service health status"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        health_response = {
            "status": "healthy",
            "uptime_seconds": 3600,
            "restart_count": 2,
            "cpu_usage": 45.2,
            "memory_usage": 512
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = health_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            external_service_manager.db.commit = AsyncMock()
            
            result = await external_service_manager.get_service_health(
                "service-123",
                "user@example.com"
            )
            
            assert result == health_response
            assert sample_service_instance.health_status == "healthy"
            assert sample_service_instance.restart_count == 2
            assert sample_service_instance.last_health_check is not None

    async def test_get_service_health_error(self, external_service_manager, sample_service_instance):
        """Test health check with Resource Cluster error"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            external_service_manager.db.commit = AsyncMock()
            
            result = await external_service_manager.get_service_health(
                "service-123",
                "user@example.com"
            )
            
            assert result["status"] == "error"
            assert "Health check failed: 500" in result["error"]

    async def test_generate_sso_token_success(self, external_service_manager, sample_service_instance):
        """Test SSO token generation for iframe embedding"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        sso_response = {
            "sso_token": "sso-token-123",
            "expires_at": "2024-12-31T23:59:59Z",
            "iframe_url": "https://ctfd.test.gt2.com/sso?token=sso-token-123"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sso_response
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            external_service_manager.db.commit = AsyncMock()
            
            result = await external_service_manager.generate_sso_token(
                "service-123",
                "user@example.com"
            )
            
            assert result == sso_response
            assert sample_service_instance.last_accessed is not None

    async def test_generate_sso_token_error(self, external_service_manager, sample_service_instance):
        """Test SSO token generation failure"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"detail": "Authentication failed"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with pytest.raises(RuntimeError, match="Failed to generate SSO token: Authentication failed"):
                await external_service_manager.generate_sso_token(
                    "service-123",
                    "user@example.com"
                )

    async def test_log_service_access_success(self, external_service_manager):
        """Test logging service access event"""
        external_service_manager.db.commit = AsyncMock()
        external_service_manager.db.refresh = AsyncMock()
        
        result = await external_service_manager.log_service_access(
            service_instance_id="service-123",
            service_type="ctfd",
            user_email="user@example.com",
            access_type="login",
            session_id="session-456",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0...",
            referer="https://tenant.gt2.com",
            actions_performed=["view_challenges", "submit_flag"]
        )
        
        external_service_manager.db.add.assert_called_once()
        external_service_manager.db.commit.assert_called_once()

    async def test_get_service_analytics_success(self, external_service_manager, sample_service_instance):
        """Test getting service usage analytics"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        # Mock access logs
        mock_logs = [
            ServiceAccessLog(
                id="log-1",
                service_instance_id="service-123",
                service_type="ctfd",
                user_email="user1@example.com",
                session_id="session-1",
                access_type="login",
                session_duration_seconds=3600,
                timestamp=datetime.utcnow() - timedelta(days=1)
            ),
            ServiceAccessLog(
                id="log-2",
                service_instance_id="service-123",
                service_type="ctfd",
                user_email="user2@example.com",
                session_id="session-2",
                access_type="login",
                session_duration_seconds=1800,
                timestamp=datetime.utcnow() - timedelta(days=2)
            ),
            ServiceAccessLog(
                id="log-3",
                service_instance_id="service-123",
                service_type="ctfd",
                user_email="user1@example.com",
                session_id="session-3",
                access_type="logout",
                timestamp=datetime.utcnow() - timedelta(hours=2)
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.get_service_analytics(
            "service-123",
            "user@example.com",
            days=30
        )
        
        assert result["instance_id"] == "service-123"
        assert result["service_type"] == "ctfd"
        assert result["total_sessions"] == 3  # 3 unique session IDs
        assert result["unique_users"] == 2  # 2 unique users
        assert result["total_time_hours"] == 1.5  # (3600 + 1800) / 3600
        assert result["analytics_period_days"] == 30
        assert "daily_usage" in result
        assert "uptime_percentage" in result

    async def test_get_service_analytics_access_denied(self, external_service_manager):
        """Test analytics access denied"""
        external_service_manager.get_service_instance = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="Service instance service-123 not found or access denied"):
            await external_service_manager.get_service_analytics(
                "service-123",
                "unauthorized@example.com"
            )

    async def test_create_service_template_success(self, external_service_manager):
        """Test creating service template"""
        external_service_manager.db.commit = AsyncMock()
        external_service_manager.db.refresh = AsyncMock()
        
        result = await external_service_manager.create_service_template(
            template_name="CTFd Cybersecurity Lab",
            service_type="ctfd",
            description="Pre-configured CTFd for cyber training",
            default_config={"team_mode": False, "challenges_enabled": True},
            created_by="admin@example.com",
            category="cybersecurity",
            resource_requirements={"cpu": "500m", "memory": "1Gi"}
        )
        
        external_service_manager.db.add.assert_called_once()
        external_service_manager.db.commit.assert_called_once()

    async def test_get_service_template_success(self, external_service_manager, sample_service_template):
        """Test retrieving service template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_service_template
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.get_service_template("template-123")
        
        assert result is not None
        assert result.id == "template-123"
        assert result.template_name == "CTFd Cybersecurity Lab"

    async def test_get_service_template_not_found(self, external_service_manager):
        """Test template not found"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.get_service_template("nonexistent")
        
        assert result is None

    async def test_list_service_templates_success(self, external_service_manager):
        """Test listing service templates with filters"""
        mock_templates = [
            ServiceTemplate(
                id="template-1",
                template_name="CTFd Lab",
                service_type="ctfd",
                category="cybersecurity",
                is_active=True,
                is_public=True,
                usage_count=10
            ),
            ServiceTemplate(
                id="template-2",
                template_name="Canvas Course",
                service_type="canvas",
                category="education",
                is_active=True,
                is_public=True,
                usage_count=5
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_templates
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.list_service_templates(
            service_type="ctfd",
            category="cybersecurity"
        )
        
        assert len(result) == 2  # Mock returns all, filtering is in SQL

    async def test_share_service_instance_success(self, external_service_manager, sample_service_instance):
        """Test sharing service instance with other users"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        external_service_manager.db.commit = AsyncMock()
        
        result = await external_service_manager.share_service_instance(
            instance_id="service-123",
            owner_email="user@example.com",
            share_with_emails=["colleague1@example.com", "colleague2@example.com"]
        )
        
        assert result is True
        assert len(sample_service_instance.allowed_users) == 3  # Original + 2 new
        assert "colleague1@example.com" in sample_service_instance.allowed_users
        assert "colleague2@example.com" in sample_service_instance.allowed_users
        assert sample_service_instance.access_level == "team"

    async def test_share_service_instance_not_owner(self, external_service_manager):
        """Test sharing service when user is not the owner"""
        non_owner_instance = ExternalServiceInstance(
            id="service-123",
            service_type="ctfd",
            service_name="Test CTFd",
            created_by="original_owner@example.com",
            allowed_users=["user@example.com", "original_owner@example.com"]
        )
        
        external_service_manager.get_service_instance = AsyncMock(return_value=non_owner_instance)
        
        with pytest.raises(ValueError, match="Only the instance creator can share access"):
            await external_service_manager.share_service_instance(
                instance_id="service-123",
                owner_email="user@example.com",  # Not the creator
                share_with_emails=["colleague@example.com"]
            )

    async def test_share_service_instance_not_found(self, external_service_manager):
        """Test sharing non-existent service instance"""
        external_service_manager.get_service_instance = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="Service instance service-123 not found or access denied"):
            await external_service_manager.share_service_instance(
                instance_id="service-123",
                owner_email="user@example.com",
                share_with_emails=["colleague@example.com"]
            )

    async def test_uptime_calculation_recent_activity(self, external_service_manager):
        """Test uptime calculation with recent activity"""
        recent_logs = [
            ServiceAccessLog(
                access_type="login",
                timestamp=datetime.utcnow() - timedelta(hours=2)
            )
        ]
        
        uptime = external_service_manager._calculate_uptime_percentage(recent_logs, 30)
        assert uptime == 95.0

    async def test_uptime_calculation_historical_activity(self, external_service_manager):
        """Test uptime calculation with only historical activity"""
        old_logs = [
            ServiceAccessLog(
                access_type="login",
                timestamp=datetime.utcnow() - timedelta(days=5)
            )
        ]
        
        uptime = external_service_manager._calculate_uptime_percentage(old_logs, 30)
        assert uptime == 85.0

    async def test_uptime_calculation_no_activity(self, external_service_manager):
        """Test uptime calculation with no activity"""
        uptime = external_service_manager._calculate_uptime_percentage([], 30)
        assert uptime == 0.0

    async def test_capability_token_setting(self, external_service_manager):
        """Test setting capability token"""
        token = "new-capability-token"
        external_service_manager.set_capability_token(token)
        assert external_service_manager.capability_token == token

    async def test_service_instance_to_dict(self, sample_service_instance):
        """Test service instance serialization"""
        result = sample_service_instance.to_dict()
        
        assert result["id"] == "service-123"
        assert result["service_type"] == "ctfd"
        assert result["service_name"] == "Test CTFd Instance"
        assert result["status"] == "running"
        assert result["created_by"] == "user@example.com"
        assert result["health_status"] == "healthy"

    async def test_service_access_log_to_dict(self):
        """Test service access log serialization"""
        log = ServiceAccessLog(
            id="log-123",
            service_instance_id="service-456",
            service_type="ctfd",
            user_email="user@example.com",
            session_id="session-789",
            access_type="login",
            ip_address="192.168.1.100",
            session_duration_seconds=3600,
            actions_performed=["view_challenges", "submit_flag"]
        )
        
        result = log.to_dict()
        
        assert result["id"] == "log-123"
        assert result["service_instance_id"] == "service-456"
        assert result["access_type"] == "login"
        assert result["session_duration_seconds"] == 3600
        assert result["actions_performed"] == ["view_challenges", "submit_flag"]

    async def test_service_template_to_dict(self, sample_service_template):
        """Test service template serialization"""
        result = sample_service_template.to_dict()
        
        assert result["id"] == "template-123"
        assert result["template_name"] == "CTFd Cybersecurity Lab"
        assert result["service_type"] == "ctfd"
        assert result["category"] == "cybersecurity"
        assert result["is_active"] is True
        assert result["is_public"] is True

    async def test_http_timeout_handling(self, external_service_manager):
        """Test HTTP timeout handling in Resource Cluster calls"""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock timeout exception
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(httpx.TimeoutException):
                await external_service_manager.create_service_instance(
                    service_type="ctfd",
                    service_name="Test CTFd",
                    user_email="user@example.com"
                )

    async def test_analytics_daily_usage_calculation(self, external_service_manager, sample_service_instance):
        """Test daily usage analytics calculation"""
        external_service_manager.get_service_instance = AsyncMock(return_value=sample_service_instance)
        
        # Mock logs from different days
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        mock_logs = [
            ServiceAccessLog(
                service_instance_id="service-123",
                user_email="user1@example.com",
                session_id="session-1",
                access_type="login",
                timestamp=datetime.combine(today, datetime.min.time())
            ),
            ServiceAccessLog(
                service_instance_id="service-123",
                user_email="user2@example.com",
                session_id="session-2", 
                access_type="login",
                timestamp=datetime.combine(today, datetime.min.time())
            ),
            ServiceAccessLog(
                service_instance_id="service-123",
                user_email="user1@example.com",
                session_id="session-3",
                access_type="login",
                timestamp=datetime.combine(yesterday, datetime.min.time())
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        external_service_manager.db.execute.return_value = mock_result
        
        result = await external_service_manager.get_service_analytics(
            "service-123",
            "user@example.com"
        )
        
        daily_usage = result["daily_usage"]
        assert today.isoformat() in daily_usage
        assert yesterday.isoformat() in daily_usage
        assert daily_usage[today.isoformat()]["sessions"] == 2
        assert daily_usage[today.isoformat()]["unique_users"] == 2
        assert daily_usage[yesterday.isoformat()]["sessions"] == 1
        assert daily_usage[yesterday.isoformat()]["unique_users"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])