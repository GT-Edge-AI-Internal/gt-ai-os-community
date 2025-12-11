"""
Event Automation API endpoints for GT 2.0 Tenant Backend

Manages event subscriptions, triggers, and automation workflows
with perfect tenant isolation.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_current_user_email, get_tenant_info
from app.services.event_service import EventService, EventType, ActionType, EventActionConfig
from app.schemas.event import (
    EventSubscriptionCreate, EventSubscriptionResponse, EventActionCreate,
    EventResponse, EventStatistics, ScheduledTaskResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])


@router.post("/subscriptions", response_model=EventSubscriptionResponse)
async def create_event_subscription(
    subscription: EventSubscriptionCreate,
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new event subscription"""
    try:
        event_service = EventService(db)
        
        # Convert actions
        actions = []
        for action_data in subscription.actions:
            action_config = EventActionConfig(
                action_type=ActionType(action_data.action_type),
                config=action_data.config,
                delay_seconds=action_data.delay_seconds,
                retry_count=action_data.retry_count,
                retry_delay=action_data.retry_delay,
                condition=action_data.condition
            )
            actions.append(action_config)
        
        subscription_id = await event_service.create_subscription(
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            event_type=EventType(subscription.event_type),
            actions=actions,
            name=subscription.name,
            description=subscription.description
        )
        
        # Get created subscription
        subscriptions = await event_service.get_user_subscriptions(
            current_user, tenant_info["tenant_id"]
        )
        created_subscription = next(
            (s for s in subscriptions if s.id == subscription_id), None
        )
        
        if not created_subscription:
            raise HTTPException(status_code=500, detail="Failed to retrieve created subscription")
        
        return EventSubscriptionResponse.from_orm(created_subscription)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create event subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions", response_model=List[EventSubscriptionResponse])
async def list_event_subscriptions(
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """List user's event subscriptions"""
    try:
        event_service = EventService(db)
        subscriptions = await event_service.get_user_subscriptions(
            current_user, tenant_info["tenant_id"]
        )
        
        return [EventSubscriptionResponse.from_orm(sub) for sub in subscriptions]
        
    except Exception as e:
        logger.error(f"Failed to list event subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/subscriptions/{subscription_id}/status")
async def update_subscription_status(
    subscription_id: str,
    is_active: bool,
    current_user: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db_session)
):
    """Update event subscription status"""
    try:
        event_service = EventService(db)
        success = await event_service.update_subscription_status(
            subscription_id, current_user, is_active
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return JSONResponse(content={
            "message": f"Subscription {'activated' if is_active else 'deactivated'} successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update subscription status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscriptions/{subscription_id}")
async def delete_event_subscription(
    subscription_id: str,
    current_user: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete event subscription"""
    try:
        event_service = EventService(db)
        success = await event_service.delete_subscription(subscription_id, current_user)
        
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return JSONResponse(content={"message": "Subscription deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emit")
async def emit_event(
    event_type: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Manually emit an event"""
    try:
        event_service = EventService(db)
        
        # Validate event type
        try:
            event_type_enum = EventType(event_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
        
        event_id = await event_service.emit_event(
            event_type=event_type_enum,
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            data=data,
            metadata=metadata
        )
        
        return JSONResponse(content={
            "event_id": event_id,
            "message": "Event emitted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to emit event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[EventResponse])
async def get_event_history(
    event_types: Optional[List[str]] = Query(None, description="Filter by event types"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Get event history for user"""
    try:
        event_service = EventService(db)
        
        # Convert event types if provided
        event_type_enums = None
        if event_types:
            try:
                event_type_enums = [EventType(et) for et in event_types]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
        
        events = await event_service.get_event_history(
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            event_types=event_type_enums,
            limit=limit,
            offset=offset
        )
        
        return [EventResponse.from_orm(event) for event in events]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get event history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=EventStatistics)
async def get_event_statistics(
    days: int = Query(30, ge=1, le=365),
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Get event statistics for user"""
    try:
        event_service = EventService(db)
        stats = await event_service.get_event_statistics(
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            days=days
        )
        
        return EventStatistics(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get event statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def get_available_event_types():
    """Get available event types and actions"""
    return JSONResponse(content={
        "event_types": [
            {"value": et.value, "description": et.value.replace("_", " ").title()}
            for et in EventType
        ],
        "action_types": [
            {"value": at.value, "description": at.value.replace("_", " ").title()}
            for at in ActionType
        ]
    })


# Document automation endpoints
@router.post("/documents/{document_id}/auto-process")
async def trigger_document_processing(
    document_id: int,
    chunking_strategy: Optional[str] = Query("hybrid", description="Chunking strategy"),
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Trigger automated document processing"""
    try:
        event_service = EventService(db)
        
        event_id = await event_service.emit_event(
            event_type=EventType.DOCUMENT_UPLOADED,
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            data={
                "document_id": document_id,
                "filename": f"document_{document_id}",
                "chunking_strategy": chunking_strategy,
                "manual_trigger": True
            }
        )
        
        return JSONResponse(content={
            "event_id": event_id,
            "message": "Document processing automation triggered"
        })
        
    except Exception as e:
        logger.error(f"Failed to trigger document processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Conversation automation endpoints
@router.post("/conversations/{conversation_id}/auto-analyze")
async def trigger_conversation_analysis(
    conversation_id: int,
    analysis_type: str = Query("sentiment", description="Type of analysis"),
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Trigger automated conversation analysis"""
    try:
        event_service = EventService(db)
        
        event_id = await event_service.emit_event(
            event_type=EventType.CONVERSATION_STARTED,
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            data={
                "conversation_id": conversation_id,
                "analysis_type": analysis_type,
                "manual_trigger": True
            }
        )
        
        return JSONResponse(content={
            "event_id": event_id,
            "message": "Conversation analysis automation triggered"
        })
        
    except Exception as e:
        logger.error(f"Failed to trigger conversation analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Default subscriptions endpoint
@router.post("/setup-defaults")
async def setup_default_subscriptions(
    current_user: str = Depends(get_current_user_email),
    tenant_info: Dict[str, str] = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """Setup default event subscriptions for user"""
    try:
        from app.services.event_service import setup_default_subscriptions
        
        event_service = EventService(db)
        await setup_default_subscriptions(
            user_id=current_user,
            tenant_id=tenant_info["tenant_id"],
            event_service=event_service
        )
        
        return JSONResponse(content={
            "message": "Default event subscriptions created successfully"
        })
        
    except Exception as e:
        logger.error(f"Failed to setup default subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))