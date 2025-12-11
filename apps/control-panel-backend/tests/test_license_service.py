"""
Unit tests for License Service and enforcement
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import HTTPException
from faker import Faker

from app.services.license_service import LicenseService
from app.models.license import License, LicenseSeat
from app.models.tenant import Tenant
from app.models.user import User
from app.models.resource import AIResource, TenantResource

fake = Faker()


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def license_service(mock_db_session):
    """Create LicenseService instance with mocked database"""
    return LicenseService(mock_db_session)


@pytest.fixture
def sample_tenant():
    """Sample tenant data"""
    tenant = Mock(spec=Tenant)
    tenant.id = 1
    tenant.name = "Test Corporation"
    tenant.domain = "testcorp"
    return tenant


@pytest.fixture
def sample_license():
    """Sample license data"""
    license = Mock(spec=License)
    license.id = 1
    license.tenant_id = 1
    license.license_key = "GT2-TEST-1234-ABCD-EFGH"
    license.license_type = "professional"
    license.max_seats = 50
    license.used_seats = 15
    license.billing_status = "active"
    license.billing_cycle = "monthly"
    license.price_per_seat = Decimal("50.00")
    license.resource_multiplier = Decimal("1.0")
    license.enforcement_mode = "soft"
    license.valid_from = datetime.utcnow() - timedelta(days=30)
    license.valid_until = datetime.utcnow() + timedelta(days=335)
    license.grace_period_ends = None
    license.resource_limits = {
        "llm_tokens_monthly": 5000000,
        "storage_gb": 200,
        "api_calls_hourly": 500
    }
    license.feature_flags = {
        "advanced_analytics": True,
        "multi_agent": True,
        "api_access": True
    }
    license.allowed_resources = None
    license.last_validated = datetime.utcnow()
    license.created_at = datetime.utcnow() - timedelta(days=30)
    license.updated_at = datetime.utcnow()
    license.grace_period_days = 7
    return license


@pytest.fixture
def sample_user():
    """Sample user data"""
    user = Mock(spec=User)
    user.id = 1
    user.email = "user@testcorp.com"
    user.full_name = "Test User"
    user.tenant_id = 1
    user.is_active = True
    return user


@pytest.fixture
def sample_license_seat():
    """Sample license seat data"""
    seat = Mock(spec=LicenseSeat)
    seat.id = 1
    seat.license_id = 1
    seat.user_id = 1
    seat.seat_type = "standard"
    seat.is_active = True
    seat.assigned_at = datetime.utcnow() - timedelta(days=5)
    seat.last_accessed = datetime.utcnow() - timedelta(hours=1)
    seat.expires_at = None
    return seat


class TestLicenseService:
    """Test the LicenseService class"""
    
    def test_create_license_success(self, license_service, mock_db_session):
        """Test successful license creation"""
        # Mock no existing license
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with patch.object(license_service, '_generate_license_key', return_value="GT2-TEST-1234-ABCD-EFGH"):
            result = license_service.create_license(
                tenant_id=1,
                license_type="professional",
                max_seats=50,
                billing_cycle="monthly",
                price_per_seat=50.00,
                valid_days=365,
                created_by="admin@company.com"
            )
        
        # Verify license was added to database
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
        
        # Verify license structure (mocked serialization)
        assert isinstance(result, dict)
    
    def test_create_license_already_exists(self, license_service, mock_db_session, sample_license):
        """Test license creation when tenant already has license"""
        # Mock existing license
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.create_license(
                tenant_id=1,
                license_type="professional",
                max_seats=50,
                billing_cycle="monthly",
                price_per_seat=50.00
            )
        
        assert exc_info.value.status_code == 400
        assert "Tenant already has a license" in exc_info.value.detail
    
    def test_get_license_success(self, license_service, mock_db_session, sample_license):
        """Test successful license retrieval"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with patch.object(license_service, '_serialize_license', return_value={"license_id": 1}):
            result = license_service.get_license(1)
        
        assert result["license_id"] == 1
    
    def test_get_license_not_found(self, license_service, mock_db_session):
        """Test license retrieval when not found"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.get_license(999)
        
        assert exc_info.value.status_code == 404
        assert "License not found for tenant" in exc_info.value.detail
    
    def test_update_license_success(self, license_service, mock_db_session, sample_license):
        """Test successful license update"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with patch.object(license_service, '_serialize_license', return_value={"license_id": 1, "max_seats": 100}):
            result = license_service.update_license(
                tenant_id=1,
                max_seats=100,
                billing_status="active",
                modified_by="admin@company.com"
            )
        
        # Verify updates were applied
        assert sample_license.max_seats == 100
        assert sample_license.billing_status == "active"
        assert sample_license.last_modified_by == "admin@company.com"
        
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    def test_update_license_reduce_seats_below_usage(self, license_service, mock_db_session, sample_license):
        """Test license update when reducing seats below current usage"""
        sample_license.used_seats = 30
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.update_license(tenant_id=1, max_seats=20)
        
        assert exc_info.value.status_code == 400
        assert "Cannot reduce seats below current usage (30)" in exc_info.value.detail
    
    def test_update_license_suspended_sets_grace_period(self, license_service, mock_db_session, sample_license):
        """Test that suspending license sets grace period"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with patch.object(license_service, '_serialize_license', return_value={}):
            license_service.update_license(tenant_id=1, billing_status="suspended")
        
        # Verify grace period was set
        assert sample_license.grace_period_ends is not None
        assert sample_license.grace_period_ends > datetime.utcnow()
    
    def test_assign_seat_success(self, license_service, mock_db_session, sample_license):
        """Test successful seat assignment"""
        # Mock license lookup and no existing seat
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,  # license lookup
            None            # no existing seat
        ]
        
        result = license_service.assign_seat(tenant_id=1, user_id=1, seat_type="standard")
        
        # Verify seat was created
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
        
        # Verify used seats was incremented
        assert sample_license.used_seats == 16  # was 15, now 16
        
        # Verify response structure
        assert result["user_id"] == 1
        assert result["seat_type"] == "standard"
        assert "assigned_at" in result
        assert result["remaining_seats"] == 34  # 50 - 16
    
    def test_assign_seat_license_not_found(self, license_service, mock_db_session):
        """Test seat assignment when license not found"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.assign_seat(tenant_id=999, user_id=1)
        
        assert exc_info.value.status_code == 404
        assert "License not found" in exc_info.value.detail
    
    def test_assign_seat_license_suspended_hard_mode(self, license_service, mock_db_session, sample_license):
        """Test seat assignment when license suspended in hard enforcement mode"""
        sample_license.billing_status = "suspended"
        sample_license.enforcement_mode = "hard"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.assign_seat(tenant_id=1, user_id=1)
        
        assert exc_info.value.status_code == 403
        assert "License is suspended" in exc_info.value.detail
    
    def test_assign_seat_limit_reached(self, license_service, mock_db_session, sample_license):
        """Test seat assignment when seat limit reached"""
        sample_license.used_seats = 50  # Equal to max_seats
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.assign_seat(tenant_id=1, user_id=1)
        
        assert exc_info.value.status_code == 403
        assert "License seat limit reached (50)" in exc_info.value.detail
    
    def test_assign_seat_user_already_has_seat(self, license_service, mock_db_session, sample_license, sample_license_seat):
        """Test seat assignment when user already has active seat"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,      # license lookup
            sample_license_seat  # existing seat found
        ]
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.assign_seat(tenant_id=1, user_id=1)
        
        assert exc_info.value.status_code == 400
        assert "User already has an active seat" in exc_info.value.detail
    
    def test_release_seat_success(self, license_service, mock_db_session, sample_license, sample_license_seat):
        """Test successful seat release"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,      # license lookup
            sample_license_seat  # seat lookup
        ]
        
        result = license_service.release_seat(tenant_id=1, user_id=1)
        
        # Verify seat was deactivated
        assert sample_license_seat.is_active is False
        assert sample_license_seat.expires_at is not None
        
        # Verify used seats was decremented
        assert sample_license.used_seats == 14  # was 15, now 14
        
        mock_db_session.commit.assert_called_once()
        
        # Verify response
        assert result["user_id"] == 1
        assert "released_at" in result
        assert result["available_seats"] == 36  # 50 - 14
    
    def test_release_seat_license_not_found(self, license_service, mock_db_session):
        """Test seat release when license not found"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.release_seat(tenant_id=999, user_id=1)
        
        assert exc_info.value.status_code == 404
        assert "License not found" in exc_info.value.detail
    
    def test_release_seat_no_active_seat(self, license_service, mock_db_session, sample_license):
        """Test seat release when user has no active seat"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,  # license found
            None            # no active seat
        ]
        
        with pytest.raises(HTTPException) as exc_info:
            license_service.release_seat(tenant_id=1, user_id=999)
        
        assert exc_info.value.status_code == 404
        assert "No active seat found for user" in exc_info.value.detail
    
    def test_get_seat_usage(self, license_service, mock_db_session, sample_license, sample_license_seat, sample_user):
        """Test seat usage retrieval"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        mock_db_session.query.return_value.join.return_value.filter.return_value.all.return_value = [
            (sample_license_seat, sample_user)
        ]
        
        result = license_service.get_seat_usage(1)
        
        assert result["tenant_id"] == 1
        assert result["license_type"] == "professional"
        assert result["max_seats"] == 50
        assert result["used_seats"] == 15
        assert result["available_seats"] == 35
        assert result["billing_status"] == "active"
        
        # Verify active seats list
        assert len(result["active_seats"]) == 1
        seat_info = result["active_seats"][0]
        assert seat_info["user_id"] == 1
        assert seat_info["user_email"] == "user@testcorp.com"
        assert seat_info["user_name"] == "Test User"
        assert seat_info["seat_type"] == "standard"
    
    def test_validate_resource_access_success(self, license_service, mock_db_session, sample_license):
        """Test successful resource access validation"""
        # Mock tenant resource exists
        tenant_resource = Mock(spec=TenantResource)
        tenant_resource.tenant_id = 1
        tenant_resource.resource_id = 1
        tenant_resource.is_enabled = True
        
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,     # license lookup
            tenant_resource     # tenant resource lookup
        ]
        
        result = license_service.validate_resource_access(tenant_id=1, resource_id=1)
        
        assert result is True
    
    def test_validate_resource_access_no_license(self, license_service, mock_db_session):
        """Test resource access validation when no license exists"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        result = license_service.validate_resource_access(tenant_id=999, resource_id=1)
        
        assert result is False
    
    def test_validate_resource_access_license_suspended_hard_mode(self, license_service, mock_db_session, sample_license):
        """Test resource access validation when license suspended in hard mode"""
        sample_license.billing_status = "suspended"
        sample_license.enforcement_mode = "hard"
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        result = license_service.validate_resource_access(tenant_id=1, resource_id=1)
        
        assert result is False
    
    def test_validate_resource_access_resource_not_allowed(self, license_service, mock_db_session, sample_license):
        """Test resource access validation when resource not in allowed list"""
        sample_license.allowed_resources = [
            {"resource_id": 2},
            {"resource_id": 3}
        ]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        result = license_service.validate_resource_access(tenant_id=1, resource_id=1)
        
        assert result is False
    
    def test_validate_resource_access_tenant_resource_not_assigned(self, license_service, mock_db_session, sample_license):
        """Test resource access validation when tenant doesn't have resource assigned"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,  # license found
            None            # no tenant resource
        ]
        
        result = license_service.validate_resource_access(tenant_id=1, resource_id=1)
        
        assert result is False
    
    def test_enforce_license_limits_expired(self, license_service, mock_db_session, sample_license):
        """Test license enforcement when license expired"""
        sample_license.valid_until = datetime.utcnow() - timedelta(days=1)  # Expired
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        result = license_service.enforce_license_limits(1)
        
        assert result["enforced"] is True
        assert "License expired" in result["actions"]
        assert sample_license.billing_status == "expired"
        
        mock_db_session.commit.assert_called_once()
    
    def test_enforce_license_limits_grace_period_ended(self, license_service, mock_db_session, sample_license):
        """Test license enforcement when grace period ended"""
        sample_license.billing_status = "grace_period"
        sample_license.grace_period_ends = datetime.utcnow() - timedelta(hours=1)  # Ended
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        result = license_service.enforce_license_limits(1)
        
        assert result["enforced"] is True
        assert "Grace period ended" in result["actions"]
        assert sample_license.billing_status == "suspended"
    
    def test_enforce_license_limits_excess_seats(self, license_service, mock_db_session, sample_license):
        """Test license enforcement when there are excess seats"""
        sample_license.used_seats = 55  # Exceeds max_seats of 50
        
        # Mock excess seats query
        excess_seat1 = Mock(spec=LicenseSeat)
        excess_seat1.assigned_at = datetime.utcnow() - timedelta(days=10)
        excess_seat1.is_active = True
        
        excess_seat2 = Mock(spec=LicenseSeat)
        excess_seat2.assigned_at = datetime.utcnow() - timedelta(days=8)
        excess_seat2.is_active = True
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            excess_seat1, excess_seat2, Mock(), Mock(), Mock()  # 5 excess seats
        ]
        
        result = license_service.enforce_license_limits(1)
        
        assert result["enforced"] is True
        assert "Deactivated 5 excess seats" in result["actions"]
        assert sample_license.used_seats == 50  # Reduced from 55 to 50
        
        # Verify seats were deactivated
        assert excess_seat1.is_active is False
        assert excess_seat1.expires_at is not None
    
    def test_enforce_license_limits_no_license(self, license_service, mock_db_session):
        """Test license enforcement when no license exists"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        result = license_service.enforce_license_limits(999)
        
        assert result["enforced"] is False
        assert result["reason"] == "No license found"
    
    def test_generate_license_key(self, license_service):
        """Test license key generation"""
        key = license_service._generate_license_key()
        
        # Verify format: GT2-XXXX-XXXX-XXXX-XXXX
        assert key.startswith("GT2-")
        segments = key.split("-")
        assert len(segments) == 5
        assert segments[0] == "GT2"
        
        for segment in segments[1:]:
            assert len(segment) == 4
            assert segment.isalnum()
    
    def test_get_default_resource_limits(self, license_service):
        """Test default resource limits for different license types"""
        # Standard license
        standard_limits = license_service._get_default_resource_limits("standard")
        assert standard_limits["llm_tokens_monthly"] == 1000000
        assert standard_limits["storage_gb"] == 50
        assert standard_limits["concurrent_agents"] == 2
        
        # Professional license
        pro_limits = license_service._get_default_resource_limits("professional")
        assert pro_limits["llm_tokens_monthly"] == 5000000
        assert pro_limits["storage_gb"] == 200
        assert pro_limits["concurrent_agents"] == 5
        
        # Enterprise license
        enterprise_limits = license_service._get_default_resource_limits("enterprise")
        assert enterprise_limits["llm_tokens_monthly"] == -1  # Unlimited
        assert enterprise_limits["storage_gb"] == 1000
        assert enterprise_limits["concurrent_agents"] == 20
        
        # Unknown license type defaults to standard
        unknown_limits = license_service._get_default_resource_limits("unknown")
        assert unknown_limits == standard_limits
    
    def test_get_default_feature_flags(self, license_service):
        """Test default feature flags for different license types"""
        # Standard license
        standard_flags = license_service._get_default_feature_flags("standard")
        assert standard_flags["advanced_analytics"] is False
        assert standard_flags["multi_agent"] is False
        assert standard_flags["api_access"] is True
        
        # Professional license
        pro_flags = license_service._get_default_feature_flags("professional")
        assert pro_flags["advanced_analytics"] is True
        assert pro_flags["multi_agent"] is True
        assert pro_flags["team_collaboration"] is True
        
        # Enterprise license
        enterprise_flags = license_service._get_default_feature_flags("enterprise")
        assert enterprise_flags["advanced_analytics"] is True
        assert enterprise_flags["multi_agent"] is True
        assert enterprise_flags["custom_models"] is True
        assert enterprise_flags["white_label"] is True
        
        # Unknown license type defaults to standard
        unknown_flags = license_service._get_default_feature_flags("unknown")
        assert unknown_flags == standard_flags
    
    def test_serialize_license(self, license_service, sample_license):
        """Test license serialization"""
        # Mock license UUID (not in fixture)
        sample_license.license_uuid = "550e8400-e29b-41d4-a716-446655440000"
        
        result = license_service._serialize_license(sample_license)
        
        assert result["license_id"] == 1
        assert result["license_uuid"] == "550e8400-e29b-41d4-a716-446655440000"
        assert result["tenant_id"] == 1
        assert result["license_key"] == "GT2-TEST-1234-ABCD-EFGH"
        assert result["license_type"] == "professional"
        assert result["max_seats"] == 50
        assert result["used_seats"] == 15
        assert result["available_seats"] == 35
        assert result["billing_status"] == "active"
        assert result["price_per_seat"] == 50.00
        assert result["enforcement_mode"] == "soft"
        assert "valid_from" in result
        assert "valid_until" in result
        assert result["resource_limits"]["llm_tokens_monthly"] == 5000000
        assert result["feature_flags"]["advanced_analytics"] is True


class TestLicenseServiceIntegration:
    """Integration tests for LicenseService"""
    
    def test_complete_license_lifecycle(self, license_service, mock_db_session):
        """Test complete license lifecycle from creation to enforcement"""
        # 1. Create license
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with patch.object(license_service, '_generate_license_key', return_value="GT2-INTEG-TEST-1234-ABCD"), \
             patch.object(license_service, '_serialize_license', return_value={"license_id": 1}):
            
            create_result = license_service.create_license(
                tenant_id=1,
                license_type="professional",
                max_seats=10,
                billing_cycle="monthly",
                price_per_seat=50.00
            )
        
        assert create_result["license_id"] == 1
        
        # 2. Assign seats (simulate multiple users)
        sample_license = Mock(spec=License)
        sample_license.id = 1
        sample_license.tenant_id = 1
        sample_license.max_seats = 10
        sample_license.used_seats = 0
        sample_license.billing_status = "active"
        sample_license.enforcement_mode = "soft"
        
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,  # license lookup
            None            # no existing seat
        ]
        
        # Assign seat
        seat_result = license_service.assign_seat(tenant_id=1, user_id=1)
        assert seat_result["user_id"] == 1
        assert sample_license.used_seats == 1
        
        # 3. Check seat usage
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        
        mock_seat = Mock(spec=LicenseSeat)
        mock_seat.id = 1
        mock_seat.user_id = 1
        mock_seat.seat_type = "standard"
        mock_seat.assigned_at = datetime.utcnow()
        mock_seat.last_accessed = datetime.utcnow()
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        mock_db_session.query.return_value.join.return_value.filter.return_value.all.return_value = [
            (mock_seat, mock_user)
        ]
        
        usage_result = license_service.get_seat_usage(1)
        assert usage_result["used_seats"] == 1
        assert usage_result["available_seats"] == 9
        assert len(usage_result["active_seats"]) == 1
        
        # 4. Validate resource access
        mock_tenant_resource = Mock(spec=TenantResource)
        mock_tenant_resource.tenant_id = 1
        mock_tenant_resource.resource_id = 1
        mock_tenant_resource.is_enabled = True
        
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_license,      # license lookup
            mock_tenant_resource # tenant resource lookup
        ]
        
        access_result = license_service.validate_resource_access(tenant_id=1, resource_id=1)
        assert access_result is True
        
        # 5. Enforce limits (simulate no violations)
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_license
        
        enforcement_result = license_service.enforce_license_limits(1)
        assert enforcement_result["enforced"] is False  # No violations
    
    def test_license_enforcement_scenarios(self, license_service, mock_db_session):
        """Test various license enforcement scenarios"""
        # Scenario 1: License expiration
        expired_license = Mock(spec=License)
        expired_license.valid_until = datetime.utcnow() - timedelta(days=1)
        expired_license.billing_status = "active"
        expired_license.used_seats = 5
        expired_license.max_seats = 10
        expired_license.last_validated = datetime.utcnow() - timedelta(hours=1)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = expired_license
        
        result = license_service.enforce_license_limits(1)
        assert result["enforced"] is True
        assert "License expired" in result["actions"]
        assert expired_license.billing_status == "expired"
        
        # Scenario 2: Seat limit exceeded
        overlimit_license = Mock(spec=License)
        overlimit_license.valid_until = datetime.utcnow() + timedelta(days=30)
        overlimit_license.billing_status = "active"
        overlimit_license.used_seats = 12  # Exceeds limit
        overlimit_license.max_seats = 10
        overlimit_license.grace_period_ends = None
        overlimit_license.last_validated = datetime.utcnow() - timedelta(hours=1)
        
        # Mock excess seats to deactivate
        excess_seats = []
        for i in range(2):  # 2 excess seats
            seat = Mock(spec=LicenseSeat)
            seat.assigned_at = datetime.utcnow() - timedelta(days=i+1)
            seat.is_active = True
            excess_seats.append(seat)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = overlimit_license
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = excess_seats
        
        result = license_service.enforce_license_limits(1)
        assert result["enforced"] is True
        assert "Deactivated 2 excess seats" in result["actions"]
        assert overlimit_license.used_seats == 10
        
        for seat in excess_seats:
            assert seat.is_active is False
            assert seat.expires_at is not None
    
    def test_license_type_feature_validation(self, license_service):
        """Test that different license types have appropriate features"""
        # Standard license - limited features
        standard_limits = license_service._get_default_resource_limits("standard")
        standard_flags = license_service._get_default_feature_flags("standard")
        
        assert standard_limits["llm_tokens_monthly"] == 1000000  # Limited
        assert standard_flags["multi_agent"] is False
        assert standard_flags["custom_models"] is False
        
        # Professional license - more features
        pro_limits = license_service._get_default_resource_limits("professional")
        pro_flags = license_service._get_default_feature_flags("professional")
        
        assert pro_limits["llm_tokens_monthly"] == 5000000  # Higher limit
        assert pro_flags["multi_agent"] is True
        assert pro_flags["team_collaboration"] is True
        assert pro_flags["custom_models"] is False  # Still restricted
        
        # Enterprise license - full features
        enterprise_limits = license_service._get_default_resource_limits("enterprise")
        enterprise_flags = license_service._get_default_feature_flags("enterprise")
        
        assert enterprise_limits["llm_tokens_monthly"] == -1  # Unlimited
        assert enterprise_flags["multi_agent"] is True
        assert enterprise_flags["custom_models"] is True
        assert enterprise_flags["white_label"] is True