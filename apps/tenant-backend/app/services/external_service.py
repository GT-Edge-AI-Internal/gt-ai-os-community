"""
GT 2.0 Tenant Backend - External Service Management
Business logic for managing external web services with Resource Cluster integration
"""

import asyncio
import httpx
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_service import ExternalServiceInstance, ServiceAccessLog, ServiceTemplate
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ExternalServiceManager:
    """Manages external service instances and Resource Cluster integration"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.resource_cluster_base_url = settings.resource_cluster_url or "http://resource-cluster:8003"
        self.capability_token = None
    
    def set_capability_token(self, token: str):
        """Set capability token for Resource Cluster API calls"""
        self.capability_token = token
    
    async def create_service_instance(
        self,
        service_type: str,
        service_name: str,
        user_email: str,
        config_overrides: Optional[Dict[str, Any]] = None,
        template_id: Optional[str] = None
    ) -> ExternalServiceInstance:
        """Create a new external service instance"""
        
        # Validate service type
        supported_services = ['ctfd', 'canvas', 'guacamole']
        if service_type not in supported_services:
            raise ValueError(f"Unsupported service type: {service_type}")
        
        # Load template if provided
        template = None
        if template_id:
            template = await self.get_service_template(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
        
        # Prepare configuration
        service_config = {}
        if template:
            service_config.update(template.default_config)
        if config_overrides:
            service_config.update(config_overrides)
        
        # Call Resource Cluster to create instance
        resource_instance = await self._create_resource_cluster_instance(
            service_type=service_type,
            config_overrides=service_config
        )
        
        # Create database record
        instance = ExternalServiceInstance(
            service_type=service_type,
            service_name=service_name,
            description=f"{service_type.title()} instance for {user_email}",
            resource_instance_id=resource_instance['instance_id'],
            endpoint_url=resource_instance['endpoint_url'],
            status=resource_instance['status'],
            service_config=service_config,
            created_by=user_email,
            allowed_users=[user_email],
            resource_limits=template.resource_requirements if template else {},
            auto_start=template.default_config.get('auto_start', True) if template else True
        )
        
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        
        logger.info(
            f"Created {service_type} service instance {instance.id} "
            f"for user {user_email}"
        )
        
        return instance
    
    async def _create_resource_cluster_instance(
        self,
        service_type: str,
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create instance via Resource Cluster API with zero downtime error handling"""
        
        if not self.capability_token:
            raise ValueError("Capability token not set")
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                timeout = httpx.Timeout(60.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.resource_cluster_base_url}/api/v1/services/instances",
                        json={
                            "service_type": service_type,
                            "config_overrides": config_overrides
                        },
                        headers={
                            "Authorization": f"Bearer {self.capability_token}",
                            "Content-Type": "application/json"
                        }
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                        # Retry for server errors
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Service creation failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        try:
                            error_detail = response.json().get('detail', f'HTTP {response.status_code}')
                        except:
                            error_detail = f'HTTP {response.status_code}'
                        raise RuntimeError(f"Failed to create service instance: {error_detail}")
                        
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Service creation timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise RuntimeError("Failed to create service instance: timeout after retries")
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Service creation request error (attempt {attempt + 1}/{max_retries}): {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise RuntimeError(f"Failed to create service instance: {e}")
        
        raise RuntimeError("Failed to create service instance: maximum retries exceeded")
    
    async def get_service_instance(
        self,
        instance_id: str,
        user_email: str
    ) -> Optional[ExternalServiceInstance]:
        """Get service instance with access control"""
        
        query = select(ExternalServiceInstance).where(
            and_(
                ExternalServiceInstance.id == instance_id,
                ExternalServiceInstance.allowed_users.op('json_extract_path_text')('*').op('@>')([user_email])
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_user_services(
        self,
        user_email: str,
        service_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[ExternalServiceInstance]:
        """List all services accessible to a user"""
        
        query = select(ExternalServiceInstance).where(
            ExternalServiceInstance.allowed_users.op('json_extract_path_text')('*').op('@>')([user_email])
        )
        
        if service_type:
            query = query.where(ExternalServiceInstance.service_type == service_type)
        
        if status:
            query = query.where(ExternalServiceInstance.status == status)
        
        query = query.order_by(ExternalServiceInstance.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def stop_service_instance(
        self,
        instance_id: str,
        user_email: str
    ) -> bool:
        """Stop a service instance"""
        
        # Check access
        instance = await self.get_service_instance(instance_id, user_email)
        if not instance:
            raise ValueError(f"Service instance {instance_id} not found or access denied")
        
        # Call Resource Cluster to stop instance
        success = await self._stop_resource_cluster_instance(instance.resource_instance_id)
        
        if success:
            # Update database status
            instance.status = 'stopped'
            instance.updated_at = datetime.utcnow()
            await self.db.commit()
            
            logger.info(
                f"Stopped {instance.service_type} instance {instance_id} "
                f"by user {user_email}"
            )
        
        return success
    
    async def _stop_resource_cluster_instance(self, resource_instance_id: str) -> bool:
        """Stop instance via Resource Cluster API with zero downtime error handling"""
        
        if not self.capability_token:
            raise ValueError("Capability token not set")
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                timeout = httpx.Timeout(30.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.delete(
                        f"{self.resource_cluster_base_url}/api/v1/services/instances/{resource_instance_id}",
                        headers={
                            "Authorization": f"Bearer {self.capability_token}"
                        }
                    )
                    
                    if response.status_code == 200:
                        return True
                    elif response.status_code == 404:
                        # Instance already gone, consider it successfully stopped
                        logger.info(f"Instance {resource_instance_id} not found, assuming already stopped")
                        return True
                    elif response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                        # Retry for server errors
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Instance stop failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Failed to stop instance {resource_instance_id}: HTTP {response.status_code}")
                        return False
                        
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Instance stop timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to stop instance {resource_instance_id}: timeout after retries")
                    return False
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Instance stop request error (attempt {attempt + 1}/{max_retries}): {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to stop instance {resource_instance_id}: {e}")
                    return False
        
        logger.error(f"Failed to stop instance {resource_instance_id}: maximum retries exceeded")
        return False
    
    async def get_service_health(
        self,
        instance_id: str,
        user_email: str
    ) -> Dict[str, Any]:
        """Get service health status"""
        
        # Check access
        instance = await self.get_service_instance(instance_id, user_email)
        if not instance:
            raise ValueError(f"Service instance {instance_id} not found or access denied")
        
        # Get health from Resource Cluster
        health = await self._get_resource_cluster_health(instance.resource_instance_id)
        
        # Update instance health status
        instance.health_status = health.get('status', 'unknown')
        instance.last_health_check = datetime.utcnow()
        if health.get('restart_count', 0) != instance.restart_count:
            instance.restart_count = health.get('restart_count', 0)
        
        await self.db.commit()
        
        return health
    
    async def _get_resource_cluster_health(self, resource_instance_id: str) -> Dict[str, Any]:
        """Get health status via Resource Cluster API with zero downtime error handling"""
        
        if not self.capability_token:
            raise ValueError("Capability token not set")
        
        try:
            timeout = httpx.Timeout(10.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.resource_cluster_base_url}/api/v1/services/health/{resource_instance_id}",
                    headers={
                        "Authorization": f"Bearer {self.capability_token}"
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return {
                        'status': 'not_found',
                        'error': 'Instance not found'
                    }
                else:
                    return {
                        'status': 'error',
                        'error': f'Health check failed: HTTP {response.status_code}'
                    }
                    
        except httpx.TimeoutException:
            logger.warning(f"Health check timeout for instance {resource_instance_id}")
            return {
                'status': 'timeout',
                'error': 'Health check timeout'
            }
        except httpx.RequestError as e:
            logger.warning(f"Health check request error for instance {resource_instance_id}: {e}")
            return {
                'status': 'connection_error',
                'error': f'Connection error: {e}'
            }
    
    async def generate_sso_token(
        self,
        instance_id: str,
        user_email: str
    ) -> Dict[str, Any]:
        """Generate SSO token for iframe embedding"""
        
        # Check access
        instance = await self.get_service_instance(instance_id, user_email)
        if not instance:
            raise ValueError(f"Service instance {instance_id} not found or access denied")
        
        # Generate SSO token via Resource Cluster
        sso_data = await self._generate_resource_cluster_sso_token(instance.resource_instance_id)
        
        # Update last accessed time
        instance.last_accessed = datetime.utcnow()
        await self.db.commit()
        
        return sso_data
    
    async def _generate_resource_cluster_sso_token(self, resource_instance_id: str) -> Dict[str, Any]:
        """Generate SSO token via Resource Cluster API with zero downtime error handling"""
        
        if not self.capability_token:
            raise ValueError("Capability token not set")
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                timeout = httpx.Timeout(10.0, connect=5.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.resource_cluster_base_url}/api/v1/services/sso-token/{resource_instance_id}",
                        headers={
                            "Authorization": f"Bearer {self.capability_token}"
                        }
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                        # Retry for server errors
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"SSO token generation failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        try:
                            error_detail = response.json().get('detail', f'HTTP {response.status_code}')
                        except:
                            error_detail = f'HTTP {response.status_code}'
                        raise RuntimeError(f"Failed to generate SSO token: {error_detail}")
                        
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"SSO token generation timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise RuntimeError("Failed to generate SSO token: timeout after retries")
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"SSO token generation request error (attempt {attempt + 1}/{max_retries}): {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise RuntimeError(f"Failed to generate SSO token: {e}")
        
        raise RuntimeError("Failed to generate SSO token: maximum retries exceeded")
    
    async def log_service_access(
        self,
        service_instance_id: str,
        service_type: str,
        user_email: str,
        access_type: str,
        session_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referer: Optional[str] = None,
        session_duration_seconds: Optional[int] = None,
        actions_performed: Optional[List[str]] = None
    ) -> ServiceAccessLog:
        """Log service access event"""
        
        access_log = ServiceAccessLog(
            service_instance_id=service_instance_id,
            service_type=service_type,
            user_email=user_email,
            session_id=session_id,
            access_type=access_type,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            session_duration_seconds=session_duration_seconds,
            actions_performed=actions_performed or []
        )
        
        self.db.add(access_log)
        await self.db.commit()
        await self.db.refresh(access_log)
        
        return access_log
    
    async def get_service_analytics(
        self,
        instance_id: str,
        user_email: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get service usage analytics"""
        
        # Check access
        instance = await self.get_service_instance(instance_id, user_email)
        if not instance:
            raise ValueError(f"Service instance {instance_id} not found or access denied")
        
        # Query access logs
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(ServiceAccessLog).where(
            and_(
                ServiceAccessLog.service_instance_id == instance_id,
                ServiceAccessLog.timestamp >= since_date
            )
        ).order_by(ServiceAccessLog.timestamp.desc())
        
        result = await self.db.execute(query)
        access_logs = result.scalars().all()
        
        # Compute analytics
        total_sessions = len(set(log.session_id for log in access_logs))
        total_time_seconds = sum(
            log.session_duration_seconds or 0 
            for log in access_logs 
            if log.session_duration_seconds
        )
        unique_users = len(set(log.user_email for log in access_logs))
        
        # Group by day for trend analysis
        daily_usage = {}
        for log in access_logs:
            day = log.timestamp.date().isoformat()
            if day not in daily_usage:
                daily_usage[day] = {'sessions': 0, 'users': set()}
            if log.access_type == 'login':
                daily_usage[day]['sessions'] += 1
                daily_usage[day]['users'].add(log.user_email)
        
        # Convert sets to counts
        for day_data in daily_usage.values():
            day_data['unique_users'] = len(day_data['users'])
            del day_data['users']
        
        return {
            'instance_id': instance_id,
            'service_type': instance.service_type,
            'service_name': instance.service_name,
            'analytics_period_days': days,
            'total_sessions': total_sessions,
            'total_time_hours': round(total_time_seconds / 3600, 1),
            'unique_users': unique_users,
            'average_session_duration_minutes': round(
                total_time_seconds / max(total_sessions, 1) / 60, 1
            ),
            'daily_usage': daily_usage,
            'health_status': instance.health_status,
            'uptime_percentage': self._calculate_uptime_percentage(access_logs, days),
            'last_accessed': instance.last_accessed.isoformat() if instance.last_accessed else None,
            'created_at': instance.created_at.isoformat()
        }
    
    def _calculate_uptime_percentage(self, access_logs: List[ServiceAccessLog], days: int) -> float:
        """Calculate approximate uptime percentage based on access patterns"""
        if not access_logs:
            return 0.0
        
        # Simple heuristic: if we have recent login events, assume service is up
        recent_logins = [
            log for log in access_logs 
            if log.access_type == 'login' and 
            log.timestamp > datetime.utcnow() - timedelta(days=1)
        ]
        
        if recent_logins:
            return 95.0  # Assume good uptime if recently accessed
        elif len(access_logs) > 0:
            return 85.0  # Some historical usage
        else:
            return 50.0  # No usage data
    
    async def create_service_template(
        self,
        template_name: str,
        service_type: str,
        description: str,
        default_config: Dict[str, Any],
        created_by: str,
        **kwargs
    ) -> ServiceTemplate:
        """Create a new service template"""
        
        template = ServiceTemplate(
            template_name=template_name,
            service_type=service_type,
            description=description,
            default_config=default_config,
            created_by=created_by,
            **kwargs
        )
        
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        
        return template
    
    async def get_service_template(self, template_id: str) -> Optional[ServiceTemplate]:
        """Get service template by ID"""
        
        query = select(ServiceTemplate).where(ServiceTemplate.id == template_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_service_templates(
        self,
        service_type: Optional[str] = None,
        category: Optional[str] = None,
        public_only: bool = True
    ) -> List[ServiceTemplate]:
        """List available service templates"""
        
        query = select(ServiceTemplate).where(ServiceTemplate.is_active == True)
        
        if public_only:
            query = query.where(ServiceTemplate.is_public == True)
        
        if service_type:
            query = query.where(ServiceTemplate.service_type == service_type)
        
        if category:
            query = query.where(ServiceTemplate.category == category)
        
        query = query.order_by(ServiceTemplate.usage_count.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def share_service_instance(
        self,
        instance_id: str,
        owner_email: str,
        share_with_emails: List[str],
        access_level: str = 'read'
    ) -> bool:
        """Share service instance with other users"""
        
        # Check owner access
        instance = await self.get_service_instance(instance_id, owner_email)
        if not instance:
            raise ValueError(f"Service instance {instance_id} not found or access denied")
        
        if instance.created_by != owner_email:
            raise ValueError("Only the instance creator can share access")
        
        # Update allowed users
        current_users = set(instance.allowed_users)
        new_users = current_users.union(set(share_with_emails))
        
        instance.allowed_users = list(new_users)
        instance.access_level = 'team' if len(new_users) > 1 else 'private'
        instance.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(
            f"Shared {instance.service_type} instance {instance_id} "
            f"with {len(share_with_emails)} users"
        )
        
        return True