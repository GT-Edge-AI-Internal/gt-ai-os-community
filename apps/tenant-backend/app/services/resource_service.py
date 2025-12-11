"""
Resource Service for GT 2.0 Tenant Backend

Provides access to Resource Cluster capabilities and services.
This is a wrapper around the resource_cluster_client for agent services.
"""

import logging
from typing import Dict, List, Optional, Any
from app.core.resource_client import ResourceClusterClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class ResourceService:
    """Service for accessing Resource Cluster capabilities"""
    
    def __init__(self):
        """Initialize resource service"""
        self.settings = get_settings()
        self.client = ResourceClusterClient()
    
    async def get_available_models(self, user_id: str) -> List[Dict[str, Any]]:
        """Get available AI models for user from Resource Cluster"""
        try:
            # Get models from Resource Cluster via capability token
            token = await self.client._get_capability_token(
                tenant_id=self.settings.tenant_domain,
                user_id=user_id,
                resources=['model_registry']
            )
            
            import aiohttp
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'X-Tenant-ID': self.settings.tenant_domain,
                'X-User-ID': user_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.client.base_url}/api/v1/models/",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        models_data = response_data.get("models", [])
                        
                        # Transform to expected format
                        available_models = []
                        for model in models_data:
                            if model.get("status", {}).get("deployment") == "available":
                                available_models.append({
                                    "model_id": model["id"],
                                    "name": model["name"],
                                    "provider": model["provider"],
                                    "capabilities": ["chat", "completion"],
                                    "context_length": model.get("performance", {}).get("context_window", 4000),
                                    "available": True
                                })
                        
                        logger.info(f"Retrieved {len(available_models)} models from Resource Cluster")
                        return available_models
                    else:
                        logger.error(f"Resource Cluster returned {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Failed to get available models from Resource Cluster: {e}")
            return []
    
    async def get_available_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """Get available tools for user"""
        try:
            # Mock tools for development
            return [
                {
                    "tool_id": "web_search",
                    "name": "Web Search",
                    "description": "Search the web for information",
                    "available": True,
                    "capabilities": ["search", "retrieve"]
                },
                {
                    "tool_id": "document_analysis",
                    "name": "Document Analysis",
                    "description": "Analyze documents and extract information",
                    "available": True,
                    "capabilities": ["analyze", "extract", "summarize"]
                },
                {
                    "tool_id": "code_execution",
                    "name": "Code Execution",
                    "description": "Execute code in safe sandbox",
                    "available": True,
                    "capabilities": ["execute", "debug", "test"]
                }
            ]
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return []
    
    async def validate_capabilities(self, user_id: str, capabilities: List[str]) -> bool:
        """Validate that user has access to required capabilities"""
        try:
            # For development, allow all capabilities
            logger.info(f"Validating capabilities {capabilities} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to validate capabilities: {e}")
            return False
    
    async def execute_agent_task(self, 
                                agent_id: str,
                                task_description: str, 
                                parameters: Dict[str, Any],
                                user_id: str) -> Dict[str, Any]:
        """Execute an agent task via Resource Cluster"""
        try:
            # Mock execution for development
            execution_result = {
                "execution_id": f"exec_{agent_id}_{int(datetime.now().timestamp())}",
                "status": "completed",
                "result": f"Mock execution of task: {task_description}",
                "output_artifacts": [],
                "tokens_used": 150,
                "cost_cents": 1,
                "execution_time_ms": 2500
            }
            
            logger.info(f"Mock agent execution: {execution_result['execution_id']}")
            return execution_result
        except Exception as e:
            logger.error(f"Failed to execute agent task: {e}")
            return {
                "execution_id": f"failed_{agent_id}",
                "status": "failed",
                "error": str(e)
            }
    
    async def get_resource_usage(self, user_id: str, timeframe_hours: int = 24) -> Dict[str, Any]:
        """Get resource usage statistics for user"""
        try:
            # Mock usage data for development
            return {
                "total_requests": 25,
                "total_tokens": 15000,
                "total_cost_cents": 150,
                "execution_count": 12,
                "average_response_time_ms": 1250,
                "timeframe_hours": timeframe_hours
            }
        except Exception as e:
            logger.error(f"Failed to get resource usage: {e}")
            return {}
    
    async def check_rate_limits(self, user_id: str) -> Dict[str, Any]:
        """Check current rate limits for user"""
        try:
            # Mock rate limit data for development
            return {
                "requests_per_minute": {"current": 5, "limit": 60, "reset_time": "2024-01-01T00:00:00Z"},
                "tokens_per_hour": {"current": 2500, "limit": 50000, "reset_time": "2024-01-01T00:00:00Z"},
                "executions_per_day": {"current": 12, "limit": 1000, "reset_time": "2024-01-01T00:00:00Z"}
            }
        except Exception as e:
            logger.error(f"Failed to check rate limits: {e}")
            return {}

# Import datetime for mock execution
from datetime import datetime