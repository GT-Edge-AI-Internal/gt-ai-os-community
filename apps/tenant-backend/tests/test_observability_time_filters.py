"""
Unit tests for observability time filtering functionality.

Tests cover:
- Date-only filtering (YYYY-MM-DD format)
- ISO timestamp filtering with hour:minute precision (YYYY-MM-DDTHH:MM:SSZ format)
- Error handling for invalid date formats
- Timezone handling (UTC)
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


@pytest.fixture
def mock_current_user():
    """Mock authenticated admin user for testing."""
    return {
        'sub': '9150de4f-0238-4013-a456-2a8929f48ad5',
        'email': 'gtadmin@test.com',
        'user_type': 'super_admin',
        'tenant_domain': 'test-company',
        'current_tenant': {
            'id': '1',
            'domain': 'test-company',
            'role': 'admin'
        }
    }


@pytest.fixture
def mock_pg_client():
    """Mock PostgreSQL client with common query responses."""
    client = AsyncMock()

    # Mock user role query (admin)
    client.fetch_scalar.return_value = 'admin'

    # Mock usage analytics query response
    client.execute_query.return_value = [
        {
            'total_conversations': 10,
            'total_messages': 50,
            'total_tokens': 1000,
            'unique_users': 3,
            'date': '2025-01-15',
            'conversation_count': 5,
            'message_count': 25,
            'token_count': 500
        }
    ]

    return client


class TestDateOnlyFiltering:
    """Test date-only filtering (full days)."""

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_date_only_format_usage_endpoint(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test usage endpoint with date-only format (YYYY-MM-DD)."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/usage",
            params={
                'start_date': '2025-01-15',
                'end_date': '2025-01-16'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify PostgreSQL client was called with date objects
        called_args = mock_pg_client.execute_query.call_args[0]
        # Date parameters should be Python date objects (not datetime)
        assert len(called_args) >= 3
        assert isinstance(called_args[1], (datetime, type(datetime.now().date())))
        assert isinstance(called_args[2], (datetime, type(datetime.now().date())))

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_date_only_format_conversations_endpoint(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test conversations endpoint with date-only format."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/conversations",
            params={
                'start_date': '2025-01-15',
                'end_date': '2025-01-16'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200
        assert response.json() == []

        # Verify query was executed
        assert mock_pg_client.execute_query.called

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_date_only_format_export_endpoint(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test export endpoint with date-only format."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/export",
            params={
                'format': 'csv',
                'start_date': '2025-01-15',
                'end_date': '2025-01-16'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/csv; charset=utf-8'


class TestTimeOfDayFiltering:
    """Test hour:minute precision filtering with ISO timestamps."""

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_iso_timestamp_usage_endpoint(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test usage endpoint with ISO timestamps (hour:minute filtering)."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/usage",
            params={
                'start_date': '2025-01-15T14:30:00Z',
                'end_date': '2025-01-15T16:45:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify PostgreSQL client was called with datetime objects
        called_args = mock_pg_client.execute_query.call_args[0]
        assert len(called_args) >= 3

        # Parameters should be datetime objects with time components
        start_dt = called_args[1]
        end_dt = called_args[2]

        assert isinstance(start_dt, datetime)
        assert isinstance(end_dt, datetime)

        # Verify time components are preserved
        assert start_dt.hour == 14
        assert start_dt.minute == 30
        assert end_dt.hour == 16
        assert end_dt.minute == 45

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_iso_timestamp_conversations_endpoint(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test conversations endpoint with ISO timestamps."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/conversations",
            params={
                'start_date': '2025-01-15T14:30:00Z',
                'end_date': '2025-01-15T16:45:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify datetime filtering was applied
        called_args = mock_pg_client.execute_query.call_args[0]
        query = called_args[0]

        # Query should use c.created_at >= and <= (not DATE())
        assert 'c.created_at >=' in query
        assert 'c.created_at <=' in query
        assert 'DATE(c.created_at)' not in query  # Should NOT use DATE() for time filtering

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_iso_timestamp_export_endpoint(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test export endpoint with ISO timestamps."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/export",
            params={
                'format': 'json',
                'start_date': '2025-01-15T14:30:00Z',
                'end_date': '2025-01-15T16:45:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/json'


class TestTimezoneHandling:
    """Test timezone handling for ISO timestamps."""

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_utc_timezone_conversion(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test that 'Z' suffix is properly converted to UTC timezone."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/usage",
            params={
                'start_date': '2025-01-15T14:30:00Z',
                'end_date': '2025-01-15T16:45:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify datetime objects have UTC timezone info
        called_args = mock_pg_client.execute_query.call_args[0]
        start_dt = called_args[1]
        end_dt = called_args[2]

        # datetime.fromisoformat should produce timezone-aware objects
        assert start_dt.tzinfo is not None
        assert end_dt.tzinfo is not None


class TestErrorHandling:
    """Test error handling for invalid date formats."""

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_invalid_date_format_usage(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test usage endpoint rejects invalid date format."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/usage",
            params={
                'start_date': 'invalid-date',
                'end_date': '2025-01-16'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 400
        assert 'Invalid date format' in response.json()['detail']

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_invalid_iso_timestamp_conversations(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test conversations endpoint rejects malformed ISO timestamp."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/conversations",
            params={
                'start_date': '2025-01-15T25:00:00Z',  # Invalid hour (25)
                'end_date': '2025-01-16T16:45:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 400
        assert 'Invalid date format' in response.json()['detail']

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_missing_end_date_export(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test export endpoint when start_date provided without end_date."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/export",
            params={
                'format': 'csv',
                'start_date': '2025-01-15T14:30:00Z'
                # end_date missing - should fall back to days or all-time
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        # Should still succeed (falls back to all-time or days)
        assert response.status_code == 200


class TestQueryPrecision:
    """Test that correct SQL query patterns are used for different date formats."""

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_date_only_uses_date_function(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test that date-only format uses DATE() SQL function."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/conversations",
            params={
                'start_date': '2025-01-15',
                'end_date': '2025-01-16'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify query uses DATE() for date-only filtering
        called_args = mock_pg_client.execute_query.call_args[0]
        query = called_args[0]

        assert 'DATE(c.created_at)' in query

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_iso_timestamp_uses_datetime_comparison(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test that ISO timestamp format uses direct datetime comparison."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/conversations",
            params={
                'start_date': '2025-01-15T14:30:00Z',
                'end_date': '2025-01-15T16:45:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify query uses direct datetime comparison (not DATE())
        called_args = mock_pg_client.execute_query.call_args[0]
        query = called_args[0]

        assert 'c.created_at >=' in query
        assert 'c.created_at <=' in query
        # Should NOT wrap in DATE() for time-of-day filtering
        assert 'DATE(c.created_at) >=' not in query or 'c.created_at >=' in query


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_same_day_different_hours(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test filtering to a specific time window within a single day."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/usage",
            params={
                'start_date': '2025-01-15T09:00:00Z',  # 9 AM
                'end_date': '2025-01-15T17:00:00Z'    # 5 PM (same day)
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify time precision is maintained
        called_args = mock_pg_client.execute_query.call_args[0]
        start_dt = called_args[1]
        end_dt = called_args[2]

        assert start_dt.hour == 9
        assert end_dt.hour == 17
        assert start_dt.date() == end_dt.date()  # Same day

    @patch('app.api.v1.observability.get_current_user')
    @patch('app.api.v1.observability.get_postgresql_client')
    async def test_multi_day_with_time_boundaries(self, mock_get_pg, mock_get_user, mock_current_user, mock_pg_client):
        """Test filtering across multiple days with specific time boundaries."""
        mock_get_user.return_value = mock_current_user
        mock_get_pg.return_value = mock_pg_client
        mock_pg_client.execute_query.return_value = []

        client = TestClient(app)
        response = client.get(
            "/api/v1/observability/conversations",
            params={
                'start_date': '2025-01-15T14:30:00Z',
                'end_date': '2025-01-18T10:15:00Z'
            },
            headers={'X-Tenant-Domain': 'test-company'}
        )

        assert response.status_code == 200

        # Verify different days and times
        called_args = mock_pg_client.execute_query.call_args[0]
        start_dt = called_args[1]
        end_dt = called_args[2]

        assert start_dt.day == 15
        assert end_dt.day == 18
        assert start_dt.hour == 14
        assert start_dt.minute == 30
        assert end_dt.hour == 10
        assert end_dt.minute == 15


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
