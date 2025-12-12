"""
GT 2.0 MCP Tool Executor

Handles execution of MCP tools from agents. This is the main endpoint
that receives tool calls from the tenant backend and routes them to
the appropriate MCP servers with proper authentication and rate limiting.
"""

from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
import logging
import asyncio
from datetime import datetime

# Removed: from app.core.security import verify_capability_token
from app.services.mcp_rag_server import mcp_rag_server

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp_execution"])


# Request/Response Models
class MCPToolCall(BaseModel):
    """MCP tool call request"""
    tool_name: str = Field(..., description="Name of the tool to execute")
    server_name: str = Field(..., description="MCP server that provides the tool")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")


class MCPToolResult(BaseModel):
    """MCP tool execution result"""
    success: bool
    tool_name: str
    server_name: str
    execution_time_ms: float
    result: Dict[str, Any]
    error: Optional[str] = None
    timestamp: str


class MCPBatchRequest(BaseModel):
    """Request for executing multiple MCP tools"""
    tool_calls: List[MCPToolCall] = Field(..., min_items=1, max_items=10)


class MCPBatchResponse(BaseModel):
    """Response for batch tool execution"""
    results: List[MCPToolResult]
    success_count: int
    error_count: int
    total_execution_time_ms: float


# Rate limiting (simple in-memory counter)
_rate_limits = {}


def check_rate_limit(user_id: str, server_name: str) -> bool:
    """Simple rate limiting check"""
    # TODO: Implement proper rate limiting with Redis or similar
    key = f"{user_id}:{server_name}"
    current_time = datetime.now().timestamp()

    if key not in _rate_limits:
        _rate_limits[key] = []

    # Remove old entries (older than 1 minute)
    _rate_limits[key] = [t for t in _rate_limits[key] if current_time - t < 60]

    # Check if under limit (60 requests per minute)
    if len(_rate_limits[key]) >= 60:
        return False

    # Add current request
    _rate_limits[key].append(current_time)
    return True


@router.post("/tool", response_model=MCPToolResult)
async def execute_mcp_tool(
    request: MCPToolCall,
    x_tenant_domain: str = Header(..., description="Tenant domain for isolation"),
    x_user_id: str = Header(..., description="User ID for authorization"),
    agent_context: Optional[Dict[str, Any]] = None
):
    """
    Execute a single MCP tool.

    This is the main endpoint that agents use to execute MCP tools.
    It handles rate limiting and routing to the appropriate MCP server.
    User authentication is handled by the tenant backend before reaching here.
    """
    start_time = datetime.now()

    try:
        # Validate required headers
        if not x_user_id or not x_tenant_domain:
            raise HTTPException(
                status_code=400,
                detail="Missing required authentication headers"
            )

        # Check rate limiting
        if not check_rate_limit(x_user_id, request.server_name):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for MCP server"
            )

        # Route to appropriate MCP server (no capability token needed)
        if request.server_name == "rag_server":
            result = await mcp_rag_server.handle_tool_call(
                tool_name=request.tool_name,
                parameters=request.parameters,
                tenant_domain=x_tenant_domain,
                user_id=x_user_id,
                agent_context=agent_context
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown MCP server: {request.server_name}"
            )

        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000

        # Check if tool execution was successful
        success = "error" not in result
        error_message = result.get("error") if not success else None

        logger.info(f"🔧 MCP Tool executed: {request.tool_name} ({execution_time:.2f}ms) - {'✅' if success else '❌'}")

        return MCPToolResult(
            success=success,
            tool_name=request.tool_name,
            server_name=request.server_name,
            execution_time_ms=execution_time,
            result=result,
            error=error_message,
            timestamp=end_time.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing MCP tool {request.tool_name}: {e}")

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000

        return MCPToolResult(
            success=False,
            tool_name=request.tool_name,
            server_name=request.server_name,
            execution_time_ms=execution_time,
            result={},
            error=f"Tool execution failed: {str(e)}",
            timestamp=end_time.isoformat()
        )


class MCPExecuteRequest(BaseModel):
    """Direct execution request format used by RAG orchestrator"""
    server_id: str = Field(..., description="Server ID (rag_server)")
    tool_name: str = Field(..., description="Tool name to execute")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")
    tenant_domain: str = Field(..., description="Tenant domain")
    user_id: str = Field(..., description="User ID")
    agent_context: Optional[Dict[str, Any]] = Field(None, description="Agent context with dataset info")


@router.post("/execute")
async def execute_mcp_direct(request: MCPExecuteRequest):
    """
    Direct execution endpoint used by RAG orchestrator.
    Simplified without capability tokens - uses user context for authorization.
    """
    logger.info(f"🔧 Direct MCP execution request: server={request.server_id}, tool={request.tool_name}, tenant={request.tenant_domain}, user={request.user_id}")
    logger.debug(f"📝 Tool parameters: {request.parameters}")

    try:
        # Map server_id to server_name
        server_mapping = {
            "rag_server": "rag_server"
        }

        server_name = server_mapping.get(request.server_id)
        if not server_name:
            logger.error(f"❌ Unknown server_id: {request.server_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown server_id: {request.server_id}"
            )

        logger.info(f"🎯 Mapped server_id '{request.server_id}' → server_name '{server_name}'")

        # Create simplified tool call request
        tool_call = MCPToolCall(
            tool_name=request.tool_name,
            server_name=server_name,
            parameters=request.parameters
        )

        # Execute the tool with agent context
        result = await execute_mcp_tool(
            request=tool_call,
            x_tenant_domain=request.tenant_domain,
            x_user_id=request.user_id,
            agent_context=request.agent_context
        )

        # Return result in format expected by RAG orchestrator
        if result.success:
            return result.result
        else:
            return {
                "success": False,
                "error": result.error
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Direct MCP execution failed: {e}")
        return {
            "success": False,
            "error": "MCP execution failed"
        }


@router.post("/batch", response_model=MCPBatchResponse)
async def execute_mcp_batch(
    request: MCPBatchRequest,
    x_tenant_domain: str = Header(..., description="Tenant domain for isolation"),
    x_user_id: str = Header(..., description="User ID for authorization")
):
    """
    Execute multiple MCP tools in batch.

    Useful for agents that need to call multiple tools simultaneously
    for more efficient execution.
    """
    batch_start_time = datetime.now()

    try:
        # Validate required headers
        if not x_user_id or not x_tenant_domain:
            raise HTTPException(
                status_code=400,
                detail="Missing required authentication headers"
            )

        # Execute all tool calls concurrently
        tasks = []
        for tool_call in request.tool_calls:
            # Create individual tool call request
            individual_request = MCPToolCall(
                tool_name=tool_call.tool_name,
                server_name=tool_call.server_name,
                parameters=tool_call.parameters
            )

            # Create task for concurrent execution
            task = execute_mcp_tool(
                request=individual_request,
                x_tenant_domain=x_tenant_domain,
                x_user_id=x_user_id
            )
            tasks.append(task)

        # Execute all tools concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        tool_results = []
        success_count = 0
        error_count = 0

        for result in results:
            if isinstance(result, Exception):
                # Handle exceptions from individual tool calls
                tool_results.append(MCPToolResult(
                    success=False,
                    tool_name="unknown",
                    server_name="unknown",
                    execution_time_ms=0,
                    result={},
                    error=str(result),
                    timestamp=datetime.now().isoformat()
                ))
                error_count += 1
            else:
                tool_results.append(result)
                if result.success:
                    success_count += 1
                else:
                    error_count += 1

        # Calculate total execution time
        batch_end_time = datetime.now()
        total_execution_time = (batch_end_time - batch_start_time).total_seconds() * 1000

        return MCPBatchResponse(
            results=tool_results,
            success_count=success_count,
            error_count=error_count,
            total_execution_time_ms=total_execution_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing MCP batch: {e}")
        raise HTTPException(status_code=500, detail=f"Batch execution failed: {str(e)}")


@router.post("/rag/{tool_name}")
async def execute_rag_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    x_tenant_domain: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    """
    Direct endpoint for executing RAG tools.

    Convenience endpoint for common RAG operations without
    needing to specify server name.
    """
    # Create standard tool call request
    tool_call = MCPToolCall(
        tool_name=tool_name,
        server_name="rag_server",
        parameters=parameters
    )

    return await execute_mcp_tool(
        request=tool_call,
        x_tenant_domain=x_tenant_domain,
        x_user_id=x_user_id
    )


@router.post("/conversation/{tool_name}")
async def execute_conversation_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    x_tenant_domain: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    """
    Direct endpoint for executing conversation search tools.

    Convenience endpoint for common conversation search operations
    without needing to specify server name.
    """
    # Create standard tool call request
    tool_call = MCPToolCall(
        tool_name=tool_name,
        server_name="conversation_server",
        parameters=parameters
    )

    return await execute_mcp_tool(
        request=tool_call,
        x_tenant_domain=x_tenant_domain,
        x_user_id=x_user_id
    )


@router.get("/status")
async def get_executor_status(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for context")
):
    """
    Get status of the MCP executor and connected servers.

    Returns health information and statistics about MCP tool execution.
    """
    try:
        # Calculate basic statistics
        total_requests = sum(len(requests) for requests in _rate_limits.values())
        active_users = len(_rate_limits)

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_requests_last_hour": total_requests,  # Approximate
                "active_users": active_users,
                "available_servers": 2,  # RAG and conversation servers
                "total_tools": len(mcp_rag_server.available_tools) + len(mcp_conversation_server.available_tools)
            },
            "servers": {
                "rag_server": {
                    "status": "healthy",
                    "tools_count": len(mcp_rag_server.available_tools),
                    "tools": mcp_rag_server.available_tools
                },
                "conversation_server": {
                    "status": "healthy",
                    "tools_count": len(mcp_conversation_server.available_tools),
                    "tools": mcp_conversation_server.available_tools
                }
            }
        }

    except Exception as e:
        logger.error(f"Error getting executor status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "mcp_executor"
    }