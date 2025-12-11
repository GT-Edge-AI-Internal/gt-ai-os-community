"""
Event Pydantic schemas for GT 2.0 Tenant Backend

Defines request/response schemas for event automation operations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class EventActionCreate(BaseModel):
    """Schema for creating an event action"""
    action_type: str = Field(..., description="Type of action to execute")
    config: Dict[str, Any] = Field(default_factory=dict, description="Action configuration")
    delay_seconds: int = Field(default=0, ge=0, le=3600, description="Delay before execution")
    retry_count: int = Field(default=3, ge=0, le=10, description="Number of retries on failure")
    retry_delay: int = Field(default=60, ge=1, le=3600, description="Delay between retries")
    condition: Optional[str] = Field(None, max_length=1000, description="Python expression for conditional execution")
    execution_order: int = Field(default=0, ge=0, description="Order of execution within subscription")

    @validator('action_type')
    def validate_action_type(cls, v):
        valid_types = [
            'process_document', 'send_notification', 'update_statistics',
            'trigger_rag_indexing', 'log_analytics', 'execute_webhook',
            'create_assistant', 'schedule_task'
        ]
        if v not in valid_types:
            raise ValueError(f'action_type must be one of: {", ".join(valid_types)}')
        return v


class EventActionResponse(BaseModel):
    """Event action response schema"""
    id: str
    action_type: str
    subscription_id: str
    config: Dict[str, Any]
    condition: Optional[str] = None
    delay_seconds: int
    retry_count: int
    retry_delay: int
    execution_order: int
    is_active: bool
    execution_count: int
    success_count: int
    failure_count: int
    last_executed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventSubscriptionCreate(BaseModel):
    """Schema for creating an event subscription"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    event_type: str = Field(..., description="Type of event to subscribe to")
    actions: List[EventActionCreate] = Field(..., min_items=1, description="Actions to execute")
    filter_conditions: Dict[str, Any] = Field(default_factory=dict, description="Conditions for subscription activation")

    @validator('event_type')
    def validate_event_type(cls, v):
        valid_types = [
            'document.uploaded', 'document.processed', 'document.failed',
            'conversation.started', 'message.sent', 'agent.created',
            'rag.search_performed', 'user.login', 'user.activity',
            'system.health_check'
        ]
        if v not in valid_types:
            raise ValueError(f'event_type must be one of: {", ".join(valid_types)}')
        return v


class EventSubscriptionResponse(BaseModel):
    """Event subscription response schema"""
    id: str
    name: str
    description: Optional[str] = None
    event_type: str
    user_id: str
    tenant_id: str
    trigger_id: Optional[str] = None
    filter_conditions: Dict[str, Any]
    is_active: bool
    trigger_count: int
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    actions: List[EventActionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    """Event response schema"""
    id: int
    event_id: str
    event_type: str
    user_id: str
    tenant_id: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any]
    status: str
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventStatistics(BaseModel):
    """Event statistics response schema"""
    total_events: int
    events_by_type: Dict[str, int]
    events_by_status: Dict[str, int]
    average_events_per_day: float


class EventTriggerCreate(BaseModel):
    """Schema for creating an event trigger"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    trigger_type: str = Field(..., description="Type of trigger")
    config: Dict[str, Any] = Field(default_factory=dict, description="Trigger configuration")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Trigger conditions")

    @validator('trigger_type')
    def validate_trigger_type(cls, v):
        valid_types = [
            'schedule', 'webhook', 'file_watch', 'database_change',
            'api_call', 'user_action', 'system_event'
        ]
        if v not in valid_types:
            raise ValueError(f'trigger_type must be one of: {", ".join(valid_types)}')
        return v


class EventTriggerResponse(BaseModel):
    """Event trigger response schema"""
    id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    user_id: str
    tenant_id: str
    config: Dict[str, Any]
    conditions: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_triggered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScheduledTaskResponse(BaseModel):
    """Scheduled task response schema"""
    id: str
    task_type: str
    name: str
    description: Optional[str] = None
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    config: Dict[str, Any]
    context: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    user_id: str
    tenant_id: str
    retry_count: int
    max_retries: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventLogResponse(BaseModel):
    """Event log response schema"""
    id: int
    event_id: str
    log_level: str
    message: str
    details: Dict[str, Any]
    action_id: Optional[str] = None
    subscription_id: Optional[str] = None
    user_id: str
    tenant_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class EmitEventRequest(BaseModel):
    """Request schema for manually emitting events"""
    event_type: str = Field(..., description="Type of event to emit")
    data: Dict[str, Any] = Field(..., description="Event data payload")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @validator('event_type')
    def validate_event_type(cls, v):
        valid_types = [
            'document.uploaded', 'document.processed', 'document.failed',
            'conversation.started', 'message.sent', 'agent.created',
            'rag.search_performed', 'user.login', 'user.activity',
            'system.health_check'
        ]
        if v not in valid_types:
            raise ValueError(f'event_type must be one of: {", ".join(valid_types)}')
        return v


class WebhookConfig(BaseModel):
    """Configuration for webhook actions"""
    url: str = Field(..., description="Webhook URL")
    method: str = Field(default="POST", pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1, le=300)
    retry_on_failure: bool = Field(default=True)


class NotificationConfig(BaseModel):
    """Configuration for notification actions"""
    type: str = Field(default="system", description="Notification type")
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    channels: List[str] = Field(default_factory=list, description="Notification channels")


class DocumentProcessingConfig(BaseModel):
    """Configuration for document processing actions"""
    chunking_strategy: str = Field(default="hybrid", pattern="^(fixed|semantic|hierarchical|hybrid)$")
    chunk_size: int = Field(default=512, ge=128, le=2048)
    chunk_overlap: int = Field(default=128, ge=0, le=512)
    auto_index: bool = Field(default=True, description="Automatically index in RAG system")


class StatisticsUpdateConfig(BaseModel):
    """Configuration for statistics update actions"""
    type: str = Field(..., description="Type of statistic to update")
    increment: int = Field(default=1, description="Amount to increment")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AssistantCreationConfig(BaseModel):
    """Configuration for agent creation actions"""
    template_id: str = Field(default="general_assistant", description="Agent template ID")
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    config_overrides: Dict[str, Any] = Field(default_factory=dict, description="Configuration overrides")


class TaskSchedulingConfig(BaseModel):
    """Configuration for task scheduling actions"""
    task_type: str = Field(..., description="Type of task to schedule")
    delay_minutes: int = Field(default=0, ge=0, description="Delay before execution")
    task_config: Dict[str, Any] = Field(default_factory=dict, description="Task configuration")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")