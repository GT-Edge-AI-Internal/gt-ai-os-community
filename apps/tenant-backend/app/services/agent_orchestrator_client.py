"""
GT 2.0 Agent Orchestrator Client

Client for interacting with the Resource Cluster's Agent Orchestration system.
Enables spawning and managing subagents for complex task execution.
"""

import logging
import asyncio
import httpx
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from app.services.task_classifier import SubagentType, TaskClassification
from app.models.agent import Agent

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    """Execution strategies for subagents"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    PIPELINE = "pipeline"
    MAP_REDUCE = "map_reduce"


class SubagentOrchestrator:
    """
    Orchestrates subagent execution for complex tasks.

    Manages lifecycle of subagents spawned from main agent templates,
    coordinates their execution, and aggregates results.
    """

    def __init__(self, tenant_domain: str, user_id: str):
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.resource_cluster_url = "http://resource-cluster:8000"
        self.active_subagents: Dict[str, Dict[str, Any]] = {}
        self.execution_history: List[Dict[str, Any]] = []

    async def execute_task_plan(
        self,
        task_classification: TaskClassification,
        parent_agent: Agent,
        conversation_id: str,
        user_message: str,
        available_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a task plan using subagents.

        Args:
            task_classification: Task classification with execution plan
            parent_agent: Parent agent spawning subagents
            conversation_id: Current conversation ID
            user_message: Original user message
            available_tools: Available MCP tools

        Returns:
            Aggregated results from subagent execution
        """
        try:
            execution_id = str(uuid.uuid4())
            logger.info(f"Starting subagent execution {execution_id} for {task_classification.complexity} task")

            # Track execution
            execution_record = {
                "execution_id": execution_id,
                "conversation_id": conversation_id,
                "parent_agent_id": parent_agent.id,
                "task_complexity": task_classification.complexity,
                "started_at": datetime.now().isoformat(),
                "subagent_plan": task_classification.subagent_plan
            }
            self.execution_history.append(execution_record)

            # Determine execution strategy
            strategy = self._determine_strategy(task_classification)

            # Execute based on strategy
            if strategy == ExecutionStrategy.PARALLEL:
                results = await self._execute_parallel(
                    task_classification.subagent_plan,
                    parent_agent,
                    conversation_id,
                    user_message,
                    available_tools
                )
            elif strategy == ExecutionStrategy.SEQUENTIAL:
                results = await self._execute_sequential(
                    task_classification.subagent_plan,
                    parent_agent,
                    conversation_id,
                    user_message,
                    available_tools
                )
            elif strategy == ExecutionStrategy.PIPELINE:
                results = await self._execute_pipeline(
                    task_classification.subagent_plan,
                    parent_agent,
                    conversation_id,
                    user_message,
                    available_tools
                )
            else:
                # Default to sequential
                results = await self._execute_sequential(
                    task_classification.subagent_plan,
                    parent_agent,
                    conversation_id,
                    user_message,
                    available_tools
                )

            # Update execution record
            execution_record["completed_at"] = datetime.now().isoformat()
            execution_record["results"] = results

            # Synthesize final response
            final_response = await self._synthesize_results(
                results,
                task_classification,
                user_message
            )

            logger.info(f"Completed subagent execution {execution_id}")

            return {
                "execution_id": execution_id,
                "strategy": strategy,
                "subagent_results": results,
                "final_response": final_response,
                "execution_time_ms": self._calculate_execution_time(execution_record)
            }

        except Exception as e:
            logger.error(f"Subagent execution failed: {e}")
            return {
                "error": str(e),
                "partial_results": self.active_subagents
            }

    async def _execute_parallel(
        self,
        subagent_plan: List[Dict[str, Any]],
        parent_agent: Agent,
        conversation_id: str,
        user_message: str,
        available_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute subagents in parallel"""
        # Group subagents by priority
        priority_groups = {}
        for plan_item in subagent_plan:
            priority = plan_item.get("priority", 1)
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(plan_item)

        results = {}

        # Execute each priority group
        for priority in sorted(priority_groups.keys()):
            group_tasks = []

            for plan_item in priority_groups[priority]:
                # Check dependencies
                if self._dependencies_met(plan_item, results):
                    task = asyncio.create_task(
                        self._execute_subagent(
                            plan_item,
                            parent_agent,
                            conversation_id,
                            user_message,
                            available_tools,
                            results
                        )
                    )
                    group_tasks.append((plan_item["id"], task))

            # Wait for group to complete
            for agent_id, task in group_tasks:
                try:
                    results[agent_id] = await task
                except Exception as e:
                    logger.error(f"Subagent {agent_id} failed: {e}")
                    results[agent_id] = {"error": str(e)}

        return results

    async def _execute_sequential(
        self,
        subagent_plan: List[Dict[str, Any]],
        parent_agent: Agent,
        conversation_id: str,
        user_message: str,
        available_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute subagents sequentially"""
        results = {}

        for plan_item in subagent_plan:
            if self._dependencies_met(plan_item, results):
                try:
                    results[plan_item["id"]] = await self._execute_subagent(
                        plan_item,
                        parent_agent,
                        conversation_id,
                        user_message,
                        available_tools,
                        results
                    )
                except Exception as e:
                    logger.error(f"Subagent {plan_item['id']} failed: {e}")
                    results[plan_item["id"]] = {"error": str(e)}

        return results

    async def _execute_pipeline(
        self,
        subagent_plan: List[Dict[str, Any]],
        parent_agent: Agent,
        conversation_id: str,
        user_message: str,
        available_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute subagents in pipeline mode"""
        results = {}
        pipeline_data = {"original_message": user_message}

        for plan_item in subagent_plan:
            try:
                # Pass output from previous stage as input
                result = await self._execute_subagent(
                    plan_item,
                    parent_agent,
                    conversation_id,
                    user_message,
                    available_tools,
                    results,
                    pipeline_data
                )

                results[plan_item["id"]] = result

                # Update pipeline data with output
                if "output" in result:
                    pipeline_data = result["output"]

            except Exception as e:
                logger.error(f"Pipeline stage {plan_item['id']} failed: {e}")
                results[plan_item["id"]] = {"error": str(e)}
                break  # Pipeline broken

        return results

    async def _execute_subagent(
        self,
        plan_item: Dict[str, Any],
        parent_agent: Agent,
        conversation_id: str,
        user_message: str,
        available_tools: List[Dict[str, Any]],
        previous_results: Dict[str, Any],
        pipeline_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a single subagent"""
        subagent_id = plan_item["id"]
        subagent_type = plan_item["type"]
        task_description = plan_item["task"]

        logger.info(f"Executing subagent {subagent_id} ({subagent_type}): {task_description[:50]}...")

        # Track subagent
        self.active_subagents[subagent_id] = {
            "type": subagent_type,
            "task": task_description,
            "started_at": datetime.now().isoformat(),
            "status": "running"
        }

        try:
            # Create subagent configuration based on type
            subagent_config = self._create_subagent_config(
                subagent_type,
                parent_agent,
                task_description,
                pipeline_data
            )

            # Select tools for this subagent
            subagent_tools = self._select_tools_for_subagent(
                subagent_type,
                available_tools
            )

            # Execute subagent based on type
            if subagent_type == SubagentType.RESEARCH:
                result = await self._execute_research_agent(
                    subagent_config,
                    task_description,
                    subagent_tools,
                    conversation_id
                )
            elif subagent_type == SubagentType.PLANNING:
                result = await self._execute_planning_agent(
                    subagent_config,
                    task_description,
                    user_message,
                    previous_results
                )
            elif subagent_type == SubagentType.IMPLEMENTATION:
                result = await self._execute_implementation_agent(
                    subagent_config,
                    task_description,
                    subagent_tools,
                    previous_results
                )
            elif subagent_type == SubagentType.VALIDATION:
                result = await self._execute_validation_agent(
                    subagent_config,
                    task_description,
                    previous_results
                )
            elif subagent_type == SubagentType.SYNTHESIS:
                result = await self._execute_synthesis_agent(
                    subagent_config,
                    task_description,
                    previous_results
                )
            elif subagent_type == SubagentType.ANALYST:
                result = await self._execute_analyst_agent(
                    subagent_config,
                    task_description,
                    previous_results
                )
            else:
                # Default execution
                result = await self._execute_generic_agent(
                    subagent_config,
                    task_description,
                    subagent_tools
                )

            # Update tracking
            self.active_subagents[subagent_id]["status"] = "completed"
            self.active_subagents[subagent_id]["completed_at"] = datetime.now().isoformat()
            self.active_subagents[subagent_id]["result"] = result

            return result

        except Exception as e:
            logger.error(f"Subagent {subagent_id} execution failed: {e}")
            self.active_subagents[subagent_id]["status"] = "failed"
            self.active_subagents[subagent_id]["error"] = str(e)
            raise

    async def _execute_research_agent(
        self,
        config: Dict[str, Any],
        task: str,
        tools: List[Dict[str, Any]],
        conversation_id: str
    ) -> Dict[str, Any]:
        """Execute research subagent"""
        # Research agents focus on information gathering
        prompt = f"""You are a research specialist. Your task is to:
{task}

Available tools: {[t['name'] for t in tools]}

Gather comprehensive information and return structured findings."""

        result = await self._call_llm_with_tools(
            prompt,
            config,
            tools,
            max_iterations=3
        )

        return {
            "type": "research",
            "findings": result.get("content", ""),
            "sources": result.get("tool_results", []),
            "output": result
        }

    async def _execute_planning_agent(
        self,
        config: Dict[str, Any],
        task: str,
        original_query: str,
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute planning subagent"""
        context = self._format_previous_results(previous_results)

        prompt = f"""You are a planning specialist. Break down this task into actionable steps:

Original request: {original_query}
Specific task: {task}

Context from previous agents:
{context}

Create a detailed execution plan with clear steps."""

        result = await self._call_llm(prompt, config)

        return {
            "type": "planning",
            "plan": result.get("content", ""),
            "steps": self._extract_steps(result.get("content", "")),
            "output": result
        }

    async def _execute_implementation_agent(
        self,
        config: Dict[str, Any],
        task: str,
        tools: List[Dict[str, Any]],
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute implementation subagent"""
        context = self._format_previous_results(previous_results)

        prompt = f"""You are an implementation specialist. Execute this task:
{task}

Context:
{context}

Available tools: {[t['name'] for t in tools]}

Complete the implementation and return results."""

        result = await self._call_llm_with_tools(
            prompt,
            config,
            tools,
            max_iterations=5
        )

        return {
            "type": "implementation",
            "implementation": result.get("content", ""),
            "tool_calls": result.get("tool_calls", []),
            "output": result
        }

    async def _execute_validation_agent(
        self,
        config: Dict[str, Any],
        task: str,
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute validation subagent"""
        context = self._format_previous_results(previous_results)

        prompt = f"""You are a validation specialist. Verify the following:
{task}

Results to validate:
{context}

Check for correctness, completeness, and quality."""

        result = await self._call_llm(prompt, config)

        return {
            "type": "validation",
            "validation_result": result.get("content", ""),
            "issues_found": self._extract_issues(result.get("content", "")),
            "output": result
        }

    async def _execute_synthesis_agent(
        self,
        config: Dict[str, Any],
        task: str,
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute synthesis subagent"""
        all_results = self._format_all_results(previous_results)

        prompt = f"""You are a synthesis specialist. Combine and summarize these results:

Task: {task}

Results from all agents:
{all_results}

Create a comprehensive, coherent response that addresses the original request."""

        result = await self._call_llm(prompt, config)

        return {
            "type": "synthesis",
            "final_response": result.get("content", ""),
            "output": result
        }

    async def _execute_analyst_agent(
        self,
        config: Dict[str, Any],
        task: str,
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute analyst subagent"""
        data = self._format_previous_results(previous_results)

        prompt = f"""You are an analysis specialist. Analyze the following:
{task}

Data to analyze:
{data}

Identify patterns, insights, and recommendations."""

        result = await self._call_llm(prompt, config)

        return {
            "type": "analysis",
            "analysis": result.get("content", ""),
            "insights": self._extract_insights(result.get("content", "")),
            "output": result
        }

    async def _execute_generic_agent(
        self,
        config: Dict[str, Any],
        task: str,
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute generic subagent"""
        prompt = f"""Complete the following task:
{task}

Available tools: {[t['name'] for t in tools] if tools else 'None'}"""

        if tools:
            result = await self._call_llm_with_tools(prompt, config, tools)
        else:
            result = await self._call_llm(prompt, config)

        return {
            "type": "generic",
            "result": result.get("content", ""),
            "output": result
        }

    async def _call_llm(
        self,
        prompt: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call LLM without tools"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Require model to be specified in config - no hardcoded fallbacks
                model = config.get("model")
                if not model:
                    raise ValueError(f"No model specified in subagent config: {config}")

                response = await client.post(
                    f"{self.resource_cluster_url}/api/v1/ai/chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": config.get("instructions", "")},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": config.get("temperature", 0.7),
                        "max_tokens": config.get("max_tokens", 2000)
                    },
                    headers={
                        "X-Tenant-ID": self.tenant_domain,
                        "X-User-ID": self.user_id
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "model": result["model"]
                    }
                else:
                    raise Exception(f"LLM call failed: {response.status_code}")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"content": f"Error: {str(e)}"}

    async def _call_llm_with_tools(
        self,
        prompt: str,
        config: Dict[str, Any],
        tools: List[Dict[str, Any]],
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """Call LLM with tool execution capability"""
        messages = [
            {"role": "system", "content": config.get("instructions", "")},
            {"role": "user", "content": prompt}
        ]

        tool_results = []
        iterations = 0

        while iterations < max_iterations:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # Require model to be specified in config - no hardcoded fallbacks
                    model = config.get("model")
                    if not model:
                        raise ValueError(f"No model specified in subagent config: {config}")

                    response = await client.post(
                        f"{self.resource_cluster_url}/api/v1/ai/chat/completions",
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": config.get("temperature", 0.7),
                            "max_tokens": config.get("max_tokens", 2000),
                            "tools": tools,
                            "tool_choice": "auto"
                        },
                        headers={
                            "X-Tenant-ID": self.tenant_domain,
                            "X-User-ID": self.user_id
                        }
                    )

                    if response.status_code != 200:
                        raise Exception(f"LLM call failed: {response.status_code}")

                    result = response.json()
                    choice = result["choices"][0]
                    message = choice["message"]

                    # Add agent's response to messages
                    messages.append(message)

                    # Check for tool calls
                    if message.get("tool_calls"):
                        # Execute tools
                        for tool_call in message["tool_calls"]:
                            tool_result = await self._execute_tool(
                                tool_call["function"]["name"],
                                tool_call["function"].get("arguments", {})
                            )

                            tool_results.append({
                                "tool": tool_call["function"]["name"],
                                "result": tool_result
                            })

                            # Add tool result to messages
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": str(tool_result)
                            })

                        iterations += 1
                        continue  # Get next response

                    # No more tool calls, return final result
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls", []),
                        "tool_results": tool_results,
                        "model": result["model"]
                    }

            except Exception as e:
                logger.error(f"LLM with tools call failed: {e}")
                return {"content": f"Error: {str(e)}", "tool_results": tool_results}

            iterations += 1

        # Max iterations reached
        return {
            "content": "Max iterations reached",
            "tool_results": tool_results
        }

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an MCP tool"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.resource_cluster_url}/api/v1/mcp/execute",
                    json={
                        "tool_name": tool_name,
                        "parameters": arguments,
                        "tenant_domain": self.tenant_domain,
                        "user_id": self.user_id
                    }
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Tool execution failed: {response.status_code}"}

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {"error": str(e)}

    def _determine_strategy(self, task_classification: TaskClassification) -> ExecutionStrategy:
        """Determine execution strategy based on task classification"""
        if task_classification.parallel_execution:
            return ExecutionStrategy.PARALLEL
        elif len(task_classification.subagent_plan) > 3:
            return ExecutionStrategy.PIPELINE
        else:
            return ExecutionStrategy.SEQUENTIAL

    def _dependencies_met(
        self,
        plan_item: Dict[str, Any],
        completed_results: Dict[str, Any]
    ) -> bool:
        """Check if dependencies are met for a subagent"""
        depends_on = plan_item.get("depends_on", [])
        return all(dep in completed_results for dep in depends_on)

    def _create_subagent_config(
        self,
        subagent_type: SubagentType,
        parent_agent: Agent,
        task: str,
        pipeline_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create configuration for subagent"""
        # Base config from parent
        config = {
            "model": parent_agent.model_name,
            "temperature": parent_agent.model_settings.get("temperature", 0.7),
            "max_tokens": parent_agent.model_settings.get("max_tokens", 2000)
        }

        # Customize based on subagent type
        if subagent_type == SubagentType.RESEARCH:
            config["instructions"] = "You are a research specialist. Be thorough and accurate."
            config["temperature"] = 0.3  # Lower for factual research
        elif subagent_type == SubagentType.PLANNING:
            config["instructions"] = "You are a planning specialist. Create clear, actionable plans."
            config["temperature"] = 0.5
        elif subagent_type == SubagentType.IMPLEMENTATION:
            config["instructions"] = "You are an implementation specialist. Execute tasks precisely."
            config["temperature"] = 0.3
        elif subagent_type == SubagentType.SYNTHESIS:
            config["instructions"] = "You are a synthesis specialist. Create coherent summaries."
            config["temperature"] = 0.7
        else:
            config["instructions"] = parent_agent.instructions or ""

        return config

    def _select_tools_for_subagent(
        self,
        subagent_type: SubagentType,
        available_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Select appropriate tools for subagent type"""
        if not available_tools:
            return []

        # Tool selection based on subagent type
        if subagent_type == SubagentType.RESEARCH:
            # Research agents get search tools
            return [t for t in available_tools if any(
                keyword in t["name"].lower()
                for keyword in ["search", "find", "list", "get", "fetch"]
            )]
        elif subagent_type == SubagentType.IMPLEMENTATION:
            # Implementation agents get action tools
            return [t for t in available_tools if any(
                keyword in t["name"].lower()
                for keyword in ["create", "update", "write", "execute", "run"]
            )]
        elif subagent_type == SubagentType.VALIDATION:
            # Validation agents get read/check tools
            return [t for t in available_tools if any(
                keyword in t["name"].lower()
                for keyword in ["read", "check", "verify", "test"]
            )]
        else:
            # Give all tools to other types
            return available_tools

    async def _synthesize_results(
        self,
        results: Dict[str, Any],
        task_classification: TaskClassification,
        user_message: str
    ) -> str:
        """Synthesize final response from all subagent results"""
        # Look for synthesis agent result first
        for agent_id, result in results.items():
            if result.get("type") == "synthesis":
                return result.get("final_response", "")

        # Otherwise, compile results
        response_parts = []

        # Add results in order of priority
        for plan_item in sorted(
            task_classification.subagent_plan,
            key=lambda x: x.get("priority", 999)
        ):
            agent_id = plan_item["id"]
            if agent_id in results:
                result = results[agent_id]
                if "error" not in result:
                    content = result.get("output", {}).get("content", "")
                    if content:
                        response_parts.append(content)

        return "\n\n".join(response_parts) if response_parts else "Task completed"

    def _format_previous_results(self, results: Dict[str, Any]) -> str:
        """Format previous results for context"""
        if not results:
            return "No previous results"

        formatted = []
        for agent_id, result in results.items():
            if "error" not in result:
                formatted.append(f"{agent_id}: {result.get('output', {}).get('content', '')[:200]}")

        return "\n".join(formatted) if formatted else "No valid previous results"

    def _format_all_results(self, results: Dict[str, Any]) -> str:
        """Format all results for synthesis"""
        if not results:
            return "No results to synthesize"

        formatted = []
        for agent_id, result in results.items():
            if "error" not in result:
                agent_type = result.get("type", "unknown")
                content = result.get("output", {}).get("content", "")
                formatted.append(f"[{agent_type}] {agent_id}:\n{content}\n")

        return "\n".join(formatted) if formatted else "No valid results to synthesize"

    def _extract_steps(self, content: str) -> List[str]:
        """Extract steps from planning content"""
        import re
        steps = []

        # Look for numbered lists
        pattern = r"(?:^|\n)\s*(?:\d+[\.\)]|\-|\*)\s+(.+)"
        matches = re.findall(pattern, content)

        for match in matches:
            steps.append(match.strip())

        return steps

    def _extract_issues(self, content: str) -> List[str]:
        """Extract issues from validation content"""
        import re
        issues = []

        # Look for issue indicators
        issue_patterns = [
            r"(?:issue|problem|error|warning|concern):\s*(.+)",
            r"(?:^|\n)\s*[\-\*]\s*(?:Issue|Problem|Error):\s*(.+)"
        ]

        for pattern in issue_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            issues.extend([m.strip() for m in matches])

        return issues

    def _extract_insights(self, content: str) -> List[str]:
        """Extract insights from analysis content"""
        import re
        insights = []

        # Look for insight indicators
        insight_patterns = [
            r"(?:insight|finding|observation|pattern):\s*(.+)",
            r"(?:^|\n)\s*\d+[\.\)]\s*(.+(?:shows?|indicates?|suggests?|reveals?).+)"
        ]

        for pattern in insight_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            insights.extend([m.strip() for m in matches])

        return insights

    def _calculate_execution_time(self, execution_record: Dict[str, Any]) -> float:
        """Calculate execution time in milliseconds"""
        if "completed_at" in execution_record and "started_at" in execution_record:
            start = datetime.fromisoformat(execution_record["started_at"])
            end = datetime.fromisoformat(execution_record["completed_at"])
            return (end - start).total_seconds() * 1000
        return 0.0


# Factory function
def get_subagent_orchestrator(tenant_domain: str, user_id: str) -> SubagentOrchestrator:
    """Get subagent orchestrator instance"""
    return SubagentOrchestrator(tenant_domain, user_id)