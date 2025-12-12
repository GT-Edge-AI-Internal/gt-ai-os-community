"""
Model Context Protocol (MCP) Integration Service
Enables extensible tool integration for GT 2.0 agents
"""

from typing import List, Dict, Any, Optional
import httpx
import asyncio
import json
from pydantic import BaseModel, Field
from datetime import datetime
import logging
from app.models.agent import Agent

logger = logging.getLogger(__name__)

class MCPTool(BaseModel):
    """MCP Tool definition"""
    name: str
    description: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any] = Field(default_factory=dict)
    endpoint: str
    requires_auth: bool = False
    rate_limit: Optional[int] = None  # requests per minute
    timeout: int = 30  # seconds
    enabled: bool = True

class MCPServer(BaseModel):
    """MCP Server configuration"""
    id: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    tools: List[MCPTool] = Field(default_factory=list)
    health_check_endpoint: str = "/health"
    tools_endpoint: str = "/tools"
    timeout: int = 30
    max_retries: int = 3
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"  # healthy, unhealthy, unknown

class MCPExecutionResult(BaseModel):
    """Result of tool execution"""
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: int
    tokens_used: Optional[int] = None
    cost_cents: Optional[int] = None

class MCPIntegrationService:
    """Service for managing MCP integrations"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.rate_limits: Dict[str, Dict[str, List[datetime]]] = {}  # server_id -> tool_name -> timestamps
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    
    async def register_server(self, server: MCPServer) -> bool:
        """Register a new MCP server"""
        try:
            # Validate server is reachable
            if await self.health_check(server):
                # Discover available tools
                tools = await self.discover_tools(server)
                server.tools = tools
                server.health_status = "healthy"
                server.last_health_check = datetime.utcnow()
                
                self.servers[server.id] = server
                self.rate_limits[server.id] = {}
                
                logger.info(f"Registered MCP server: {server.name} with {len(tools)} tools")
                return True
            else:
                server.health_status = "unhealthy"
                logger.error(f"Failed to register MCP server: {server.name} - health check failed")
                return False
        except Exception as e:
            server.health_status = "unhealthy"
            logger.error(f"Failed to register MCP server: {server.name} - {str(e)}")
            return False
    
    async def health_check(self, server: MCPServer) -> bool:
        """Check if MCP server is healthy"""
        try:
            headers = {}
            if server.api_key:
                headers["Authorization"] = f"Bearer {server.api_key}"
                
            response = await self.client.get(
                f"{server.base_url.rstrip('/')}{server.health_check_endpoint}",
                headers=headers,
                timeout=10.0
            )
            
            is_healthy = response.status_code == 200
            
            if server.id in self.servers:
                self.servers[server.id].health_status = "healthy" if is_healthy else "unhealthy"
                self.servers[server.id].last_health_check = datetime.utcnow()
                
            return is_healthy
            
        except Exception as e:
            logger.warning(f"Health check failed for {server.name}: {e}")
            if server.id in self.servers:
                self.servers[server.id].health_status = "unhealthy"
            return False
    
    async def discover_tools(self, server: MCPServer) -> List[MCPTool]:
        """Discover available tools from MCP server"""
        try:
            headers = {}
            if server.api_key:
                headers["Authorization"] = f"Bearer {server.api_key}"
                
            response = await self.client.get(
                f"{server.base_url.rstrip('/')}{server.tools_endpoint}",
                headers=headers
            )
            
            if response.status_code == 200:
                tools_data = response.json()
                tools = []
                
                for tool_data in tools_data.get("tools", []):
                    try:
                        tool = MCPTool(**tool_data)
                        tools.append(tool)
                    except Exception as e:
                        logger.warning(f"Invalid tool definition from {server.name}: {e}")
                        
                return tools
                
        except Exception as e:
            logger.error(f"Tool discovery failed for {server.name}: {e}")
        return []
    
    def _check_rate_limit(self, server_id: str, tool_name: str) -> bool:
        """Check if rate limit allows execution"""
        server = self.servers.get(server_id)
        if not server:
            return False
            
        tool = next((t for t in server.tools if t.name == tool_name), None)
        if not tool or not tool.rate_limit:
            return True
            
        now = datetime.utcnow()
        minute_ago = now.timestamp() - 60
        
        # Initialize tracking if needed
        if server_id not in self.rate_limits:
            self.rate_limits[server_id] = {}
        if tool_name not in self.rate_limits[server_id]:
            self.rate_limits[server_id][tool_name] = []
            
        # Clean old timestamps
        timestamps = self.rate_limits[server_id][tool_name]
        self.rate_limits[server_id][tool_name] = [
            ts for ts in timestamps if ts.timestamp() > minute_ago
        ]
        
        # Check limit
        current_count = len(self.rate_limits[server_id][tool_name])
        if current_count >= tool.rate_limit:
            return False
            
        # Record this request
        self.rate_limits[server_id][tool_name].append(now)
        return True
    
    async def execute_tool(
        self,
        server_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        assistant_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> MCPExecutionResult:
        """Execute a tool on an MCP server"""
        start_time = datetime.utcnow()
        
        try:
            # Validate server exists and is enabled
            if server_id not in self.servers:
                return MCPExecutionResult(
                    success=False,
                    error=f"Server {server_id} not registered",
                    execution_time_ms=0
                )
            
            server = self.servers[server_id]
            if not server.enabled:
                return MCPExecutionResult(
                    success=False,
                    error=f"Server {server_id} is disabled",
                    execution_time_ms=0
                )
            
            # Find tool
            tool = next((t for t in server.tools if t.name == tool_name), None)
            if not tool:
                return MCPExecutionResult(
                    success=False,
                    error=f"Tool {tool_name} not found on server {server_id}",
                    execution_time_ms=0
                )
            
            if not tool.enabled:
                return MCPExecutionResult(
                    success=False,
                    error=f"Tool {tool_name} is disabled",
                    execution_time_ms=0
                )
            
            # Check rate limit
            if not self._check_rate_limit(server_id, tool_name):
                return MCPExecutionResult(
                    success=False,
                    error=f"Rate limit exceeded for tool {tool_name}",
                    execution_time_ms=0
                )
            
            # Prepare request
            headers = {"Content-Type": "application/json"}
            if server.api_key:
                headers["Authorization"] = f"Bearer {server.api_key}"
            
            payload = {
                "tool": tool_name,
                "parameters": parameters
            }
            
            # Add context if provided
            if assistant_context:
                payload["assistant_context"] = assistant_context
            if user_context:
                payload["user_context"] = user_context
            
            # Execute with retries
            last_exception = None
            for attempt in range(server.max_retries):
                try:
                    response = await self.client.post(
                        f"{server.base_url.rstrip('/')}{tool.endpoint}",
                        json=payload,
                        headers=headers,
                        timeout=tool.timeout
                    )
                    
                    execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        return MCPExecutionResult(
                            success=True,
                            data=result_data,
                            execution_time_ms=execution_time,
                            tokens_used=result_data.get("tokens_used"),
                            cost_cents=result_data.get("cost_cents")
                        )
                    else:
                        return MCPExecutionResult(
                            success=False,
                            error=f"HTTP {response.status_code}: {response.text}",
                            execution_time_ms=execution_time
                        )
                        
                except httpx.TimeoutException as e:
                    last_exception = e
                    if attempt == server.max_retries - 1:
                        break
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                except Exception as e:
                    last_exception = e
                    if attempt == server.max_retries - 1:
                        break
                    await asyncio.sleep(2 ** attempt)
            
            # All retries failed
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return MCPExecutionResult(
                success=False,
                error=f"Tool execution failed after {server.max_retries} attempts: {str(last_exception)}",
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return MCPExecutionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                execution_time_ms=execution_time
            )
    
    async def get_tools_for_assistant(
        self,
        agent: Agent
    ) -> List[MCPTool]:
        """Get all available tools for an agent based on integrations"""
        tools = []
        for integration_id in agent.mcp_integration_ids:
            if integration_id in self.servers:
                server = self.servers[integration_id]
                if server.enabled:
                    # Filter by enabled tools only
                    tools.extend([tool for tool in server.tools if tool.enabled])
        return tools
    
    def format_tools_for_llm(self, tools: List[MCPTool]) -> List[Dict[str, Any]]:
        """Format tools for LLM function calling (OpenAI format)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in tools
        ]
    
    async def get_server_status(self, server_id: str) -> Dict[str, Any]:
        """Get detailed status of an MCP server"""
        if server_id not in self.servers:
            return {"error": "Server not found"}
        
        server = self.servers[server_id]
        
        # Perform health check
        await self.health_check(server)
        
        return {
            "id": server.id,
            "name": server.name,
            "base_url": server.base_url,
            "enabled": server.enabled,
            "health_status": server.health_status,
            "last_health_check": server.last_health_check.isoformat() if server.last_health_check else None,
            "tools_count": len(server.tools),
            "enabled_tools_count": sum(1 for tool in server.tools if tool.enabled),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "enabled": tool.enabled,
                    "rate_limit": tool.rate_limit
                }
                for tool in server.tools
            ]
        }
    
    async def list_servers(self) -> List[Dict[str, Any]]:
        """List all registered MCP servers"""
        servers = []
        for server_id, server in self.servers.items():
            servers.append(await self.get_server_status(server_id))
        return servers
    
    async def remove_server(self, server_id: str) -> bool:
        """Remove an MCP server"""
        if server_id in self.servers:
            del self.servers[server_id]
            if server_id in self.rate_limits:
                del self.rate_limits[server_id]
            logger.info(f"Removed MCP server: {server_id}")
            return True
        return False
    
    async def update_server_config(self, server_id: str, config: Dict[str, Any]) -> bool:
        """Update MCP server configuration"""
        if server_id not in self.servers:
            return False
            
        server = self.servers[server_id]
        
        # Update allowed fields
        if "enabled" in config:
            server.enabled = config["enabled"]
        if "api_key" in config:
            server.api_key = config["api_key"]
        if "timeout" in config:
            server.timeout = config["timeout"]
        if "max_retries" in config:
            server.max_retries = config["max_retries"]
            
        # Rediscover tools if server was re-enabled or config changed
        if server.enabled:
            tools = await self.discover_tools(server)
            server.tools = tools
            
        logger.info(f"Updated MCP server config: {server_id}")
        return True
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Singleton instance
mcp_service = MCPIntegrationService()

# Default MCP servers for GT 2.0 (can be configured via admin)
DEFAULT_MCP_SERVERS = [
    {
        "id": "gt2_core_tools",
        "name": "GT 2.0 Core Tools",
        "base_url": "http://localhost:8003",  # Internal tools server
        "tools_endpoint": "/mcp/tools",
        "health_check_endpoint": "/mcp/health"
    },
    {
        "id": "web_search",
        "name": "Web Search Tools",
        "base_url": "http://localhost:8004",
        "api_key": None  # Configured via admin
    }
]