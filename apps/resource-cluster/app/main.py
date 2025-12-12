"""
GT 2.0 Resource Cluster - Main Application

Air-gapped resource management hub for AI/ML resources, RAG engines,
agentic workflows, app integrations, external services, and AI literacy.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
import logging

from app.core.config import get_settings
from app.api import inference, embeddings, rag, agents, templates, health, internal
from app.api.v1 import services, models, ai_inference, mcp_registry, mcp_executor
from app.core.backends import initialize_backends
from app.services.consul_registry import ConsulRegistry
from app.services.config_sync import get_config_sync_service
from app.api.v1.mcp_registry import initialize_mcp_servers

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting GT 2.0 Resource Cluster")
    
    # Initialize resource backends
    await initialize_backends()
    
    # Initialize MCP servers (RAG and Conversation)
    try:
        await initialize_mcp_servers()
        logger.info("MCP servers initialized")
    except Exception as e:
        logger.error(f"MCP server initialization failed: {e}")
    
    # Start configuration sync from admin cluster
    if settings.config_sync_enabled:
        config_sync = get_config_sync_service()

        # Perform initial sync before starting background loop
        try:
            await config_sync.sync_configurations()
            logger.info("Initial configuration sync completed")

            # Give config sync time to complete provider updates
            import asyncio
            await asyncio.sleep(0.5)

            # Verify BGE-M3 model is loaded in registry before refreshing embedding backend
            try:
                from app.services.model_service import default_model_service
                from app.core.backends import get_embedding_backend

                # Retry logic to wait for BGE-M3 to appear in registry
                max_retries = 3
                retry_delay = 1.0  # seconds
                bge_m3_found = False

                for attempt in range(max_retries):
                    bge_m3_config = default_model_service.model_registry.get("BAAI/bge-m3")

                    if bge_m3_config:
                        endpoint = bge_m3_config.get("endpoint_url")
                        config = bge_m3_config.get("parameters", {})
                        is_local_mode = config.get("is_local_mode", True)

                        logger.info(f"BGE-M3 found in registry on attempt {attempt + 1}: endpoint={endpoint}, is_local_mode={is_local_mode}")
                        bge_m3_found = True
                        break
                    else:
                        logger.debug(f"BGE-M3 not yet in registry (attempt {attempt + 1}/{max_retries}), retrying...")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)

                if not bge_m3_found:
                    logger.warning("BGE-M3 not found in registry after initial sync - will use defaults until next sync")

                # Refresh embedding backend with database configuration
                embedding_backend = get_embedding_backend()
                embedding_backend.refresh_endpoint_from_registry()
                logger.info(f"Embedding backend refreshed with database configuration: {embedding_backend.embedding_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to refresh embedding backend on startup: {e}")
        except Exception as e:
            logger.warning(f"Initial configuration sync failed: {e}")

        # Start sync loop in background
        asyncio.create_task(config_sync.start_sync_loop())
        logger.info("Started configuration sync from admin cluster")
    
    # Register with Consul for service discovery
    if settings.environment == "production":
        consul = ConsulRegistry()
        await consul.register_service(
            name="resource-cluster",
            service_id=f"resource-cluster-{settings.cluster_name}",
            address="localhost",
            port=settings.service_port,
            tags=["ai", "resource", "cluster"],
            check_interval="10s"
        )
    
    logger.info(f"Resource Cluster started on port {settings.service_port}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Resource Cluster")
    
    # Deregister from Consul
    if settings.environment == "production":
        await consul.deregister_service(f"resource-cluster-{settings.cluster_name}")


# Create FastAPI application
app = FastAPI(
    title="GT 2.0 Resource Cluster",
    description="Centralized AI resource management with high availability",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware with configurable hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts
)

# Include API routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(inference.router, prefix="/api/v1/inference", tags=["inference"])
app.include_router(embeddings.router, prefix="/api/v1/embeddings", tags=["embeddings"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(services.router, prefix="/api/v1/services", tags=["services"])
app.include_router(models.router, tags=["models"])
app.include_router(ai_inference.router, prefix="/api/v1", tags=["ai"])  # Add AI inference router
app.include_router(mcp_registry.router, prefix="/api/v1", tags=["mcp"])
app.include_router(mcp_executor.router, prefix="/api/v1", tags=["mcp"])
app.include_router(internal.router, tags=["internal"])  # Internal service-to-service APIs

# Mount Prometheus metrics endpoint
if settings.prometheus_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "GT 2.0 Resource Cluster",
        "version": "1.0.0",
        "status": "operational",
        "environment": settings.environment,
        "capabilities": {
            "ai_ml": ["llm", "embeddings", "image_generation"],
            "rag_engine": ["vector_search", "document_processing"],
            "agentic_workflows": ["single_agent", "multi_agent"],
            "app_integrations": ["oauth2", "webhooks"],
            "external_services": ["ctfd", "canvas", "guacamole", "iframe_embed", "sso"],
            "ai_literacy": ["games", "puzzles", "education"]
        }
    }


@app.get("/health")
async def health_check():
    """Docker health check endpoint (without trailing slash)"""
    return {
        "status": "healthy",
        "service": "resource-cluster",
        "timestamp": datetime.utcnow()
    }


@app.get("/ready")
async def ready_check():
    """Kubernetes readiness probe endpoint"""
    return {
        "status": "ready",
        "service": "resource-cluster",
        "timestamp": datetime.utcnow(),
        "health": "ok"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred processing your request"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )