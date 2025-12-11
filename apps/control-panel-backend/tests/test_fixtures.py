"""
Test fixtures and utilities for unit tests
"""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment variables before importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test-key-for-unit-tests-only")
os.environ["API_KEY_ENCRYPTION_KEY"] = "test-encryption-key-32-bytes-long!"


def create_mock_tenant(
    id: int = 1,
    name: str = "Test Company",
    domain: str = "testcompany",
    status: str = "active",
    api_keys: dict = None
):
    """Create a mock tenant object without database dependencies"""
    tenant = MagicMock()
    tenant.id = id
    tenant.name = name
    tenant.domain = domain
    tenant.status = status
    tenant.namespace = f"gt-{domain}"
    tenant.api_keys = api_keys or {}
    tenant.api_key_encryption_version = "v1"
    tenant.created_at = datetime.utcnow()
    tenant.updated_at = datetime.utcnow()
    tenant.is_active = status == "active"
    return tenant


def create_mock_user(
    id: int = 1,
    email: str = "test@example.com",
    tenant_id: int = 1,
    user_type: str = "tenant_admin",
    last_login: datetime = None
):
    """Create a mock user object"""
    user = MagicMock()
    user.id = id
    user.email = email
    user.tenant_id = tenant_id
    user.user_type = user_type
    user.last_login = last_login or datetime.utcnow()
    user.is_active = True
    user.created_at = datetime.utcnow()
    return user


def create_mock_usage_record(
    id: int = 1,
    tenant_id: int = 1,
    operation_type: str = "inference",
    tokens_used: int = 1000,
    cost_cents: int = 10,
    started_at: datetime = None
):
    """Create a mock usage record"""
    record = MagicMock()
    record.id = id
    record.tenant_id = tenant_id
    record.operation_type = operation_type
    record.tokens_used = tokens_used
    record.cost_cents = cost_cents
    record.requests_count = 1
    record.started_at = started_at or (datetime.utcnow() - timedelta(days=1))
    record.completed_at = started_at or datetime.utcnow()
    return record


def create_mock_billing_usage(
    id: int = 1,
    tenant_id: int = 1,
    total_cost_cents: int = 500,
    billing_date: datetime = None
):
    """Create a mock billing usage record"""
    billing = MagicMock()
    billing.id = id
    billing.tenant_id = tenant_id
    billing.total_cost_cents = total_cost_cents
    billing.compute_cost_cents = int(total_cost_cents * 0.4)
    billing.storage_cost_cents = int(total_cost_cents * 0.2)
    billing.api_cost_cents = int(total_cost_cents * 0.3)
    billing.transfer_cost_cents = int(total_cost_cents * 0.1)
    billing.billing_date = billing_date or datetime.utcnow().replace(day=1)
    billing.status = "pending"
    return billing


def create_mock_db_session():
    """Create a mock database session"""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    session.scalar_one_or_none = AsyncMock()
    session.scalars = AsyncMock()
    return session


def create_mock_query_result(data=None, scalar=False, one_or_none=False):
    """Create a mock query result"""
    result = MagicMock()
    
    if scalar:
        result.scalar_one_or_none = MagicMock(return_value=data)
        result.scalar = MagicMock(return_value=data)
    elif one_or_none:
        result.one_or_none = MagicMock(return_value=data)
    else:
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=data or [])
        result.scalars = MagicMock(return_value=scalars_mock)
    
    return result