"""
Unit Tests for Event & Automation System

Tests event bus, automation chain executor, and webhook handling
with tenant isolation and capability-based access control.
"""

import pytest
import asyncio
import tempfile
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from app.services.event_bus import (
    TenantEventBus, Event, Automation, TriggerType, EVENT_CATALOG
)
from app.services.automation_executor import (
    AutomationChainExecutor, ExecutionContext, ChainDepthExceeded
)


class TestEvent:
    """Test Event data structure"""
    
    def test_event_creation(self):
        """Test event creation and serialization"""
        event = Event(
            type="document.uploaded",
            tenant="customer1.com",
            user="test@example.com",
            data={"document_id": "doc123", "filename": "test.pdf"}
        )
        
        assert event.type == "document.uploaded"
        assert event.tenant == "customer1.com"
        assert event.user == "test@example.com"
        assert event.data["document_id"] == "doc123"
        assert event.id  # Should have generated ID
        assert isinstance(event.timestamp, datetime)
    
    def test_event_serialization(self):
        """Test event to/from dict conversion"""
        original = Event(
            type="test.event",
            tenant="test.com",
            user="user@test.com",
            data={"key": "value"}
        )
        
        # Convert to dict and back
        event_dict = original.to_dict()
        restored = Event.from_dict(event_dict)
        
        assert restored.type == original.type
        assert restored.tenant == original.tenant
        assert restored.user == original.user
        assert restored.data == original.data
        assert restored.id == original.id


class TestAutomation:
    """Test Automation configuration"""
    
    def test_automation_creation(self):
        """Test automation creation"""
        automation = Automation(
            name="Test Automation",
            owner_id="user@test.com",
            trigger_type=TriggerType.EVENT,
            trigger_config={"event_types": ["document.uploaded"]},
            actions=[{"type": "log", "message": "Document uploaded"}]
        )
        
        assert automation.name == "Test Automation"
        assert automation.trigger_type == TriggerType.EVENT
        assert automation.is_active == True
        assert len(automation.actions) == 1
    
    def test_event_matching(self):
        """Test automation event matching"""
        automation = Automation(
            name="Document Handler",
            trigger_type=TriggerType.EVENT,
            trigger_config={"event_types": ["document.uploaded", "document.processed"]},
            conditions=[
                {"field": "data.filename", "operator": "contains", "value": ".pdf"}
            ],
            actions=[{"type": "log", "message": "PDF processed"}]
        )
        
        # Matching event
        matching_event = Event(
            type="document.uploaded",
            data={"filename": "test.pdf"}
        )
        assert automation.matches_event(matching_event) == True
        
        # Non-matching event type
        wrong_type_event = Event(
            type="user.login",
            data={"filename": "test.pdf"}
        )
        assert automation.matches_event(wrong_type_event) == False
        
        # Non-matching condition
        wrong_condition_event = Event(
            type="document.uploaded",
            data={"filename": "test.txt"}
        )
        assert automation.matches_event(wrong_condition_event) == False
    
    def test_condition_evaluation(self):
        """Test condition evaluation logic"""
        automation = Automation()
        
        event = Event(
            type="test",
            user="user123",
            data={"count": 5, "status": "active"}
        )
        
        # Equals condition
        condition = {"field": "data.status", "operator": "equals", "value": "active"}
        assert automation._evaluate_condition(condition, event) == True
        
        # Not equals condition
        condition = {"field": "data.status", "operator": "not_equals", "value": "inactive"}
        assert automation._evaluate_condition(condition, event) == True
        
        # Contains condition
        condition = {"field": "user", "operator": "contains", "value": "user"}
        assert automation._evaluate_condition(condition, event) == True
        
        # Greater than condition
        condition = {"field": "data.count", "operator": "greater_than", "value": "3"}
        assert automation._evaluate_condition(condition, event) == True
        
        # Less than condition
        condition = {"field": "data.count", "operator": "less_than", "value": "10"}
        assert automation._evaluate_condition(condition, event) == True


class TestTenantEventBus:
    """Test Tenant Event Bus functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def event_bus(self, temp_dir):
        """Create event bus with temporary storage"""
        return TenantEventBus("test.com", base_path=temp_dir)
    
    @pytest.mark.asyncio
    async def test_event_emission(self, event_bus):
        """Test event emission and storage"""
        event = await event_bus.emit_event(
            event_type="document.uploaded",
            user_id="test@example.com",
            data={"document_id": "doc123", "filename": "test.pdf"}
        )
        
        assert event.type == "document.uploaded"
        assert event.tenant == "test.com"
        assert event.user == "test@example.com"
        assert event.data["document_id"] == "doc123"
        
        # Check event was stored
        date_str = event.timestamp.strftime("%Y-%m-%d")
        event_file = event_bus.event_store_path / f"events_{date_str}.jsonl"
        assert event_file.exists()
        
        # Read and verify stored event
        with open(event_file, "r") as f:
            stored_event = json.loads(f.read().strip())
            assert stored_event["id"] == event.id
            assert stored_event["type"] == "document.uploaded"
    
    @pytest.mark.asyncio
    async def test_automation_creation(self, event_bus):
        """Test automation creation and storage"""
        automation = await event_bus.create_automation(
            name="Test Automation",
            owner_id="test@example.com",
            trigger_type=TriggerType.EVENT,
            trigger_config={"event_types": ["document.uploaded"]},
            actions=[{"type": "log", "message": "Document uploaded"}]
        )
        
        assert automation.name == "Test Automation"
        assert automation.owner_id == "test@example.com"
        
        # Check automation was stored
        automation_file = event_bus.automations_path / f"{automation.id}.json"
        assert automation_file.exists()
        
        # Verify it can be loaded
        loaded = await event_bus.get_automation(automation.id)
        assert loaded.name == automation.name
        assert loaded.owner_id == automation.owner_id
    
    @pytest.mark.asyncio
    async def test_automation_matching(self, event_bus):
        """Test automation matching and triggering"""
        # Create automation
        automation = await event_bus.create_automation(
            name="PDF Handler",
            owner_id="test@example.com",
            trigger_type=TriggerType.EVENT,
            trigger_config={"event_types": ["document.uploaded"]},
            actions=[{"type": "log", "message": "PDF processed"}],
            conditions=[
                {"field": "data.filename", "operator": "contains", "value": ".pdf"}
            ]
        )
        
        # Track triggered automations
        triggered_automations = []
        
        async def mock_trigger(auto, event):
            triggered_automations.append((auto.id, event.type))
        
        # Replace trigger method
        event_bus._trigger_automation = mock_trigger
        
        # Emit matching event
        await event_bus.emit_event(
            event_type="document.uploaded",
            user_id="test@example.com",
            data={"filename": "test.pdf", "document_id": "doc123"}
        )
        
        # Should have triggered automation
        assert len(triggered_automations) == 1
        assert triggered_automations[0][0] == automation.id
        assert triggered_automations[0][1] == "document.uploaded"
    
    @pytest.mark.asyncio
    async def test_event_handlers(self, event_bus):
        """Test event handler registration and calling"""
        handled_events = []
        
        async def test_handler(event):
            handled_events.append(event.type)
        
        # Register handler
        event_bus.register_handler("test.event", test_handler)
        
        # Emit event
        await event_bus.emit_event(
            event_type="test.event",
            user_id="test@example.com",
            data={"test": True}
        )
        
        # Give handlers time to run
        await asyncio.sleep(0.1)
        
        assert "test.event" in handled_events
    
    @pytest.mark.asyncio
    async def test_event_history(self, event_bus):
        """Test event history retrieval"""
        # Emit several events
        for i in range(5):
            await event_bus.emit_event(
                event_type="test.event",
                user_id=f"user{i}@example.com",
                data={"index": i}
            )
        
        # Get all events
        history = await event_bus.get_event_history(limit=10)
        assert len(history) == 5
        
        # Get events for specific user
        user_history = await event_bus.get_event_history(
            user_id="user1@example.com",
            limit=10
        )
        assert len(user_history) == 1
        assert user_history[0].user == "user1@example.com"
        
        # Get events by type
        type_history = await event_bus.get_event_history(
            event_type="test.event",
            limit=10
        )
        assert len(type_history) == 5
    
    @pytest.mark.asyncio
    async def test_automation_ownership(self, event_bus):
        """Test automation access control"""
        # Create automation
        automation = await event_bus.create_automation(
            name="Owner Test",
            owner_id="owner@example.com",
            trigger_type=TriggerType.MANUAL,
            trigger_config={},
            actions=[{"type": "log", "message": "Test"}]
        )
        
        # Owner can delete
        success = await event_bus.delete_automation(automation.id, "owner@example.com")
        assert success == True
        
        # Create another automation
        automation2 = await event_bus.create_automation(
            name="Owner Test 2",
            owner_id="owner@example.com",
            trigger_type=TriggerType.MANUAL,
            trigger_config={},
            actions=[{"type": "log", "message": "Test"}]
        )
        
        # Non-owner cannot delete
        success = await event_bus.delete_automation(automation2.id, "other@example.com")
        assert success == False
        
        # Automation should still exist
        existing = await event_bus.get_automation(automation2.id)
        assert existing is not None


class TestAutomationChainExecutor:
    """Test Automation Chain Executor"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def event_bus(self, temp_dir):
        """Create event bus with temporary storage"""
        return TenantEventBus("test.com", base_path=temp_dir)
    
    @pytest.fixture
    def executor(self, event_bus, temp_dir):
        """Create automation executor"""
        return AutomationChainExecutor("test.com", event_bus, base_path=temp_dir)
    
    @pytest.fixture
    def sample_token(self):
        """Sample capability token data"""
        return {
            "tenant_id": "test.com",
            "sub": "test@example.com",
            "capabilities": [
                {"resource": "automation:api_calls"},
                {"resource": "automation:logic"}
            ],
            "constraints": {
                "max_automation_chain_depth": 3,
                "automation_timeout_seconds": 60,
                "max_loop_iterations": 50
            }
        }
    
    def test_execution_context(self):
        """Test execution context management"""
        context = ExecutionContext("auto123")
        
        assert context.automation_id == "auto123"
        assert context.chain_depth == 0
        assert context.execution_history == []
        assert context.variables == {}
        
        # Add execution
        context.add_execution("log", {"status": "success"}, 150.5)
        
        assert len(context.execution_history) == 1
        assert context.execution_history[0]["action"] == "log"
        assert context.execution_history[0]["duration_ms"] == 150.5
    
    @pytest.mark.asyncio
    async def test_chain_depth_limit(self, executor, sample_token):
        """Test chain depth enforcement"""
        automation = Automation(
            name="Deep Chain",
            trigger_type=TriggerType.MANUAL,
            actions=[{"type": "log", "message": "test"}]
        )
        
        event = Event(type="test", tenant="test.com")
        
        # Mock token verification
        with patch('app.services.automation_executor.verify_capability_token') as mock_verify:
            mock_verify.return_value = sample_token
            
            # Should succeed at depth 2
            result = await executor.execute_chain(automation, event, "mock_token", 2)
            assert result is not None
            
            # Should fail at depth 3 (limit is 3, so depth 3 equals limit)
            with pytest.raises(ChainDepthExceeded):
                await executor.execute_chain(automation, event, "mock_token", 3)
    
    @pytest.mark.asyncio
    async def test_action_execution(self, executor, sample_token):
        """Test individual action execution"""
        context = ExecutionContext("test_auto")
        event = Event(type="test", tenant="test.com")
        
        # Test wait action
        wait_action = {"type": "wait", "duration": 0.1}  # Very short wait
        result = await executor._execute_action(wait_action, event, context, sample_token)
        assert result["waited"] == 0.1
        
        # Test variable set action
        var_action = {
            "type": "variable_set",
            "variables": {"test_var": "test_value", "number": 42}
        }
        result = await executor._execute_action(var_action, event, context, sample_token)
        assert context.variables["test_var"] == "test_value"
        assert context.variables["number"] == 42
    
    @pytest.mark.asyncio
    async def test_conditional_execution(self, executor, sample_token):
        """Test conditional action execution"""
        context = ExecutionContext("test_auto")
        context.variables = {"status": "success", "count": 5}
        
        # Conditional that should execute 'then' branch
        conditional_action = {
            "type": "conditional",
            "condition": {
                "left": "$status",
                "operator": "equals",
                "right": "success"
            },
            "then": [{"type": "variable_set", "variables": {"result": "passed"}}],
            "else": [{"type": "variable_set", "variables": {"result": "failed"}}]
        }
        
        result = await executor._execute_action(conditional_action, None, context, sample_token)
        
        assert result["branch"] == "then"
        assert context.variables["result"] == "passed"
        
        # Conditional that should execute 'else' branch
        context.variables["status"] = "failure"
        
        result = await executor._execute_action(conditional_action, None, context, sample_token)
        
        assert result["branch"] == "else"
        assert context.variables["result"] == "failed"
    
    @pytest.mark.asyncio
    async def test_loop_execution(self, executor, sample_token):
        """Test loop action execution"""
        context = ExecutionContext("test_auto")
        context.variables = {"items": ["a", "b", "c"]}
        
        loop_action = {
            "type": "loop",
            "items": "$items",
            "variable": "current_item",
            "actions": [
                {
                    "type": "variable_set",
                    "variables": {"processed": "${current_item}_processed"}
                }
            ]
        }
        
        event = Event(type="test", tenant="test.com")
        result = await executor._execute_action(loop_action, event, context, sample_token)
        
        assert result["loop_count"] == 3
        assert context.variables["current_item"] == "c"  # Last item
        assert context.variables["processed"] == "c_processed"
    
    @pytest.mark.asyncio
    async def test_data_transform(self, executor):
        """Test data transformation actions"""
        context = ExecutionContext("test_auto")
        context.variables = {
            "json_string": '{"name": "test", "data": {"value": 42}}',
            "object_data": {"user": "john", "settings": {"theme": "dark"}}
        }
        
        # JSON parse transform
        parse_action = {
            "type": "data_transform",
            "transform_type": "json_parse",
            "source": "json_string",
            "target": "parsed_data"
        }
        
        result = await executor._execute_data_transform(parse_action, context)
        assert context.variables["parsed_data"]["name"] == "test"
        assert context.variables["parsed_data"]["data"]["value"] == 42
        
        # Extract transform
        extract_action = {
            "type": "data_transform",
            "transform_type": "extract",
            "source": "object_data",
            "target": "theme",
            "path": "settings.theme"
        }
        
        result = await executor._execute_data_transform(extract_action, context)
        assert context.variables["theme"] == "dark"
    
    @pytest.mark.asyncio
    async def test_variable_substitution(self, executor):
        """Test variable substitution in templates"""
        variables = {
            "user": "john",
            "action": "login",
            "timestamp": "2024-01-01"
        }
        
        # Test ${variable} format
        template = "User ${user} performed ${action} at ${timestamp}"
        result = executor._substitute_variables(template, variables)
        assert result == "User john performed login at 2024-01-01"
        
        # Test $variable format
        template = "User $user performed $action"
        result = executor._substitute_variables(template, variables)
        assert result == "User john performed login"
        
        # Test with missing variable (should leave as-is)
        template = "User ${user} has ${unknown_var}"
        result = executor._substitute_variables(template, variables)
        assert result == "User john has ${unknown_var}"
    
    @pytest.mark.asyncio
    async def test_path_extraction(self, executor):
        """Test nested data path extraction"""
        data = {
            "user": {
                "profile": {
                    "name": "John Doe",
                    "settings": {
                        "theme": "dark",
                        "notifications": True
                    }
                },
                "permissions": ["read", "write"]
            },
            "stats": [10, 20, 30]
        }
        
        # Test nested object access
        assert executor._extract_path(data, "user.profile.name") == "John Doe"
        assert executor._extract_path(data, "user.profile.settings.theme") == "dark"
        
        # Test array access
        assert executor._extract_path(data, "user.permissions.0") == "read"
        assert executor._extract_path(data, "stats.1") == 20
        
        # Test missing path
        assert executor._extract_path(data, "user.profile.missing") is None
        assert executor._extract_path(data, "stats.10") is None
    
    @pytest.mark.asyncio
    async def test_capability_checking(self, executor, sample_token):
        """Test action capability validation"""
        # Action that requires capability
        api_action = {"type": "api_call", "endpoint": "/test"}
        assert executor._is_action_allowed(api_action, sample_token) == True
        
        # Action without required capability
        webhook_action = {"type": "webhook", "url": "http://example.com"}
        assert executor._is_action_allowed(webhook_action, sample_token) == False
        
        # Unknown action (should be allowed)
        unknown_action = {"type": "unknown_action"}
        assert executor._is_action_allowed(unknown_action, sample_token) == True
    
    @pytest.mark.asyncio
    async def test_execution_history_storage(self, executor, temp_dir):
        """Test execution history persistence"""
        context = ExecutionContext("test_automation")
        context.add_execution("log", {"message": "test"}, 100.0)
        context.add_execution("api_call", {"status": 200}, 250.0)
        
        result = {"status": "completed", "actions": 2}
        
        # Store execution
        await executor._store_execution(context, result)
        
        # Check file was created
        execution_files = list(executor.execution_path.glob("test_automation_*.json"))
        assert len(execution_files) == 1
        
        # Read and verify content
        with open(execution_files[0], "r") as f:
            stored_data = json.load(f)
            assert stored_data["automation_id"] == "test_automation"
            assert len(stored_data["execution_history"]) == 2
            assert stored_data["result"] == result
    
    @pytest.mark.asyncio
    async def test_constraint_extraction(self, executor, sample_token):
        """Test constraint value extraction from token"""
        # Existing constraint
        depth = executor._get_constraint(sample_token, "max_automation_chain_depth", 5)
        assert depth == 3
        
        # Non-existing constraint (should return default)
        timeout = executor._get_constraint(sample_token, "non_existent", 100)
        assert timeout == 100
        
        # Missing constraints object
        empty_token = {"tenant_id": "test.com"}
        value = executor._get_constraint(empty_token, "any_key", "default")
        assert value == "default"