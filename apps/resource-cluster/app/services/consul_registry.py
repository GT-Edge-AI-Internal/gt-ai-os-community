"""
Consul Service Registry

Handles service registration and discovery for the Resource Cluster.
"""

import logging
from typing import Dict, Any, List, Optional
import consul
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ConsulRegistry:
    """Service registry using Consul"""
    
    def __init__(self):
        self.consul = None
        try:
            self.consul = consul.Consul(
                host=settings.consul_host,
                port=settings.consul_port,
                token=settings.consul_token
            )
        except Exception as e:
            logger.warning(f"Consul not available: {e}")
    
    async def register_service(
        self,
        name: str,
        service_id: str,
        address: str,
        port: int,
        tags: List[str] = None,
        check_interval: str = "10s"
    ) -> bool:
        """Register service with Consul"""
        
        if not self.consul:
            logger.warning("Consul not available, skipping registration")
            return False
        
        try:
            self.consul.agent.service.register(
                name=name,
                service_id=service_id,
                address=address,
                port=port,
                tags=tags or [],
                check=consul.Check.http(
                    f"http://{address}:{port}/health",
                    interval=check_interval
                )
            )
            logger.info(f"Registered service {service_id} with Consul")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register with Consul: {e}")
            return False
    
    async def deregister_service(self, service_id: str) -> bool:
        """Deregister service from Consul"""
        
        if not self.consul:
            return False
        
        try:
            self.consul.agent.service.deregister(service_id)
            logger.info(f"Deregistered service {service_id} from Consul")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deregister from Consul: {e}")
            return False
    
    async def discover_service(self, service_name: str) -> List[Dict[str, Any]]:
        """Discover service instances"""
        
        if not self.consul:
            return []
        
        try:
            _, services = self.consul.health.service(service_name, passing=True)
            
            instances = []
            for service in services:
                instances.append({
                    "id": service["Service"]["ID"],
                    "address": service["Service"]["Address"],
                    "port": service["Service"]["Port"],
                    "tags": service["Service"]["Tags"]
                })
            
            return instances
            
        except Exception as e:
            logger.error(f"Failed to discover service: {e}")
            return []