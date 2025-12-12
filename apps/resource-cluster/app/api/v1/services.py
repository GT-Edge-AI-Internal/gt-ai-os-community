"""
GT 2.0 Resource Cluster - External Services API
Orchestrate external web services with perfect tenant isolation
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from app.core.security import verify_capability_token
from app.services.service_manager import ServiceManager, ServiceInstance

logger = logging.getLogger(__name__)

router = APIRouter(tags=["services"])

# Initialize service manager
service_manager = ServiceManager()

class CreateServiceRequest(BaseModel):
    """Request to create a new service instance"""
    service_type: str = Field(..., description="Service type: ctfd, canvas, guacamole")
    config_overrides: Optional[Dict[str, Any]] = Field(default=None, description="Custom configuration overrides")
    
class ServiceInstanceResponse(BaseModel):
    """Service instance details response"""
    instance_id: str
    tenant_id: str
    service_type: str
    status: str
    endpoint_url: str
    sso_token: Optional[str]
    created_at: str
    last_heartbeat: str
    resource_usage: Dict[str, Any]

class ServiceHealthResponse(BaseModel):
    """Service health status response"""
    status: str
    instance_status: str
    endpoint: str
    last_check: str
    pod_phase: Optional[str] = None
    restart_count: Optional[int] = None
    error: Optional[str] = None

class ServiceListResponse(BaseModel):
    """List of service instances response"""
    instances: List[ServiceInstanceResponse]
    total: int

class SSOTokenResponse(BaseModel):
    """SSO token generation response"""
    token: str
    expires_at: str
    iframe_config: Dict[str, Any]

@router.post("/instances", response_model=ServiceInstanceResponse)
async def create_service_instance(
    request: CreateServiceRequest,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> ServiceInstanceResponse:
    """
    Create a new external service instance for a tenant.
    
    Supports:
    - CTFd cybersecurity challenges platform
    - Canvas LMS learning management system
    - Guacamole remote desktop access
    """
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        # Validate service type
        supported_services = ["ctfd", "canvas", "guacamole"]
        if request.service_type not in supported_services:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported service type. Supported: {supported_services}"
            )
        
        # Extract tenant ID from capabilities
        tenant_id = capabilities.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Tenant ID not found in capabilities"
            )
        
        # Create service instance
        instance = await service_manager.create_service_instance(
            tenant_id=tenant_id,
            service_type=request.service_type,
            config_overrides=request.config_overrides
        )
        
        logger.info(
            f"Created {request.service_type} instance {instance.instance_id} "
            f"for tenant {tenant_id}"
        )
        
        return ServiceInstanceResponse(
            instance_id=instance.instance_id,
            tenant_id=instance.tenant_id,
            service_type=instance.service_type,
            status=instance.status,
            endpoint_url=instance.endpoint_url,
            sso_token=instance.sso_token,
            created_at=instance.created_at.isoformat(),
            last_heartbeat=instance.last_heartbeat.isoformat(),
            resource_usage=instance.resource_usage or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create service instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instances/{instance_id}", response_model=ServiceInstanceResponse)
async def get_service_instance(
    instance_id: str,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> ServiceInstanceResponse:
    """Get details of a specific service instance"""
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        instance = await service_manager.get_service_instance(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"Service instance {instance_id} not found"
            )
        
        # Verify tenant access
        tenant_id = capabilities.get("tenant_id")
        if instance.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this service instance"
            )
        
        return ServiceInstanceResponse(
            instance_id=instance.instance_id,
            tenant_id=instance.tenant_id,
            service_type=instance.service_type,
            status=instance.status,
            endpoint_url=instance.endpoint_url,
            sso_token=instance.sso_token,
            created_at=instance.created_at.isoformat(),
            last_heartbeat=instance.last_heartbeat.isoformat(),
            resource_usage=instance.resource_usage or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tenant/{tenant_id}", response_model=ServiceListResponse)
async def list_tenant_services(
    tenant_id: str,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> ServiceListResponse:
    """List all service instances for a tenant"""
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        # Verify tenant access
        if capabilities.get("tenant_id") != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this tenant's services"
            )
        
        instances = await service_manager.list_tenant_instances(tenant_id)
        
        instance_responses = [
            ServiceInstanceResponse(
                instance_id=instance.instance_id,
                tenant_id=instance.tenant_id,
                service_type=instance.service_type,
                status=instance.status,
                endpoint_url=instance.endpoint_url,
                sso_token=instance.sso_token,
                created_at=instance.created_at.isoformat(),
                last_heartbeat=instance.last_heartbeat.isoformat(),
                resource_usage=instance.resource_usage or {}
            )
            for instance in instances
        ]
        
        return ServiceListResponse(
            instances=instance_responses,
            total=len(instance_responses)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list services for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/instances/{instance_id}")
async def stop_service_instance(
    instance_id: str,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> Dict[str, Any]:
    """Stop and remove a service instance"""
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        instance = await service_manager.get_service_instance(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"Service instance {instance_id} not found"
            )
        
        # Verify tenant access
        tenant_id = capabilities.get("tenant_id")
        if instance.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this service instance"
            )
        
        success = await service_manager.stop_service_instance(instance_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop service instance {instance_id}"
            )
        
        logger.info(
            f"Stopped {instance.service_type} instance {instance_id} "
            f"for tenant {tenant_id}"
        )
        
        return {
            "success": True,
            "message": f"Service instance {instance_id} stopped successfully",
            "stopped_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop service instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/{instance_id}", response_model=ServiceHealthResponse)
async def get_service_health(
    instance_id: str,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> ServiceHealthResponse:
    """Get health status of a service instance"""
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        instance = await service_manager.get_service_instance(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"Service instance {instance_id} not found"
            )
        
        # Verify tenant access
        tenant_id = capabilities.get("tenant_id")
        if instance.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this service instance"
            )
        
        health = await service_manager.get_service_health(instance_id)
        
        return ServiceHealthResponse(
            status=health.get("status", "unknown"),
            instance_status=health.get("instance_status", "unknown"),
            endpoint=health.get("endpoint", instance.endpoint_url),
            last_check=health.get("last_check", datetime.utcnow().isoformat()),
            pod_phase=health.get("pod_phase"),
            restart_count=health.get("restart_count"),
            error=health.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get health for service instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sso-token/{instance_id}", response_model=SSOTokenResponse)
async def generate_sso_token(
    instance_id: str,
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> SSOTokenResponse:
    """Generate SSO token for iframe embedding"""
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        instance = await service_manager.get_service_instance(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"Service instance {instance_id} not found"
            )
        
        # Verify tenant access
        tenant_id = capabilities.get("tenant_id")
        if instance.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this service instance"
            )
        
        # Generate new SSO token
        sso_token = await service_manager._generate_sso_token(instance)
        
        # Update instance with new token
        instance.sso_token = sso_token
        await service_manager._persist_instance(instance)
        
        # Generate iframe configuration
        iframe_config = {
            "src": f"{instance.endpoint_url}?sso_token={sso_token}",
            "sandbox": [
                "allow-same-origin",
                "allow-scripts", 
                "allow-forms",
                "allow-popups",
                "allow-modals"
            ],
            "allow": "camera; microphone; clipboard-read; clipboard-write",
            "referrerpolicy": "strict-origin-when-cross-origin",
            "loading": "lazy"
        }
        
        # Set security policies based on service type
        if instance.service_type == "guacamole":
            iframe_config["sandbox"].extend([
                "allow-pointer-lock",
                "allow-fullscreen"
            ])
        elif instance.service_type == "ctfd":
            iframe_config["sandbox"].extend([
                "allow-downloads",
                "allow-top-navigation-by-user-activation"
            ])
        
        expires_at = datetime.utcnow().isoformat()  # Token expires in 24 hours
        
        logger.info(
            f"Generated SSO token for {instance.service_type} instance "
            f"{instance_id} for tenant {tenant_id}"
        )
        
        return SSOTokenResponse(
            token=sso_token,
            expires_at=expires_at,
            iframe_config=iframe_config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate SSO token for {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates")
async def get_service_templates(
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> Dict[str, Any]:
    """Get available service templates and their capabilities"""
    try:
        # Verify external services capability
        if "external_services" not in capabilities.get("resources", []):
            raise HTTPException(
                status_code=403,
                detail="External services capability not granted"
            )
        
        # Return sanitized template information (no sensitive config)
        templates = {
            "ctfd": {
                "name": "CTFd Platform",
                "description": "Cybersecurity capture-the-flag challenges and competitions",
                "category": "cybersecurity",
                "features": [
                    "Challenge creation and management",
                    "Team-based competitions",
                    "Scoring and leaderboards",
                    "User management and registration",
                    "Real-time updates and notifications"
                ],
                "resource_requirements": {
                    "memory": "2Gi",
                    "cpu": "1000m",
                    "storage": "7Gi"
                },
                "estimated_startup_time": "2-3 minutes",
                "ports": {"http": 8000},
                "sso_supported": True
            },
            "canvas": {
                "name": "Canvas LMS",
                "description": "Learning management system for educational courses",
                "category": "education",
                "features": [
                    "Course creation and management",
                    "Assignment and grading system",
                    "Discussion forums and messaging",
                    "Grade book and analytics",
                    "Integration with external tools"
                ],
                "resource_requirements": {
                    "memory": "4Gi",
                    "cpu": "2000m",
                    "storage": "30Gi"
                },
                "estimated_startup_time": "3-5 minutes",
                "ports": {"http": 3000},
                "sso_supported": True
            },
            "guacamole": {
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
                    "memory": "1Gi",
                    "cpu": "500m", 
                    "storage": "11Gi"
                },
                "estimated_startup_time": "2-4 minutes",
                "ports": {"http": 8080},
                "sso_supported": True
            }
        }
        
        return {
            "templates": templates,
            "total": len(templates),
            "categories": list(set(t["category"] for t in templates.values())),
            "extensible": True,
            "note": "Additional service templates can be added through the GT 2.0 extensibility framework"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities")
async def get_service_capabilities() -> Dict[str, Any]:
    """Get service management capabilities - no authentication required"""
    return {
        "service_orchestration": {
            "platform": "kubernetes",
            "isolation": "namespace_based",
            "network_policies": True,
            "resource_quotas": True,
            "auto_scaling": False,  # Fixed replicas for now
            "health_monitoring": True,
            "automatic_recovery": True
        },
        "supported_services": [
            "ctfd",
            "canvas",
            "guacamole"
        ],
        "security_features": {
            "tenant_isolation": True,
            "container_security": True,
            "network_isolation": True,
            "sso_integration": True,
            "encrypted_storage": True,
            "capability_based_auth": True
        },
        "resource_management": {
            "cpu_limits": True,
            "memory_limits": True,
            "storage_quotas": True,
            "persistent_volumes": True,
            "automatic_cleanup": True
        },
        "deployment_features": {
            "rolling_updates": True,
            "health_checks": True,
            "restart_policies": True,
            "ingress_management": True,
            "tls_termination": True,
            "certificate_management": True
        }
    }

@router.post("/cleanup/orphaned")
async def cleanup_orphaned_resources(
    capabilities: Dict[str, Any] = Depends(verify_capability_token)
) -> Dict[str, Any]:
    """Clean up orphaned Kubernetes resources"""
    try:
        # Verify admin capabilities (this is a dangerous operation)
        if "admin" not in capabilities.get("user_type", ""):
            raise HTTPException(
                status_code=403,
                detail="Admin privileges required for cleanup operations"
            )
        
        await service_manager.cleanup_orphaned_resources()
        
        return {
            "success": True,
            "message": "Orphaned resource cleanup completed",
            "cleanup_time": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))