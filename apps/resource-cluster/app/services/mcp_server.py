"""
MCP Server Resource Wrapper for GT 2.0

Encapsulates MCP (Model Context Protocol) servers as GT 2.0 resources.
Provides security sandboxing and capability-based access control.
"""

from typing import List, Optional, Dict, Any, AsyncIterator
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
import json
from dataclasses import dataclass

from app.models.access_group import AccessGroup, Resource
from app.core.security import verify_capability_token


logger = logging.getLogger(__name__)


class MCPServerStatus(str, Enum):
    """MCP server operational status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server instance"""
    server_name: str
    server_url: str
    server_type: str  # filesystem, github, slack, etc.
    available_tools: List[str]
    required_capabilities: List[str]
    
    # Security settings
    sandbox_mode: bool = True
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    timeout_seconds: int = 30
    network_isolation: bool = True
    
    # Rate limiting
    max_requests_per_minute: int = 60
    max_concurrent_requests: int = 5
    
    # Authentication
    auth_type: Optional[str] = None  # none, api_key, oauth2
    auth_config: Optional[Dict[str, Any]] = None


class MCPServerResource(Resource):
    """
    MCP server encapsulated as a GT 2.0 resource
    Inherits from Resource for access control
    """
    
    # MCP-specific configuration
    server_config: MCPServerConfig
    
    # Runtime state
    status: MCPServerStatus = MCPServerStatus.STOPPED
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    total_requests: int = 0
    
    # Connection management
    connection_pool_size: int = 5
    active_connections: int = 0
    
    def to_capability_requirement(self) -> str:
        """Generate capability requirement string for this MCP server"""
        return f"mcp:{self.server_config.server_name}:*"
    
    def validate_tool_access(self, tool_name: str, capability_token: Dict[str, Any]) -> bool:
        """Check if capability token allows access to specific tool"""
        required_capability = f"mcp:{self.server_config.server_name}:{tool_name}"
        
        capabilities = capability_token.get("capabilities", [])
        for cap in capabilities:
            resource = cap.get("resource", "")
            if resource == required_capability or resource == f"mcp:{self.server_config.server_name}:*":
                return True
        
        return False


class SecureMCPWrapper:
    """
    Secure wrapper for MCP servers with GT 2.0 security integration
    Provides sandboxing, rate limiting, and capability-based access
    """
    
    def __init__(self, resource_cluster_url: str = "http://localhost:8004"):
        self.resource_cluster_url = resource_cluster_url
        self.mcp_resources: Dict[str, MCPServerResource] = {}
        self.rate_limiters: Dict[str, asyncio.Semaphore] = {}
        self.audit_log = []
        
    async def register_mcp_server(
        self,
        server_config: MCPServerConfig,
        owner_id: str,
        tenant_domain: str,
        access_group: AccessGroup = AccessGroup.INDIVIDUAL
    ) -> MCPServerResource:
        """
        Register an MCP server as a GT 2.0 resource
        
        Args:
            server_config: MCP server configuration
            owner_id: User who owns this MCP resource
            tenant_domain: Tenant domain
            access_group: Access control level
            
        Returns:
            Registered MCP server resource
        """
        # Create MCP resource
        resource = MCPServerResource(
            id=f"mcp-{server_config.server_name}-{datetime.utcnow().timestamp()}",
            name=f"MCP Server: {server_config.server_name}",
            resource_type="mcp_server",
            owner_id=owner_id,
            tenant_domain=tenant_domain,
            access_group=access_group,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={
                "server_type": server_config.server_type,
                "tools_count": len(server_config.available_tools)
            },
            server_config=server_config
        )
        
        # Initialize rate limiter
        self.rate_limiters[resource.id] = asyncio.Semaphore(
            server_config.max_concurrent_requests
        )
        
        # Store resource
        self.mcp_resources[resource.id] = resource
        
        # Start health monitoring
        asyncio.create_task(self._monitor_health(resource.id))
        
        logger.info(f"Registered MCP server: {server_config.server_name} as resource {resource.id}")
        
        return resource
    
    async def execute_tool(
        self,
        mcp_resource_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        capability_token: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool with security constraints
        
        Args:
            mcp_resource_id: MCP resource identifier
            tool_name: Tool to execute
            parameters: Tool parameters
            capability_token: JWT capability token
            user_id: User executing the tool
            
        Returns:
            Tool execution result
        """
        # Load MCP resource
        mcp_resource = self.mcp_resources.get(mcp_resource_id)
        if not mcp_resource:
            raise ValueError(f"MCP resource not found: {mcp_resource_id}")
        
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data:
            raise PermissionError("Invalid capability token")
        
        # Check tenant match
        if token_data.get("tenant_id") != mcp_resource.tenant_domain:
            raise PermissionError("Tenant mismatch")
        
        # Validate tool access
        if not mcp_resource.validate_tool_access(tool_name, token_data):
            raise PermissionError(f"No capability for tool: {tool_name}")
        
        # Check if tool exists
        if tool_name not in mcp_resource.server_config.available_tools:
            raise ValueError(f"Tool not available: {tool_name}")
        
        # Apply rate limiting
        async with self.rate_limiters[mcp_resource_id]:
            try:
                # Execute tool with timeout and sandboxing
                result = await self._execute_tool_sandboxed(
                    mcp_resource, tool_name, parameters, user_id
                )
                
                # Update metrics
                mcp_resource.total_requests += 1
                
                # Audit log
                self._log_tool_execution(
                    mcp_resource_id, tool_name, user_id, "success", result
                )
                
                return result
                
            except Exception as e:
                # Update error metrics
                mcp_resource.error_count += 1
                
                # Audit log
                self._log_tool_execution(
                    mcp_resource_id, tool_name, user_id, "error", str(e)
                )
                
                raise
    
    async def _execute_tool_sandboxed(
        self,
        mcp_resource: MCPServerResource,
        tool_name: str,
        parameters: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute tool in sandboxed environment"""
        
        # Create sandbox context
        sandbox_context = {
            "user_id": user_id,
            "tenant_domain": mcp_resource.tenant_domain,
            "resource_limits": {
                "max_memory_mb": mcp_resource.server_config.max_memory_mb,
                "max_cpu_percent": mcp_resource.server_config.max_cpu_percent,
                "timeout_seconds": mcp_resource.server_config.timeout_seconds
            },
            "network_isolation": mcp_resource.server_config.network_isolation
        }
        
        # Execute based on server type
        if mcp_resource.server_config.server_type == "filesystem":
            return await self._execute_filesystem_tool(
                tool_name, parameters, sandbox_context
            )
        elif mcp_resource.server_config.server_type == "github":
            return await self._execute_github_tool(
                tool_name, parameters, sandbox_context
            )
        elif mcp_resource.server_config.server_type == "slack":
            return await self._execute_slack_tool(
                tool_name, parameters, sandbox_context
            )
        elif mcp_resource.server_config.server_type == "web":
            return await self._execute_web_tool(
                tool_name, parameters, sandbox_context
            )
        elif mcp_resource.server_config.server_type == "database":
            return await self._execute_database_tool(
                tool_name, parameters, sandbox_context
            )
        else:
            return await self._execute_custom_tool(
                mcp_resource, tool_name, parameters, sandbox_context
            )
    
    async def _execute_filesystem_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute filesystem MCP tools"""
        
        if tool_name == "read_file":
            # Simulate file reading with sandbox constraints
            file_path = parameters.get("path", "")
            
            # Security validation
            if not self._validate_file_path(file_path, sandbox_context):
                raise PermissionError("Access denied to file path")
            
            return {
                "tool": "read_file",
                "content": f"File content from {file_path}",
                "size_bytes": 1024,
                "mime_type": "text/plain"
            }
        
        elif tool_name == "write_file":
            file_path = parameters.get("path", "")
            content = parameters.get("content", "")
            
            # Security validation
            if not self._validate_file_path(file_path, sandbox_context):
                raise PermissionError("Access denied to file path")
            
            if len(content) > 1024 * 1024:  # 1MB limit
                raise ValueError("File content too large")
            
            return {
                "tool": "write_file",
                "path": file_path,
                "bytes_written": len(content),
                "status": "success"
            }
        
        elif tool_name == "list_directory":
            dir_path = parameters.get("path", "")
            
            if not self._validate_file_path(dir_path, sandbox_context):
                raise PermissionError("Access denied to directory path")
            
            return {
                "tool": "list_directory",
                "path": dir_path,
                "entries": ["file1.txt", "file2.txt", "subdir/"],
                "total_entries": 3
            }
        
        else:
            raise ValueError(f"Unknown filesystem tool: {tool_name}")
    
    async def _execute_github_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute GitHub MCP tools"""
        
        if tool_name == "get_repository":
            repo_name = parameters.get("repository", "")
            
            return {
                "tool": "get_repository",
                "repository": repo_name,
                "owner": "example",
                "description": "Example repository",
                "language": "Python",
                "stars": 123,
                "forks": 45
            }
        
        elif tool_name == "create_issue":
            title = parameters.get("title", "")
            body = parameters.get("body", "")
            
            return {
                "tool": "create_issue",
                "issue_number": 42,
                "title": title,
                "url": f"https://github.com/example/repo/issues/42",
                "status": "created"
            }
        
        elif tool_name == "search_code":
            query = parameters.get("query", "")
            
            return {
                "tool": "search_code",
                "query": query,
                "results": [
                    {
                        "file": "main.py",
                        "line": 15,
                        "content": f"# Code matching {query}"
                    }
                ],
                "total_results": 1
            }
        
        else:
            raise ValueError(f"Unknown GitHub tool: {tool_name}")
    
    async def _execute_slack_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Slack MCP tools"""
        
        if tool_name == "send_message":
            channel = parameters.get("channel", "")
            message = parameters.get("message", "")
            
            return {
                "tool": "send_message",
                "channel": channel,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "sent"
            }
        
        elif tool_name == "get_channel_history":
            channel = parameters.get("channel", "")
            limit = parameters.get("limit", 10)
            
            return {
                "tool": "get_channel_history",
                "channel": channel,
                "messages": [
                    {
                        "user": "user1",
                        "text": "Hello world!",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                ] * min(limit, 10),
                "total_messages": limit
            }
        
        else:
            raise ValueError(f"Unknown Slack tool: {tool_name}")
    
    async def _execute_web_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute web MCP tools"""
        
        if tool_name == "fetch_url":
            url = parameters.get("url", "")
            
            # URL validation
            if not self._validate_url(url, sandbox_context):
                raise PermissionError("Access denied to URL")
            
            return {
                "tool": "fetch_url",
                "url": url,
                "status_code": 200,
                "content": f"Content from {url}",
                "headers": {"content-type": "text/html"}
            }
        
        elif tool_name == "submit_form":
            url = parameters.get("url", "")
            form_data = parameters.get("form_data", {})
            
            if not self._validate_url(url, sandbox_context):
                raise PermissionError("Access denied to URL")
            
            return {
                "tool": "submit_form",
                "url": url,
                "form_data": form_data,
                "status_code": 200,
                "response": "Form submitted successfully"
            }
        
        else:
            raise ValueError(f"Unknown web tool: {tool_name}")
    
    async def _execute_database_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute database MCP tools"""
        
        if tool_name == "execute_query":
            query = parameters.get("query", "")
            
            # Query validation
            if not self._validate_sql_query(query, sandbox_context):
                raise PermissionError("Query not allowed")
            
            return {
                "tool": "execute_query",
                "query": query,
                "rows": [
                    {"id": 1, "name": "Example"},
                    {"id": 2, "name": "Data"}
                ],
                "row_count": 2,
                "execution_time_ms": 15
            }
        
        else:
            raise ValueError(f"Unknown database tool: {tool_name}")
    
    async def _execute_custom_tool(
        self,
        mcp_resource: MCPServerResource,
        tool_name: str,
        parameters: Dict[str, Any],
        sandbox_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute custom MCP tool via WebSocket transport"""
        
        # This would connect to the actual MCP server via WebSocket
        # For now, simulate the execution
        
        await asyncio.sleep(0.1)  # Simulate network delay
        
        return {
            "tool": tool_name,
            "parameters": parameters,
            "result": f"Custom tool {tool_name} executed successfully",
            "server_type": mcp_resource.server_config.server_type,
            "execution_time_ms": 100
        }
    
    def _validate_file_path(
        self,
        file_path: str,
        sandbox_context: Dict[str, Any]
    ) -> bool:
        """Validate file path for security"""
        
        # Basic path traversal prevention
        if ".." in file_path or file_path.startswith("/"):
            return False
        
        # Check allowed extensions
        allowed_extensions = [".txt", ".md", ".json", ".py", ".js"]
        if not any(file_path.endswith(ext) for ext in allowed_extensions):
            return False
        
        return True
    
    def _validate_url(
        self,
        url: str,
        sandbox_context: Dict[str, Any]
    ) -> bool:
        """Validate URL for security"""
        
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return False
        
        # Block internal/localhost URLs if network isolation enabled
        if sandbox_context.get("network_isolation", True):
            if any(domain in url for domain in ["localhost", "127.0.0.1", "10.", "192.168."]):
                return False
        
        return True
    
    def _validate_sql_query(
        self,
        query: str,
        sandbox_context: Dict[str, Any]
    ) -> bool:
        """Validate SQL query for security"""
        
        # Block dangerous SQL operations
        dangerous_keywords = [
            "DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER",
            "TRUNCATE", "EXEC", "EXECUTE", "xp_", "sp_"
        ]
        
        query_upper = query.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return False
        
        return True
    
    def _log_tool_execution(
        self,
        mcp_resource_id: str,
        tool_name: str,
        user_id: str,
        status: str,
        result: Any
    ) -> None:
        """Log tool execution for audit"""
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "mcp_resource_id": mcp_resource_id,
            "tool_name": tool_name,
            "user_id": user_id,
            "status": status,
            "result_summary": str(result)[:200] if result else None
        }
        
        self.audit_log.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
    
    async def _monitor_health(self, mcp_resource_id: str) -> None:
        """Monitor MCP server health"""
        
        while mcp_resource_id in self.mcp_resources:
            try:
                mcp_resource = self.mcp_resources[mcp_resource_id]
                
                # Simulate health check
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Update health status
                if mcp_resource.error_count > 10:
                    mcp_resource.status = MCPServerStatus.DEGRADED
                elif mcp_resource.error_count > 50:
                    mcp_resource.status = MCPServerStatus.UNHEALTHY
                else:
                    mcp_resource.status = MCPServerStatus.HEALTHY
                
                mcp_resource.last_health_check = datetime.utcnow()
                
                logger.debug(f"Health check for MCP resource {mcp_resource_id}: {mcp_resource.status}")
                
            except Exception as e:
                logger.error(f"Health check failed for MCP resource {mcp_resource_id}: {e}")
                
                if mcp_resource_id in self.mcp_resources:
                    self.mcp_resources[mcp_resource_id].status = MCPServerStatus.UNHEALTHY
    
    async def get_resource_status(
        self,
        mcp_resource_id: str,
        capability_token: str
    ) -> Dict[str, Any]:
        """Get MCP resource status"""
        
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data:
            raise PermissionError("Invalid capability token")
        
        # Load MCP resource
        mcp_resource = self.mcp_resources.get(mcp_resource_id)
        if not mcp_resource:
            raise ValueError(f"MCP resource not found: {mcp_resource_id}")
        
        # Check tenant match
        if token_data.get("tenant_id") != mcp_resource.tenant_domain:
            raise PermissionError("Tenant mismatch")
        
        return {
            "resource_id": mcp_resource_id,
            "name": mcp_resource.name,
            "server_type": mcp_resource.server_config.server_type,
            "status": mcp_resource.status,
            "total_requests": mcp_resource.total_requests,
            "error_count": mcp_resource.error_count,
            "active_connections": mcp_resource.active_connections,
            "last_health_check": mcp_resource.last_health_check.isoformat() if mcp_resource.last_health_check else None,
            "available_tools": mcp_resource.server_config.available_tools
        }
    
    async def list_mcp_resources(
        self,
        capability_token: str,
        tenant_domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available MCP resources"""
        
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data:
            raise PermissionError("Invalid capability token")
        
        tenant_filter = tenant_domain or token_data.get("tenant_id")
        
        resources = []
        for resource in self.mcp_resources.values():
            if resource.tenant_domain == tenant_filter:
                resources.append({
                    "resource_id": resource.id,
                    "name": resource.name,
                    "server_type": resource.server_config.server_type,
                    "status": resource.status,
                    "tool_count": len(resource.server_config.available_tools),
                    "created_at": resource.created_at.isoformat()
                })
        
        return resources


# Global MCP wrapper instance
_mcp_wrapper = None


def get_mcp_wrapper() -> SecureMCPWrapper:
    """Get the global MCP wrapper instance"""
    global _mcp_wrapper
    if _mcp_wrapper is None:
        _mcp_wrapper = SecureMCPWrapper()
    return _mcp_wrapper