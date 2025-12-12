from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.workflow_service import WorkflowService, WorkflowValidationError
from app.models.workflow import WorkflowStatus, TriggerType, InteractionMode


router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


# Request/Response models
class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    definition: Dict[str, Any] = Field(..., description="Workflow nodes and edges")
    triggers: Optional[List[Dict[str, Any]]] = Field(default=[])
    interaction_modes: Optional[List[str]] = Field(default=["button"])
    api_key_ids: Optional[List[str]] = Field(default=[])
    webhook_ids: Optional[List[str]] = Field(default=[])
    dataset_ids: Optional[List[str]] = Field(default=[])
    integration_ids: Optional[List[str]] = Field(default=[])
    config: Optional[Dict[str, Any]] = Field(default={})
    timeout_seconds: Optional[int] = Field(default=300, ge=30, le=3600)
    max_retries: Optional[int] = Field(default=3, ge=0, le=10)


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    definition: Optional[Dict[str, Any]] = None
    triggers: Optional[List[Dict[str, Any]]] = None
    interaction_modes: Optional[List[str]] = None
    status: Optional[WorkflowStatus] = None
    config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(None, ge=30, le=3600)
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class WorkflowExecutionRequest(BaseModel):
    input_data: Dict[str, Any] = Field(default={})
    trigger_type: Optional[str] = Field(default="manual")
    interaction_mode: Optional[str] = Field(default="api")


class WorkflowTriggerRequest(BaseModel):
    type: TriggerType
    config: Dict[str, Any] = Field(default={})


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    definition: Dict[str, Any]
    interaction_modes: List[str]
    execution_count: int
    last_executed: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    progress_percentage: int
    current_node_id: Optional[str]
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_details: Optional[str]
    started_at: str
    completed_at: Optional[str]
    duration_ms: Optional[int]
    tokens_used: int
    cost_cents: int
    interaction_mode: str

    class Config:
        from_attributes = True


# Workflow CRUD endpoints
@router.post("/", response_model=WorkflowResponse)
def create_workflow(
    workflow_data: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new workflow - temporary mock implementation"""
    try:
        # TODO: Implement proper PostgreSQL service integration
        # For now, return a mock workflow to avoid database integration issues
        from datetime import datetime
        import uuid
        
        mock_workflow = {
            "id": str(uuid.uuid4()),
            "name": workflow_data.name,
            "description": workflow_data.description or "",
            "status": "draft",
            "definition": workflow_data.definition,
            "interaction_modes": workflow_data.interaction_modes or ["button"],
            "execution_count": 0,
            "last_executed": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        return WorkflowResponse(**mock_workflow)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")


@router.get("/", response_model=List[WorkflowResponse])
def list_workflows(
    status: Optional[WorkflowStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List user's workflows - temporary mock implementation"""
    try:
        # TODO: Implement proper PostgreSQL service integration
        # For now, return empty list to avoid database integration issues
        return []
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get workflow by ID"""
    try:
        service = WorkflowService(db)
        workflow = service.get_workflow(workflow_id, current_user["sub"])
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Convert to dict with proper datetime formatting
        workflow_dict = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status,
            "definition": workflow.definition,
            "interaction_modes": workflow.interaction_modes,
            "execution_count": workflow.execution_count,
            "last_executed": workflow.last_executed.isoformat() if workflow.last_executed else None,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat()
        }
        return WorkflowResponse(**workflow_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow: {str(e)}")


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    updates: WorkflowUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a workflow"""
    try:
        service = WorkflowService(db)
        
        # Filter out None values
        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        
        workflow = service.update_workflow(
            workflow_id=workflow_id,
            user_id=current_user["sub"],
            updates=update_data
        )
        
        # Convert to dict with proper datetime formatting
        workflow_dict = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status,
            "definition": workflow.definition,
            "interaction_modes": workflow.interaction_modes,
            "execution_count": workflow.execution_count,
            "last_executed": workflow.last_executed.isoformat() if workflow.last_executed else None,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat()
        }
        return WorkflowResponse(**workflow_dict)
    
    except WorkflowValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a workflow"""
    try:
        service = WorkflowService(db)
        success = service.delete_workflow(workflow_id, current_user["sub"])
        
        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return {"message": "Workflow deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")


# Workflow execution endpoints
@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    execution_data: WorkflowExecutionRequest,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Execute a workflow"""
    try:
        service = WorkflowService(db)
        execution = await service.execute_workflow(
            workflow_id=workflow_id,
            user_id=current_user["sub"],
            input_data=execution_data.input_data,
            trigger_type=execution_data.trigger_type,
            interaction_mode=execution_data.interaction_mode
        )
        
        return WorkflowExecutionResponse.from_orm(execution)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute workflow: {str(e)}")


@router.get("/{workflow_id}/executions")
async def list_workflow_executions(
    workflow_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List workflow executions"""
    try:
        # Verify workflow ownership first
        service = WorkflowService(db)
        workflow = await service.get_workflow(workflow_id, current_user["sub"])
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Get executions (implementation would query WorkflowExecution table)
        # For now, return empty list
        return []
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list executions: {str(e)}")


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_execution_status(
    execution_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get execution status"""
    try:
        service = WorkflowService(db)
        execution = await service.get_execution_status(execution_id, current_user["sub"])
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        return WorkflowExecutionResponse.from_orm(execution)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get execution: {str(e)}")


# Workflow trigger endpoints
@router.post("/{workflow_id}/triggers")
async def create_workflow_trigger(
    workflow_id: str,
    trigger_data: WorkflowTriggerRequest,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a trigger for a workflow"""
    try:
        service = WorkflowService(db)
        
        # Verify workflow ownership
        workflow = await service.get_workflow(workflow_id, current_user["sub"])
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        trigger = await service.create_workflow_trigger(
            workflow_id=workflow_id,
            user_id=current_user["sub"],
            tenant_id=current_user["tenant_id"],
            trigger_config=trigger_data.dict()
        )
        
        return {"id": trigger.id, "webhook_url": trigger.webhook_url}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create trigger: {str(e)}")


# Chat interface endpoints
@router.post("/{workflow_id}/chat/sessions")
async def create_chat_session(
    workflow_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a chat session for workflow interaction"""
    try:
        service = WorkflowService(db)
        
        # Verify workflow ownership
        workflow = await service.get_workflow(workflow_id, current_user["sub"])
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Check if workflow supports chat mode
        if "chat" not in workflow.interaction_modes:
            raise HTTPException(status_code=400, detail="Workflow does not support chat mode")
        
        session = await service.create_chat_session(
            workflow_id=workflow_id,
            user_id=current_user["sub"],
            tenant_id=current_user["tenant_id"]
        )
        
        return {"session_id": session.id, "expires_at": session.expires_at.isoformat()}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")


@router.post("/{workflow_id}/chat/message")
async def send_chat_message(
    workflow_id: str,
    message_data: ChatMessageRequest,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Send a message to workflow chat"""
    try:
        service = WorkflowService(db)
        
        # Create or get session
        session_id = message_data.session_id
        if not session_id:
            session = await service.create_chat_session(
                workflow_id=workflow_id,
                user_id=current_user["sub"],
                tenant_id=current_user["tenant_id"]
            )
            session_id = session.id
        
        # Add user message
        user_message = await service.add_chat_message(
            session_id=session_id,
            user_id=current_user["sub"],
            role="user",
            content=message_data.message
        )
        
        # Execute workflow with message as input
        execution = await service.execute_workflow(
            workflow_id=workflow_id,
            user_id=current_user["sub"],
            input_data={"message": message_data.message},
            trigger_type="chat",
            interaction_mode="chat"
        )
        
        # Add agent response (in real implementation, this would come from workflow execution)
        assistant_response = execution.output_data.get('result', 'Workflow response')
        
        assistant_message = await service.add_chat_message(
            session_id=session_id,
            user_id=current_user["sub"],
            role="agent",
            content=assistant_response,
            execution_id=execution.id
        )
        
        return {
            "session_id": session_id,
            "user_message": {
                "id": user_message.id,
                "content": user_message.content,
                "timestamp": user_message.created_at.isoformat()
            },
            "assistant_message": {
                "id": assistant_message.id,
                "content": assistant_message.content,
                "timestamp": assistant_message.created_at.isoformat()
            },
            "execution": {
                "id": execution.id,
                "status": execution.status
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")


# Workflow interface generation endpoints
@router.get("/{workflow_id}/interface/{mode}")
async def get_workflow_interface(
    workflow_id: str,
    mode: InteractionMode,
    db = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get workflow interface configuration for specified mode"""
    try:
        service = WorkflowService(db)
        workflow = await service.get_workflow(workflow_id, current_user["sub"])
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        if mode not in workflow.interaction_modes:
            raise HTTPException(status_code=400, detail=f"Workflow does not support {mode} mode")
        
        # Generate interface configuration based on mode
        from app.models.workflow import INTERACTION_MODE_CONFIGS
        
        interface_config = INTERACTION_MODE_CONFIGS.get(mode, {})
        
        # Customize based on workflow definition
        if mode == "form":
            # Generate form fields from workflow inputs
            trigger_nodes = [n for n in workflow.definition.get('nodes', []) if n.get('type') == 'trigger']
            form_fields = []
            
            for node in trigger_nodes:
                if node.get('data', {}).get('input_schema'):
                    form_fields.extend(node['data']['input_schema'])
            
            interface_config['form_fields'] = form_fields
        
        elif mode == "button":
            # Simple button configuration
            interface_config['button_text'] = f"Execute {workflow.name}"
            interface_config['description'] = workflow.description
        
        elif mode == "dashboard":
            # Dashboard metrics configuration
            interface_config['metrics'] = {
                'execution_count': workflow.execution_count,
                'total_cost': workflow.total_cost_cents / 100,
                'avg_execution_time': workflow.average_execution_time_ms,
                'status': workflow.status
            }
        
        return {
            'workflow_id': workflow_id,
            'mode': mode,
            'config': interface_config,
            'workflow': {
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get interface: {str(e)}")


# Node type information endpoints
@router.get("/node-types")
async def get_workflow_node_types():
    """Get available workflow node types and their configurations"""
    from app.models.workflow import WORKFLOW_NODE_TYPES
    return WORKFLOW_NODE_TYPES


@router.get("/interaction-modes")
async def get_interaction_modes():
    """Get available interaction modes and their configurations"""
    from app.models.workflow import INTERACTION_MODE_CONFIGS
    return INTERACTION_MODE_CONFIGS