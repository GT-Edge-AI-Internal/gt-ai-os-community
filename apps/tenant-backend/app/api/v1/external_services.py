"""
GT 2.0 Tenant Backend - External Services API
Manage external web service instances with Resource Cluster integration
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from app.api.auth import get_current_user
from app.core.database import get_db_session
from app.services.external_service import ExternalServiceManager
from app.core.capability_client import CapabilityClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["external_services"])

class CreateServiceRequest(BaseModel):
    """Request to create external service"""
    service_type: str = Field(..., description="Service type: ctfd, canvas, guacamole")
    service_name: str = Field(..., description="Human-readable service name")
    description: Optional[str] = Field(None, description="Service description")
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Custom configuration")
    template_id: Optional[str] = Field(None, description="Template to use as base")

class ShareServiceRequest(BaseModel):
    """Request to share service with other users"""
    share_with_emails: List[str] = Field(..., description="Email addresses to share with")
    access_level: str = Field(default="read", description="Access level: read, write")

class ServiceResponse(BaseModel):
    """Service instance response"""
    id: str
    service_type: str
    service_name: str
    description: Optional[str]
    endpoint_url: str
    status: str
    health_status: str
    created_by: str
    allowed_users: List[str]
    access_level: str
    created_at: str
    last_accessed: Optional[str]

class ServiceListResponse(BaseModel):
    """List of services response"""
    services: List[ServiceResponse]
    total: int

class EmbedConfigResponse(BaseModel):
    """Iframe embed configuration response"""
    iframe_url: str
    sandbox_attributes: List[str]
    security_policies: Dict[str, Any]
    sso_token: str
    expires_at: str

class ServiceAnalyticsResponse(BaseModel):
    """Service analytics response"""
    instance_id: str
    service_type: str
    service_name: str
    analytics_period_days: int
    total_sessions: int
    total_time_hours: float
    unique_users: int
    average_session_duration_minutes: float
    daily_usage: Dict[str, Any]
    uptime_percentage: float

@router.post("/create", response_model=ServiceResponse)
async def create_external_service(
    request: CreateServiceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> ServiceResponse:
    """Create a new external service instance"""
    try:
        # Initialize service manager
        service_manager = ExternalServiceManager(db)
        
        # Get capability token for Resource Cluster calls
        capability_client = CapabilityClient()
        capability_token = await capability_client.generate_capability_token(
            user_email=current_user['email'],
            tenant_id=current_user['tenant_id'],
            resources=['external_services'],
            expires_hours=24
        )
        service_manager.set_capability_token(capability_token)
        
        # Create service instance
        instance = await service_manager.create_service_instance(
            service_type=request.service_type,
            service_name=request.service_name,
            user_email=current_user['email'],
            config_overrides=request.config_overrides,
            template_id=request.template_id
        )
        
        logger.info(
            f"Created {request.service_type} service '{request.service_name}' "
            f"for user {current_user['email']}"
        )
        
        return ServiceResponse(
            id=instance.id,
            service_type=instance.service_type,
            service_name=instance.service_name,
            description=instance.description,
            endpoint_url=instance.endpoint_url,
            status=instance.status,
            health_status=instance.health_status,
            created_by=instance.created_by,
            allowed_users=instance.allowed_users,
            access_level=instance.access_level,
            created_at=instance.created_at.isoformat(),
            last_accessed=instance.last_accessed.isoformat() if instance.last_accessed else None
        )
        
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    except RuntimeError as e:
        logger.error(f"Resource cluster error: {e}")
        raise HTTPException(status_code=502, detail="Resource cluster unavailable")
    except Exception as e:
        logger.error(f"Failed to create external service: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list", response_model=ServiceListResponse)
async def list_external_services(
    service_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> ServiceListResponse:
    """List external services accessible to the user"""
    try:
        service_manager = ExternalServiceManager(db)
        
        instances = await service_manager.list_user_services(
            user_email=current_user['email'],
            service_type=service_type,
            status=status
        )
        
        services = [
            ServiceResponse(
                id=instance.id,
                service_type=instance.service_type,
                service_name=instance.service_name,
                description=instance.description,
                endpoint_url=instance.endpoint_url,
                status=instance.status,
                health_status=instance.health_status,
                created_by=instance.created_by,
                allowed_users=instance.allowed_users,
                access_level=instance.access_level,
                created_at=instance.created_at.isoformat(),
                last_accessed=instance.last_accessed.isoformat() if instance.last_accessed else None
            )
            for instance in instances
        ]
        
        return ServiceListResponse(
            services=services,
            total=len(services)
        )
        
    except Exception as e:
        logger.error(f"Failed to list external services: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{instance_id}", response_model=ServiceResponse)
async def get_external_service(
    instance_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> ServiceResponse:
    """Get specific external service details"""
    try:
        service_manager = ExternalServiceManager(db)
        
        instance = await service_manager.get_service_instance(
            instance_id=instance_id,
            user_email=current_user['email']
        )
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail="Service instance not found or access denied"
            )
        
        return ServiceResponse(
            id=instance.id,
            service_type=instance.service_type,
            service_name=instance.service_name,
            description=instance.description,
            endpoint_url=instance.endpoint_url,
            status=instance.status,
            health_status=instance.health_status,
            created_by=instance.created_by,
            allowed_users=instance.allowed_users,
            access_level=instance.access_level,
            created_at=instance.created_at.isoformat(),
            last_accessed=instance.last_accessed.isoformat() if instance.last_accessed else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get external service {instance_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{instance_id}")
async def stop_external_service(
    instance_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> Dict[str, Any]:
    """Stop external service instance"""
    try:
        service_manager = ExternalServiceManager(db)
        
        # Get capability token for Resource Cluster calls
        capability_client = CapabilityClient()
        capability_token = await capability_client.generate_capability_token(
            user_email=current_user['email'],
            tenant_id=current_user['tenant_id'],
            resources=['external_services'],
            expires_hours=1
        )
        service_manager.set_capability_token(capability_token)
        
        success = await service_manager.stop_service_instance(
            instance_id=instance_id,
            user_email=current_user['email']
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to stop service instance"
            )
        
        return {
            "success": True,
            "message": f"Service instance {instance_id} stopped successfully",
            "stopped_at": datetime.utcnow().isoformat()
        }

    except ValueError as e:
        logger.warning(f"Service not found: {e}")
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Failed to stop external service {instance_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{instance_id}/health")
async def get_service_health(
    instance_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> Dict[str, Any]:
    """Get service health status"""
    try:
        service_manager = ExternalServiceManager(db)
        
        # Get capability token for Resource Cluster calls
        capability_client = CapabilityClient()
        capability_token = await capability_client.generate_capability_token(
            user_email=current_user['email'],
            tenant_id=current_user['tenant_id'],
            resources=['external_services'],
            expires_hours=1
        )
        service_manager.set_capability_token(capability_token)
        
        health = await service_manager.get_service_health(
            instance_id=instance_id,
            user_email=current_user['email']
        )

        # codeql[py/stack-trace-exposure] returns health status dict, not error details
        return health

    except ValueError as e:
        logger.warning(f"Service not found: {e}")
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Failed to get service health for {instance_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{instance_id}/embed-config", response_model=EmbedConfigResponse)
async def get_embed_config(
    instance_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> EmbedConfigResponse:
    """Get iframe embed configuration with SSO token"""
    try:
        service_manager = ExternalServiceManager(db)
        
        # Get capability token for Resource Cluster calls
        capability_client = CapabilityClient()
        capability_token = await capability_client.generate_capability_token(
            user_email=current_user['email'],
            tenant_id=current_user['tenant_id'],
            resources=['external_services'],
            expires_hours=24
        )
        service_manager.set_capability_token(capability_token)
        
        # Generate SSO token and get embed config
        sso_data = await service_manager.generate_sso_token(
            instance_id=instance_id,
            user_email=current_user['email']
        )
        
        # Log access event
        await service_manager.log_service_access(
            service_instance_id=instance_id,
            service_type="unknown",  # Will be filled by service lookup
            user_email=current_user['email'],
            access_type="embed_access",
            session_id=f"embed_{datetime.utcnow().timestamp()}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            referer=request.headers.get("referer")
        )
        
        return EmbedConfigResponse(
            iframe_url=sso_data['iframe_config']['src'],
            sandbox_attributes=sso_data['iframe_config']['sandbox'],
            security_policies={
                'allow': sso_data['iframe_config']['allow'],
                'referrerpolicy': sso_data['iframe_config']['referrerpolicy'],
                'loading': sso_data['iframe_config']['loading']
            },
            sso_token=sso_data['token'],
            expires_at=sso_data['expires_at']
        )

    except ValueError as e:
        logger.warning(f"Service not found: {e}")
        raise HTTPException(status_code=404, detail="Service not found")
    except RuntimeError as e:
        logger.error(f"Resource cluster error: {e}")
        raise HTTPException(status_code=502, detail="Resource cluster unavailable")
    except Exception as e:
        logger.error(f"Failed to get embed config for {instance_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{instance_id}/analytics", response_model=ServiceAnalyticsResponse)
async def get_service_analytics(
    instance_id: str,
    days: int = 30,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> ServiceAnalyticsResponse:
    """Get service usage analytics"""
    try:
        service_manager = ExternalServiceManager(db)
        
        analytics = await service_manager.get_service_analytics(
            instance_id=instance_id,
            user_email=current_user['email'],
            days=days
        )
        
        return ServiceAnalyticsResponse(**analytics)

    except ValueError as e:
        logger.warning(f"Service not found: {e}")
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Failed to get analytics for {instance_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{instance_id}/share")
async def share_service(
    instance_id: str,
    request: ShareServiceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db_session)
) -> Dict[str, Any]:
    """Share service instance with other users"""
    try:
        service_manager = ExternalServiceManager(db)
        
        success = await service_manager.share_service_instance(
            instance_id=instance_id,
            owner_email=current_user['email'],
            share_with_emails=request.share_with_emails,
            access_level=request.access_level
        )
        
        return {
            "success": success,
            "shared_with": request.share_with_emails,
            "access_level": request.access_level,
            "shared_at": datetime.utcnow().isoformat()
        }

    except ValueError as e:
        logger.warning(f"Service not found: {e}")
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Failed to share service {instance_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/templates/list")
async def list_service_templates(
    service_type: Optional[str] = None,
    category: Optional[str] = None,
    db=Depends(get_db_session)
) -> Dict[str, Any]:
    """List available service templates"""
    try:
        service_manager = ExternalServiceManager(db)
        
        templates = await service_manager.list_service_templates(
            service_type=service_type,
            category=category,
            public_only=True
        )
        
        return {
            "templates": [template.to_dict() for template in templates],
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Failed to list service templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/types/supported")
async def get_supported_service_types() -> Dict[str, Any]:
    """Get supported external service types and their capabilities"""
    return {
        "supported_types": [
            {
                "type": "ctfd",
                "name": "CTFd Platform",
                "description": "Cybersecurity capture-the-flag challenges and competitions",
                "category": "cybersecurity",
                "features": [
                    "Challenge creation and management",
                    "Team-based competitions", 
                    "Scoring and leaderboards",
                    "User registration and management",
                    "Real-time notifications"
                ],
                "resource_requirements": {
                    "cpu": "1000m",
                    "memory": "2Gi",
                    "storage": "7Gi"
                },
                "estimated_startup_time": "2-3 minutes",
                "sso_supported": True
            },
            {
                "type": "canvas",
                "name": "Canvas LMS",
                "description": "Learning management system for educational courses",
                "category": "education", 
                "features": [
                    "Course creation and management",
                    "Assignment and grading system",
                    "Discussion forums and messaging",
                    "Grade book and analytics",
                    "External tool integrations"
                ],
                "resource_requirements": {
                    "cpu": "2000m",
                    "memory": "4Gi", 
                    "storage": "30Gi"
                },
                "estimated_startup_time": "3-5 minutes",
                "sso_supported": True
            },
            {
                "type": "guacamole",
                "name": "Apache Guacamole",
                "description": "Remote desktop access for cyber lab environments",
                "category": "remote_access",
                "features": [
                    "RDP, VNC, and SSH connections",
                    "Session recording and playback", 
                    "Multi-user concurrent access",
                    "Connection sharing and collaboration",
                    "File transfer capabilities"
                ],
                "resource_requirements": {
                    "cpu": "500m",
                    "memory": "1Gi",
                    "storage": "11Gi" 
                },
                "estimated_startup_time": "2-4 minutes",
                "sso_supported": True
            }
        ],
        "total_types": 3,
        "categories": ["cybersecurity", "education", "remote_access"],
        "extensible": True
    }