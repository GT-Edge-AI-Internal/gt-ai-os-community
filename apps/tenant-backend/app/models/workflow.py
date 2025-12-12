"""
Workflow Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for workflow entities using the PostgreSQL + PGVector backend.
Stores workflow definitions, executions, triggers, and chat sessions.
Perfect tenant isolation - each tenant has separate workflow data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


class WorkflowStatus(str, Enum):
    """Workflow status enumeration"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TriggerType(str, Enum):
    """Trigger type enumeration"""
    MANUAL = "manual"
    WEBHOOK = "webhook"
    CRON = "cron"
    EVENT = "event"
    API = "api"


class InteractionMode(str, Enum):
    """Interaction mode enumeration"""
    CHAT = "chat"
    BUTTON = "button"
    FORM = "form"
    DASHBOARD = "dashboard"
    API = "api"


class ExecutionStatus(str, Enum):
    """Execution status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Workflow(BaseServiceModel):
    """
    Workflow model for GT 2.0 service-based architecture.
    
    Represents an agentic workflow with nodes, triggers, and execution logic.
    Supports chat interfaces, form inputs, API endpoints, and dashboard views.
    """
    
    # Basic workflow properties
    tenant_id: str = Field(..., description="Tenant domain identifier")
    user_id: str = Field(..., description="User who owns this workflow")
    name: str = Field(..., min_length=1, max_length=200, description="Workflow name")
    description: Optional[str] = Field(None, max_length=1000, description="Workflow description")
    
    # Workflow definition as JSON structure
    definition: Dict[str, Any] = Field(..., description="Nodes, edges, and configuration")
    
    # Triggers and interaction modes
    triggers: List[Dict[str, Any]] = Field(default_factory=list, description="Webhook, cron, event triggers")
    interaction_modes: List[InteractionMode] = Field(default_factory=list, description="UI interaction modes")
    
    # Resource references - ensuring user owns all resources
    agent_ids: List[str] = Field(default_factory=list, description="Referenced agents")
    api_key_ids: List[str] = Field(default_factory=list, description="Referenced API keys")
    webhook_ids: List[str] = Field(default_factory=list, description="Referenced webhooks")
    dataset_ids: List[str] = Field(default_factory=list, description="Referenced datasets")
    integration_ids: List[str] = Field(default_factory=list, description="Referenced integrations")
    
    # Workflow configuration
    config: Dict[str, Any] = Field(default_factory=dict, description="Runtime configuration")
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Execution timeout (5 min default)")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    
    # Status and metadata
    status: WorkflowStatus = Field(default=WorkflowStatus.DRAFT, description="Workflow status")
    execution_count: int = Field(default=0, description="Total execution count")
    last_executed: Optional[datetime] = Field(None, description="Last execution timestamp")
    
    # Analytics
    total_tokens_used: int = Field(default=0, description="Total tokens consumed")
    total_cost_cents: int = Field(default=0, description="Total cost in cents")
    average_execution_time_ms: Optional[int] = Field(None, description="Average execution time")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "workflows"
    
    def activate(self) -> None:
        """Activate the workflow"""
        self.status = WorkflowStatus.ACTIVE
        self.update_timestamp()
    
    def pause(self) -> None:
        """Pause the workflow"""
        self.status = WorkflowStatus.PAUSED
        self.update_timestamp()
    
    def archive(self) -> None:
        """Archive the workflow"""
        self.status = WorkflowStatus.ARCHIVED
        self.update_timestamp()
    
    def update_execution_stats(self, tokens_used: int, cost_cents: int, execution_time_ms: int) -> None:
        """Update execution statistics"""
        self.execution_count += 1
        self.total_tokens_used += tokens_used
        self.total_cost_cents += cost_cents
        self.last_executed = datetime.utcnow()
        
        # Update rolling average execution time
        if self.average_execution_time_ms is None:
            self.average_execution_time_ms = execution_time_ms
        else:
            # Simple moving average
            self.average_execution_time_ms = int(
                (self.average_execution_time_ms * (self.execution_count - 1) + execution_time_ms) / self.execution_count
            )
        
        self.update_timestamp()


class WorkflowExecution(BaseServiceModel):
    """
    Workflow execution model for tracking individual workflow runs.
    
    Stores execution state, progress, timing, and resource usage.
    """
    
    # Core execution properties
    workflow_id: str = Field(..., description="Parent workflow ID")
    user_id: str = Field(..., description="User who triggered execution")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Execution state
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING, description="Execution status")
    current_node_id: Optional[str] = Field(None, description="Currently executing node")
    progress_percentage: int = Field(default=0, ge=0, le=100, description="Execution progress")
    
    # Data and context
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Execution input data")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="Execution output data")
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list, description="Step-by-step log")
    error_details: Optional[str] = Field(None, description="Error details if failed")
    
    # Timing and performance
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    
    # Resource usage
    tokens_used: int = Field(default=0, description="Tokens consumed")
    cost_cents: int = Field(default=0, description="Cost in cents")
    tool_calls_count: int = Field(default=0, description="Number of tool calls made")
    
    # Trigger information
    trigger_type: Optional[TriggerType] = Field(None, description="How execution was triggered")
    trigger_data: Dict[str, Any] = Field(default_factory=dict, description="Trigger-specific data")
    trigger_source: Optional[str] = Field(None, description="Source identifier for trigger")
    
    # Session information for chat mode
    session_id: Optional[str] = Field(None, description="Chat session ID if applicable")
    interaction_mode: Optional[InteractionMode] = Field(None, description="User interaction mode")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "workflow_executions"
    
    def mark_running(self, current_node_id: str) -> None:
        """Mark execution as running"""
        self.status = ExecutionStatus.RUNNING
        self.current_node_id = current_node_id
        self.update_timestamp()
    
    def mark_completed(self, output_data: Dict[str, Any]) -> None:
        """Mark execution as completed"""
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.output_data = output_data
        self.progress_percentage = 100
        
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        
        self.update_timestamp()
    
    def mark_failed(self, error_details: str) -> None:
        """Mark execution as failed"""
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_details = error_details
        
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        
        self.update_timestamp()
    
    def add_trace_entry(self, node_id: str, action: str, data: Dict[str, Any]) -> None:
        """Add entry to execution trace"""
        trace_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "node_id": node_id,
            "action": action,
            "data": data
        }
        self.execution_trace.append(trace_entry)


class WorkflowTrigger(BaseServiceModel):
    """
    Workflow trigger model for automated workflow execution.
    
    Supports webhook, cron, event, and API triggers.
    """
    
    # Core trigger properties
    workflow_id: str = Field(..., description="Parent workflow ID")
    user_id: str = Field(..., description="User who owns this trigger")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Trigger configuration
    trigger_type: TriggerType = Field(..., description="Type of trigger")
    trigger_config: Dict[str, Any] = Field(..., description="Trigger-specific configuration")
    
    # Webhook-specific fields
    webhook_url: Optional[str] = Field(None, description="Generated webhook URL")
    webhook_secret: Optional[str] = Field(None, max_length=128, description="Webhook signature secret")
    
    # Cron-specific fields
    cron_schedule: Optional[str] = Field(None, max_length=100, description="Cron expression")
    timezone: str = Field(default="UTC", max_length=50, description="Timezone for cron schedule")
    
    # Event-specific fields
    event_source: Optional[str] = Field(None, max_length=100, description="Event source system")
    event_filters: Dict[str, Any] = Field(default_factory=dict, description="Event filtering criteria")
    
    # Status and metadata
    is_active: bool = Field(default=True, description="Whether trigger is active")
    trigger_count: int = Field(default=0, description="Number of times triggered")
    last_triggered: Optional[datetime] = Field(None, description="Last trigger timestamp")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "workflow_triggers"
    
    def activate(self) -> None:
        """Activate the trigger"""
        self.is_active = True
        self.update_timestamp()
    
    def deactivate(self) -> None:
        """Deactivate the trigger"""
        self.is_active = False
        self.update_timestamp()
    
    def record_trigger(self) -> None:
        """Record a trigger event"""
        self.trigger_count += 1
        self.last_triggered = datetime.utcnow()
        self.update_timestamp()


class WorkflowSession(BaseServiceModel):
    """
    Workflow session model for chat-based workflow interactions.
    
    Manages conversational state for workflow chat interfaces.
    """
    
    # Core session properties
    workflow_id: str = Field(..., description="Parent workflow ID")
    user_id: str = Field(..., description="User participating in session")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Session configuration
    session_type: str = Field(default="chat", max_length=50, description="Session type")
    session_state: Dict[str, Any] = Field(default_factory=dict, description="Current conversation state")
    
    # Chat history
    message_count: int = Field(default=0, description="Number of messages in session")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    
    # Status
    is_active: bool = Field(default=True, description="Whether session is active")
    expires_at: Optional[datetime] = Field(None, description="Session expiration time")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "workflow_sessions"
    
    def add_message(self) -> None:
        """Record a new message in the session"""
        self.message_count += 1
        self.last_message_at = datetime.utcnow()
        self.update_timestamp()
    
    def close_session(self) -> None:
        """Close the session"""
        self.is_active = False
        self.update_timestamp()


class WorkflowMessage(BaseServiceModel):
    """
    Workflow message model for chat session messages.
    
    Stores individual messages within workflow chat sessions.
    """
    
    # Core message properties
    session_id: str = Field(..., description="Parent session ID")
    workflow_id: str = Field(..., description="Parent workflow ID")
    execution_id: Optional[str] = Field(None, description="Associated execution ID")
    user_id: str = Field(..., description="User who sent/received message")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Message content
    role: str = Field(..., max_length=20, description="Message role (user, agent, system)")
    content: str = Field(..., description="Message content")
    message_type: str = Field(default="text", max_length=50, description="Message type")
    
    # Agent information for agent messages
    agent_id: Optional[str] = Field(None, description="Agent that generated this message")
    confidence_score: Optional[int] = Field(None, ge=0, le=100, description="Agent confidence (0-100)")
    
    # Additional data
    message_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message data")
    tokens_used: int = Field(default=0, description="Tokens consumed for this message")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "workflow_messages"


# Create/Update/Response models for each entity

class WorkflowCreate(BaseCreateModel):
    """Model for creating new workflows"""
    tenant_id: str
    user_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    definition: Dict[str, Any]
    triggers: List[Dict[str, Any]] = Field(default_factory=list)
    interaction_modes: List[InteractionMode] = Field(default_factory=list)
    agent_ids: List[str] = Field(default_factory=list)
    api_key_ids: List[str] = Field(default_factory=list)
    webhook_ids: List[str] = Field(default_factory=list)
    dataset_ids: List[str] = Field(default_factory=list)
    integration_ids: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=10)


class WorkflowUpdate(BaseUpdateModel):
    """Model for updating workflows"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    definition: Optional[Dict[str, Any]] = None
    triggers: Optional[List[Dict[str, Any]]] = None
    interaction_modes: Optional[List[InteractionMode]] = None
    config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    status: Optional[WorkflowStatus] = None


class WorkflowResponse(BaseResponseModel):
    """Model for workflow API responses"""
    id: str
    tenant_id: str
    user_id: str
    name: str
    description: Optional[str]
    definition: Dict[str, Any]
    triggers: List[Dict[str, Any]]
    interaction_modes: List[InteractionMode]
    agent_ids: List[str]
    api_key_ids: List[str]
    webhook_ids: List[str]
    dataset_ids: List[str]
    integration_ids: List[str]
    config: Dict[str, Any]
    timeout_seconds: int
    max_retries: int
    status: WorkflowStatus
    execution_count: int
    last_executed: Optional[datetime]
    total_tokens_used: int
    total_cost_cents: int
    average_execution_time_ms: Optional[int]
    created_at: datetime
    updated_at: datetime


class WorkflowExecutionCreate(BaseCreateModel):
    """Model for creating new workflow executions"""
    workflow_id: str
    user_id: str
    tenant_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    trigger_type: Optional[TriggerType] = None
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    trigger_source: Optional[str] = None
    session_id: Optional[str] = None
    interaction_mode: Optional[InteractionMode] = None


class WorkflowExecutionUpdate(BaseUpdateModel):
    """Model for updating workflow executions"""
    status: Optional[ExecutionStatus] = None
    current_node_id: Optional[str] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    output_data: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None
    completed_at: Optional[datetime] = None
    tokens_used: Optional[int] = Field(None, ge=0)
    cost_cents: Optional[int] = Field(None, ge=0)
    tool_calls_count: Optional[int] = Field(None, ge=0)


class WorkflowExecutionResponse(BaseResponseModel):
    """Model for workflow execution API responses"""
    id: str
    workflow_id: str
    user_id: str
    tenant_id: str
    status: ExecutionStatus
    current_node_id: Optional[str]
    progress_percentage: int
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    execution_trace: List[Dict[str, Any]]
    error_details: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    tokens_used: int
    cost_cents: int
    tool_calls_count: int
    trigger_type: Optional[TriggerType]
    trigger_data: Dict[str, Any]
    trigger_source: Optional[str]
    session_id: Optional[str]
    interaction_mode: Optional[InteractionMode]
    created_at: datetime
    updated_at: datetime


# Node type definitions for workflow canvas
WORKFLOW_NODE_TYPES = {
    "agent": {
        "name": "Agent",
        "description": "Execute an AI Agent with personality",
        "inputs": ["text", "context"],
        "outputs": ["response", "confidence"],
        "config_schema": {
            "agent_id": {"type": "string", "required": True},
            "confidence_threshold": {"type": "integer", "default": 70},
            "max_tokens": {"type": "integer", "default": 2000},
            "temperature": {"type": "number", "default": 0.7}
        }
    },
    "trigger": {
        "name": "Trigger",
        "description": "Start workflow execution",
        "inputs": [],
        "outputs": ["trigger_data"],
        "subtypes": ["webhook", "cron", "event", "manual", "api"],
        "config_schema": {
            "trigger_type": {"type": "string", "required": True}
        }
    },
    "integration": {
        "name": "Integration",
        "description": "Connect to external services",
        "inputs": ["data"],
        "outputs": ["response"],
        "subtypes": ["api", "database", "storage", "webhook"],
        "config_schema": {
            "integration_type": {"type": "string", "required": True},
            "api_key_id": {"type": "string"},
            "endpoint_url": {"type": "string"},
            "method": {"type": "string", "default": "GET"}
        }
    },
    "logic": {
        "name": "Logic",
        "description": "Control flow and data transformation",
        "inputs": ["data"],
        "outputs": ["result"],
        "subtypes": ["decision", "loop", "transform", "aggregate", "filter"],
        "config_schema": {
            "logic_type": {"type": "string", "required": True}
        }
    },
    "output": {
        "name": "Output",
        "description": "Send results to external systems",
        "inputs": ["data"],
        "outputs": [],
        "subtypes": ["webhook", "api", "email", "storage", "notification"],
        "config_schema": {
            "output_type": {"type": "string", "required": True}
        }
    }
}


# Interaction mode configurations
INTERACTION_MODE_CONFIGS = {
    "chat": {
        "name": "Chat Interface",
        "description": "Conversational interaction with workflow",
        "supports_streaming": True,
        "supports_history": True,
        "ui_components": ["chat_input", "message_history", "agent_avatars"]
    },
    "button": {
        "name": "Button Trigger",
        "description": "Simple one-click workflow execution",
        "supports_streaming": False,
        "supports_history": False,
        "ui_components": ["trigger_button", "progress_indicator", "result_display"]
    },
    "form": {
        "name": "Form Input",
        "description": "Structured input with validation",
        "supports_streaming": False,
        "supports_history": True,
        "ui_components": ["dynamic_form", "validation", "submit_button"]
    },
    "dashboard": {
        "name": "Dashboard View",
        "description": "Overview of workflow status and metrics",
        "supports_streaming": True,
        "supports_history": True,
        "ui_components": ["metrics_cards", "execution_history", "status_indicators"]
    },
    "api": {
        "name": "API Endpoint",
        "description": "Programmatic access to workflow",
        "supports_streaming": True,
        "supports_history": False,
        "ui_components": []
    }
}