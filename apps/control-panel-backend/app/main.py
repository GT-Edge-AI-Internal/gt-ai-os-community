"""
GT 2.0 Control Panel Backend - FastAPI Application
"""
import warnings
# Suppress passlib's bcrypt version detection warning (cosmetic only, doesn't affect functionality)
# passlib 1.7.4 tries to read bcrypt.__about__.__version__ which was removed in bcrypt 4.1.x
warnings.filterwarnings("ignore", message=".*module 'bcrypt' has no attribute '__about__'.*")

import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.core.config import settings
from app.core.database import engine, init_db
from app.core.api_standards import setup_api_standards
from app.api import auth, resources, tenants, users, tfa, public
from app.api.v1 import api_keys, analytics, resource_management, models, tenant_models, templates, system
from app.api.internal import api_keys as internal_api_keys
from app.api.internal import optics as internal_optics
from app.api.internal import sessions as internal_sessions
from app.middleware.session_validation import SessionValidationMiddleware

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting GT 2.0 Control Panel Backend")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GT 2.0 Control Panel Backend")


# Create FastAPI application
app = FastAPI(
    title="GT 2.0 Control Panel API",
    description="Enterprise AI as a Service Platform - Control Panel Backend",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# Setup CB-REST API standards (adds middleware)
setup_api_standards(app, settings.SECRET_KEY)

# Add CORS middleware (must be added after CB-REST middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Warning", "X-Session-Expired"],  # Issue #264: Expose session headers to frontend
)

# Add session validation middleware (Issue #264: OWASP/NIST compliant session management)
app.add_middleware(SessionValidationMiddleware)


# Security headers middleware (production only)
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Middleware for request logging
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log request
    logger.info(
        "Request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=duration,
        user_agent=request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None
    )

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error"
            }
        }
    )


# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "gt2-control-panel-backend"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    try:
        # Check database connection
        from app.core.database import get_db_session
        async with get_db_session() as session:
            await session.execute("SELECT 1")
        
        return {"status": "ready", "service": "gt2-control-panel-backend"}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "error": "Database connection failed"}
        )


# Include API routers
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(tfa.router, prefix="/api/v1", tags=["Two-Factor Authentication"])
app.include_router(public.router, prefix="/api/v1", tags=["Public"])
app.include_router(tenants.router, prefix="/api/v1", tags=["Tenants"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(resources.router, prefix="/api/v1", tags=["AI Resources"])

# V1 API routes
app.include_router(api_keys.router, tags=["API Keys"])
app.include_router(analytics.router, tags=["Analytics"])
app.include_router(resource_management.router, prefix="/api/v1", tags=["Resource Management"])
app.include_router(models.router, prefix="/api/v1", tags=["Model Management"])
app.include_router(tenant_models.router, prefix="/api/v1", tags=["Tenant Model Management"])
app.include_router(tenant_models.router, prefix="/api/v1/tenant-models", tags=["Tenant Model Access"])
app.include_router(templates.router, tags=["Templates"])
app.include_router(system.router, tags=["System Management"])

# Internal service-to-service routes
app.include_router(internal_api_keys.router, tags=["Internal"])
app.include_router(internal_optics.router, tags=["Internal"])
app.include_router(internal_sessions.router, tags=["Internal"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="info"
    )