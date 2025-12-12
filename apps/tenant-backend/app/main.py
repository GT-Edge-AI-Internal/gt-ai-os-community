"""
GT 2.0 Tenant Backend - Main Application Entry Point

This is the customer-facing API server that provides:
- AI chat interface with WebSocket support
- Document upload and processing
- User authentication and session management
- Perfect tenant isolation with file-based databases
"""

import os
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

from app.core.config import get_settings
from app.core.database import init_database as startup_database, close_database as shutdown_database
from app.core.logging_config import setup_logging
# Import models to ensure they're registered with the Base metadata
# TEMPORARY: Commented out SQLAlchemy-based models during PostgreSQL migration
# from app.models import workflow, agent, conversation, message, document
from app.api.auth import router as auth_router
# from app.api.agents import router as assistants_router  # Legacy: replaced with agents_router
# Import the migrated PostgreSQL-based conversations API
from app.api.v1.conversations import router as conversations_router
# from app.api.messages import router as messages_router
from app.api.v1.documents import router as documents_router
# from app.api.websocket import router as websocket_router
# from app.api.events import router as events_router
from app.api.v1.agents import router as agents_router
# from app.api.v1.games import router as games_router
# from app.api.v1.external_services import router as external_services_router
# assistants_enhanced module removed - using agents terminology only
from app.api.v1.rag_visualization import router as rag_visualization_router
# from app.api.v1.dataset_sharing import router as dataset_sharing_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.chat import router as chat_router
# from app.api.v1.workflows import router as workflows_router
from app.api.v1.models import router as models_router
from app.api.v1.files import router as files_router
from app.api.v1.search import router as search_router
from app.api.v1.users import router as users_router
from app.api.v1.observability import router as observability_router
from app.api.v1.teams import router as teams_router
from app.api.v1.auth_logs import router as auth_logs_router
from app.api.v1.categories import router as categories_router
from app.middleware.tenant_isolation import TenantIsolationMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.oauth2_auth import OAuth2AuthMiddleware
from app.middleware.session_validation import SessionValidationMiddleware
from app.services.message_bus_client import initialize_message_bus, message_bus_client

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
start_time = time.time()  # Track service startup time for metrics


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management"""
    logger.info("Starting GT 2.0 Tenant Backend...")
    
    # Initialize database connections
    await startup_database()
    logger.info("PostgreSQL + PGVector database connection initialized")
    
    # Initialize message bus for admin communication
    try:
        message_bus_connected = await initialize_message_bus()
        if message_bus_connected:
            logger.info("Message bus connected - admin communication enabled")
        else:
            logger.warning("Message bus connection failed - admin communication disabled")
    except Exception as e:
        logger.error(f"Message bus initialization error: {e}")

    # Load BGE-M3 configuration from Control Panel database on startup
    try:
        import httpx
        control_panel_url = os.getenv('CONTROL_PANEL_BACKEND_URL', 'http://control-panel-backend:8000')

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch BGE-M3 configuration from Control Panel
            response = await client.get(f"{control_panel_url}/api/v1/models/BAAI%2Fbge-m3")

            if response.status_code == 200:
                model_config = response.json()
                config = model_config.get('config', {})
                is_local_mode = config.get('is_local_mode', True)
                external_endpoint = config.get('external_endpoint')

                # Update embedding client with database configuration
                from app.services.embedding_client import get_embedding_client
                embedding_client = get_embedding_client()

                if is_local_mode:
                    new_endpoint = os.getenv('EMBEDDING_ENDPOINT', 'http://host.docker.internal:8005')
                else:
                    new_endpoint = external_endpoint if external_endpoint else 'http://host.docker.internal:8005'

                embedding_client.update_endpoint(new_endpoint)

                # Update environment variables for consistency
                os.environ['BGE_M3_LOCAL_MODE'] = str(is_local_mode).lower()
                if external_endpoint:
                    os.environ['BGE_M3_EXTERNAL_ENDPOINT'] = external_endpoint

                logger.info(f"BGE-M3 configuration loaded from database: is_local_mode={is_local_mode}, endpoint={new_endpoint}")
            else:
                logger.warning(f"Failed to load BGE-M3 configuration from Control Panel (status {response.status_code}), using defaults")
    except Exception as e:
        logger.warning(f"Could not load BGE-M3 configuration from Control Panel: {e}, using defaults")

    # Log configuration
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Tenant ID: {settings.tenant_id}")
    logger.info(f"Database URL: {settings.database_url}")
    logger.info(f"PostgreSQL Schema: {settings.postgres_schema}")
    logger.info(f"Resource cluster URL: {settings.resource_cluster_url}")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down GT 2.0 Tenant Backend...")
    
    # Disconnect message bus
    try:
        await message_bus_client.disconnect()
        logger.info("Message bus disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting message bus: {e}")
    
    await shutdown_database()
    logger.info("PostgreSQL database connections closed")


# Create FastAPI application
app = FastAPI(
    title="GT 2.0 Tenant Backend",
    description="Customer-facing API for GT 2.0 Enterprise AI Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    redirect_slashes=False,  # Disable redirects - Next.js proxy can't follow internal Docker URLs
)

# Security Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts
)

# OAuth2 Authentication Middleware (temporarily disabled for development)
# app.add_middleware(OAuth2AuthMiddleware, require_auth=settings.require_oauth2_auth)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TenantIsolationMiddleware)
# Session validation middleware for OWASP/NIST compliance (Issue #264)
app.add_middleware(SessionValidationMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Warning", "X-Session-Expired"],  # Issue #264: Expose session headers to frontend
)

# API Routes
app.include_router(auth_router, prefix="/api/v1")
# app.include_router(assistants_router, prefix="/api/v1")  # Legacy: replaced with agents_router
app.include_router(conversations_router)  # Already has prefix
# app.include_router(messages_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
# app.include_router(events_router, prefix="/api/v1/events")
app.include_router(agents_router, prefix="/api/v1")
# app.include_router(games_router, prefix="/api/v1")
# app.include_router(external_services_router, prefix="/api/v1/external-services")
from app.api.websocket import router as websocket_router
from app.api.embeddings import router as embeddings_router
from app.websocket.manager import socket_app
app.include_router(websocket_router, prefix="/ws")
app.include_router(embeddings_router, prefix="/api/embeddings")

# Enhanced API Routes for GT 2.0 comprehensive agent platform
# assistants_enhanced module removed - architecture now uses agents only
# TEMPORARY: Commented out during PostgreSQL migration
app.include_router(rag_visualization_router)  # Already has /api/v1/rag/visualization prefix
app.include_router(datasets_router)  # Already has /api/v1/datasets prefix
app.include_router(chat_router)  # Already has /api/v1/chat prefix
# app.include_router(dataset_sharing_router, prefix="/api/v1/datasets")  # Dataset sharing endpoints
# app.include_router(workflows_router)  # Already has /api/v1/workflows prefix
app.include_router(models_router)  # Already has /api/v1/models prefix
app.include_router(files_router, prefix="/api/v1")  # Files upload/download API
app.include_router(search_router)  # Already has /api/v1/search prefix
app.include_router(users_router, prefix="/api/v1")  # User preferences and favorite agents
app.include_router(observability_router, prefix="/api/v1")  # Observability dashboard (admin-only)
app.include_router(teams_router, prefix="/api/v1")  # Team collaboration and resource sharing
app.include_router(auth_logs_router, prefix="/api/v1")  # Authentication logs for security monitoring (Issue #152)
app.include_router(categories_router)  # Agent categories CRUD (Issue #215) - already has /api/v1/categories prefix

# Note: Socket.IO integration moved to composite ASGI router to prevent protocol conflicts


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer and Kubernetes"""
    # Import here to avoid circular imports
    from app.core.database import health_check as db_health_check
    
    try:
        db_health = await db_health_check()
        is_healthy = db_health.get("status") == "healthy"

        # codeql[py/stack-trace-exposure] returns health status dict, not error details
        return {
            "status": "healthy" if is_healthy else "degraded",
            "service": "gt2-tenant-backend",
            "version": "1.0.0",
            "tenant_id": settings.tenant_id,
            "environment": settings.environment,
            "database": db_health,
            "postgresql_pgvector": True
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "service": "gt2-tenant-backend",
            "version": "1.0.0",
            "error": "Health check failed",
            "database": {"status": "failed"}
        }


@app.get("/api/v1/health")
async def api_health_check():
    """API v1 health check endpoint for frontend compatibility"""
    return {
        "status": "healthy",
        "service": "gt2-tenant-backend",
        "version": "1.0.0",
        "tenant_id": settings.tenant_id,
        "environment": settings.environment,
    }


@app.get("/ready")
async def ready_check():
    """Kubernetes readiness probe endpoint"""
    return {
        "status": "ready",
        "service": "tenant-backend",
        "timestamp": datetime.utcnow(),
        "health": "ok"
    }


@app.get("/metrics")
async def metrics(request: Request):
    """Prometheus metrics endpoint"""
    try:
        # Basic metrics for now - in production would use prometheus_client
        import psutil
        import time

        # Be permissive with Accept headers for monitoring tools
        # Most legitimate monitoring tools will accept text/plain or send */*
        accept_header = request.headers.get("accept", "text/plain")
        if (accept_header and
            accept_header != "text/plain" and
            not any(pattern in accept_header.lower() for pattern in [
                "text/plain", "text/*", "*/*", "application/openmetrics-text",
                "application/json", "text/html"  # Common but non-metrics requests
            ])):
            # Only return 400 for truly incompatible Accept headers
            logger.warning(f"Metrics endpoint received unsupported Accept header: {accept_header}")
            raise HTTPException(
                status_code=400,
                detail="Unsupported media type. Metrics endpoint supports text/plain."
            )

        # Get basic system metrics with error handling
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)  # Reduced interval to avoid blocking
        except Exception:
            cpu_percent = 0.0

        try:
            memory = psutil.virtual_memory()
        except Exception:
            # Fallback values if psutil fails
            memory = type('Memory', (), {'used': 0, 'available': 0})()

        metrics_data = f"""# HELP tenant_backend_cpu_usage_percent CPU usage percentage
# TYPE tenant_backend_cpu_usage_percent gauge
tenant_backend_cpu_usage_percent {cpu_percent}

# HELP tenant_backend_memory_usage_bytes Memory usage in bytes
# TYPE tenant_backend_memory_usage_bytes gauge
tenant_backend_memory_usage_bytes {memory.used}

# HELP tenant_backend_memory_available_bytes Available memory in bytes
# TYPE tenant_backend_memory_available_bytes gauge
tenant_backend_memory_available_bytes {memory.available}

# HELP tenant_backend_uptime_seconds Service uptime in seconds
# TYPE tenant_backend_uptime_seconds counter
tenant_backend_uptime_seconds {time.time() - start_time}

# HELP tenant_backend_requests_total Total HTTP requests
# TYPE tenant_backend_requests_total counter
tenant_backend_requests_total 1
"""

        return Response(content=metrics_data, media_type="text/plain; version=0.0.4; charset=utf-8")

    except HTTPException:
        raise
    except Exception as e:
        # Log the error but return basic metrics to avoid breaking monitoring
        logger.error(f"Error generating metrics: {e}")

        # Return minimal metrics on error
        fallback_metrics = f"""# HELP tenant_backend_uptime_seconds Service uptime in seconds
# TYPE tenant_backend_uptime_seconds counter
tenant_backend_uptime_seconds {time.time() - start_time}

# HELP tenant_backend_errors_total Total errors
# TYPE tenant_backend_errors_total counter
tenant_backend_errors_total 1
"""
        return Response(content=fallback_metrics, media_type="text/plain")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "code": exc.status_code,
                "type": "http_error"
            },
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": "2024-01-01T00:00:00Z"  # TODO: Use actual timestamp
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unhandled errors"""
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "code": 500,
                "type": "internal_error"
            },
            "request_id": getattr(request.state, "request_id", None),
            "timestamp": "2024-01-01T00:00:00Z"  # TODO: Use actual timestamp
        }
    )


# Create composite ASGI application for Socket.IO + FastAPI coexistence
from app.core.asgi_router import create_composite_asgi_app

# Create the composite application that routes between FastAPI and Socket.IO
composite_app = create_composite_asgi_app(app, socket_app)

if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "app.main:composite_app",
        host="0.0.0.0",
        port=8002,
        reload=True if settings.environment == "development" else False,
        log_level="info",
        access_log=True,
    )