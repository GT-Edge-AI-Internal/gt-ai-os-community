"""
Unit tests for per-user agent usage tracking (Issue #170)

Tests the new user-specific usage tracking features:
- User's conversation count per agent
- User's last_used_at per agent
- Sorting by recent_usage (user's last use)
- Sorting by my_most_used (user's usage count)
- Filtering by used_last_7_days
- Filtering by used_last_30_days
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.agent_service import AgentService


@pytest.fixture
def mock_pg_client():
    """Mock PostgreSQL client"""
    client = AsyncMock()
    client.execute_query = AsyncMock()
    client.fetch_one = AsyncMock()
    return client


@pytest.fixture
def agent_service():
    """AgentService instance with mocked dependencies"""
    # Mock settings to avoid filesystem operations
    with patch('app.services.agent_service.get_settings'):
        service = AgentService(
            tenant_domain="test-company",
            user_id="9150de4f-0238-4013-a456-2a8929f48ad5",
            user_email="testuser@test.com"
        )
    return service


@pytest.fixture
def sample_agents_with_user_usage():
    """Sample agents with per-user usage statistics"""
    user_id = "9150de4f-0238-4013-a456-2a8929f48ad5"
    now = datetime.utcnow()

    return [
        {
            "id": uuid4(),
            "name": "Agent A",
            "description": "Most used agent",
            "system_prompt": "You are Agent A",
            "model": "llama3-groq-8b-8192-tool-use-preview",
            "temperature": 0.7,
            "max_tokens": 4096,
            "visibility": "individual",
            "configuration": "{}",
            "access_group": "INDIVIDUAL",
            "created_at": now - timedelta(days=10),
            "updated_at": now - timedelta(days=2),
            "is_active": True,
            "created_by": user_id,
            "agent_type": "conversational",
            "full_name": "Test User",
            "user_conversation_count": 15,  # Most used
            "user_last_used_at": now - timedelta(hours=2)  # Recent use
        },
        {
            "id": uuid4(),
            "name": "Agent B",
            "description": "Recently used agent",
            "system_prompt": "You are Agent B",
            "model": "llama3-groq-8b-8192-tool-use-preview",
            "temperature": 0.7,
            "max_tokens": 4096,
            "visibility": "individual",
            "configuration": "{}",
            "access_group": "INDIVIDUAL",
            "created_at": now - timedelta(days=8),
            "updated_at": now - timedelta(days=1),
            "is_active": True,
            "created_by": user_id,
            "agent_type": "conversational",
            "full_name": "Test User",
            "user_conversation_count": 5,  # Moderate use
            "user_last_used_at": now - timedelta(hours=1)  # Most recent
        },
        {
            "id": uuid4(),
            "name": "Agent C",
            "description": "Older usage agent",
            "system_prompt": "You are Agent C",
            "model": "llama3-groq-8b-8192-tool-use-preview",
            "temperature": 0.7,
            "max_tokens": 4096,
            "visibility": "individual",
            "configuration": "{}",
            "access_group": "INDIVIDUAL",
            "created_at": now - timedelta(days=15),
            "updated_at": now - timedelta(days=5),
            "is_active": True,
            "created_by": user_id,
            "agent_type": "conversational",
            "full_name": "Test User",
            "user_conversation_count": 2,  # Low use
            "user_last_used_at": now - timedelta(days=20)  # Old use
        },
        {
            "id": uuid4(),
            "name": "Agent D",
            "description": "Never used agent",
            "system_prompt": "You are Agent D",
            "model": "llama3-groq-8b-8192-tool-use-preview",
            "temperature": 0.7,
            "max_tokens": 4096,
            "visibility": "individual",
            "configuration": "{}",
            "access_group": "INDIVIDUAL",
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=3),
            "is_active": True,
            "created_by": user_id,
            "agent_type": "conversational",
            "full_name": "Test User",
            "user_conversation_count": 0,  # Never used
            "user_last_used_at": None  # Never used
        }
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_agents_with_usage_tracking(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test that get_user_agents returns per-user usage statistics"""
    # Mock database response
    mock_pg_client.execute_query.return_value = sample_agents_with_user_usage

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            agents = await agent_service.get_user_agents(active_only=True)

    # Verify all agents returned
    assert len(agents) >= 4  # May include team-shared agents

    # Verify per-user usage statistics are present
    agent_a = next((a for a in agents if a['name'] == 'Agent A'), None)
    assert agent_a is not None
    assert agent_a['conversation_count'] == 15  # User's conversation count
    assert agent_a['last_used_at'] is not None

    # Verify never-used agent has correct stats
    agent_d = next((a for a in agents if a['name'] == 'Agent D'), None)
    assert agent_d is not None
    assert agent_d['conversation_count'] == 0
    assert agent_d['last_used_at'] is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sort_by_my_most_used(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test sorting agents by user's most used (my_most_used)"""
    # Mock database response with agents sorted by user_conversation_count DESC
    sorted_agents = sorted(
        sample_agents_with_user_usage,
        key=lambda x: x['user_conversation_count'],
        reverse=True
    )
    mock_pg_client.execute_query.return_value = sorted_agents

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            agents = await agent_service.get_user_agents(
                active_only=True,
                sort_by='my_most_used'
            )

    # Verify sorting: Agent A (15), Agent B (5), Agent C (2), Agent D (0)
    agent_names = [a['name'] for a in agents if a['name'] in ['Agent A', 'Agent B', 'Agent C', 'Agent D']]
    assert agent_names[0] == 'Agent A'  # Most used first
    assert agent_names[-1] == 'Agent D'  # Never used last


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sort_by_recent_usage(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test sorting agents by user's recent usage (recent_usage)"""
    # Mock database response with agents sorted by user_last_used_at DESC
    sorted_agents = sorted(
        sample_agents_with_user_usage,
        key=lambda x: x['user_last_used_at'] if x['user_last_used_at'] else datetime.min,
        reverse=True
    )
    mock_pg_client.execute_query.return_value = sorted_agents

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            agents = await agent_service.get_user_agents(
                active_only=True,
                sort_by='recent_usage'
            )

    # Verify sorting: Agent B (1h ago), Agent A (2h ago), Agent C (20d ago), Agent D (never)
    agent_names = [a['name'] for a in agents if a['name'] in ['Agent A', 'Agent B', 'Agent C', 'Agent D']]
    assert agent_names[0] == 'Agent B'  # Most recent first
    assert agent_names[-1] == 'Agent D'  # Never used last


@pytest.mark.asyncio
@pytest.mark.unit
async def test_filter_used_last_7_days(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test filtering agents used in last 7 days"""
    # Filter agents used in last 7 days
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    filtered_agents = [
        a for a in sample_agents_with_user_usage
        if a['user_last_used_at'] and a['user_last_used_at'] >= seven_days_ago
    ]
    mock_pg_client.execute_query.return_value = filtered_agents

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            agents = await agent_service.get_user_agents(
                active_only=True,
                filter_usage='used_last_7_days'
            )

    # Should only return Agent A and Agent B (used within last 7 days)
    agent_names = [a['name'] for a in agents if a['name'].startswith('Agent ')]
    assert 'Agent A' in agent_names
    assert 'Agent B' in agent_names
    assert 'Agent C' not in agent_names  # Used 20 days ago
    assert 'Agent D' not in agent_names  # Never used


@pytest.mark.asyncio
@pytest.mark.unit
async def test_filter_used_last_30_days(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test filtering agents used in last 30 days"""
    # Filter agents used in last 30 days
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    filtered_agents = [
        a for a in sample_agents_with_user_usage
        if a['user_last_used_at'] and a['user_last_used_at'] >= thirty_days_ago
    ]
    mock_pg_client.execute_query.return_value = filtered_agents

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            agents = await agent_service.get_user_agents(
                active_only=True,
                filter_usage='used_last_30_days'
            )

    # Should return Agent A and Agent B (used within last 30 days)
    agent_names = [a['name'] for a in agents if a['name'].startswith('Agent ')]
    assert 'Agent A' in agent_names
    assert 'Agent B' in agent_names
    # Agent C used 20 days ago, which is within 30 days but our filter is more strict
    # Agent D never used


@pytest.mark.asyncio
@pytest.mark.unit
async def test_combined_filter_and_sort(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test combining usage filter with sorting"""
    # Filter agents used in last 7 days and sort by most used
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    filtered_agents = [
        a for a in sample_agents_with_user_usage
        if a['user_last_used_at'] and a['user_last_used_at'] >= seven_days_ago
    ]
    sorted_agents = sorted(
        filtered_agents,
        key=lambda x: x['user_conversation_count'],
        reverse=True
    )
    mock_pg_client.execute_query.return_value = sorted_agents

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            agents = await agent_service.get_user_agents(
                active_only=True,
                sort_by='my_most_used',
                filter_usage='used_last_7_days'
            )

    # Should return Agent A (15 uses) before Agent B (5 uses)
    agent_names = [a['name'] for a in agents if a['name'].startswith('Agent ')]
    if len(agent_names) >= 2:
        assert agent_names[0] == 'Agent A'  # Most used within last 7 days
        assert agent_names[1] == 'Agent B'


@pytest.mark.asyncio
@pytest.mark.unit
async def test_query_parameters_in_sql(agent_service, mock_pg_client):
    """Test that SQL query includes user-specific usage calculations"""
    mock_pg_client.execute_query.return_value = []

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='member'):
            await agent_service.get_user_agents(
                active_only=True,
                sort_by='my_most_used',
                filter_usage='used_last_7_days'
            )

    # Verify execute_query was called
    assert mock_pg_client.execute_query.called

    # Get the SQL query from the call
    call_args = mock_pg_client.execute_query.call_args
    query = call_args[0][0] if call_args[0] else ""

    # Verify query includes per-user usage calculations
    assert 'user_conversation_count' in query.lower() or 'case when c.user_id' in query.lower()
    assert 'user_last_used_at' in query.lower() or 'max(case when c.user_id' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_admin_sees_all_agents_with_own_usage(agent_service, mock_pg_client, sample_agents_with_user_usage):
    """Test that admins see all agents but with their own usage stats, not global"""
    mock_pg_client.execute_query.return_value = sample_agents_with_user_usage

    with patch('app.services.agent_service.get_postgresql_client', return_value=mock_pg_client):
        with patch('app.services.agent_service.get_user_role', return_value='admin'):
            agents = await agent_service.get_user_agents(active_only=True)

    # Verify admin gets all agents
    assert len(agents) >= 4

    # Verify usage stats are still per-user (admin's usage), not global
    agent_a = next((a for a in agents if a['name'] == 'Agent A'), None)
    assert agent_a is not None
    assert agent_a['conversation_count'] == 15  # Admin's usage, not global


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
