"""
BGE-M3 Embedding Configuration API for Tenant Backend

Provides endpoint to update embedding configuration at runtime.
This allows the tenant backend to switch between local and external embedding endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
import logging
import os

from app.services.embedding_client import get_embedding_client

router = APIRouter()
logger = logging.getLogger(__name__)


class BGE_M3_ConfigRequest(BaseModel):
    """BGE-M3 configuration update request"""
    is_local_mode: bool = True
    external_endpoint: Optional[str] = None


class BGE_M3_ConfigResponse(BaseModel):
    """BGE-M3 configuration response"""
    is_local_mode: bool
    current_endpoint: str
    message: str


@router.post("/config/bge-m3", response_model=BGE_M3_ConfigResponse)
async def update_bge_m3_config(
    config_request: BGE_M3_ConfigRequest
) -> BGE_M3_ConfigResponse:
    """
    Update BGE-M3 configuration for the tenant backend.

    This allows switching between local and external endpoints at runtime.
    No authentication required for service-to-service calls.
    """
    try:
        # Get the global embedding client
        embedding_client = get_embedding_client()

        # Determine new endpoint
        if config_request.is_local_mode:
            new_endpoint = os.getenv('EMBEDDING_ENDPOINT', 'http://host.docker.internal:8005')
        else:
            if not config_request.external_endpoint:
                raise HTTPException(status_code=400, detail="External endpoint required when not in local mode")
            new_endpoint = config_request.external_endpoint

        # Update the client endpoint
        embedding_client.update_endpoint(new_endpoint)

        # Update environment variables for future client instances
        os.environ['BGE_M3_LOCAL_MODE'] = str(config_request.is_local_mode).lower()
        if config_request.external_endpoint:
            os.environ['BGE_M3_EXTERNAL_ENDPOINT'] = config_request.external_endpoint

        logger.info(
            f"BGE-M3 configuration updated: "
            f"local_mode={config_request.is_local_mode}, "
            f"endpoint={new_endpoint}"
        )

        return BGE_M3_ConfigResponse(
            is_local_mode=config_request.is_local_mode,
            current_endpoint=new_endpoint,
            message=f"BGE-M3 configuration updated to {'local' if config_request.is_local_mode else 'external'} mode"
        )

    except Exception as e:
        logger.error(f"Error updating BGE-M3 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/bge-m3", response_model=BGE_M3_ConfigResponse)
async def get_bge_m3_config() -> BGE_M3_ConfigResponse:
    """
    Get current BGE-M3 configuration.
    """
    try:
        embedding_client = get_embedding_client()

        # Determine if currently in local mode
        is_local_mode = os.getenv('BGE_M3_LOCAL_MODE', 'true').lower() == 'true'

        return BGE_M3_ConfigResponse(
            is_local_mode=is_local_mode,
            current_endpoint=embedding_client.base_url,
            message="Current BGE-M3 configuration"
        )

    except Exception as e:
        logger.error(f"Error getting BGE-M3 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))