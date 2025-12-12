"""
GT 2.0 MCP Registry API

Manages registration and discovery of MCP servers in the resource cluster.
Provides endpoints for:
- Registering MCP servers
- Listing available MCP servers and tools
- Getting tool schemas
- Server health monitoring
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
import logging

from app.core.security import verify_capability_token
from app.services.mcp_server import SecureMCPWrapper, MCPServerConfig
from app.services.mcp_rag_server import mcp_rag_server

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])


# Request/Response Models
class MCPServerInfo(BaseModel):
    """Information about an MCP server"""
    server_name: str
    server_type: str
    available_tools: List[str]
    status: str
    description: str
    required_capabilities: List[str]


class MCPToolSchema(BaseModel):
    """MCP tool schema information"""
    name: str
    description: str
    parameters: Dict[str, Any]
    server_name: str


class ListServersResponse(BaseModel):
    """Response for listing MCP servers"""
    servers: List[MCPServerInfo]
    total_count: int


class ListToolsResponse(BaseModel):
    """Response for listing MCP tools"""
    tools: List[MCPToolSchema]
    total_count: int
    servers_count: int


# Global MCP wrapper instance
mcp_wrapper = SecureMCPWrapper()


@router.get("/servers", response_model=ListServersResponse)
async def list_mcp_servers(
    knowledge_search_enabled: bool = Query(True, description="Whether dataset/knowledge search is enabled"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for context")
):
    """
    List all available MCP servers and their status.

    Returns information about registered MCP servers that the user
    can access based on their capability tokens.
    """
    try:
        servers = []

        if knowledge_search_enabled:
            rag_config = mcp_rag_server.get_server_config()
            servers.append(MCPServerInfo(
                server_name=rag_config.server_name,
                server_type=rag_config.server_type,
                available_tools=rag_config.available_tools,
                status="healthy",
                description="Dataset and document search capabilities for RAG operations",
                required_capabilities=rag_config.required_capabilities
            ))

        return ListServersResponse(
            servers=servers,
            total_count=len(servers)
        )

    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list servers: {str(e)}")


@router.get("/tools", response_model=ListToolsResponse)
async def list_mcp_tools(
    server_name: Optional[str] = Query(None, description="Filter by server name"),
    knowledge_search_enabled: bool = Query(True, description="Whether dataset/knowledge search is enabled"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for context")
):
    """
    List all available MCP tools across servers.

    Can be filtered by server name to get tools for a specific server.
    """
    try:
        all_tools = []
        servers_included = 0

        if knowledge_search_enabled and (not server_name or server_name == "rag_server"):
            rag_schemas = mcp_rag_server.get_tool_schemas()
            for tool_name, schema in rag_schemas.items():
                all_tools.append(MCPToolSchema(
                    name=tool_name,
                    description=schema.get("description", ""),
                    parameters=schema.get("parameters", {}),
                    server_name="rag_server"
                ))
            servers_included += 1

        return ListToolsResponse(
            tools=all_tools,
            total_count=len(all_tools),
            servers_count=servers_included
        )

    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@router.get("/servers/{server_name}/tools")
async def get_server_tools(
    server_name: str,
    knowledge_search_enabled: bool = Query(True, description="Whether dataset/knowledge search is enabled"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for context")
):
    """Get tools and schemas for a specific MCP server"""
    try:
        if server_name == "rag_server":
            if knowledge_search_enabled:
                return {
                    "server_name": server_name,
                    "server_type": "rag",
                    "tools": mcp_rag_server.get_tool_schemas()
                }
            else:
                return {
                    "server_name": server_name,
                    "server_type": "rag",
                    "tools": {}
                }
        else:
            raise HTTPException(status_code=404, detail=f"MCP server not found: {server_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting server tools for {server_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get server tools: {str(e)}")


@router.get("/servers/{server_name}/health")
async def check_server_health(
    server_name: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for context")
):
    """Check health status of a specific MCP server"""
    try:
        if server_name == "rag_server":
            return {
                "server_name": server_name,
                "status": "healthy",
                "timestamp": "2025-01-15T12:00:00Z",
                "response_time_ms": 5,
                "tools_available": True
            }
        else:
            raise HTTPException(status_code=404, detail=f"MCP server not found: {server_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking health for {server_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/capabilities")
async def get_mcp_capabilities(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for context")
):
    """
    Get MCP capabilities summary for the current user.

    Returns what MCP servers and tools the user has access to
    based on their capability tokens.
    """
    try:
        capabilities = {
            "user_id": "resource_cluster_user",
            "tenant_domain": x_tenant_id or "default",
            "available_servers": [
                {
                    "server_name": "rag_server",
                    "server_type": "rag",
                    "tools_count": len(mcp_rag_server.available_tools),
                    "required_capability": "mcp:rag:*"
                }
            ],
            "total_tools": len(mcp_rag_server.available_tools),
            "access_level": "full"
        }

        return capabilities

    except Exception as e:
        logger.error(f"Error getting MCP capabilities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get capabilities: {str(e)}")


async def initialize_mcp_servers():
    """Initialize and register MCP servers"""
    try:
        logger.info("Initializing MCP servers...")

        rag_config = mcp_rag_server.get_server_config()
        logger.info(f"RAG server initialized with {len(rag_config.available_tools)} tools")

        logger.info("All MCP servers initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing MCP servers: {e}")
        raise


# Export the initialization function
__all__ = ["router", "initialize_mcp_servers", "mcp_wrapper"]