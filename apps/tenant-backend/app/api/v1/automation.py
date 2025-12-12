"""
Automation Management API

REST endpoints for creating, managing, and monitoring automations
with capability-based access control.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.services.event_bus import TenantEventBus, TriggerType, EVENT_CATALOG
from app.services.automation_executor import AutomationChainExecutor
from app.core.dependencies import get_current_user, get_tenant_domain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation", tags=["automation"])


class AutomationCreate(BaseModel):
    """Create automation request"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    trigger_type: str = Field(..., regex="^(cron|webhook|event|manual)$")
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(..., min_items=1)
    is_active: bool = True
    max_retries: int = Field(default=3, ge=0, le=5)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class AutomationUpdate(BaseModel):
    """Update automation request"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    trigger_config: Optional[Dict[str, Any]] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=5)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)


class AutomationResponse(BaseModel):
    """Automation response"""
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    trigger_type: str
    trigger_config: Dict[str, Any]
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    is_active: bool
    max_retries: int
    timeout_seconds: int
    created_at: str
    updated_at: str


class TriggerAutomationRequest(BaseModel):
    """Manual trigger request"""
    event_data: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)


@router.get("/catalog/events")
async def get_event_catalog():
    """Get available event types and their required fields"""
    return {
        "events": EVENT_CATALOG,
        "trigger_types": [trigger.value for trigger in TriggerType]
    }


@router.get("/catalog/actions")
async def get_action_catalog():
    """Get available action types and their configurations"""
    return {
        "actions": {
            "webhook": {
                "description": "Send HTTP request to external endpoint",
                "required_fields": ["url"],
                "optional_fields": ["method", "headers", "body"],
                "example": {
                    "type": "webhook",
                    "url": "https://api.example.com/notify",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"message": "Automation triggered"}
                }
            },
            "email": {
                "description": "Send email notification",
                "required_fields": ["to", "subject"],
                "optional_fields": ["body", "template"],
                "example": {
                    "type": "email",
                    "to": "user@example.com",
                    "subject": "Automation Alert",
                    "body": "Your automation has completed"
                }
            },
            "log": {
                "description": "Write to application logs",
                "required_fields": ["message"],
                "optional_fields": ["level"],
                "example": {
                    "type": "log",
                    "message": "Document processed successfully",
                    "level": "info"
                }
            },
            "api_call": {
                "description": "Call internal or external API",
                "required_fields": ["endpoint"],
                "optional_fields": ["method", "headers", "body"],
                "example": {
                    "type": "api_call",
                    "endpoint": "/api/v1/documents/process",
                    "method": "POST",
                    "body": {"document_id": "${document_id}"}
                }
            },
            "data_transform": {
                "description": "Transform data between steps",
                "required_fields": ["transform_type", "source", "target"],
                "optional_fields": ["path", "mapping"],
                "example": {
                    "type": "data_transform",
                    "transform_type": "extract",
                    "source": "api_response",
                    "target": "document_id",
                    "path": "data.document.id"
                }
            },
            "conditional": {
                "description": "Execute actions based on conditions",
                "required_fields": ["condition", "then"],
                "optional_fields": ["else"],
                "example": {
                    "type": "conditional",
                    "condition": {"left": "$status", "operator": "equals", "right": "success"},
                    "then": [{"type": "log", "message": "Success"}],
                    "else": [{"type": "log", "message": "Failed"}]
                }
            }
        }
    }


@router.post("", response_model=AutomationResponse)
async def create_automation(
    automation: AutomationCreate,
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Create a new automation"""
    try:
        # Initialize event bus
        event_bus = TenantEventBus(tenant_domain)
        
        # Convert trigger type to enum
        trigger_type = TriggerType(automation.trigger_type)
        
        # Create automation
        created_automation = await event_bus.create_automation(
            name=automation.name,
            owner_id=current_user,
            trigger_type=trigger_type,
            trigger_config=automation.trigger_config,
            actions=automation.actions,
            conditions=automation.conditions
        )
        
        # Set additional properties
        created_automation.max_retries = automation.max_retries
        created_automation.timeout_seconds = automation.timeout_seconds
        created_automation.is_active = automation.is_active
        
        # Log creation
        await event_bus.emit_event(
            event_type="automation.created",
            user_id=current_user,
            data={
                "automation_id": created_automation.id,
                "name": created_automation.name,
                "trigger_type": trigger_type.value
            }
        )
        
        return AutomationResponse(
            id=created_automation.id,
            name=created_automation.name,
            description=automation.description,
            owner_id=created_automation.owner_id,
            trigger_type=trigger_type.value,
            trigger_config=created_automation.trigger_config,
            conditions=created_automation.conditions,
            actions=created_automation.actions,
            is_active=created_automation.is_active,
            max_retries=created_automation.max_retries,
            timeout_seconds=created_automation.timeout_seconds,
            created_at=created_automation.created_at.isoformat(),
            updated_at=created_automation.updated_at.isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating automation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create automation")


@router.get("", response_model=List[AutomationResponse])
async def list_automations(
    owner_only: bool = True,
    active_only: bool = False,
    trigger_type: Optional[str] = None,
    limit: int = 50,
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """List automations with optional filtering"""
    try:
        event_bus = TenantEventBus(tenant_domain)
        
        # Get automations
        owner_filter = current_user if owner_only else None
        automations = await event_bus.list_automations(owner_id=owner_filter)
        
        # Apply filters
        filtered = []
        for automation in automations:
            if active_only and not automation.is_active:
                continue
            
            if trigger_type and automation.trigger_type.value != trigger_type:
                continue
            
            filtered.append(AutomationResponse(
                id=automation.id,
                name=automation.name,
                description="",  # Not stored in current model
                owner_id=automation.owner_id,
                trigger_type=automation.trigger_type.value,
                trigger_config=automation.trigger_config,
                conditions=automation.conditions,
                actions=automation.actions,
                is_active=automation.is_active,
                max_retries=automation.max_retries,
                timeout_seconds=automation.timeout_seconds,
                created_at=automation.created_at.isoformat(),
                updated_at=automation.updated_at.isoformat()
            ))
        
        # Apply limit
        return filtered[:limit]
        
    except Exception as e:
        logger.error(f"Error listing automations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list automations")


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    automation_id: str,
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Get automation by ID"""
    try:
        event_bus = TenantEventBus(tenant_domain)
        automation = await event_bus.get_automation(automation_id)
        
        if not automation:
            raise HTTPException(status_code=404, detail="Automation not found")
        
        # Check ownership
        if automation.owner_id != current_user:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        return AutomationResponse(
            id=automation.id,
            name=automation.name,
            description="",
            owner_id=automation.owner_id,
            trigger_type=automation.trigger_type.value,
            trigger_config=automation.trigger_config,
            conditions=automation.conditions,
            actions=automation.actions,
            is_active=automation.is_active,
            max_retries=automation.max_retries,
            timeout_seconds=automation.timeout_seconds,
            created_at=automation.created_at.isoformat(),
            updated_at=automation.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation: {e}")
        raise HTTPException(status_code=500, detail="Failed to get automation")


@router.delete("/{automation_id}")
async def delete_automation(
    automation_id: str,
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Delete automation"""
    try:
        event_bus = TenantEventBus(tenant_domain)
        
        # Check if automation exists and user owns it
        automation = await event_bus.get_automation(automation_id)
        if not automation:
            raise HTTPException(status_code=404, detail="Automation not found")
        
        if automation.owner_id != current_user:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Delete automation
        success = await event_bus.delete_automation(automation_id, current_user)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete automation")
        
        # Log deletion
        await event_bus.emit_event(
            event_type="automation.deleted",
            user_id=current_user,
            data={
                "automation_id": automation_id,
                "name": automation.name
            }
        )
        
        return {"status": "deleted", "automation_id": automation_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete automation")


@router.post("/{automation_id}/trigger")
async def trigger_automation(
    automation_id: str,
    trigger_request: TriggerAutomationRequest,
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Manually trigger an automation"""
    try:
        event_bus = TenantEventBus(tenant_domain)
        
        # Get automation
        automation = await event_bus.get_automation(automation_id)
        if not automation:
            raise HTTPException(status_code=404, detail="Automation not found")
        
        # Check ownership
        if automation.owner_id != current_user:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Check if automation supports manual triggering
        if automation.trigger_type != TriggerType.MANUAL:
            raise HTTPException(
                status_code=400,
                detail="Automation does not support manual triggering"
            )
        
        # Create manual trigger event
        await event_bus.emit_event(
            event_type="automation.manual_trigger",
            user_id=current_user,
            data={
                "automation_id": automation_id,
                "trigger_data": trigger_request.event_data,
                "variables": trigger_request.variables
            },
            metadata={
                "trigger_type": TriggerType.MANUAL.value
            }
        )
        
        return {
            "status": "triggered",
            "automation_id": automation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering automation: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger automation")


@router.get("/{automation_id}/executions")
async def get_execution_history(
    automation_id: str,
    limit: int = 10,
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Get execution history for automation"""
    try:
        # Check automation ownership first
        event_bus = TenantEventBus(tenant_domain)
        automation = await event_bus.get_automation(automation_id)
        
        if not automation:
            raise HTTPException(status_code=404, detail="Automation not found")
        
        if automation.owner_id != current_user:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get execution history
        executor = AutomationChainExecutor(tenant_domain, event_bus)
        executions = await executor.get_execution_history(automation_id, limit)
        
        return {
            "automation_id": automation_id,
            "executions": executions,
            "total": len(executions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get execution history")


@router.post("/{automation_id}/test")
async def test_automation(
    automation_id: str,
    test_data: Dict[str, Any] = {},
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Test automation with sample data"""
    try:
        event_bus = TenantEventBus(tenant_domain)
        
        # Get automation
        automation = await event_bus.get_automation(automation_id)
        if not automation:
            raise HTTPException(status_code=404, detail="Automation not found")
        
        # Check ownership
        if automation.owner_id != current_user:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Create test event
        test_event_type = automation.trigger_config.get("event_types", ["test.event"])[0]
        
        await event_bus.emit_event(
            event_type=test_event_type,
            user_id=current_user,
            data={
                "test": True,
                "automation_id": automation_id,
                **test_data
            },
            metadata={
                "test_mode": True,
                "test_timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return {
            "status": "test_triggered",
            "automation_id": automation_id,
            "test_event": test_event_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing automation: {e}")
        raise HTTPException(status_code=500, detail="Failed to test automation")


@router.get("/stats/summary")
async def get_automation_stats(
    current_user: str = Depends(get_current_user),
    tenant_domain: str = Depends(get_tenant_domain)
):
    """Get automation statistics for current user"""
    try:
        event_bus = TenantEventBus(tenant_domain)
        
        # Get user's automations
        automations = await event_bus.list_automations(owner_id=current_user)
        
        # Calculate stats
        total = len(automations)
        active = sum(1 for a in automations if a.is_active)
        by_trigger_type = {}
        
        for automation in automations:
            trigger = automation.trigger_type.value
            by_trigger_type[trigger] = by_trigger_type.get(trigger, 0) + 1
        
        # Get recent events
        recent_events = await event_bus.get_event_history(
            user_id=current_user,
            limit=10
        )
        
        return {
            "total_automations": total,
            "active_automations": active,
            "inactive_automations": total - active,
            "by_trigger_type": by_trigger_type,
            "recent_events": [
                {
                    "type": event.type,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data
                }
                for event in recent_events
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting automation stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get automation stats")