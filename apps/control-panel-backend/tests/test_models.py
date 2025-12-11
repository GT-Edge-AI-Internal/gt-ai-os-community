"""
Unit tests for database models
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.tenant import Tenant, TenantResource
from app.models.ai_resource import AIResource
from app.models.usage import UsageRecord
from app.models.audit import AuditLog


@pytest.mark.unit
class TestUserModel:
    """Test User model functionality."""

    async def test_create_user(self, db_session: AsyncSession, user_data: dict):
        """Test creating a new user."""
        user = User(**user_data, hashed_password="hashed_password")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.email == user_data["email"]
        assert user.full_name == user_data["full_name"]
        assert user.user_type == user_data["user_type"]
        assert user.is_active is True
        assert user.uuid is not None

    async def test_user_email_uniqueness(self, db_session: AsyncSession):
        """Test that user emails must be unique."""
        user1 = User(
            email="test@example.com",
            full_name="Test User 1",
            hashed_password="hash1"
        )
        user2 = User(
            email="test@example.com",
            full_name="Test User 2", 
            hashed_password="hash2"
        )

        db_session.add(user1)
        await db_session.commit()

        db_session.add(user2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    def test_user_to_dict(self, test_user: User):
        """Test user to_dict method."""
        user_dict = test_user.to_dict()

        assert "id" in user_dict
        assert "uuid" in user_dict
        assert "email" in user_dict
        assert "full_name" in user_dict
        assert "user_type" in user_dict
        assert "capabilities" in user_dict
        assert "hashed_password" not in user_dict  # Sensitive data excluded by default

    def test_user_to_dict_with_sensitive(self, test_user: User):
        """Test user to_dict method with sensitive data included."""
        user_dict = test_user.to_dict(include_sensitive=True)

        assert "hashed_password" in user_dict

    def test_user_is_super_admin(self, test_admin: User):
        """Test user type checking methods."""
        assert test_admin.is_super_admin is True
        assert test_admin.is_tenant_admin is False
        assert test_admin.is_tenant_user is False

    def test_user_has_capability(self, test_user: User):
        """Test user capability checking."""
        # Assuming test_user has tenant:test:* read/write capabilities
        assert test_user.has_capability("tenant:test:conversations", "read") is True
        assert test_user.has_capability("tenant:test:conversations", "write") is True
        assert test_user.has_capability("tenant:test:conversations", "admin") is False
        assert test_user.has_capability("tenant:other:conversations", "read") is False


@pytest.mark.unit
class TestTenantModel:
    """Test Tenant model functionality."""

    async def test_create_tenant(self, db_session: AsyncSession, tenant_data: dict):
        """Test creating a new tenant."""
        tenant = Tenant(**tenant_data)
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        assert tenant.id is not None
        assert tenant.name == tenant_data["name"]
        assert tenant.domain == tenant_data["domain"]
        assert tenant.status == "pending"
        assert tenant.uuid is not None

    async def test_tenant_domain_uniqueness(self, db_session: AsyncSession):
        """Test that tenant domains must be unique."""
        tenant1 = Tenant(name="Tenant 1", domain="test", namespace="gt-test", subdomain="test")
        tenant2 = Tenant(name="Tenant 2", domain="test", namespace="gt-test2", subdomain="test2")

        db_session.add(tenant1)
        await db_session.commit()

        db_session.add(tenant2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    def test_tenant_to_dict(self, test_tenant: Tenant):
        """Test tenant to_dict method."""
        tenant_dict = test_tenant.to_dict()

        assert "id" in tenant_dict
        assert "uuid" in tenant_dict
        assert "name" in tenant_dict
        assert "domain" in tenant_dict
        assert "status" in tenant_dict
        assert "resource_limits" in tenant_dict

    def test_tenant_is_active(self, test_tenant: Tenant):
        """Test tenant active status checking."""
        test_tenant.status = "active"
        assert test_tenant.is_active is True

        test_tenant.status = "suspended"
        assert test_tenant.is_active is False


@pytest.mark.unit  
class TestAIResourceModel:
    """Test AIResource model functionality."""

    async def test_create_ai_resource(self, db_session: AsyncSession, ai_resource_data: dict):
        """Test creating a new AI resource."""
        resource = AIResource(**ai_resource_data)
        db_session.add(resource)
        await db_session.commit()
        await db_session.refresh(resource)

        assert resource.id is not None
        assert resource.name == ai_resource_data["name"]
        assert resource.resource_type == ai_resource_data["resource_type"]
        assert resource.provider == ai_resource_data["provider"]
        assert resource.is_active is True

    def test_ai_resource_type_properties(self, test_ai_resource: AIResource):
        """Test AI resource type checking properties."""
        test_ai_resource.resource_type = "llm"
        assert test_ai_resource.is_llm is True
        assert test_ai_resource.is_embedding is False
        assert test_ai_resource.is_image_generation is False

    def test_ai_resource_default_config(self, test_ai_resource: AIResource):
        """Test AI resource default configuration."""
        test_ai_resource.resource_type = "llm"
        default_config = test_ai_resource.get_default_config()
        
        assert "max_tokens" in default_config
        assert "temperature" in default_config
        assert default_config["max_tokens"] == 4000

    def test_ai_resource_merge_config(self, test_ai_resource: AIResource):
        """Test AI resource configuration merging."""
        test_ai_resource.resource_type = "llm"
        test_ai_resource.configuration = {"temperature": 0.9}
        
        custom_config = {"max_tokens": 8000}
        merged = test_ai_resource.merge_config(custom_config)
        
        assert merged["temperature"] == 0.9  # From resource config
        assert merged["max_tokens"] == 8000  # From custom config
    
    def test_ai_resource_ha_properties(self, test_ai_resource: AIResource):
        """Test HA-specific properties."""
        test_ai_resource.health_status = "healthy"
        test_ai_resource.is_active = True
        test_ai_resource.failover_endpoints = ["https://backup1.com", "https://backup2.com"]
        
        assert test_ai_resource.is_healthy is True
        assert test_ai_resource.has_failover is True
        
        test_ai_resource.health_status = "unhealthy"
        assert test_ai_resource.is_healthy is False
        
        test_ai_resource.failover_endpoints = []
        assert test_ai_resource.has_failover is False
    
    def test_ai_resource_get_available_endpoints(self, test_ai_resource: AIResource):
        """Test getting available endpoints."""
        test_ai_resource.primary_endpoint = "https://primary.com"
        test_ai_resource.api_endpoints = ["https://primary.com", "https://api1.com"]
        test_ai_resource.failover_endpoints = ["https://backup1.com", "https://backup2.com"]
        
        endpoints = test_ai_resource.get_available_endpoints()
        
        assert "https://primary.com" in endpoints
        assert "https://api1.com" in endpoints
        assert "https://backup1.com" in endpoints
        assert "https://backup2.com" in endpoints
        # Should not have duplicates
        assert len(endpoints) == len(set(endpoints))
    
    def test_ai_resource_get_healthy_endpoints(self, test_ai_resource: AIResource):
        """Test getting healthy endpoints."""
        test_ai_resource.primary_endpoint = "https://primary.com"
        test_ai_resource.api_endpoints = ["https://primary.com", "https://api1.com"]
        test_ai_resource.health_status = "healthy"
        test_ai_resource.is_active = True
        
        endpoints = test_ai_resource.get_healthy_endpoints()
        assert len(endpoints) > 0
        
        test_ai_resource.health_status = "unhealthy"
        endpoints = test_ai_resource.get_healthy_endpoints()
        assert len(endpoints) == 0
    
    def test_ai_resource_update_health_status(self, test_ai_resource: AIResource):
        """Test updating health status."""
        from datetime import datetime
        
        test_time = datetime.utcnow()
        test_ai_resource.update_health_status("healthy", test_time)
        
        assert test_ai_resource.health_status == "healthy"
        assert test_ai_resource.last_health_check == test_time
    
    def test_ai_resource_calculate_cost(self, test_ai_resource: AIResource):
        """Test cost calculation."""
        test_ai_resource.cost_per_1k_tokens = 0.005  # $0.005 per 1K tokens
        
        cost = test_ai_resource.calculate_cost(1000)  # 1K tokens
        assert cost == 50  # 50 cents
        
        cost = test_ai_resource.calculate_cost(2500)  # 2.5K tokens
        assert cost == 125  # 125 cents
        
        test_ai_resource.cost_per_1k_tokens = 0.0
        cost = test_ai_resource.calculate_cost(1000)
        assert cost == 0  # Free resource
    
    def test_ai_resource_groq_defaults(self):
        """Test Groq default configuration."""
        defaults = AIResource.get_groq_defaults()
        
        assert defaults["provider"] == "groq"
        assert "api_endpoints" in defaults
        assert "primary_endpoint" in defaults
        assert "health_check_url" in defaults
        assert defaults["max_requests_per_minute"] > 0
        assert defaults["latency_sla_ms"] > 0
    
    def test_ai_resource_function_calling_type(self, test_ai_resource: AIResource):
        """Test function calling resource type."""
        test_ai_resource.resource_type = "function_calling"
        
        assert test_ai_resource.is_function_calling is True
        assert test_ai_resource.is_llm is False
        assert test_ai_resource.is_embedding is False
        assert test_ai_resource.is_image_generation is False
    
    def test_ai_resource_enhanced_to_dict(self, test_ai_resource: AIResource):
        """Test enhanced to_dict method with HA information."""
        test_ai_resource.description = "Test description"
        test_ai_resource.primary_endpoint = "https://api.test.com"
        test_ai_resource.health_status = "healthy"
        test_ai_resource.priority = 150
        test_ai_resource.api_endpoints = ["https://api.test.com"]
        test_ai_resource.failover_endpoints = ["https://backup.test.com"]
        
        # Test without sensitive data
        data = test_ai_resource.to_dict(include_sensitive=False)
        assert "description" in data
        assert "primary_endpoint" in data
        assert "health_status" in data
        assert "priority" in data
        assert "api_endpoints" not in data
        assert "failover_endpoints" not in data
        
        # Test with sensitive data
        sensitive_data = test_ai_resource.to_dict(include_sensitive=True)
        assert "api_endpoints" in sensitive_data
        assert "failover_endpoints" in sensitive_data
    
    def test_ai_resource_enhanced_default_configs(self, test_ai_resource: AIResource):
        """Test enhanced default configurations."""
        # Test LLM config
        test_ai_resource.resource_type = "llm"
        config = test_ai_resource.get_default_config()
        assert "stream" in config
        assert "stop" in config
        
        # Test embedding config
        test_ai_resource.resource_type = "embedding"
        config = test_ai_resource.get_default_config()
        assert "encoding_format" in config
        
        # Test function calling config
        test_ai_resource.resource_type = "function_calling"
        config = test_ai_resource.get_default_config()
        assert "function_call" in config
        assert "tools" in config
        assert config["temperature"] == 0.1  # Lower temp for function calling


@pytest.mark.unit
class TestUsageRecordModel:
    """Test UsageRecord model functionality."""

    async def test_create_usage_record(
        self, 
        db_session: AsyncSession, 
        test_tenant: Tenant, 
        test_ai_resource: AIResource
    ):
        """Test creating a usage record."""
        usage = UsageRecord(
            tenant_id=test_tenant.id,
            resource_id=test_ai_resource.id,
            user_email="test@example.com",
            request_type="chat",
            tokens_used=1000,
            cost_cents=50
        )
        
        db_session.add(usage)
        await db_session.commit()
        await db_session.refresh(usage)

        assert usage.id is not None
        assert usage.tenant_id == test_tenant.id
        assert usage.resource_id == test_ai_resource.id
        assert usage.tokens_used == 1000
        assert usage.cost_cents == 50

    def test_usage_record_cost_dollars(self, test_tenant: Tenant, test_ai_resource: AIResource):
        """Test usage record cost in dollars calculation."""
        usage = UsageRecord(
            tenant_id=test_tenant.id,
            resource_id=test_ai_resource.id,
            user_email="test@example.com",
            request_type="chat",
            tokens_used=1000,
            cost_cents=150
        )

        assert usage.cost_dollars == 1.50

    def test_usage_record_calculate_cost(self):
        """Test usage cost calculation."""
        # Test Groq LLM cost
        cost = UsageRecord.calculate_cost(1000, "llm", "groq")
        assert cost > 0
        assert isinstance(cost, int)  # Cost in cents

        # Test different token amounts
        cost_1k = UsageRecord.calculate_cost(1000, "llm", "groq")
        cost_2k = UsageRecord.calculate_cost(2000, "llm", "groq")
        assert cost_2k > cost_1k


@pytest.mark.unit
class TestAuditLogModel:
    """Test AuditLog model functionality."""

    async def test_create_audit_log(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_tenant: Tenant
    ):
        """Test creating an audit log entry."""
        audit = AuditLog.create_log(
            action="user.login",
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            details={"ip": "127.0.0.1"}
        )
        
        db_session.add(audit)
        await db_session.commit()
        await db_session.refresh(audit)

        assert audit.id is not None
        assert audit.action == "user.login"
        assert audit.user_id == test_user.id
        assert audit.tenant_id == test_tenant.id
        assert audit.details["ip"] == "127.0.0.1"

    def test_audit_log_to_dict(self, test_user: User):
        """Test audit log to_dict method."""
        audit = AuditLog.create_log(
            action="test.action",
            user_id=test_user.id,
            details={"test": "value"}
        )

        audit_dict = audit.to_dict()
        assert "action" in audit_dict
        assert "user_id" in audit_dict
        assert "details" in audit_dict


@pytest.mark.unit  
class TestTenantResourceModel:
    """Test TenantResource model functionality."""

    async def test_create_tenant_resource(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        test_ai_resource: AIResource
    ):
        """Test creating a tenant resource assignment."""
        tenant_resource = TenantResource(
            tenant_id=test_tenant.id,
            resource_id=test_ai_resource.id,
            usage_limits={
                "max_requests_per_hour": 500,
                "max_tokens_per_request": 4000
            }
        )

        db_session.add(tenant_resource)
        await db_session.commit()
        await db_session.refresh(tenant_resource)

        assert tenant_resource.id is not None
        assert tenant_resource.tenant_id == test_tenant.id
        assert tenant_resource.resource_id == test_ai_resource.id
        assert tenant_resource.is_enabled is True

    async def test_tenant_resource_uniqueness(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        test_ai_resource: AIResource
    ):
        """Test that tenant-resource combinations must be unique."""
        tr1 = TenantResource(tenant_id=test_tenant.id, resource_id=test_ai_resource.id)
        tr2 = TenantResource(tenant_id=test_tenant.id, resource_id=test_ai_resource.id)

        db_session.add(tr1)
        await db_session.commit()

        db_session.add(tr2)
        with pytest.raises(IntegrityError):
            await db_session.commit()