"""
GT 2.0 Task Classifier Service

Analyzes user queries to determine task complexity and required subagent orchestration.
Enables highly agentic behavior by intelligently routing tasks to specialized subagents.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels"""
    SIMPLE = "simple"          # Direct response, no tools needed
    TOOL_ASSISTED = "tool_assisted"  # Single tool call required
    MULTI_STEP = "multi_step"   # Multiple sequential steps
    RESEARCH = "research"        # Information gathering from multiple sources
    IMPLEMENTATION = "implementation"  # Code/config changes
    COMPLEX = "complex"         # Requires multiple subagents


class SubagentType(str, Enum):
    """Types of specialized subagents"""
    RESEARCH = "research"       # Information gathering
    PLANNING = "planning"       # Task decomposition
    IMPLEMENTATION = "implementation"  # Execution
    VALIDATION = "validation"   # Quality checks
    SYNTHESIS = "synthesis"     # Result aggregation
    MONITOR = "monitor"         # Status checking
    ANALYST = "analyst"         # Data analysis


@dataclass
class TaskClassification:
    """Result of task classification"""
    complexity: TaskComplexity
    confidence: float
    primary_intent: str
    subagent_plan: List[Dict[str, Any]]
    estimated_tools: List[str]
    parallel_execution: bool
    requires_confirmation: bool
    reasoning: str


@dataclass
class SubagentTask:
    """Task definition for a subagent"""
    subagent_type: SubagentType
    task_description: str
    required_tools: List[str]
    depends_on: List[str]  # IDs of other subagent tasks
    priority: int
    timeout_seconds: int
    input_data: Optional[Dict[str, Any]] = None


class TaskClassifier:
    """
    Classifies user tasks and creates subagent execution plans.

    Analyzes query patterns, identifies required capabilities,
    and orchestrates multi-agent workflows for complex tasks.
    """

    def __init__(self):
        # Pattern matchers for different task types
        self.research_patterns = [
            r"find\s+(?:all\s+)?(?:information|documents?|files?)\s+about",
            r"search\s+for",
            r"what\s+(?:is|are|does|do)",
            r"explain\s+(?:how|what|why)",
            r"list\s+(?:all\s+)?the",
            r"show\s+me\s+(?:all\s+)?(?:the\s+)?",
            r"check\s+(?:the\s+)?(?:recent|latest|current)",
        ]

        self.implementation_patterns = [
            r"(?:create|add|implement|build|write)\s+(?:a\s+)?(?:new\s+)?",
            r"(?:update|modify|change|edit|fix)\s+(?:the\s+)?",
            r"(?:delete|remove|clean\s+up)\s+(?:the\s+)?",
            r"(?:deploy|install|configure|setup)\s+",
            r"(?:refactor|optimize|improve)\s+",
        ]

        self.analysis_patterns = [
            r"analyze\s+(?:the\s+)?",
            r"compare\s+(?:the\s+)?",
            r"summarize\s+(?:the\s+)?",
            r"evaluate\s+(?:the\s+)?",
            r"review\s+(?:the\s+)?",
            r"identify\s+(?:patterns|trends|issues)",
        ]

        self.multi_step_indicators = [
            r"(?:and\s+then|after\s+that|followed\s+by)",
            r"(?:first|second|third|finally)",
            r"(?:step\s+\d+|phase\s+\d+)",
            r"make\s+sure\s+(?:to\s+)?",
            r"(?:also|additionally|furthermore)",
            r"for\s+(?:each|every|all)\s+",
        ]

        logger.info("Task classifier initialized")

    async def classify_task(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        available_tools: Optional[List[str]] = None
    ) -> TaskClassification:
        """
        Classify a user query and create execution plan.

        Args:
            query: User's input query
            conversation_context: Previous messages for context
            available_tools: List of available MCP tools

        Returns:
            TaskClassification with complexity assessment and execution plan
        """
        query_lower = query.lower()

        # Analyze query characteristics
        is_research = self._matches_patterns(query_lower, self.research_patterns)
        is_implementation = self._matches_patterns(query_lower, self.implementation_patterns)
        is_analysis = self._matches_patterns(query_lower, self.analysis_patterns)
        is_multi_step = self._matches_patterns(query_lower, self.multi_step_indicators)

        # Count potential tool requirements
        tool_indicators = self._identify_tool_indicators(query_lower)

        # Determine complexity
        complexity = self._determine_complexity(
            is_research, is_implementation, is_analysis, is_multi_step, tool_indicators
        )

        # Create subagent plan based on complexity
        subagent_plan = await self._create_subagent_plan(
            query, complexity, is_research, is_implementation, is_analysis, available_tools
        )

        # Estimate required tools
        estimated_tools = self._estimate_required_tools(query_lower, available_tools)

        # Determine if parallel execution is possible
        parallel_execution = self._can_execute_parallel(subagent_plan)

        # Check if confirmation is needed
        requires_confirmation = complexity in [TaskComplexity.IMPLEMENTATION, TaskComplexity.COMPLEX]

        # Generate reasoning
        reasoning = self._generate_reasoning(
            query, complexity, is_research, is_implementation, is_analysis, is_multi_step
        )

        return TaskClassification(
            complexity=complexity,
            confidence=self._calculate_confidence(complexity, subagent_plan),
            primary_intent=self._identify_primary_intent(is_research, is_implementation, is_analysis),
            subagent_plan=subagent_plan,
            estimated_tools=estimated_tools,
            parallel_execution=parallel_execution,
            requires_confirmation=requires_confirmation,
            reasoning=reasoning
        )

    def _matches_patterns(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any of the patterns"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _identify_tool_indicators(self, query: str) -> List[str]:
        """Identify potential tool usage from query"""
        indicators = []

        tool_keywords = {
            "search": ["search", "find", "look for", "locate"],
            "database": ["database", "query", "sql", "records"],
            "file": ["file", "document", "upload", "download"],
            "api": ["api", "endpoint", "service", "integration"],
            "conversation": ["conversation", "chat", "history", "previous"],
            "web": ["website", "url", "browse", "fetch"],
        }

        for tool_type, keywords in tool_keywords.items():
            if any(keyword in query for keyword in keywords):
                indicators.append(tool_type)

        return indicators

    def _determine_complexity(
        self,
        is_research: bool,
        is_implementation: bool,
        is_analysis: bool,
        is_multi_step: bool,
        tool_indicators: List[str]
    ) -> TaskComplexity:
        """Determine task complexity based on characteristics"""

        # Count complexity factors
        factors = sum([is_research, is_implementation, is_analysis, is_multi_step])
        tool_count = len(tool_indicators)

        if factors == 0 and tool_count == 0:
            return TaskComplexity.SIMPLE
        elif factors == 1 and tool_count <= 1:
            return TaskComplexity.TOOL_ASSISTED
        elif is_multi_step or factors >= 2:
            if is_implementation:
                return TaskComplexity.IMPLEMENTATION
            elif is_research and (is_analysis or tool_count > 2):
                return TaskComplexity.RESEARCH
            else:
                return TaskComplexity.MULTI_STEP
        elif factors > 2 or (is_multi_step and is_implementation):
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.TOOL_ASSISTED

    async def _create_subagent_plan(
        self,
        query: str,
        complexity: TaskComplexity,
        is_research: bool,
        is_implementation: bool,
        is_analysis: bool,
        available_tools: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Create execution plan with subagents"""
        plan = []

        if complexity == TaskComplexity.SIMPLE:
            # No subagents needed
            return []

        elif complexity == TaskComplexity.TOOL_ASSISTED:
            # Single subagent for tool execution
            plan.append({
                "id": "tool_executor_1",
                "type": SubagentType.IMPLEMENTATION,
                "task": f"Execute required tool for: {query[:100]}",
                "depends_on": [],
                "priority": 1
            })

        elif complexity == TaskComplexity.RESEARCH:
            # Research workflow
            plan.extend([
                {
                    "id": "researcher_1",
                    "type": SubagentType.RESEARCH,
                    "task": f"Gather information about: {query[:100]}",
                    "depends_on": [],
                    "priority": 1
                },
                {
                    "id": "analyst_1",
                    "type": SubagentType.ANALYST,
                    "task": "Analyze gathered information",
                    "depends_on": ["researcher_1"],
                    "priority": 2
                },
                {
                    "id": "synthesizer_1",
                    "type": SubagentType.SYNTHESIS,
                    "task": "Compile findings into comprehensive response",
                    "depends_on": ["analyst_1"],
                    "priority": 3
                }
            ])

        elif complexity == TaskComplexity.IMPLEMENTATION:
            # Implementation workflow
            plan.extend([
                {
                    "id": "planner_1",
                    "type": SubagentType.PLANNING,
                    "task": f"Create implementation plan for: {query[:100]}",
                    "depends_on": [],
                    "priority": 1
                },
                {
                    "id": "implementer_1",
                    "type": SubagentType.IMPLEMENTATION,
                    "task": "Execute implementation steps",
                    "depends_on": ["planner_1"],
                    "priority": 2
                },
                {
                    "id": "validator_1",
                    "type": SubagentType.VALIDATION,
                    "task": "Validate implementation results",
                    "depends_on": ["implementer_1"],
                    "priority": 3
                }
            ])

        elif complexity in [TaskComplexity.MULTI_STEP, TaskComplexity.COMPLEX]:
            # Complex multi-agent workflow
            if is_research:
                plan.append({
                    "id": "researcher_1",
                    "type": SubagentType.RESEARCH,
                    "task": "Research required information",
                    "depends_on": [],
                    "priority": 1
                })

            plan.append({
                "id": "planner_1",
                "type": SubagentType.PLANNING,
                "task": f"Decompose complex task: {query[:100]}",
                "depends_on": ["researcher_1"] if is_research else [],
                "priority": 2
            })

            if is_implementation:
                plan.append({
                    "id": "implementer_1",
                    "type": SubagentType.IMPLEMENTATION,
                    "task": "Execute planned steps",
                    "depends_on": ["planner_1"],
                    "priority": 3
                })

            if is_analysis:
                plan.append({
                    "id": "analyst_1",
                    "type": SubagentType.ANALYST,
                    "task": "Analyze results and patterns",
                    "depends_on": ["implementer_1"] if is_implementation else ["planner_1"],
                    "priority": 4
                })

            # Always add synthesis for complex tasks
            final_deps = []
            if is_analysis:
                final_deps.append("analyst_1")
            elif is_implementation:
                final_deps.append("implementer_1")
            else:
                final_deps.append("planner_1")

            plan.append({
                "id": "synthesizer_1",
                "type": SubagentType.SYNTHESIS,
                "task": "Synthesize all results into final response",
                "depends_on": final_deps,
                "priority": 5
            })

        return plan

    def _estimate_required_tools(
        self,
        query: str,
        available_tools: Optional[List[str]]
    ) -> List[str]:
        """Estimate which tools will be needed"""
        if not available_tools:
            return []

        estimated = []

        # Map query patterns to tools
        tool_patterns = {
            "search_datasets": ["search", "find", "look for", "dataset", "document"],
            "brave_search": ["web", "internet", "online", "website", "current"],
            "list_directory": ["files", "directory", "folder", "ls"],
            "read_file": ["read", "view", "open", "file content"],
            "write_file": ["write", "create", "save", "generate file"],
        }

        for tool in available_tools:
            if tool in tool_patterns:
                if any(pattern in query for pattern in tool_patterns[tool]):
                    estimated.append(tool)

        return estimated

    def _can_execute_parallel(self, subagent_plan: List[Dict[str, Any]]) -> bool:
        """Check if any subagents can run in parallel"""
        if len(subagent_plan) < 2:
            return False

        # Group by priority to find parallel opportunities
        priority_groups = {}
        for agent in subagent_plan:
            priority = agent.get("priority", 1)
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(agent)

        # If any priority level has multiple agents, parallel execution is possible
        return any(len(agents) > 1 for agents in priority_groups.values())

    def _calculate_confidence(
        self,
        complexity: TaskComplexity,
        subagent_plan: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for classification"""
        base_confidence = {
            TaskComplexity.SIMPLE: 0.95,
            TaskComplexity.TOOL_ASSISTED: 0.9,
            TaskComplexity.MULTI_STEP: 0.85,
            TaskComplexity.RESEARCH: 0.85,
            TaskComplexity.IMPLEMENTATION: 0.8,
            TaskComplexity.COMPLEX: 0.75
        }

        confidence = base_confidence.get(complexity, 0.7)

        # Adjust based on plan clarity
        if len(subagent_plan) > 0:
            confidence += 0.05

        return min(confidence, 1.0)

    def _identify_primary_intent(
        self,
        is_research: bool,
        is_implementation: bool,
        is_analysis: bool
    ) -> str:
        """Identify the primary intent of the query"""
        if is_implementation:
            return "implementation"
        elif is_research:
            return "research"
        elif is_analysis:
            return "analysis"
        else:
            return "general"

    def _generate_reasoning(
        self,
        query: str,
        complexity: TaskComplexity,
        is_research: bool,
        is_implementation: bool,
        is_analysis: bool,
        is_multi_step: bool
    ) -> str:
        """Generate reasoning explanation for classification"""
        reasons = []

        if is_multi_step:
            reasons.append("Query indicates multiple sequential steps")
        if is_research:
            reasons.append("Information gathering required")
        if is_implementation:
            reasons.append("Code or configuration changes needed")
        if is_analysis:
            reasons.append("Data analysis and synthesis required")

        if complexity == TaskComplexity.COMPLEX:
            reasons.append("Multiple specialized agents needed for comprehensive execution")
        elif complexity == TaskComplexity.SIMPLE:
            reasons.append("Straightforward query with direct response possible")

        return ". ".join(reasons) if reasons else "Standard query processing"


# Factory function
def get_task_classifier() -> TaskClassifier:
    """Get task classifier instance"""
    return TaskClassifier()