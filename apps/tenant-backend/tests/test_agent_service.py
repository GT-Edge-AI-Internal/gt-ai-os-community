"""
Multi-Agent Orchestration Engine Unit Tests

Tests the AgentService and WorkflowService for tenant-based agent management.
Includes agent lifecycle, execution tracking, memory management, and workflow orchestration.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_service import AgentService, WorkflowService
from app.models.agent import Agent, AgentExecution, AgentMemory, WorkflowDefinition, WorkflowExecution
from app.services.resource_service import ResourceService


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_resource_service():
    """Mock resource service"""
    service = AsyncMock(spec=ResourceService)
    return service


@pytest.fixture
def agent_service(mock_db_session):
    """AgentService instance with mocked dependencies"""
    service = AgentService(mock_db_session)
    service.resource_service = AsyncMock(spec=ResourceService)
    return service


@pytest.fixture
def workflow_service(mock_db_session):
    """WorkflowService instance with mocked dependencies"""
    service = WorkflowService(mock_db_session)
    service.agent_service = AsyncMock(spec=AgentService)
    return service


@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing"""
    return {
        "user_id": "user@example.com",
        "name": "Research Agent",
        "agent_type": "research",
        "prompt_template": "You are a research agent...",
        "description": "AI agent for research tasks",
        "capabilities": ["web_search", "document_analysis"],
        "available_tools": ["search_tool", "analysis_tool"],
        "resource_bindings": ["research_dataset"]
    }


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing"""
    return {
        "user_id": "user@example.com",
        "name": "Research Workflow",
        "workflow_type": "sequential",
        "workflow_definition": {
            "steps": [
                {
                    "type": "agent",
                    "agent_id": "agent-123",
                    "task": "Initial research",
                    "parameters": {"query": "test query"}
                },
                {
                    "type": "delay",
                    "delay_seconds": 1
                },
                {
                    "type": "custom",
                    "name": "Custom processing"
                }
            ]
        },
        "description": "Multi-step research workflow"
    }


class TestAgentService:
    """Test AgentService functionality"""

    async def test_create_agent_success(self, agent_service, sample_agent_data):
        """Test successful agent creation"""
        # Mock database behavior
        agent_service.db.commit = AsyncMock()
        agent_service.db.refresh = AsyncMock()
        
        result = await agent_service.create_agent(**sample_agent_data)
        
        # Verify agent creation
        assert result.user_id == sample_agent_data["user_id"]
        assert result.name == sample_agent_data["name"]
        assert result.agent_type == sample_agent_data["agent_type"]
        assert result.prompt_template == sample_agent_data["prompt_template"]
        
        # Verify database operations
        agent_service.db.add.assert_called_once()
        agent_service.db.commit.assert_called_once()
        agent_service.db.refresh.assert_called_once()

    async def test_get_user_agents_success(self, agent_service):
        """Test retrieving user's agents"""
        # Mock database response
        mock_agents = [
            Agent(
                id="agent-1",
                user_id="user@example.com",
                name="Agent 1",
                agent_type="research",
                prompt_template="Template 1",
                is_active=True
            ),
            Agent(
                id="agent-2",
                user_id="user@example.com",
                name="Agent 2",
                agent_type="coding",
                prompt_template="Template 2",
                is_active=True
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_agents
        agent_service.db.execute.return_value = mock_result
        
        result = await agent_service.get_user_agents("user@example.com")
        
        assert len(result) == 2
        assert result[0].name == "Agent 1"
        assert result[1].name == "Agent 2"
        agent_service.db.execute.assert_called_once()

    async def test_get_agent_by_id_success(self, agent_service):
        """Test retrieving specific agent by ID"""
        # Mock database response
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Test Agent",
            agent_type="research",
            prompt_template="Test template",
            is_active=True
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        agent_service.db.execute.return_value = mock_result
        
        result = await agent_service.get_agent("agent-123", "user@example.com")
        
        assert result is not None
        assert result.id == "agent-123"
        assert result.name == "Test Agent"
        agent_service.db.execute.assert_called_once()

    async def test_get_agent_not_found(self, agent_service):
        """Test agent not found scenario"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        agent_service.db.execute.return_value = mock_result
        
        result = await agent_service.get_agent("nonexistent", "user@example.com")
        
        assert result is None

    async def test_update_agent_success(self, agent_service):
        """Test successful agent update"""
        # Mock existing agent
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Old Name",
            description="Old description",
            agent_type="research",
            prompt_template="Old template"
        )
        
        agent_service.get_agent = AsyncMock(return_value=mock_agent)
        agent_service.db.commit = AsyncMock()
        agent_service.db.refresh = AsyncMock()
        
        updates = {
            "name": "New Name",
            "description": "New description"
        }
        
        result = await agent_service.update_agent("agent-123", "user@example.com", updates)
        
        assert result is not None
        assert result.name == "New Name"
        assert result.description == "New description"
        agent_service.db.commit.assert_called_once()

    async def test_update_agent_not_found(self, agent_service):
        """Test updating non-existent agent"""
        agent_service.get_agent = AsyncMock(return_value=None)
        
        result = await agent_service.update_agent(
            "nonexistent", 
            "user@example.com", 
            {"name": "New Name"}
        )
        
        assert result is None

    async def test_delete_agent_success(self, agent_service):
        """Test successful agent deletion (soft delete)"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Test Agent",
            agent_type="research",
            prompt_template="Template",
            is_active=True
        )
        
        agent_service.get_agent = AsyncMock(return_value=mock_agent)
        agent_service.db.commit = AsyncMock()
        
        result = await agent_service.delete_agent("agent-123", "user@example.com")
        
        assert result is True
        assert mock_agent.is_active is False
        agent_service.db.commit.assert_called_once()

    async def test_delete_agent_not_found(self, agent_service):
        """Test deleting non-existent agent"""
        agent_service.get_agent = AsyncMock(return_value=None)
        
        result = await agent_service.delete_agent("nonexistent", "user@example.com")
        
        assert result is False

    async def test_execute_agent_success(self, agent_service):
        """Test successful agent execution"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Test Agent",
            agent_type="research",
            prompt_template="Template"
        )
        
        agent_service.get_agent = AsyncMock(return_value=mock_agent)
        agent_service.db.add = MagicMock()
        agent_service.db.commit = AsyncMock()
        agent_service.db.refresh = AsyncMock()
        
        # Mock asyncio.create_task to prevent actual background execution
        with patch('asyncio.create_task') as mock_create_task:
            result = await agent_service.execute_agent(
                agent_id="agent-123",
                user_id="user@example.com",
                task_description="Test task",
                task_parameters={"param": "value"}
            )
            
            assert result.agent_id == "agent-123"
            assert result.user_id == "user@example.com"
            assert result.task_description == "Test task"
            assert result.status == "pending"
            
            agent_service.db.add.assert_called_once()
            agent_service.db.commit.assert_called_once()
            mock_create_task.assert_called_once()

    async def test_execute_agent_not_found(self, agent_service):
        """Test executing non-existent agent"""
        agent_service.get_agent = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="Agent agent-123 not found"):
            await agent_service.execute_agent(
                agent_id="agent-123",
                user_id="user@example.com",
                task_description="Test task"
            )

    async def test_execute_research_agent(self, agent_service):
        """Test research agent execution logic"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Research Agent",
            agent_type="research",
            prompt_template="Template"
        )
        
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Research task",
            status="running"
        )
        
        agent_service.db.commit = AsyncMock()
        
        context = {
            'agent': mock_agent,
            'execution': mock_execution,
            'memory': {},
            'available_tools': [],
            'resource_bindings': []
        }
        
        result = await agent_service._execute_research_agent(context)
        
        assert result['type'] == 'research_result'
        assert 'summary' in result
        assert 'findings' in result
        assert 'sources' in result
        assert 'confidence_score' in result
        assert len(result['findings']) == 3

    async def test_execute_coding_agent(self, agent_service):
        """Test coding agent execution logic"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Coding Agent",
            agent_type="coding",
            prompt_template="Template"
        )
        
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Coding task",
            status="running"
        )
        
        agent_service.db.commit = AsyncMock()
        
        context = {
            'agent': mock_agent,
            'execution': mock_execution,
            'memory': {},
            'available_tools': [],
            'resource_bindings': []
        }
        
        result = await agent_service._execute_coding_agent(context)
        
        assert result['type'] == 'coding_result'
        assert 'summary' in result
        assert 'generated_code' in result
        assert 'language' in result
        assert 'test_cases' in result
        assert 'documentation' in result

    async def test_execute_analysis_agent(self, agent_service):
        """Test analysis agent execution logic"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Analysis Agent",
            agent_type="analysis",
            prompt_template="Template"
        )
        
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Analysis task",
            status="running"
        )
        
        agent_service.db.commit = AsyncMock()
        
        context = {
            'agent': mock_agent,
            'execution': mock_execution,
            'memory': {},
            'available_tools': [],
            'resource_bindings': []
        }
        
        result = await agent_service._execute_analysis_agent(context)
        
        assert result['type'] == 'analysis_result'
        assert 'summary' in result
        assert 'insights' in result
        assert 'metrics' in result
        assert 'visualizations' in result
        assert len(result['insights']) == 3

    async def test_get_agent_executions(self, agent_service):
        """Test retrieving agent execution history"""
        mock_executions = [
            AgentExecution(
                id="exec-1",
                agent_id="agent-123",
                user_id="user@example.com",
                task_description="Task 1",
                status="completed"
            ),
            AgentExecution(
                id="exec-2",
                agent_id="agent-456",
                user_id="user@example.com",
                task_description="Task 2",
                status="failed"
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        agent_service.db.execute.return_value = mock_result
        
        result = await agent_service.get_agent_executions("user@example.com")
        
        assert len(result) == 2
        assert result[0].task_description == "Task 1"
        assert result[1].task_description == "Task 2"

    async def test_get_execution_status(self, agent_service):
        """Test retrieving specific execution status"""
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Test task",
            status="running",
            progress_percentage=50
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_execution
        agent_service.db.execute.return_value = mock_result
        
        result = await agent_service.get_execution_status("exec-123", "user@example.com")
        
        assert result is not None
        assert result.id == "exec-123"
        assert result.status == "running"
        assert result.progress_percentage == 50

    async def test_load_agent_memory(self, agent_service):
        """Test loading agent memory"""
        mock_memory_items = [
            AgentMemory(
                id="mem-1",
                agent_id="agent-123",
                user_id="user@example.com",
                memory_key="preference_1",
                memory_value={"setting": "value1"},
                importance_score=8,
                access_count=5
            ),
            AgentMemory(
                id="mem-2",
                agent_id="agent-123",
                user_id="user@example.com",
                memory_key="fact_1",
                memory_value={"fact": "important info"},
                importance_score=9,
                access_count=2
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_memory_items
        agent_service.db.execute.return_value = mock_result
        agent_service.db.commit = AsyncMock()
        
        result = await agent_service._load_agent_memory("agent-123", "user@example.com")
        
        assert len(result) == 2
        assert "preference_1" in result
        assert "fact_1" in result
        assert result["preference_1"] == {"setting": "value1"}
        assert result["fact_1"] == {"fact": "important info"}
        
        # Verify access count was incremented
        assert mock_memory_items[0].access_count == 6
        assert mock_memory_items[1].access_count == 3

    async def test_store_agent_memory_new(self, agent_service):
        """Test storing new agent memory"""
        # Mock no existing memory found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        agent_service.db.execute.return_value = mock_result
        agent_service.db.add = MagicMock()
        agent_service.db.commit = AsyncMock()
        agent_service.db.refresh = AsyncMock()
        
        result = await agent_service.store_agent_memory(
            agent_id="agent-123",
            user_id="user@example.com",
            memory_type="preference",
            memory_key="setting_1",
            memory_value={"theme": "dark"},
            importance_score=7
        )
        
        agent_service.db.add.assert_called_once()
        agent_service.db.commit.assert_called_once()

    async def test_store_agent_memory_update_existing(self, agent_service):
        """Test updating existing agent memory"""
        # Mock existing memory found
        existing_memory = AgentMemory(
            id="mem-1",
            agent_id="agent-123",
            user_id="user@example.com",
            memory_key="setting_1",
            memory_value={"theme": "light"},
            importance_score=5
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_memory
        agent_service.db.execute.return_value = mock_result
        agent_service.db.commit = AsyncMock()
        agent_service.db.refresh = AsyncMock()
        
        result = await agent_service.store_agent_memory(
            agent_id="agent-123",
            user_id="user@example.com",
            memory_type="preference",
            memory_key="setting_1",
            memory_value={"theme": "dark"},
            importance_score=7
        )
        
        # Verify existing memory was updated
        assert existing_memory.memory_value == {"theme": "dark"}
        assert existing_memory.importance_score == 7
        agent_service.db.commit.assert_called_once()


class TestWorkflowService:
    """Test WorkflowService functionality"""

    async def test_create_workflow_success(self, workflow_service, sample_workflow_data):
        """Test successful workflow creation"""
        workflow_service.db.add = MagicMock()
        workflow_service.db.commit = AsyncMock()
        workflow_service.db.refresh = AsyncMock()
        
        result = await workflow_service.create_workflow(**sample_workflow_data)
        
        assert result.user_id == sample_workflow_data["user_id"]
        assert result.name == sample_workflow_data["name"]
        assert result.workflow_type == sample_workflow_data["workflow_type"]
        assert result.workflow_definition == sample_workflow_data["workflow_definition"]
        
        workflow_service.db.add.assert_called_once()
        workflow_service.db.commit.assert_called_once()

    async def test_execute_workflow_success(self, workflow_service, sample_workflow_data):
        """Test successful workflow execution"""
        # Mock workflow definition
        mock_workflow = WorkflowDefinition(
            id="workflow-123",
            user_id="user@example.com",
            name="Test Workflow",
            workflow_type="sequential",
            workflow_definition=sample_workflow_data["workflow_definition"],
            is_active=True
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_workflow
        workflow_service.db.execute.return_value = mock_result
        workflow_service.db.add = MagicMock()
        workflow_service.db.commit = AsyncMock()
        workflow_service.db.refresh = AsyncMock()
        
        # Mock asyncio.create_task to prevent actual background execution
        with patch('asyncio.create_task') as mock_create_task:
            result = await workflow_service.execute_workflow(
                workflow_id="workflow-123",
                user_id="user@example.com",
                input_data={"query": "test query"}
            )
            
            assert result.workflow_id == "workflow-123"
            assert result.user_id == "user@example.com"
            assert result.input_data == {"query": "test query"}
            assert result.total_steps == 3  # Based on sample workflow
            
            workflow_service.db.add.assert_called_once()
            workflow_service.db.commit.assert_called_once()
            mock_create_task.assert_called_once()

    async def test_execute_workflow_not_found(self, workflow_service):
        """Test executing non-existent workflow"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        workflow_service.db.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Workflow workflow-123 not found"):
            await workflow_service.execute_workflow(
                workflow_id="workflow-123",
                user_id="user@example.com",
                input_data={"query": "test"}
            )

    async def test_execute_workflow_agent_step(self, workflow_service):
        """Test executing agent step in workflow"""
        mock_execution = WorkflowExecution(
            id="exec-123",
            workflow_id="workflow-123",
            user_id="user@example.com",
            status="running"
        )
        
        mock_agent_execution = AgentExecution(
            id="agent-exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Workflow step execution",
            status="completed"
        )
        
        workflow_service.agent_service.execute_agent = AsyncMock(return_value=mock_agent_execution)
        
        step = {
            "type": "agent",
            "agent_id": "agent-123",
            "task": "Test task",
            "parameters": {"param": "value"}
        }
        
        result = await workflow_service._execute_workflow_agent_step(step, mock_execution)
        
        assert result['step_type'] == 'agent'
        assert result['agent_id'] == 'agent-123'
        assert result['status'] == 'completed'
        workflow_service.agent_service.execute_agent.assert_called_once()

    async def test_execute_workflow_delay_step(self, workflow_service):
        """Test executing delay step in workflow"""
        step = {
            "type": "delay",
            "delay_seconds": 0.1  # Short delay for testing
        }
        
        start_time = datetime.utcnow()
        result = await workflow_service._execute_workflow_delay_step(step)
        end_time = datetime.utcnow()
        
        assert result['step_type'] == 'delay'
        assert result['delay_seconds'] == 0.1
        assert result['status'] == 'completed'
        
        # Verify delay actually occurred (allowing some tolerance)
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.05  # At least half the delay time

    async def test_execute_workflow_custom_step(self, workflow_service):
        """Test executing custom step in workflow"""
        mock_execution = WorkflowExecution(
            id="exec-123",
            workflow_id="workflow-123",
            user_id="user@example.com",
            status="running"
        )
        
        step = {
            "type": "custom",
            "name": "Custom Processing Step"
        }
        
        result = await workflow_service._execute_workflow_custom_step(step, mock_execution)
        
        assert result['step_type'] == 'custom'
        assert result['step_name'] == 'Custom Processing Step'
        assert result['status'] == 'completed'
        assert 'output' in result

    async def test_workflow_execution_steps_success(self, workflow_service):
        """Test complete workflow execution with multiple steps"""
        # Mock workflow with multiple steps
        mock_workflow = WorkflowDefinition(
            id="workflow-123",
            user_id="user@example.com",
            name="Test Workflow",
            workflow_type="sequential",
            workflow_definition={
                "steps": [
                    {"type": "delay", "delay_seconds": 0.01},
                    {"type": "custom", "name": "Step 1"},
                    {"type": "custom", "name": "Step 2"}
                ]
            },
            execution_count=0,
            success_count=0
        )
        
        mock_execution = WorkflowExecution(
            id="exec-123",
            workflow_id="workflow-123",
            user_id="user@example.com",
            status="pending",
            started_at=datetime.utcnow()
        )
        
        workflow_service.db.commit = AsyncMock()
        
        # Execute workflow steps
        await workflow_service._execute_workflow_steps(mock_execution, mock_workflow)
        
        # Verify execution completed
        assert mock_execution.status == "completed"
        assert mock_execution.progress_percentage == 100
        assert len(mock_execution.step_results) == 3
        
        # Verify workflow stats updated
        assert mock_workflow.execution_count == 1
        assert mock_workflow.success_count == 1
        assert mock_workflow.last_execution is not None

    async def test_workflow_execution_steps_failure(self, workflow_service):
        """Test workflow execution failure handling"""
        mock_workflow = WorkflowDefinition(
            id="workflow-123",
            user_id="user@example.com",
            name="Test Workflow",
            workflow_type="sequential",
            workflow_definition={"steps": []},
            execution_count=0,
            success_count=0
        )
        
        mock_execution = WorkflowExecution(
            id="exec-123",
            workflow_id="workflow-123",
            user_id="user@example.com",
            status="pending",
            started_at=datetime.utcnow()
        )
        
        workflow_service.db.commit = AsyncMock()
        
        # Force an exception during execution
        with patch.object(workflow_service, '_execute_workflow_custom_step', side_effect=Exception("Test error")):
            # Set up a workflow with a custom step that will fail
            mock_workflow.workflow_definition = {
                "steps": [{"type": "custom", "name": "Failing Step"}]
            }
            
            await workflow_service._execute_workflow_steps(mock_execution, mock_workflow)
        
        # Verify failure was handled
        assert mock_execution.status == "failed"
        assert "Test error" in mock_execution.error_details

    async def test_agent_execution_task_success(self, agent_service):
        """Test complete agent execution task"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Test Agent",
            agent_type="research",
            prompt_template="Template",
            usage_count=0
        )
        
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Test task",
            status="pending",
            started_at=datetime.utcnow()
        )
        
        agent_service.db.commit = AsyncMock()
        agent_service._load_agent_memory = AsyncMock(return_value={})
        
        # Execute agent task
        await agent_service._execute_agent_task(mock_execution, mock_agent)
        
        # Verify execution completed
        assert mock_execution.status == "completed"
        assert mock_execution.progress_percentage == 100
        assert mock_execution.result_data['type'] == 'research_result'
        
        # Verify agent stats updated
        assert mock_agent.usage_count == 1
        assert mock_agent.last_used is not None

    async def test_agent_execution_task_failure(self, agent_service):
        """Test agent execution task failure handling"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Test Agent",
            agent_type="research",
            prompt_template="Template",
            usage_count=0
        )
        
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Test task",
            status="pending",
            started_at=datetime.utcnow()
        )
        
        agent_service.db.commit = AsyncMock()
        
        # Force an exception during execution
        agent_service._load_agent_memory = AsyncMock(side_effect=Exception("Memory load failed"))
        
        await agent_service._execute_agent_task(mock_execution, mock_agent)
        
        # Verify failure was handled
        assert mock_execution.status == "failed"
        assert "Memory load failed" in mock_execution.error_details

    async def test_memory_expiration_filtering(self, agent_service):
        """Test that expired memory is filtered out"""
        mock_memory_items = [
            AgentMemory(
                id="mem-1",
                agent_id="agent-123",
                user_id="user@example.com",
                memory_key="current",
                memory_value={"data": "valid"},
                expires_at=datetime.utcnow() + timedelta(hours=1)  # Future expiry
            ),
            AgentMemory(
                id="mem-2",
                agent_id="agent-123",
                user_id="user@example.com",
                memory_key="expired",
                memory_value={"data": "expired"},
                expires_at=datetime.utcnow() - timedelta(hours=1)  # Past expiry
            )
        ]
        
        # Only the non-expired memory should be returned
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_memory_items[0]]
        agent_service.db.execute.return_value = mock_result
        agent_service.db.commit = AsyncMock()
        
        result = await agent_service._load_agent_memory("agent-123", "user@example.com")
        
        assert len(result) == 1
        assert "current" in result
        assert "expired" not in result

    async def test_workflow_with_missing_agent(self, workflow_service):
        """Test workflow step with missing agent"""
        mock_execution = WorkflowExecution(
            id="exec-123",
            workflow_id="workflow-123",
            user_id="user@example.com",
            status="running"
        )
        
        step = {
            "type": "agent",
            # No agent_id specified
            "task": "Test task"
        }
        
        result = await workflow_service._execute_workflow_agent_step(step, mock_execution)
        
        assert result['step_type'] == 'agent'
        assert result['status'] == 'skipped'
        assert result['reason'] == 'No agent specified'

    async def test_agent_memory_with_expiration(self, agent_service):
        """Test storing agent memory with expiration"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        agent_service.db.execute.return_value = mock_result
        agent_service.db.add = MagicMock()
        agent_service.db.commit = AsyncMock()
        agent_service.db.refresh = AsyncMock()
        
        await agent_service.store_agent_memory(
            agent_id="agent-123",
            user_id="user@example.com",
            memory_type="temporary",
            memory_key="temp_data",
            memory_value={"temp": "value"},
            importance_score=3,
            expires_in_hours=24
        )
        
        # Verify memory was created with correct expiration
        agent_service.db.add.assert_called_once()
        call_args = agent_service.db.add.call_args[0][0]
        assert call_args.expires_at is not None
        assert call_args.expires_at > datetime.utcnow()

    async def test_custom_agent_execution(self, agent_service):
        """Test custom agent type execution"""
        mock_agent = Agent(
            id="agent-123",
            user_id="user@example.com",
            name="Custom Agent",
            agent_type="custom",
            prompt_template="Custom template"
        )
        
        mock_execution = AgentExecution(
            id="exec-123",
            agent_id="agent-123",
            user_id="user@example.com",
            task_description="Custom task",
            status="running"
        )
        
        agent_service.db.commit = AsyncMock()
        
        context = {
            'agent': mock_agent,
            'execution': mock_execution,
            'memory': {},
            'available_tools': [],
            'resource_bindings': []
        }
        
        result = await agent_service._execute_custom_agent(context)
        
        assert result['type'] == 'custom_result'
        assert 'summary' in result
        assert 'output' in result
        assert 'metadata' in result
        assert 'custom_field_1' in result['metadata']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])