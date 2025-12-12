"""
Event Automation Service for GT 2.0 Tenant Backend

Handles event-driven automation workflows including:
- Document processing triggers
- Conversation events
- RAG pipeline automation
- Agent lifecycle events
- User activity tracking

Perfect tenant isolation with zero downtime compliance.
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.core.config import get_settings
from app.models.event import Event, EventTrigger, EventAction, EventSubscription
from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService
from app.services.assistant_manager import AssistantManager

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for automation triggers"""
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_FAILED = "document.failed"
    CONVERSATION_STARTED = "conversation.started"
    MESSAGE_SENT = "message.sent"
    ASSISTANT_CREATED = "agent.created"
    RAG_SEARCH_PERFORMED = "rag.search_performed"
    USER_LOGIN = "user.login"
    USER_ACTIVITY = "user.activity"
    SYSTEM_HEALTH_CHECK = "system.health_check"
    TEAM_INVITATION_CREATED = "team.invitation.created"
    TEAM_OBSERVABLE_REQUESTED = "team.observable_requested"


class ActionType(str, Enum):
    """Action types for event responses"""
    PROCESS_DOCUMENT = "process_document"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_STATISTICS = "update_statistics"
    TRIGGER_RAG_INDEXING = "trigger_rag_indexing"
    LOG_ANALYTICS = "log_analytics"
    EXECUTE_WEBHOOK = "execute_webhook"
    CREATE_ASSISTANT = "create_assistant"
    SCHEDULE_TASK = "schedule_task"


@dataclass
class EventPayload:
    """Event payload structure"""
    event_id: str
    event_type: EventType
    user_id: str
    tenant_id: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventActionConfig:
    """Configuration for event actions"""
    action_type: ActionType
    config: Dict[str, Any]
    delay_seconds: int = 0
    retry_count: int = 3
    retry_delay: int = 60
    condition: Optional[str] = None  # Python expression for conditional execution


class EventService:
    """
    Event automation service with perfect tenant isolation.
    
    GT 2.0 Security Principles:
    - Perfect tenant isolation (all events user-scoped)
    - Zero downtime compliance (async processing)
    - Self-contained automation (no external dependencies)
    - Stateless event processing
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.rag_service = RAGService(db)
        self.conversation_service = ConversationService(db)
        self.assistant_manager = AssistantManager(db)
        
        # Event handlers registry
        self.action_handlers: Dict[ActionType, Callable] = {
            ActionType.PROCESS_DOCUMENT: self._handle_process_document,
            ActionType.SEND_NOTIFICATION: self._handle_send_notification,
            ActionType.UPDATE_STATISTICS: self._handle_update_statistics,
            ActionType.TRIGGER_RAG_INDEXING: self._handle_trigger_rag_indexing,
            ActionType.LOG_ANALYTICS: self._handle_log_analytics,
            ActionType.EXECUTE_WEBHOOK: self._handle_execute_webhook,
            ActionType.CREATE_ASSISTANT: self._handle_create_assistant,
            ActionType.SCHEDULE_TASK: self._handle_schedule_task,
        }
        
        # Active event subscriptions cache
        self.subscriptions_cache: Dict[str, List[EventSubscription]] = {}
        self.cache_expiry: Optional[datetime] = None
        
        logger.info("Event automation service initialized with tenant isolation")
    
    async def emit_event(
        self,
        event_type: EventType,
        user_id: str,
        tenant_id: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Emit an event and trigger automated actions"""
        try:
            # Create event payload
            event_payload = EventPayload(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                user_id=user_id,
                tenant_id=tenant_id,
                timestamp=datetime.utcnow(),
                data=data,
                metadata=metadata or {}
            )
            
            # Store event in database
            event_record = Event(
                event_id=event_payload.event_id,
                event_type=event_type.value,
                user_id=user_id,
                tenant_id=tenant_id,
                payload=event_payload.to_dict(),
                status="processing"
            )
            
            self.db.add(event_record)
            await self.db.commit()
            
            # Process event asynchronously
            asyncio.create_task(self._process_event(event_payload))
            
            logger.info(f"Event emitted: {event_type.value} for user {user_id}")
            return event_payload.event_id
            
        except Exception as e:
            logger.error(f"Failed to emit event {event_type.value}: {e}")
            raise
    
    async def _process_event(self, event_payload: EventPayload) -> None:
        """Process event and execute matching actions"""
        try:
            # Get subscriptions for this event type
            subscriptions = await self._get_event_subscriptions(
                event_payload.event_type,
                event_payload.user_id,
                event_payload.tenant_id
            )
            
            if not subscriptions:
                logger.debug(f"No subscriptions found for event {event_payload.event_type}")
                return
            
            # Execute actions for each subscription
            for subscription in subscriptions:
                try:
                    await self._execute_subscription_actions(subscription, event_payload)
                except Exception as e:
                    logger.error(f"Failed to execute subscription {subscription.id}: {e}")
                    continue
            
            # Update event status
            await self._update_event_status(event_payload.event_id, "completed")
            
        except Exception as e:
            logger.error(f"Failed to process event {event_payload.event_id}: {e}")
            await self._update_event_status(event_payload.event_id, "failed", str(e))
    
    async def _get_event_subscriptions(
        self,
        event_type: EventType,
        user_id: str,
        tenant_id: str
    ) -> List[EventSubscription]:
        """Get active subscriptions for event type with tenant isolation"""
        try:
            # Check cache first
            cache_key = f"{tenant_id}:{user_id}:{event_type.value}"
            if (self.cache_expiry and datetime.utcnow() < self.cache_expiry and 
                cache_key in self.subscriptions_cache):
                return self.subscriptions_cache[cache_key]
            
            # Query database
            query = select(EventSubscription).where(
                and_(
                    EventSubscription.event_type == event_type.value,
                    EventSubscription.user_id == user_id,
                    EventSubscription.tenant_id == tenant_id,
                    EventSubscription.is_active == True
                )
            ).options(selectinload(EventSubscription.actions))
            
            result = await self.db.execute(query)
            subscriptions = result.scalars().all()
            
            # Cache results
            self.subscriptions_cache[cache_key] = list(subscriptions)
            self.cache_expiry = datetime.utcnow() + timedelta(minutes=5)
            
            return list(subscriptions)
            
        except Exception as e:
            logger.error(f"Failed to get event subscriptions: {e}")
            return []
    
    async def _execute_subscription_actions(
        self,
        subscription: EventSubscription,
        event_payload: EventPayload
    ) -> None:
        """Execute all actions for a subscription"""
        try:
            for action in subscription.actions:
                # Check if action should be executed
                if not await self._should_execute_action(action, event_payload):
                    continue
                
                # Add delay if specified
                if action.delay_seconds > 0:
                    await asyncio.sleep(action.delay_seconds)
                
                # Execute action with retry logic
                await self._execute_action_with_retry(action, event_payload)
                
        except Exception as e:
            logger.error(f"Failed to execute subscription actions: {e}")
            raise
    
    async def _should_execute_action(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> bool:
        """Check if action should be executed based on conditions"""
        try:
            if not action.condition:
                return True
            
            # Create evaluation context
            context = {
                'event': event_payload.to_dict(),
                'data': event_payload.data,
                'user_id': event_payload.user_id,
                'tenant_id': event_payload.tenant_id,
                'event_type': event_payload.event_type.value
            }
            
            # Safely evaluate condition
            try:
                result = eval(action.condition, {"__builtins__": {}}, context)
                return bool(result)
            except Exception as e:
                logger.warning(f"Failed to evaluate action condition: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking action condition: {e}")
            return False
    
    async def _execute_action_with_retry(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Execute action with retry logic"""
        last_error = None
        
        for attempt in range(action.retry_count + 1):
            try:
                await self._execute_action(action, event_payload)
                return  # Success
                
            except Exception as e:
                last_error = e
                logger.warning(f"Action execution attempt {attempt + 1} failed: {e}")
                
                if attempt < action.retry_count:
                    await asyncio.sleep(action.retry_delay)
                else:
                    logger.error(f"Action execution failed after {action.retry_count + 1} attempts")
                    raise last_error
    
    async def _execute_action(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Execute a specific action"""
        try:
            action_type = ActionType(action.action_type)
            handler = self.action_handlers.get(action_type)
            
            if not handler:
                raise ValueError(f"No handler for action type: {action_type}")
            
            await handler(action, event_payload)
            
            logger.debug(f"Action executed: {action_type.value} for event {event_payload.event_id}")
            
        except Exception as e:
            logger.error(f"Failed to execute action {action.action_type}: {e}")
            raise
    
    # Action Handlers
    
    async def _handle_process_document(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle document processing automation"""
        try:
            document_id = event_payload.data.get("document_id")
            if not document_id:
                raise ValueError("document_id required for process_document action")
            
            chunking_strategy = action.config.get("chunking_strategy", "hybrid")
            
            result = await self.rag_service.process_document(
                user_id=event_payload.user_id,
                document_id=document_id,
                tenant_id=event_payload.tenant_id,
                chunking_strategy=chunking_strategy
            )
            
            # Emit processing completed event
            await self.emit_event(
                EventType.DOCUMENT_PROCESSED,
                event_payload.user_id,
                event_payload.tenant_id,
                {
                    "document_id": document_id,
                    "chunk_count": result.get("chunk_count", 0),
                    "processing_result": result
                }
            )
            
        except Exception as e:
            # Emit processing failed event
            await self.emit_event(
                EventType.DOCUMENT_FAILED,
                event_payload.user_id,
                event_payload.tenant_id,
                {
                    "document_id": event_payload.data.get("document_id"),
                    "error": str(e)
                }
            )
            raise
    
    async def _handle_send_notification(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle notification sending"""
        try:
            notification_type = action.config.get("type", "system")
            message = action.config.get("message", "Event notification")
            
            # Format message with event data
            formatted_message = message.format(**event_payload.data)
            
            # Store notification (implement notification system later)
            notification_data = {
                "type": notification_type,
                "message": formatted_message,
                "user_id": event_payload.user_id,
                "event_id": event_payload.event_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Notification sent: {formatted_message} to user {event_payload.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            raise
    
    async def _handle_update_statistics(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle statistics updates"""
        try:
            stat_type = action.config.get("type")
            increment = action.config.get("increment", 1)
            
            # Update user statistics (implement statistics system later)
            logger.info(f"Statistics updated: {stat_type} += {increment} for user {event_payload.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to update statistics: {e}")
            raise
    
    async def _handle_trigger_rag_indexing(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle RAG reindexing automation"""
        try:
            dataset_ids = action.config.get("dataset_ids", [])
            
            if not dataset_ids:
                # Get all user datasets
                datasets = await self.rag_service.list_user_datasets(event_payload.user_id)
                dataset_ids = [d.id for d in datasets]
            
            for dataset_id in dataset_ids:
                # Trigger reindexing for dataset
                logger.info(f"RAG reindexing triggered for dataset {dataset_id}")
            
        except Exception as e:
            logger.error(f"Failed to trigger RAG indexing: {e}")
            raise
    
    async def _handle_log_analytics(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle analytics logging"""
        try:
            analytics_data = {
                "event_type": event_payload.event_type.value,
                "user_id": event_payload.user_id,
                "tenant_id": event_payload.tenant_id,
                "timestamp": event_payload.timestamp.isoformat(),
                "data": event_payload.data,
                "custom_properties": action.config.get("properties", {})
            }
            
            # Log analytics (implement analytics system later)
            logger.info(f"Analytics logged: {analytics_data}")
            
        except Exception as e:
            logger.error(f"Failed to log analytics: {e}")
            raise
    
    async def _handle_execute_webhook(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle webhook execution"""
        try:
            webhook_url = action.config.get("url")
            method = action.config.get("method", "POST")
            headers = action.config.get("headers", {})
            
            if not webhook_url:
                raise ValueError("webhook url required")
            
            # Prepare webhook payload
            webhook_payload = {
                "event": event_payload.to_dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Execute webhook (implement HTTP client later)
            logger.info(f"Webhook executed: {method} {webhook_url}")
            
        except Exception as e:
            logger.error(f"Failed to execute webhook: {e}")
            raise
    
    async def _handle_create_assistant(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle automatic agent creation"""
        try:
            template_id = action.config.get("template_id", "general_assistant")
            assistant_name = action.config.get("name", "Auto-created Agent")
            
            # Create agent
            agent_id = await self.assistant_manager.create_from_template(
                template_id=template_id,
                config={"name": assistant_name},
                user_identifier=event_payload.user_id
            )
            
            # Emit agent created event
            await self.emit_event(
                EventType.ASSISTANT_CREATED,
                event_payload.user_id,
                event_payload.tenant_id,
                {
                    "agent_id": agent_id,
                    "template_id": template_id,
                    "trigger_event": event_payload.event_id
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise
    
    async def _handle_schedule_task(
        self,
        action: EventAction,
        event_payload: EventPayload
    ) -> None:
        """Handle task scheduling"""
        try:
            task_type = action.config.get("task_type")
            delay_minutes = action.config.get("delay_minutes", 0)
            
            # Schedule task for future execution
            scheduled_time = datetime.utcnow() + timedelta(minutes=delay_minutes)
            
            logger.info(f"Task scheduled: {task_type} for {scheduled_time}")
            
        except Exception as e:
            logger.error(f"Failed to schedule task: {e}")
            raise
    
    # Subscription Management
    
    async def create_subscription(
        self,
        user_id: str,
        tenant_id: str,
        event_type: EventType,
        actions: List[EventActionConfig],
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """Create an event subscription"""
        try:
            subscription = EventSubscription(
                user_id=user_id,
                tenant_id=tenant_id,
                event_type=event_type.value,
                name=name or f"Auto-subscription for {event_type.value}",
                description=description,
                is_active=True
            )
            
            self.db.add(subscription)
            await self.db.flush()
            
            # Create actions
            for action_config in actions:
                action = EventAction(
                    subscription_id=subscription.id,
                    action_type=action_config.action_type.value,
                    config=action_config.config,
                    delay_seconds=action_config.delay_seconds,
                    retry_count=action_config.retry_count,
                    retry_delay=action_config.retry_delay,
                    condition=action_config.condition
                )
                self.db.add(action)
            
            await self.db.commit()
            
            # Clear subscriptions cache
            self._clear_subscriptions_cache()
            
            logger.info(f"Event subscription created: {subscription.id} for {event_type.value}")
            return subscription.id
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create subscription: {e}")
            raise
    
    async def get_user_subscriptions(
        self,
        user_id: str,
        tenant_id: str
    ) -> List[EventSubscription]:
        """Get all subscriptions for a user"""
        try:
            query = select(EventSubscription).where(
                and_(
                    EventSubscription.user_id == user_id,
                    EventSubscription.tenant_id == tenant_id
                )
            ).options(selectinload(EventSubscription.actions))
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get user subscriptions: {e}")
            raise
    
    async def update_subscription_status(
        self,
        subscription_id: str,
        user_id: str,
        is_active: bool
    ) -> bool:
        """Update subscription status with ownership verification"""
        try:
            query = select(EventSubscription).where(
                and_(
                    EventSubscription.id == subscription_id,
                    EventSubscription.user_id == user_id
                )
            )
            
            result = await self.db.execute(query)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return False
            
            subscription.is_active = is_active
            subscription.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            # Clear subscriptions cache
            self._clear_subscriptions_cache()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update subscription status: {e}")
            raise
    
    async def delete_subscription(
        self,
        subscription_id: str,
        user_id: str
    ) -> bool:
        """Delete subscription with ownership verification"""
        try:
            query = select(EventSubscription).where(
                and_(
                    EventSubscription.id == subscription_id,
                    EventSubscription.user_id == user_id
                )
            )
            
            result = await self.db.execute(query)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return False
            
            await self.db.delete(subscription)
            await self.db.commit()
            
            # Clear subscriptions cache
            self._clear_subscriptions_cache()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete subscription: {e}")
            raise
    
    # Utility Methods
    
    async def _update_event_status(
        self,
        event_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update event processing status"""
        try:
            query = select(Event).where(Event.event_id == event_id)
            result = await self.db.execute(query)
            event = result.scalar_one_or_none()
            
            if event:
                event.status = status
                event.error_message = error_message
                event.completed_at = datetime.utcnow()
                await self.db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update event status: {e}")
    
    def _clear_subscriptions_cache(self) -> None:
        """Clear subscriptions cache"""
        self.subscriptions_cache.clear()
        self.cache_expiry = None
    
    async def get_event_history(
        self,
        user_id: str,
        tenant_id: str,
        event_types: Optional[List[EventType]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Event]:
        """Get event history for user with filtering"""
        try:
            query = select(Event).where(
                and_(
                    Event.user_id == user_id,
                    Event.tenant_id == tenant_id
                )
            )
            
            if event_types:
                event_type_values = [et.value for et in event_types]
                query = query.where(Event.event_type.in_(event_type_values))
            
            query = query.order_by(desc(Event.created_at)).offset(offset).limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get event history: {e}")
            raise
    
    async def get_event_statistics(
        self,
        user_id: str,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get event statistics for user"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = select(Event).where(
                and_(
                    Event.user_id == user_id,
                    Event.tenant_id == tenant_id,
                    Event.created_at >= cutoff_date
                )
            )
            
            result = await self.db.execute(query)
            events = result.scalars().all()
            
            # Calculate statistics
            stats = {
                "total_events": len(events),
                "events_by_type": {},
                "events_by_status": {},
                "average_events_per_day": 0
            }
            
            for event in events:
                # Count by type
                event_type = event.event_type
                stats["events_by_type"][event_type] = stats["events_by_type"].get(event_type, 0) + 1
                
                # Count by status
                status = event.status
                stats["events_by_status"][status] = stats["events_by_status"].get(status, 0) + 1
            
            # Calculate average per day
            if days > 0:
                stats["average_events_per_day"] = round(len(events) / days, 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get event statistics: {e}")
            raise


# Factory function for dependency injection
async def get_event_service(db: AsyncSession = None) -> EventService:
    """Get event service instance"""
    if db is None:
        async with get_db_session() as session:
            return EventService(session)
    return EventService(db)


# Default event subscriptions for new users
DEFAULT_SUBSCRIPTIONS = [
    {
        "event_type": EventType.DOCUMENT_UPLOADED,
        "actions": [
            EventActionConfig(
                action_type=ActionType.PROCESS_DOCUMENT,
                config={"chunking_strategy": "hybrid"},
                delay_seconds=5  # Small delay to ensure file is fully uploaded
            )
        ]
    },
    {
        "event_type": EventType.DOCUMENT_PROCESSED,
        "actions": [
            EventActionConfig(
                action_type=ActionType.SEND_NOTIFICATION,
                config={
                    "type": "success",
                    "message": "Document '{filename}' has been processed successfully with {chunk_count} chunks."
                }
            ),
            EventActionConfig(
                action_type=ActionType.UPDATE_STATISTICS,
                config={"type": "documents_processed", "increment": 1}
            )
        ]
    },
    {
        "event_type": EventType.CONVERSATION_STARTED,
        "actions": [
            EventActionConfig(
                action_type=ActionType.LOG_ANALYTICS,
                config={"properties": {"conversation_start": True}}
            )
        ]
    }
]


async def setup_default_subscriptions(
    user_id: str,
    tenant_id: str,
    event_service: EventService
) -> None:
    """Setup default event subscriptions for new user"""
    try:
        for subscription_config in DEFAULT_SUBSCRIPTIONS:
            await event_service.create_subscription(
                user_id=user_id,
                tenant_id=tenant_id,
                event_type=subscription_config["event_type"],
                actions=subscription_config["actions"],
                name=f"Default: {subscription_config['event_type'].value}",
                description="Automatically created default subscription"
            )
        
        logger.info(f"Default event subscriptions created for user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to setup default subscriptions: {e}")
        raise