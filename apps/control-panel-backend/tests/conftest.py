"""
Pytest configuration and fixtures for GT 2.0 Control Panel Backend
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from faker import Faker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User
from app.models.tenant import Tenant
from app.models.ai_resource import AIResource

# Initialize Faker
fake = Faker()

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
    echo=False
)

# Create test session maker
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Drop tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database session override."""
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def user_data() -> dict:
    """Generate fake user data."""
    return {
        "email": fake.email(),
        "full_name": fake.name(),
        "user_type": "tenant_user",
        "capabilities": [
            {
                "resource": "tenant:test:*",
                "actions": ["read", "write"],
                "constraints": {}
            }
        ]
    }


@pytest.fixture
def admin_user_data() -> dict:
    """Generate fake admin user data."""
    return {
        "email": fake.email(),
        "full_name": fake.name(),
        "user_type": "super_admin",
        "capabilities": [
            {
                "resource": "*",
                "actions": ["*"],
                "constraints": {}
            }
        ]
    }


@pytest.fixture
def tenant_data() -> dict:
    """Generate fake tenant data."""
    domain = fake.slug()
    return {
        "name": fake.company(),
        "domain": domain,
        "template": "basic",
        "max_users": 10,
        "resource_limits": {
            "cpu": "500m",
            "memory": "1Gi",
            "storage": "5Gi"
        },
        "namespace": f"gt-{domain}",
        "subdomain": domain
    }


@pytest.fixture
def ai_resource_data() -> dict:
    """Generate fake AI resource data."""
    return {
        "name": f"Test {fake.word().title()} Model",
        "resource_type": "llm",
        "provider": "groq",
        "model_name": "llama-3.1-8b-instant",
        "api_endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "configuration": {
            "max_tokens": 4000,
            "temperature": 0.7
        }
    }


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, user_data: dict) -> User:
    """Create a test user in the database."""
    from packages.utils.auth import hashPassword
    
    hashed_password = await hashPassword("testpassword123")
    
    user = User(
        email=user_data["email"],
        full_name=user_data["full_name"],
        hashed_password=hashed_password,
        user_type=user_data["user_type"],
        capabilities=user_data["capabilities"]
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession, admin_user_data: dict) -> User:
    """Create a test admin user in the database."""
    from packages.utils.auth import hashPassword
    
    hashed_password = await hashPassword("adminpassword123")
    
    admin = User(
        email=admin_user_data["email"],
        full_name=admin_user_data["full_name"],
        hashed_password=hashed_password,
        user_type=admin_user_data["user_type"],
        capabilities=admin_user_data["capabilities"]
    )
    
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    
    return admin


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession, tenant_data: dict) -> Tenant:
    """Create a test tenant in the database."""
    tenant = Tenant(**tenant_data)
    
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    
    return tenant


@pytest_asyncio.fixture
async def test_ai_resource(db_session: AsyncSession, ai_resource_data: dict) -> AIResource:
    """Create a test AI resource in the database."""
    resource = AIResource(**ai_resource_data)
    
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)
    
    return resource


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Generate authentication headers for test user."""
    from packages.utils.auth import createJWT
    
    token = createJWT({
        "sub": test_user.email,
        "tenant_id": str(test_user.tenant_id) if test_user.tenant_id else None,
        "user_type": test_user.user_type,
        "capabilities": test_user.capabilities
    })
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin: User) -> dict:
    """Generate authentication headers for admin user."""
    from packages.utils.auth import createJWT
    
    token = createJWT({
        "sub": test_admin.email,
        "tenant_id": None,
        "user_type": test_admin.user_type,
        "capabilities": test_admin.capabilities
    })
    
    return {"Authorization": f"Bearer {token}"}


# Redis removed - PostgreSQL handles all caching


@pytest.fixture
def mock_kubernetes(mocker):
    """Mock Kubernetes client for testing."""
    mock_k8s = mocker.patch('kubernetes.client.ApiClient')
    return mock_k8s.return_value


# MinIO removed - PostgreSQL handles all file storage