"""
Pytest configuration and fixtures for GT 2.0 Resource Cluster
"""
import asyncio
import pytest
import pytest_asyncio
import tempfile
import os
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, patch
from httpx import AsyncClient
import aiosqlite
from faker import Faker

from app.main import app
from app.core.config import get_settings
from app.services.model_service import ModelService

# Initialize Faker
fake = Faker()

# Test configuration
TEST_DATABASE_PATH = ":memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[str, None]:
    """Create a temporary SQLite database for testing."""
    # Use in-memory database for tests
    yield TEST_DATABASE_PATH


@pytest_asyncio.fixture
async def model_service(test_db: str) -> AsyncGenerator[ModelService, None]:
    """Create ModelService instance with test database."""
    service = ModelService(database_path=test_db)
    await service.initialize()
    yield service
    await service.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client for Resource Cluster API."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('app.core.config.get_settings') as mock:
        settings = Mock()
        settings.secret_key = os.environ.get("SECRET_KEY", "test-key-for-unit-tests-only")
        settings.groq_api_key = "test-groq-key"
        settings.haproxy_groq_endpoint = "http://test-haproxy:8000"
        settings.haproxy_enabled = True
        settings.consul_host = "localhost"
        settings.consul_port = 8500
        settings.data_directory = "/tmp/test"
        settings.models_cache_path = "/tmp/test/models"
        mock.return_value = settings
        yield settings


@pytest.fixture
def sample_model_data():
    """Sample model data for testing."""
    return {
        "model_id": "llama-3.1-70b-versatile",
        "name": "Llama 3.1 70B Versatile",
        "version": "1.0.0",
        "provider": "groq",
        "model_type": "llm",
        "description": "Advanced LLM for versatile tasks",
        "capabilities": {
            "streaming": True,
            "function_calling": True,
            "vision": False
        },
        "performance": {
            "max_tokens": 8000,
            "cost_per_1k_tokens": 0.59,
            "avg_latency_ms": 1500
        },
        "endpoints": ["https://api.groq.com/openai/v1"],
        "config": {
            "temperature": 0.7,
            "top_p": 1.0
        }
    }


@pytest.fixture
def mock_groq_response():
    """Mock Groq API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "llama-3.1-70b-versatile",
        "choices": [{
            "index": 0,
            "message": {
                "role": "agent",
                "content": "This is a test response from the model."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    }


@pytest.fixture
def mock_consul():
    """Mock Consul client for testing."""
    mock_consul = Mock()
    mock_consul.agent.service.register = Mock()
    mock_consul.agent.service.deregister = Mock()
    mock_consul.health.service = Mock(return_value=(None, []))
    mock_consul.kv.put = Mock()
    mock_consul.kv.get = Mock(return_value=(None, None))
    return mock_consul


@pytest.fixture
def mock_haproxy_stats():
    """Mock HAProxy stats response."""
    return """
# pxname,svname,qcur,qmax,scur,smax,slim,stot,bin,bout,dreq,dresp,ereq,econ,eresp,wretr,wredis,status,weight,act,bck,chkfail,chkdown,lastchg,downtime,qlimit,pid,iid,sid,throttle,lbtot,tracked,type,rate,rate_lim,rate_max,check_status,check_code,check_duration,hrsp_1xx,hrsp_2xx,hrsp_3xx,hrsp_4xx,hrsp_5xx,hrsp_other,hanafail,req_rate,req_rate_max,req_tot,cli_abrt,srv_abrt,comp_in,comp_out,comp_byp,comp_rsp,lastsess,last_chk,last_agt,qtime,ctime,rtime,ttime,agent_status,agent_code,agent_duration,check_desc,agent_desc,check_rise,check_fall,check_health,agent_rise,agent_fall,agent_health,addr,cookie,mode,algo,conn_rate,conn_rate_max,conn_tot,intercepted,dcon,dses,
groq_general_backend,groq-primary-1,0,0,0,5,,50,1000,2000,0,0,,0,0,0,0,UP,100,1,0,0,0,100,0,,1,1,1,,50,,2,0,,5,L7OK,200,2,0,45,0,5,0,0,,0,5,50,0,0,0,0,0,0,10,,,0,1,2,10,,,,,,,2,3,15,,,,,127.0.0.1:443,,http,roundrobin,0,1,50,0,0,0,
"""


@pytest.fixture
def mock_capability_token():
    """Mock capability JWT token for testing."""
    return {
        "sub": "test@example.com",
        "tenant_id": "test-tenant",
        "capabilities": [
            {
                "resource": "models:*",
                "actions": ["read", "write", "execute"],
                "constraints": {
                    "max_tokens_per_request": 8000,
                    "rate_limit": 100
                }
            }
        ],
        "exp": 9999999999  # Far future expiry
    }


@pytest.fixture
def auth_headers(mock_capability_token):
    """Generate authentication headers with capability token."""
    # Mock JWT encoding for tests
    with patch('jwt.encode') as mock_encode:
        mock_encode.return_value = "mock.jwt.token"
        token = "mock.jwt.token"
    
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def clean_model_registry(model_service):
    """Ensure clean model registry for each test."""
    # Clear any existing models
    await model_service._clear_all_models()  # We'll implement this helper method
    yield
    # Cleanup after test
    await model_service._clear_all_models()


# Mock external dependencies
@pytest.fixture(autouse=True)
def mock_external_services():
    """Automatically mock external services for all tests."""
    with patch('consul.Consul') as mock_consul_class, \
         patch('groq.AsyncGroq') as mock_groq_class, \
         patch('httpx.AsyncClient') as mock_httpx:
        
        # Configure mock consul
        mock_consul = Mock()
        mock_consul.agent.service.register = AsyncMock()
        mock_consul.agent.service.deregister = AsyncMock()
        mock_consul.health.service = Mock(return_value=(None, []))
        mock_consul_class.return_value = mock_consul
        
        # Configure mock groq
        mock_groq = Mock()
        mock_groq.chat.completions.create = AsyncMock()
        mock_groq_class.return_value = mock_groq
        
        # Configure mock httpx
        mock_http = Mock()
        mock_httpx.return_value.__aenter__.return_value = mock_http
        
        yield {
            'consul': mock_consul,
            'groq': mock_groq,
            'httpx': mock_http
        }