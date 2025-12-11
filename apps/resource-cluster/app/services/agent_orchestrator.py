"""
Agent Orchestration System for GT 2.0 Resource Cluster

Provides multi-agent workflow execution with:
- Sequential, parallel, and conditional agent workflows
- Inter-agent communication and memory management
- Capability-based access control
- Agent lifecycle management
- Performance monitoring and metrics

GT 2.0 Architecture Principles:
- Perfect Tenant Isolation: Agent sessions isolated per tenant
- Zero Downtime: Stateless design, resumable workflows
- Self-Contained Security: Capability-based agent permissions
- No Complexity Addition: Simple orchestration patterns
"""

import asyncio
import logging
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Union, Callable, Coroutine
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import traceback

from app.core.capability_auth import verify_capability_token, CapabilityError
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentStatus(str, Enum):
    """Agent execution status"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(str, Enum):
    """Types of agent workflows"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    PIPELINE = "pipeline"
    MAP_REDUCE = "map_reduce"


class MessageType(str, Enum):
    """Inter-agent message types"""
    DATA = "data"
    CONTROL = "control"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class AgentDefinition:
    """Definition of an agent"""
    agent_id: str
    agent_type: str
    name: str
    description: str
    capabilities_required: List[str]
    memory_limit_mb: int = 256
    timeout_seconds: int = 300
    retry_count: int = 3
    environment: Dict[str, Any] = None


@dataclass
class AgentMessage:
    """Message between agents"""
    message_id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: str
    expires_at: Optional[str] = None


@dataclass
class AgentState:
    """Current state of an agent"""
    agent_id: str
    status: AgentStatus
    current_task: Optional[str]
    memory_usage_mb: int
    cpu_usage_percent: float
    started_at: str
    last_activity: str
    error_message: Optional[str] = None
    output_data: Dict[str, Any] = None


@dataclass
class WorkflowExecution:
    """Workflow execution instance"""
    workflow_id: str
    workflow_type: WorkflowType
    tenant_id: str
    created_by: str
    agents: List[AgentDefinition]
    workflow_config: Dict[str, Any]
    status: AgentStatus
    started_at: str
    completed_at: Optional[str] = None
    results: Dict[str, Any] = None
    error_message: Optional[str] = None


class AgentMemoryManager:
    """Manages agent memory and state"""
    
    def __init__(self):
        # In-memory storage (PostgreSQL used for persistent storage)
        self._agent_memory: Dict[str, Dict[str, Any]] = {}
        self._shared_memory: Dict[str, Dict[str, Any]] = {}
        self._message_queues: Dict[str, List[AgentMessage]] = {}
    
    async def store_agent_memory(
        self,
        agent_id: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Store data in agent-specific memory"""
        if agent_id not in self._agent_memory:
            self._agent_memory[agent_id] = {}
        
        self._agent_memory[agent_id][key] = {
            "value": value,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(seconds=ttl_seconds)
            ).isoformat() if ttl_seconds else None
        }
        
        logger.debug(f"Stored memory for agent {agent_id}: {key}")
    
    async def get_agent_memory(
        self,
        agent_id: str,
        key: str
    ) -> Optional[Any]:
        """Retrieve data from agent-specific memory"""
        if agent_id not in self._agent_memory:
            return None
        
        memory_item = self._agent_memory[agent_id].get(key)
        if not memory_item:
            return None
        
        # Check expiration
        if memory_item.get("expires_at"):
            expires_at = datetime.fromisoformat(memory_item["expires_at"])
            if datetime.utcnow() > expires_at:
                del self._agent_memory[agent_id][key]
                return None
        
        return memory_item["value"]
    
    async def store_shared_memory(
        self,
        tenant_id: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Store data in tenant-shared memory"""
        if tenant_id not in self._shared_memory:
            self._shared_memory[tenant_id] = {}
        
        self._shared_memory[tenant_id][key] = {
            "value": value,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(seconds=ttl_seconds)
            ).isoformat() if ttl_seconds else None
        }
        
        logger.debug(f"Stored shared memory for tenant {tenant_id}: {key}")
    
    async def get_shared_memory(
        self,
        tenant_id: str,
        key: str
    ) -> Optional[Any]:
        """Retrieve data from tenant-shared memory"""
        if tenant_id not in self._shared_memory:
            return None
        
        memory_item = self._shared_memory[tenant_id].get(key)
        if not memory_item:
            return None
        
        # Check expiration
        if memory_item.get("expires_at"):
            expires_at = datetime.fromisoformat(memory_item["expires_at"])
            if datetime.utcnow() > expires_at:
                del self._shared_memory[tenant_id][key]
                return None
        
        return memory_item["value"]
    
    async def send_message(
        self,
        message: AgentMessage
    ) -> None:
        """Send message to agent queue"""
        if message.to_agent not in self._message_queues:
            self._message_queues[message.to_agent] = []
        
        self._message_queues[message.to_agent].append(message)
        logger.debug(f"Message sent from {message.from_agent} to {message.to_agent}")
    
    async def receive_messages(
        self,
        agent_id: str,
        message_type: Optional[MessageType] = None
    ) -> List[AgentMessage]:
        """Receive messages for agent"""
        if agent_id not in self._message_queues:
            return []
        
        messages = self._message_queues[agent_id]
        
        # Filter expired messages
        now = datetime.utcnow()
        messages = [
            msg for msg in messages
            if not msg.expires_at or datetime.fromisoformat(msg.expires_at) > now
        ]
        
        # Filter by message type if specified
        if message_type:
            messages = [msg for msg in messages if msg.message_type == message_type]
        
        # Clear processed messages
        if message_type:
            self._message_queues[agent_id] = [
                msg for msg in self._message_queues[agent_id]
                if msg.message_type != message_type or 
                (msg.expires_at and datetime.fromisoformat(msg.expires_at) <= now)
            ]
        else:
            self._message_queues[agent_id] = []
        
        return messages
    
    async def cleanup_agent_memory(self, agent_id: str) -> None:
        """Clean up memory for completed agent"""
        if agent_id in self._agent_memory:
            del self._agent_memory[agent_id]
        if agent_id in self._message_queues:
            del self._message_queues[agent_id]
        
        logger.debug(f"Cleaned up memory for agent {agent_id}")


class AgentOrchestrator:
    """
    Main agent orchestration system for GT 2.0.
    
    Manages agent lifecycle, workflows, communication, and resource allocation.
    All operations are tenant-isolated and capability-protected.
    """
    
    def __init__(self):
        self.memory_manager = AgentMemoryManager()
        self.active_workflows: Dict[str, WorkflowExecution] = {}
        self.agent_states: Dict[str, AgentState] = {}
        
        # Built-in agent types
        self.agent_registry: Dict[str, Dict[str, Any]] = {
            "data_processor": {
                "description": "Processes and transforms data",
                "capabilities": ["data.read", "data.transform"],
                "memory_limit_mb": 512,
                "timeout_seconds": 300
            },
            "llm_agent": {
                "description": "Interacts with LLM services",
                "capabilities": ["llm.inference", "llm.chat"],
                "memory_limit_mb": 256,
                "timeout_seconds": 600
            },
            "embedding_agent": {
                "description": "Generates text embeddings",
                "capabilities": ["embeddings.generate"],
                "memory_limit_mb": 256,
                "timeout_seconds": 180
            },
            "rag_agent": {
                "description": "Performs retrieval-augmented generation",
                "capabilities": ["rag.search", "rag.generate"],
                "memory_limit_mb": 512,
                "timeout_seconds": 450
            },
            "integration_agent": {
                "description": "Connects to external services",
                "capabilities": ["integration.call", "integration.webhook"],
                "memory_limit_mb": 256,
                "timeout_seconds": 300
            }
        }
        
        logger.info("Agent orchestrator initialized")
    
    async def create_workflow(
        self,
        workflow_type: WorkflowType,
        agents: List[AgentDefinition],
        workflow_config: Dict[str, Any],
        capability_token: str,
        workflow_name: Optional[str] = None
    ) -> str:
        """
        Create a new agent workflow.
        
        Args:
            workflow_type: Type of workflow to create
            agents: List of agents to include in workflow
            workflow_config: Configuration for the workflow
            capability_token: JWT token with workflow permissions
            workflow_name: Optional name for the workflow
            
        Returns:
            Workflow ID
        """
        # Verify capability token
        capability = await verify_capability_token(capability_token)
        tenant_id = capability.get("tenant_id")
        user_id = capability.get("sub")
        
        # Check workflow permissions
        await self._verify_workflow_permissions(capability, workflow_type, agents)
        
        # Generate workflow ID
        workflow_id = str(uuid.uuid4())
        
        # Create workflow execution
        workflow = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            tenant_id=tenant_id,
            created_by=user_id,
            agents=agents,
            workflow_config=workflow_config,
            status=AgentStatus.IDLE,
            started_at=datetime.utcnow().isoformat()
        )
        
        # Store workflow
        self.active_workflows[workflow_id] = workflow
        
        logger.info(
            f"Created {workflow_type} workflow {workflow_id} "
            f"with {len(agents)} agents for tenant {tenant_id}"
        )
        
        return workflow_id
    
    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """
        Execute an agent workflow.
        
        Args:
            workflow_id: ID of workflow to execute
            input_data: Input data for the workflow
            capability_token: JWT token with execution permissions
            
        Returns:
            Workflow execution results
        """
        # Verify capability token
        capability = await verify_capability_token(capability_token)
        tenant_id = capability.get("tenant_id")
        
        # Get workflow
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Check tenant isolation
        if workflow.tenant_id != tenant_id:
            raise CapabilityError("Insufficient permissions for workflow")
        
        # Check workflow permissions
        await self._verify_execution_permissions(capability, workflow)
        
        try:
            # Update workflow status
            workflow.status = AgentStatus.RUNNING
            
            # Execute based on workflow type
            if workflow.workflow_type == WorkflowType.SEQUENTIAL:
                results = await self._execute_sequential_workflow(
                    workflow, input_data, capability_token
                )
            elif workflow.workflow_type == WorkflowType.PARALLEL:
                results = await self._execute_parallel_workflow(
                    workflow, input_data, capability_token
                )
            elif workflow.workflow_type == WorkflowType.CONDITIONAL:
                results = await self._execute_conditional_workflow(
                    workflow, input_data, capability_token
                )
            elif workflow.workflow_type == WorkflowType.PIPELINE:
                results = await self._execute_pipeline_workflow(
                    workflow, input_data, capability_token
                )
            elif workflow.workflow_type == WorkflowType.MAP_REDUCE:
                results = await self._execute_map_reduce_workflow(
                    workflow, input_data, capability_token
                )
            else:
                raise ValueError(f"Unsupported workflow type: {workflow.workflow_type}")
            
            # Update workflow completion
            workflow.status = AgentStatus.COMPLETED
            workflow.completed_at = datetime.utcnow().isoformat()
            workflow.results = results
            
            logger.info(f"Completed workflow {workflow_id} successfully")
            
            return results
            
        except Exception as e:
            # Update workflow error status
            workflow.status = AgentStatus.FAILED
            workflow.completed_at = datetime.utcnow().isoformat()
            workflow.error_message = str(e)
            
            logger.error(f"Workflow {workflow_id} failed: {e}")
            raise
    
    async def get_workflow_status(
        self,
        workflow_id: str,
        capability_token: str
    ) -> Dict[str, Any]:
        """Get status of a workflow"""
        # Verify capability token
        capability = await verify_capability_token(capability_token)
        tenant_id = capability.get("tenant_id")
        
        # Get workflow
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Check tenant isolation
        if workflow.tenant_id != tenant_id:
            raise CapabilityError("Insufficient permissions for workflow")
        
        # Get agent states for this workflow
        agent_states = {
            agent.agent_id: asdict(self.agent_states.get(agent.agent_id))
            for agent in workflow.agents
            if agent.agent_id in self.agent_states
        }
        
        return {
            "workflow": asdict(workflow),
            "agent_states": agent_states
        }
    
    async def cancel_workflow(
        self,
        workflow_id: str,
        capability_token: str
    ) -> None:
        """Cancel a running workflow"""
        # Verify capability token
        capability = await verify_capability_token(capability_token)
        tenant_id = capability.get("tenant_id")
        
        # Get workflow
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Check tenant isolation
        if workflow.tenant_id != tenant_id:
            raise CapabilityError("Insufficient permissions for workflow")
        
        # Cancel workflow
        workflow.status = AgentStatus.CANCELLED
        workflow.completed_at = datetime.utcnow().isoformat()
        
        # Cancel all agents in workflow
        for agent in workflow.agents:
            if agent.agent_id in self.agent_states:
                self.agent_states[agent.agent_id].status = AgentStatus.CANCELLED
        
        logger.info(f"Cancelled workflow {workflow_id}")
    
    async def _execute_sequential_workflow(
        self,
        workflow: WorkflowExecution,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute agents sequentially"""
        results = {}
        current_data = input_data
        
        for agent in workflow.agents:
            agent_result = await self._execute_agent(
                agent, current_data, capability_token
            )
            results[agent.agent_id] = agent_result
            
            # Pass output to next agent
            if "output" in agent_result:
                current_data = agent_result["output"]
        
        return {
            "workflow_type": "sequential",
            "final_output": current_data,
            "agent_results": results
        }
    
    async def _execute_parallel_workflow(
        self,
        workflow: WorkflowExecution,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute agents in parallel"""
        # Create tasks for all agents
        tasks = []
        for agent in workflow.agents:
            task = asyncio.create_task(
                self._execute_agent(agent, input_data, capability_token)
            )
            tasks.append((agent.agent_id, task))
        
        # Wait for all tasks to complete
        results = {}
        for agent_id, task in tasks:
            try:
                results[agent_id] = await task
            except Exception as e:
                results[agent_id] = {"error": str(e)}
        
        return {
            "workflow_type": "parallel",
            "agent_results": results
        }
    
    async def _execute_conditional_workflow(
        self,
        workflow: WorkflowExecution,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute agents based on conditions"""
        results = {}
        condition_config = workflow.workflow_config.get("conditions", {})
        
        for agent in workflow.agents:
            # Check if agent should execute based on conditions
            should_execute = await self._evaluate_condition(
                agent.agent_id, condition_config, input_data, results
            )
            
            if should_execute:
                agent_result = await self._execute_agent(
                    agent, input_data, capability_token
                )
                results[agent.agent_id] = agent_result
            else:
                results[agent.agent_id] = {"status": "skipped"}
        
        return {
            "workflow_type": "conditional",
            "agent_results": results
        }
    
    async def _execute_pipeline_workflow(
        self,
        workflow: WorkflowExecution,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute agents in pipeline with data transformation"""
        results = {}
        current_data = input_data
        
        for i, agent in enumerate(workflow.agents):
            # Add pipeline metadata
            pipeline_data = {
                **current_data,
                "_pipeline_stage": i,
                "_pipeline_total": len(workflow.agents)
            }
            
            agent_result = await self._execute_agent(
                agent, pipeline_data, capability_token
            )
            results[agent.agent_id] = agent_result
            
            # Transform data for next stage
            if "transformed_output" in agent_result:
                current_data = agent_result["transformed_output"]
            elif "output" in agent_result:
                current_data = agent_result["output"]
        
        return {
            "workflow_type": "pipeline",
            "final_output": current_data,
            "agent_results": results
        }
    
    async def _execute_map_reduce_workflow(
        self,
        workflow: WorkflowExecution,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute map-reduce workflow"""
        # Separate map and reduce agents
        map_agents = [a for a in workflow.agents if a.agent_type.endswith("_mapper")]
        reduce_agents = [a for a in workflow.agents if a.agent_type.endswith("_reducer")]
        
        # Execute map phase
        map_tasks = []
        input_chunks = input_data.get("chunks", [input_data])
        
        for i, chunk in enumerate(input_chunks):
            for agent in map_agents:
                task = asyncio.create_task(
                    self._execute_agent(agent, chunk, capability_token)
                )
                map_tasks.append((f"{agent.agent_id}_chunk_{i}", task))
        
        # Collect map results
        map_results = {}
        for task_id, task in map_tasks:
            try:
                map_results[task_id] = await task
            except Exception as e:
                map_results[task_id] = {"error": str(e)}
        
        # Execute reduce phase
        reduce_results = {}
        reduce_input = {"map_results": map_results}
        
        for agent in reduce_agents:
            agent_result = await self._execute_agent(
                agent, reduce_input, capability_token
            )
            reduce_results[agent.agent_id] = agent_result
        
        return {
            "workflow_type": "map_reduce",
            "map_results": map_results,
            "reduce_results": reduce_results
        }
    
    async def _execute_agent(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute a single agent"""
        start_time = time.time()
        
        # Create agent state
        agent_state = AgentState(
            agent_id=agent.agent_id,
            status=AgentStatus.RUNNING,
            current_task=f"Executing {agent.agent_type}",
            memory_usage_mb=0,
            cpu_usage_percent=0.0,
            started_at=datetime.utcnow().isoformat(),
            last_activity=datetime.utcnow().isoformat()
        )
        self.agent_states[agent.agent_id] = agent_state
        
        try:
            # Simulate agent execution based on type
            if agent.agent_type == "data_processor":
                result = await self._execute_data_processor(agent, input_data)
            elif agent.agent_type == "llm_agent":
                result = await self._execute_llm_agent(agent, input_data, capability_token)
            elif agent.agent_type == "embedding_agent":
                result = await self._execute_embedding_agent(agent, input_data, capability_token)
            elif agent.agent_type == "rag_agent":
                result = await self._execute_rag_agent(agent, input_data, capability_token)
            elif agent.agent_type == "integration_agent":
                result = await self._execute_integration_agent(agent, input_data, capability_token)
            else:
                result = await self._execute_custom_agent(agent, input_data)
            
            # Update agent state
            agent_state.status = AgentStatus.COMPLETED
            agent_state.output_data = result
            agent_state.last_activity = datetime.utcnow().isoformat()
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Agent {agent.agent_id} completed in {processing_time:.2f}s"
            )
            
            return {
                "status": "completed",
                "processing_time": processing_time,
                "output": result
            }
            
        except Exception as e:
            # Update agent error state
            agent_state.status = AgentStatus.FAILED
            agent_state.error_message = str(e)
            agent_state.last_activity = datetime.utcnow().isoformat()
            
            logger.error(f"Agent {agent.agent_id} failed: {e}")
            
            return {
                "status": "failed",
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    # Agent execution implementations would go here...
    # For now, these are placeholder implementations
    
    async def _execute_data_processor(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute data processing agent"""
        await asyncio.sleep(0.1)  # Simulate processing
        return {
            "processed_data": input_data,
            "processing_info": "Data processed successfully"
        }
    
    async def _execute_llm_agent(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute LLM agent"""
        await asyncio.sleep(0.2)  # Simulate LLM call
        return {
            "llm_response": f"LLM processed: {input_data.get('prompt', 'No prompt provided')}",
            "model_used": "groq/llama-3-8b"
        }
    
    async def _execute_embedding_agent(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute embedding agent"""
        await asyncio.sleep(0.1)  # Simulate embedding generation
        texts = input_data.get("texts", [""])
        return {
            "embeddings": [[0.1] * 1024 for _ in texts],  # Mock embeddings
            "model_used": "BAAI/bge-m3"
        }
    
    async def _execute_rag_agent(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute RAG agent"""
        await asyncio.sleep(0.3)  # Simulate RAG processing
        return {
            "rag_response": "RAG generated response",
            "retrieved_docs": ["doc1", "doc2"],
            "confidence_score": 0.85
        }
    
    async def _execute_integration_agent(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any],
        capability_token: str
    ) -> Dict[str, Any]:
        """Execute integration agent"""
        await asyncio.sleep(0.1)  # Simulate external API call
        return {
            "integration_result": "External API called successfully",
            "response_data": input_data
        }
    
    async def _execute_custom_agent(
        self,
        agent: AgentDefinition,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute custom agent type"""
        await asyncio.sleep(0.1)  # Simulate custom processing
        return {
            "custom_result": f"Custom agent {agent.agent_type} executed",
            "input_data": input_data
        }
    
    async def _verify_workflow_permissions(
        self,
        capability: Dict[str, Any],
        workflow_type: WorkflowType,
        agents: List[AgentDefinition]
    ) -> None:
        """Verify workflow creation permissions"""
        capabilities = capability.get("capabilities", [])
        
        # Check for workflow creation permission
        workflow_caps = [
            cap for cap in capabilities
            if cap.get("resource") == "workflows"
        ]
        
        if not workflow_caps:
            raise CapabilityError("No workflow permissions in capability token")
        
        # Check specific workflow type permission
        workflow_cap = workflow_caps[0]
        actions = workflow_cap.get("actions", [])
        
        if "create" not in actions:
            raise CapabilityError("No workflow creation permission")
        
        # Check agent-specific permissions
        for agent in agents:
            for required_cap in agent.capabilities_required:
                if not any(
                    cap.get("resource") == required_cap.split(".")[0]
                    for cap in capabilities
                ):
                    raise CapabilityError(
                        f"Missing capability for agent {agent.agent_id}: {required_cap}"
                    )
    
    async def _verify_execution_permissions(
        self,
        capability: Dict[str, Any],
        workflow: WorkflowExecution
    ) -> None:
        """Verify workflow execution permissions"""
        capabilities = capability.get("capabilities", [])
        
        # Check for workflow execution permission
        workflow_caps = [
            cap for cap in capabilities
            if cap.get("resource") == "workflows"
        ]
        
        if not workflow_caps:
            raise CapabilityError("No workflow permissions in capability token")
        
        workflow_cap = workflow_caps[0]
        actions = workflow_cap.get("actions", [])
        
        if "execute" not in actions:
            raise CapabilityError("No workflow execution permission")
    
    async def _evaluate_condition(
        self,
        agent_id: str,
        condition_config: Dict[str, Any],
        input_data: Dict[str, Any],
        results: Dict[str, Any]
    ) -> bool:
        """Evaluate condition for conditional workflow"""
        agent_condition = condition_config.get(agent_id, {})
        
        if not agent_condition:
            return True  # No condition means always execute
        
        condition_type = agent_condition.get("type", "always")
        
        if condition_type == "always":
            return True
        elif condition_type == "never":
            return False
        elif condition_type == "input_contains":
            key = agent_condition.get("key")
            value = agent_condition.get("value")
            return input_data.get(key) == value
        elif condition_type == "previous_success":
            previous_agent = agent_condition.get("previous_agent")
            return (
                previous_agent in results and
                results[previous_agent].get("status") == "completed"
            )
        elif condition_type == "previous_failure":
            previous_agent = agent_condition.get("previous_agent")
            return (
                previous_agent in results and
                results[previous_agent].get("status") == "failed"
            )
        
        return True  # Default to execute if condition not recognized


# Global orchestrator instance
_agent_orchestrator = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get the global agent orchestrator instance"""
    global _agent_orchestrator
    if _agent_orchestrator is None:
        _agent_orchestrator = AgentOrchestrator()
    return _agent_orchestrator