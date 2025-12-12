"""
Health check endpoints for Resource Cluster
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.core.backends import get_backend

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "resource-cluster"
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check for Kubernetes"""
    try:
        # Check if critical backends are initialized
        groq_backend = get_backend("groq_proxy")
        
        return {
            "status": "ready",
            "backends": {
                "groq_proxy": groq_backend is not None
            }
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/backends")
async def backend_health() -> Dict[str, Any]:
    """Check health of all resource backends"""
    health_status = {}
    
    try:
        # Check Groq backend
        groq_backend = get_backend("groq_proxy")
        groq_health = await groq_backend.check_health()
        health_status["groq"] = groq_health
    except Exception as e:
        health_status["groq"] = {"error": str(e)}
    
    return {
        "status": "operational",
        "backends": health_status
    }