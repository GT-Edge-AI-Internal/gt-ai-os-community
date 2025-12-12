"""
Agent orchestration API endpoints

Provides endpoints for:
- Individual agent execution by agent ID
- Agent execution status tracking
- workflows orchestration
- Capability-based authentication for all operations
"""

from fastapi import APIRouter, HTTPException, Depends, Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import uuid
import asyncio

from app.core.security import capability_validator, CapabilityToken
from app.api.auth import verify_capability

router = APIRouter()
logger = logging.getLogger(__name__)


class AgentExecutionRequest(BaseModel):
    """Agent execution request for specific agent"""
    input_data: Dict[str, Any] = Field(..., description="Input data for the agent")
    parameters: Optional[Dict[str, Any]] = Field(default={}, description="Execution parameters")
    timeout_seconds: Optional[int] = Field(default=300, description="Execution timeout")
    priority: Optional[int] = Field(default=0, description="Execution priority")
    

class AgentExecutionResponse(BaseModel):
    """Agent execution response"""
    execution_id: str = Field(..., description="Unique execution identifier")
    agent_id: str = Field(..., description="Agent identifier")
    status: str = Field(..., description="Execution status")
    created_at: datetime = Field(..., description="Creation timestamp")
    

class AgentExecutionStatus(BaseModel):
    """Agent execution status"""
    execution_id: str = Field(..., description="Execution identifier")
    agent_id: str = Field(..., description="Agent identifier")
    status: str = Field(..., description="Current status")
    progress: Optional[float] = Field(default=None, description="Execution progress (0-100)")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Execution result if completed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")


# Global execution tracking
_active_executions: Dict[str, Dict[str, Any]] = {}


class AgentRequest(BaseModel):
    """Legacy agent execution request for backward compatibility"""
    agent_type: str = Field(..., description="Type of agent to execute")
    task: str = Field(..., description="Task for the agent")
    context: Dict[str, Any] = Field(default={}, description="Additional context")


@router.post("/execute")
async def execute_agent(
    request: AgentRequest,
    token: CapabilityToken = Depends(verify_capability)
) -> Dict[str, Any]:
    """Execute an workflows"""
    
    try:
        from app.services.agent_orchestrator import AgentOrchestrator
        
        # Initialize orchestrator
        orchestrator = AgentOrchestrator()
        
        # Create workflow based on request
        workflow_config = {
            "type": request.workflow_type or "sequential",
            "agents": request.agents,
            "input_data": request.input_data,
            "configuration": request.configuration or {}
        }
        
        # Generate unique workflow ID
        import uuid
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
        
        # Create and register workflow
        workflow = await orchestrator.create_workflow(workflow_id, workflow_config)
        
        # Execute the workflow
        result = await orchestrator.execute_workflow(
            workflow_id=workflow_id,
            input_data=request.input_data,
            capability_token=token.token
        )

        # codeql[py/stack-trace-exposure] returns workflow result dict, not error details
        return {
            "success": True,
            "workflow_id": workflow_id,
            "result": result,
            "execution_time": result.get("execution_time", 0)
        }
        
    except ValueError as e:
        logger.warning(f"Invalid agent request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Agent execution failed")


@router.post("/{agent_id}/execute", response_model=AgentExecutionResponse)
async def execute_agent_by_id(
    agent_id: str = Path(..., description="Agent identifier"),
    request: AgentExecutionRequest = ...,
    token: CapabilityToken = Depends(verify_capability)
) -> AgentExecutionResponse:
    """Execute a specific agent by ID"""
    
    try:
        # Generate unique execution ID
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        
        # Create execution record
        execution_data = {
            "execution_id": execution_id,
            "agent_id": agent_id,
            "status": "queued",
            "input_data": request.input_data,
            "parameters": request.parameters or {},
            "timeout_seconds": request.timeout_seconds,
            "priority": request.priority,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "token": token.token
        }
        
        # Store execution
        _active_executions[execution_id] = execution_data
        
        # Start async execution
        asyncio.create_task(_execute_agent_async(execution_id, agent_id, request, token))
        
        logger.info(f"Started agent execution {execution_id} for agent {agent_id}")
        
        return AgentExecutionResponse(
            execution_id=execution_id,
            agent_id=agent_id,
            status="queued",
            created_at=execution_data["created_at"]
        )
        
    except Exception as e:
        logger.error(f"Failed to start agent execution: {e}")
        raise HTTPException(status_code=500, detail="Failed to start agent execution")


@router.get("/executions/{execution_id}", response_model=AgentExecutionStatus)
async def get_execution_status(
    execution_id: str = Path(..., description="Execution identifier"),
    token: CapabilityToken = Depends(verify_capability)
) -> AgentExecutionStatus:
    """Get agent execution status"""
    
    if execution_id not in _active_executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    execution = _active_executions[execution_id]
    
    return AgentExecutionStatus(
        execution_id=execution_id,
        agent_id=execution["agent_id"],
        status=execution["status"],
        progress=execution.get("progress"),
        result=execution.get("result"),
        error=execution.get("error"),
        created_at=execution["created_at"],
        updated_at=execution["updated_at"],
        completed_at=execution.get("completed_at")
    )


async def _execute_agent_async(execution_id: str, agent_id: str, request: AgentExecutionRequest, token: CapabilityToken):
    """Execute agent asynchronously"""
    try:
        # Update status to running
        _active_executions[execution_id].update({
            "status": "running",
            "updated_at": datetime.utcnow(),
            "progress": 0.0
        })
        
        # Simulate agent execution - replace with real agent orchestrator
        await asyncio.sleep(0.5)  # Initial setup
        _active_executions[execution_id]["progress"] = 25.0
        
        await asyncio.sleep(1.0)  # Processing
        _active_executions[execution_id]["progress"] = 50.0
        
        await asyncio.sleep(1.0)  # Generating result
        _active_executions[execution_id]["progress"] = 75.0
        
        # Simulate successful completion
        result = {
            "agent_id": agent_id,
            "output": f"Agent {agent_id} completed successfully",
            "processed_data": request.input_data,
            "execution_time_seconds": 2.5,
            "tokens_used": 150,
            "cost": 0.002
        }
        
        # Update to completed
        _active_executions[execution_id].update({
            "status": "completed",
            "progress": 100.0,
            "result": result,
            "updated_at": datetime.utcnow(),
            "completed_at": datetime.utcnow()
        })
        
        logger.info(f"Agent execution {execution_id} completed successfully")
        
    except asyncio.TimeoutError:
        _active_executions[execution_id].update({
            "status": "timeout",
            "error": "Execution timeout",
            "updated_at": datetime.utcnow(),
            "completed_at": datetime.utcnow()
        })
        logger.error(f"Agent execution {execution_id} timed out")
        
    except Exception as e:
        _active_executions[execution_id].update({
            "status": "failed",
            "error": str(e),
            "updated_at": datetime.utcnow(),
            "completed_at": datetime.utcnow()
        })
        logger.error(f"Agent execution {execution_id} failed: {e}")


@router.get("/")
async def list_available_agents(
    token: CapabilityToken = Depends(verify_capability)
) -> Dict[str, Any]:
    """List available agents for execution"""
    
    # Return available agents - replace with real agent registry
    available_agents = {
        "coding_assistant": {
            "id": "coding_assistant",
            "name": "Coding Agent",
            "description": "AI agent specialized in code generation and review",
            "capabilities": ["code_generation", "code_review", "debugging"],
            "status": "available"
        },
        "research_agent": {
            "id": "research_agent", 
            "name": "Research Agent",
            "description": "AI agent for information gathering and analysis",
            "capabilities": ["web_search", "document_analysis", "summarization"],
            "status": "available"
        },
        "data_analyst": {
            "id": "data_analyst",
            "name": "Data Analyst",
            "description": "AI agent for data analysis and visualization",
            "capabilities": ["data_processing", "visualization", "statistical_analysis"],
            "status": "available"
        }
    }
    
    return {
        "agents": available_agents,
        "total_count": len(available_agents),
        "available_count": len([a for a in available_agents.values() if a["status"] == "available"])
    }