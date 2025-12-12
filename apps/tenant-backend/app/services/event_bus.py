"""
Tenant Event Bus System

Implements event-driven architecture for automation triggers with perfect
tenant isolation and capability-based execution.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from enum import Enum
import json
from pathlib import Path

from app.core.path_security import sanitize_tenant_domain

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types of automation triggers"""
    CRON = "cron"              # Time-based
    WEBHOOK = "webhook"        # External HTTP
    EVENT = "event"            # Internal events
    CHAIN = "chain"            # Triggered by other automations
    MANUAL = "manual"          # User-initiated


# Event catalog with required fields
EVENT_CATALOG = {
    "document.uploaded": ["document_id", "dataset_id", "filename"],
    "document.processed": ["document_id", "chunks_created"],
    "agent.created": ["agent_id", "name", "owner_id"],
    "chat.started": ["conversation_id", "agent_id"],
    "resource.shared": ["resource_id", "access_group", "shared_with"],
    "quota.warning": ["resource_type", "current_usage", "limit"],
    "automation.completed": ["automation_id", "result", "duration_ms"],
    "automation.failed": ["automation_id", "error", "retry_count"]
}


@dataclass
class Event:
    """Event data structure"""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: str = ""
    tenant: str = ""
    user: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "id": self.id,
            "type": self.type,
            "tenant": self.tenant,
            "user": self.user,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dictionary"""
        return cls(
            id=data.get("id", str(uuid4())),
            type=data.get("type", ""),
            tenant=data.get("tenant", ""),
            user=data.get("user", ""),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
            data=data.get("data", {}),
            metadata=data.get("metadata", {})
        )


@dataclass
class Automation:
    """Automation configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    owner_id: str = ""
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    triggers_chain: bool = False
    chain_targets: List[str] = field(default_factory=list)
    max_retries: int = 3
    timeout_seconds: int = 300
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def matches_event(self, event: Event) -> bool:
        """Check if automation should trigger for event"""
        if not self.is_active:
            return False
        
        if self.trigger_type != TriggerType.EVENT:
            return False
        
        # Check event type matches
        event_types = self.trigger_config.get("event_types", [])
        if event.type not in event_types:
            return False
        
        # Check conditions
        for condition in self.conditions:
            if not self._evaluate_condition(condition, event):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: Dict[str, Any], event: Event) -> bool:
        """Evaluate a single condition"""
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        
        # Get field value from event
        if "." in field:
            parts = field.split(".")
            # Handle data.field paths by starting from the event object
            if parts[0] == "data":
                event_value = event.data
                parts = parts[1:]  # Skip the "data" part
            else:
                event_value = event
            
            for part in parts:
                if isinstance(event_value, dict):
                    event_value = event_value.get(part)
                elif hasattr(event_value, part):
                    event_value = getattr(event_value, part)
                else:
                    return False
        else:
            event_value = getattr(event, field, None)
        
        # Evaluate condition
        if operator == "equals":
            return event_value == value
        elif operator == "not_equals":
            return event_value != value
        elif operator == "contains":
            return value in str(event_value)
        elif operator == "greater_than":
            return float(event_value) > float(value)
        elif operator == "less_than":
            return float(event_value) < float(value)
        else:
            return False


class TenantEventBus:
    """
    Event system for automation triggers with tenant isolation.
    
    Features:
    - Perfect tenant isolation through file-based storage
    - Event persistence and replay capability
    - Automation matching and triggering
    - Access control for automation execution
    """
    
    def __init__(self, tenant_domain: str, base_path: Optional[Path] = None):
        self.tenant_domain = tenant_domain
        # Sanitize tenant_domain to prevent path traversal
        safe_tenant = sanitize_tenant_domain(tenant_domain)
        self.base_path = base_path or (Path("/data") / safe_tenant / "events")
        self.event_store_path = self.base_path / "store"
        self.automations_path = self.base_path / "automations"
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.running_automations: Dict[str, asyncio.Task] = {}
        
        # Ensure directories exist with proper permissions
        self._ensure_directories()
        
        logger.info(f"TenantEventBus initialized for {tenant_domain}")
    
    def _ensure_directories(self):
        """Ensure event directories exist with proper permissions"""
        import os
        import stat
        
        for path in [self.event_store_path, self.automations_path]:
            path.mkdir(parents=True, exist_ok=True)
            # Set permissions to 700 (owner only)
            # codeql[py/path-injection] paths derived from sanitize_tenant_domain() at line 175
            os.chmod(path, stat.S_IRWXU)
    
    async def emit_event(
        self,
        event_type: str,
        user_id: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Event:
        """
        Emit an event and trigger matching automations.
        
        Args:
            event_type: Type of event from EVENT_CATALOG
            user_id: User who triggered the event
            data: Event data
            metadata: Optional metadata
            
        Returns:
            Created event
        """
        # Validate event type
        if event_type not in EVENT_CATALOG:
            logger.warning(f"Unknown event type: {event_type}")
        
        # Create event
        event = Event(
            type=event_type,
            tenant=self.tenant_domain,
            user=user_id,
            data=data,
            metadata=metadata or {}
        )
        
        # Store event
        await self._store_event(event)
        
        # Find matching automations
        automations = await self._find_matching_automations(event)
        
        # Trigger automations with access control
        for automation in automations:
            if await self._can_trigger(user_id, automation):
                asyncio.create_task(self._trigger_automation(automation, event))
        
        # Call registered handlers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                asyncio.create_task(handler(event))
        
        logger.info(f"Event emitted: {event_type} by {user_id}")
        return event
    
    async def _store_event(self, event: Event):
        """Store event to file system"""
        # Create daily event file
        date_str = event.timestamp.strftime("%Y-%m-%d")
        event_file = self.event_store_path / f"events_{date_str}.jsonl"
        
        # Append event as JSON line
        with open(event_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
    
    async def _find_matching_automations(self, event: Event) -> List[Automation]:
        """Find automations that match the event"""
        matching = []
        
        # Load all automations from file system
        if self.automations_path.exists():
            for automation_file in self.automations_path.glob("*.json"):
                try:
                    with open(automation_file, "r") as f:
                        automation_data = json.load(f)
                        automation = Automation(**automation_data)
                        
                        if automation.matches_event(event):
                            matching.append(automation)
                
                except Exception as e:
                    logger.error(f"Error loading automation {automation_file}: {e}")
        
        return matching
    
    async def _can_trigger(self, user_id: str, automation: Automation) -> bool:
        """Check if user can trigger automation"""
        # Owner can always trigger their automations
        if automation.owner_id == user_id:
            return True
        
        # Check if automation is public or shared
        # This would integrate with AccessController
        # For now, only owner can trigger
        return False
    
    async def _trigger_automation(self, automation: Automation, event: Event):
        """Trigger automation execution"""
        try:
            # Check if automation is already running
            if automation.id in self.running_automations:
                logger.info(f"Automation {automation.id} already running, skipping")
                return
            
            # Create task for automation execution
            task = asyncio.create_task(
                self._execute_automation(automation, event)
            )
            self.running_automations[automation.id] = task
            
            # Wait for completion with timeout
            await asyncio.wait_for(task, timeout=automation.timeout_seconds)
            
        except asyncio.TimeoutError:
            logger.error(f"Automation {automation.id} timed out")
            await self.emit_event(
                "automation.failed",
                automation.owner_id,
                {
                    "automation_id": automation.id,
                    "error": "Timeout",
                    "retry_count": 0
                }
            )
        except Exception as e:
            logger.error(f"Error triggering automation {automation.id}: {e}")
            await self.emit_event(
                "automation.failed",
                automation.owner_id,
                {
                    "automation_id": automation.id,
                    "error": str(e),
                    "retry_count": 0
                }
            )
        finally:
            # Remove from running automations
            self.running_automations.pop(automation.id, None)
    
    async def _execute_automation(self, automation: Automation, event: Event) -> Any:
        """Execute automation actions"""
        start_time = datetime.utcnow()
        results = []
        
        try:
            # Execute each action in sequence
            for action in automation.actions:
                result = await self._execute_action(action, event, automation)
                results.append(result)
            
            # Calculate duration
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Emit completion event
            await self.emit_event(
                "automation.completed",
                automation.owner_id,
                {
                    "automation_id": automation.id,
                    "result": results,
                    "duration_ms": duration_ms
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing automation {automation.id}: {e}")
            raise
    
    async def _execute_action(
        self,
        action: Dict[str, Any],
        event: Event,
        automation: Automation
    ) -> Any:
        """Execute a single action"""
        action_type = action.get("type")
        
        if action_type == "webhook":
            return await self._execute_webhook_action(action, event)
        elif action_type == "email":
            return await self._execute_email_action(action, event)
        elif action_type == "log":
            return await self._execute_log_action(action, event)
        elif action_type == "chain":
            return await self._execute_chain_action(action, event, automation)
        else:
            logger.warning(f"Unknown action type: {action_type}")
            return None
    
    async def _execute_webhook_action(
        self,
        action: Dict[str, Any],
        event: Event
    ) -> Dict[str, Any]:
        """Execute webhook action (mock implementation)"""
        url = action.get("url")
        method = action.get("method", "POST")
        headers = action.get("headers", {})
        body = action.get("body", event.to_dict())
        
        logger.info(f"Mock webhook call to {url}")
        
        # In production, use httpx or aiohttp to make actual HTTP request
        return {
            "status": "success",
            "url": url,
            "method": method,
            "mock": True
        }
    
    async def _execute_email_action(
        self,
        action: Dict[str, Any],
        event: Event
    ) -> Dict[str, Any]:
        """Execute email action (mock implementation)"""
        to = action.get("to")
        subject = action.get("subject")
        body = action.get("body")
        
        logger.info(f"Mock email to {to}: {subject}")
        
        # In production, integrate with email service
        return {
            "status": "success",
            "to": to,
            "subject": subject,
            "mock": True
        }
    
    async def _execute_log_action(
        self,
        action: Dict[str, Any],
        event: Event
    ) -> Dict[str, Any]:
        """Execute log action"""
        message = action.get("message", f"Event: {event.type}")
        level = action.get("level", "info")
        
        if level == "debug":
            logger.debug(message)
        elif level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        
        return {
            "status": "success",
            "message": message,
            "level": level
        }
    
    async def _execute_chain_action(
        self,
        action: Dict[str, Any],
        event: Event,
        automation: Automation
    ) -> Dict[str, Any]:
        """Execute chain action to trigger other automations"""
        target_automation_id = action.get("target_automation_id")
        
        if not target_automation_id:
            return {"status": "error", "message": "No target automation specified"}
        
        # Emit chain event
        chain_event = await self.emit_event(
            "automation.chain",
            automation.owner_id,
            {
                "source_automation": automation.id,
                "target_automation": target_automation_id,
                "original_event": event.to_dict()
            }
        )
        
        return {
            "status": "success",
            "chain_event_id": chain_event.id,
            "target_automation": target_automation_id
        }
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def create_automation(
        self,
        name: str,
        owner_id: str,
        trigger_type: TriggerType,
        trigger_config: Dict[str, Any],
        actions: List[Dict[str, Any]],
        conditions: Optional[List[Dict[str, Any]]] = None
    ) -> Automation:
        """Create and save a new automation"""
        automation = Automation(
            name=name,
            owner_id=owner_id,
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            actions=actions,
            conditions=conditions or []
        )
        
        # Save to file system
        automation_file = self.automations_path / f"{automation.id}.json"
        with open(automation_file, "w") as f:
            json.dump({
                "id": automation.id,
                "name": automation.name,
                "owner_id": automation.owner_id,
                "trigger_type": automation.trigger_type.value,
                "trigger_config": automation.trigger_config,
                "conditions": automation.conditions,
                "actions": automation.actions,
                "triggers_chain": automation.triggers_chain,
                "chain_targets": automation.chain_targets,
                "max_retries": automation.max_retries,
                "timeout_seconds": automation.timeout_seconds,
                "is_active": automation.is_active,
                "created_at": automation.created_at.isoformat(),
                "updated_at": automation.updated_at.isoformat()
            }, f, indent=2)
        
        logger.info(f"Created automation: {automation.name} ({automation.id})")
        return automation
    
    async def get_automation(self, automation_id: str) -> Optional[Automation]:
        """Get automation by ID"""
        automation_file = self.automations_path / f"{automation_id}.json"
        
        if not automation_file.exists():
            return None
        
        try:
            with open(automation_file, "r") as f:
                data = json.load(f)
                data["trigger_type"] = TriggerType(data["trigger_type"])
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                return Automation(**data)
        except Exception as e:
            logger.error(f"Error loading automation {automation_id}: {e}")
            return None
    
    async def list_automations(self, owner_id: Optional[str] = None) -> List[Automation]:
        """List all automations, optionally filtered by owner"""
        automations = []
        
        if self.automations_path.exists():
            for automation_file in self.automations_path.glob("*.json"):
                try:
                    with open(automation_file, "r") as f:
                        data = json.load(f)
                        
                        # Filter by owner if specified
                        if owner_id and data.get("owner_id") != owner_id:
                            continue
                        
                        data["trigger_type"] = TriggerType(data["trigger_type"])
                        data["created_at"] = datetime.fromisoformat(data["created_at"])
                        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                        automations.append(Automation(**data))
                
                except Exception as e:
                    logger.error(f"Error loading automation {automation_file}: {e}")
        
        return automations
    
    async def delete_automation(self, automation_id: str, owner_id: str) -> bool:
        """Delete an automation"""
        automation = await self.get_automation(automation_id)
        
        if not automation:
            return False
        
        # Check ownership
        if automation.owner_id != owner_id:
            logger.warning(f"User {owner_id} attempted to delete automation owned by {automation.owner_id}")
            return False
        
        # Delete file
        automation_file = self.automations_path / f"{automation_id}.json"
        automation_file.unlink()
        
        logger.info(f"Deleted automation: {automation_id}")
        return True
    
    async def get_event_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history with optional filters"""
        events = []
        
        # Determine date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Iterate through daily event files
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            event_file = self.event_store_path / f"events_{date_str}.jsonl"
            
            if event_file.exists():
                with open(event_file, "r") as f:
                    for line in f:
                        try:
                            event_data = json.loads(line)
                            event = Event.from_dict(event_data)
                            
                            # Apply filters
                            if event_type and event.type != event_type:
                                continue
                            if user_id and event.user != user_id:
                                continue
                            
                            events.append(event)
                            
                            if len(events) >= limit:
                                return events
                        
                        except Exception as e:
                            logger.error(f"Error parsing event: {e}")
            
            # Move to next day
            current_date = current_date.replace(day=current_date.day + 1)
        
        return events