"""
Event Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for event entities using the PostgreSQL + PGVector backend.
Handles event automation, triggers, and action definitions.
Perfect tenant isolation with encrypted storage.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


def generate_uuid():
    """Generate a unique identifier"""
    return str(uuid.uuid4())


class EventStatus(str, Enum):
    """Event status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class Event(BaseServiceModel):
    """
    Event model for GT 2.0 service-based architecture.
    
    Represents an automation event with processing status,
    payload data, and retry logic.
    """
    
    # Core event properties
    event_id: str = Field(default_factory=generate_uuid, description="Unique event identifier")
    event_type: str = Field(..., min_length=1, max_length=100, description="Event type identifier")
    user_id: str = Field(..., description="User who triggered the event")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Event data
    payload: Dict[str, Any] = Field(default_factory=dict, description="Encrypted event data")
    event_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Processing status
    status: EventStatus = Field(default=EventStatus.PENDING, description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    
    # Timestamps
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    
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
        return "events"
    
    def is_completed(self) -> bool:
        """Check if event processing is completed"""
        return self.status == EventStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if event processing failed"""
        return self.status == EventStatus.FAILED
    
    def mark_processing(self) -> None:
        """Mark event as processing"""
        self.status = EventStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self.update_timestamp()
    
    def mark_completed(self) -> None:
        """Mark event as completed"""
        self.status = EventStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.update_timestamp()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark event as failed"""
        self.status = EventStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        self.update_timestamp()
    
    def increment_retry(self) -> None:
        """Increment retry count"""
        self.retry_count += 1
        self.status = EventStatus.RETRYING
        self.update_timestamp()


class EventTrigger(BaseServiceModel):
    """
    Event trigger model for automation conditions.
    
    Defines conditions that will trigger event processing.
    """
    
    # Core trigger properties
    trigger_name: str = Field(..., min_length=1, max_length=100, description="Trigger name")
    event_type: str = Field(..., min_length=1, max_length=100, description="Event type to trigger")
    user_id: str = Field(..., description="User who owns this trigger")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Trigger configuration
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Trigger conditions")
    trigger_config: Dict[str, Any] = Field(default_factory=dict, description="Trigger configuration")
    
    # Status
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
        return "event_triggers"


class EventAction(BaseServiceModel):
    """
    Event action model for automation responses.
    
    Defines actions to take when events are processed.
    """
    
    # Core action properties
    action_name: str = Field(..., min_length=1, max_length=100, description="Action name")
    event_type: str = Field(..., min_length=1, max_length=100, description="Event type this action handles")
    user_id: str = Field(..., description="User who owns this action")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Action configuration
    action_type: str = Field(..., min_length=1, max_length=50, description="Type of action")
    action_config: Dict[str, Any] = Field(default_factory=dict, description="Action configuration")
    
    # Execution settings
    priority: int = Field(default=10, ge=1, le=100, description="Execution priority")
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Action timeout")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    
    # Status
    is_active: bool = Field(default=True, description="Whether action is active")
    execution_count: int = Field(default=0, description="Number of times executed")
    last_executed: Optional[datetime] = Field(None, description="Last execution timestamp")
    
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
        return "event_actions"


class EventSubscription(BaseServiceModel):
    """
    Event subscription model for user notifications.
    
    Manages user subscriptions to specific event types.
    """
    
    # Core subscription properties
    user_id: str = Field(..., description="Subscribing user ID")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    event_type: str = Field(..., min_length=1, max_length=100, description="Subscribed event type")
    
    # Subscription configuration
    notification_method: str = Field(default="websocket", max_length=50, description="Notification delivery method")
    subscription_config: Dict[str, Any] = Field(default_factory=dict, description="Subscription settings")
    
    # Filtering
    event_filters: Dict[str, Any] = Field(default_factory=dict, description="Event filtering criteria")
    
    # Status
    is_active: bool = Field(default=True, description="Whether subscription is active")
    notification_count: int = Field(default=0, description="Number of notifications sent")
    last_notified: Optional[datetime] = Field(None, description="Last notification timestamp")
    
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
        return "event_subscriptions"


# Create/Update/Response models

class EventCreate(BaseCreateModel):
    """Model for creating new events"""
    event_type: str = Field(..., min_length=1, max_length=100)
    user_id: str
    tenant_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    event_metadata: Dict[str, Any] = Field(default_factory=dict)


class EventUpdate(BaseUpdateModel):
    """Model for updating events"""
    status: Optional[EventStatus] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = Field(None, ge=0)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EventResponse(BaseResponseModel):
    """Model for event API responses"""
    id: str
    event_id: str
    event_type: str
    user_id: str
    tenant_id: str
    payload: Dict[str, Any]
    event_metadata: Dict[str, Any]
    status: EventStatus
    error_message: Optional[str]
    retry_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# Legacy compatibility - simplified versions of missing models
class EventLog(BaseServiceModel):
    """Minimal EventLog model for compatibility"""
    event_id: str = Field(..., description="Related event ID")
    log_message: str = Field(..., description="Log message")
    log_level: str = Field(default="info", description="Log level")
    
    model_config = ConfigDict(protected_namespaces=())
    
    @classmethod
    def get_table_name(cls) -> str:
        return "event_logs"


class ScheduledTask(BaseServiceModel):
    """Minimal ScheduledTask model for compatibility"""
    task_name: str = Field(..., description="Task name")
    schedule: str = Field(..., description="Cron schedule")
    is_active: bool = Field(default=True, description="Whether task is active")
    
    model_config = ConfigDict(protected_namespaces=())
    
    @classmethod
    def get_table_name(cls) -> str:
        return "scheduled_tasks"