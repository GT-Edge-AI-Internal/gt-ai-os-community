"""
Automation Chain Executor

Executes automation chains with configurable depth, capability-based limits,
and comprehensive error handling.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

from app.services.event_bus import Event, Automation, TriggerType, TenantEventBus
from app.core.security import verify_capability_token

logger = logging.getLogger(__name__)


class ChainDepthExceeded(Exception):
    """Raised when automation chain depth exceeds limit"""
    pass


class AutomationTimeout(Exception):
    """Raised when automation execution times out"""
    pass


@dataclass
class ExecutionContext:
    """Context for automation execution"""
    automation_id: str
    chain_depth: int = 0
    parent_automation_id: Optional[str] = None
    start_time: datetime = None
    execution_history: List[Dict[str, Any]] = None
    variables: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.utcnow()
        if self.execution_history is None:
            self.execution_history = []
        if self.variables is None:
            self.variables = {}
    
    def add_execution(self, action: str, result: Any, duration_ms: float):
        """Add execution record to history"""
        self.execution_history.append({
            "action": action,
            "result": result,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_total_duration(self) -> float:
        """Get total execution duration in milliseconds"""
        return (datetime.utcnow() - self.start_time).total_seconds() * 1000


class AutomationChainExecutor:
    """
    Execute automation chains with configurable depth and capability-based limits.
    
    Features:
    - Configurable max chain depth per tenant
    - Retry logic with exponential backoff
    - Comprehensive error handling
    - Execution history tracking
    - Variable passing between chain steps
    """
    
    def __init__(
        self,
        tenant_domain: str,
        event_bus: TenantEventBus,
        base_path: Optional[Path] = None
    ):
        self.tenant_domain = tenant_domain
        self.event_bus = event_bus
        self.base_path = base_path or Path(f"/data/{tenant_domain}/automations")
        self.execution_path = self.base_path / "executions"
        self.running_chains: Dict[str, ExecutionContext] = {}
        
        # Ensure directories exist
        self._ensure_directories()
        
        logger.info(f"AutomationChainExecutor initialized for {tenant_domain}")
    
    def _ensure_directories(self):
        """Ensure execution directories exist with proper permissions"""
        import os
        import stat
        
        self.execution_path.mkdir(parents=True, exist_ok=True)
        os.chmod(self.execution_path, stat.S_IRWXU)  # 700 permissions
    
    async def execute_chain(
        self,
        automation: Automation,
        event: Event,
        capability_token: str,
        current_depth: int = 0
    ) -> Any:
        """
        Execute automation chain with depth control.
        
        Args:
            automation: Automation to execute
            event: Triggering event
            capability_token: JWT capability token
            current_depth: Current chain depth
            
        Returns:
            Execution result
            
        Raises:
            ChainDepthExceeded: If chain depth exceeds limit
            AutomationTimeout: If execution times out
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data:
            raise ValueError("Invalid capability token")
        
        # Get max chain depth from capability token (tenant-specific)
        max_depth = self._get_constraint(token_data, "max_automation_chain_depth", 5)
        
        # Check depth limit
        if current_depth >= max_depth:
            raise ChainDepthExceeded(
                f"Chain depth {current_depth} exceeds limit {max_depth}"
            )
        
        # Create execution context
        context = ExecutionContext(
            automation_id=automation.id,
            chain_depth=current_depth,
            parent_automation_id=event.metadata.get("parent_automation_id")
        )
        
        # Track running chain
        self.running_chains[automation.id] = context
        
        try:
            # Execute automation with timeout
            timeout = self._get_constraint(token_data, "automation_timeout_seconds", 300)
            result = await asyncio.wait_for(
                self._execute_automation(automation, event, context, token_data),
                timeout=timeout
            )
            
            # If this automation triggers chain
            if automation.triggers_chain:
                await self._trigger_chain_automations(
                    automation,
                    result,
                    capability_token,
                    current_depth
                )
            
            # Store execution history
            await self._store_execution(context, result)
            
            return result
            
        except asyncio.TimeoutError:
            raise AutomationTimeout(
                f"Automation {automation.id} timed out after {timeout} seconds"
            )
        finally:
            # Remove from running chains
            self.running_chains.pop(automation.id, None)
    
    async def _execute_automation(
        self,
        automation: Automation,
        event: Event,
        context: ExecutionContext,
        token_data: Dict[str, Any]
    ) -> Any:
        """Execute automation with retry logic"""
        results = []
        retry_count = 0
        max_retries = min(automation.max_retries, 5)  # Cap at 5 retries
        
        while retry_count <= max_retries:
            try:
                # Execute each action
                for action in automation.actions:
                    start_time = datetime.utcnow()
                    
                    # Check if action is allowed by capabilities
                    if not self._is_action_allowed(action, token_data):
                        logger.warning(f"Action {action.get('type')} not allowed by capabilities")
                        continue
                    
                    # Execute action with context
                    result = await self._execute_action(action, event, context, token_data)
                    
                    # Track execution
                    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    context.add_execution(action.get("type"), result, duration_ms)
                    
                    results.append(result)
                    
                    # Update variables for next action
                    if isinstance(result, dict) and "variables" in result:
                        context.variables.update(result["variables"])
                
                # Success - break retry loop
                break
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Automation {automation.id} failed after {max_retries} retries: {e}")
                    raise
                
                # Exponential backoff
                wait_time = min(2 ** retry_count, 30)  # Max 30 seconds
                logger.info(f"Retrying automation {automation.id} in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
        
        return {
            "automation_id": automation.id,
            "results": results,
            "context": {
                "chain_depth": context.chain_depth,
                "total_duration_ms": context.get_total_duration(),
                "variables": context.variables
            }
        }
    
    async def _execute_action(
        self,
        action: Dict[str, Any],
        event: Event,
        context: ExecutionContext,
        token_data: Dict[str, Any]
    ) -> Any:
        """Execute a single action with capability constraints"""
        action_type = action.get("type")
        
        if action_type == "api_call":
            return await self._execute_api_call(action, context, token_data)
        elif action_type == "data_transform":
            return await self._execute_data_transform(action, context)
        elif action_type == "conditional":
            return await self._execute_conditional(action, context)
        elif action_type == "loop":
            return await self._execute_loop(action, event, context, token_data)
        elif action_type == "wait":
            return await self._execute_wait(action)
        elif action_type == "variable_set":
            return await self._execute_variable_set(action, context)
        else:
            # Delegate to event bus for standard actions
            return await self.event_bus._execute_action(action, event, None)
    
    async def _execute_api_call(
        self,
        action: Dict[str, Any],
        context: ExecutionContext,
        token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute API call action with rate limiting"""
        endpoint = action.get("endpoint")
        method = action.get("method", "GET")
        headers = action.get("headers", {})
        body = action.get("body")
        
        # Apply variable substitution
        if body and context.variables:
            body = self._substitute_variables(body, context.variables)
        
        # Check rate limits
        rate_limit = self._get_constraint(token_data, "api_calls_per_minute", 60)
        # In production, implement actual rate limiting
        
        logger.info(f"Mock API call: {method} {endpoint}")
        
        # Mock response
        return {
            "status": 200,
            "data": {"message": "Mock API response"},
            "headers": {"content-type": "application/json"}
        }
    
    async def _execute_data_transform(
        self,
        action: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute data transformation action"""
        transform_type = action.get("transform_type")
        source = action.get("source")
        target = action.get("target")
        
        # Get source data from context
        source_data = context.variables.get(source)
        
        if transform_type == "json_parse":
            result = json.loads(source_data) if isinstance(source_data, str) else source_data
        elif transform_type == "json_stringify":
            result = json.dumps(source_data)
        elif transform_type == "extract":
            path = action.get("path", "")
            result = self._extract_path(source_data, path)
        elif transform_type == "map":
            mapping = action.get("mapping", {})
            result = {k: self._extract_path(source_data, v) for k, v in mapping.items()}
        else:
            result = source_data
        
        # Store result in context
        context.variables[target] = result
        
        return {
            "transform_type": transform_type,
            "target": target,
            "variables": {target: result}
        }
    
    async def _execute_conditional(
        self,
        action: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute conditional action"""
        condition = action.get("condition")
        then_actions = action.get("then", [])
        else_actions = action.get("else", [])
        
        # Evaluate condition
        if self._evaluate_condition(condition, context.variables):
            actions_to_execute = then_actions
            branch = "then"
        else:
            actions_to_execute = else_actions
            branch = "else"
        
        # Execute branch actions
        results = []
        for sub_action in actions_to_execute:
            result = await self._execute_action(sub_action, None, context, {})
            results.append(result)
        
        return {
            "condition": condition,
            "branch": branch,
            "results": results
        }
    
    async def _execute_loop(
        self,
        action: Dict[str, Any],
        event: Event,
        context: ExecutionContext,
        token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute loop action with iteration limit"""
        items = action.get("items", [])
        variable = action.get("variable", "item")
        loop_actions = action.get("actions", [])
        
        # Get max iterations from capabilities
        max_iterations = self._get_constraint(token_data, "max_loop_iterations", 100)
        
        # Resolve items from context if it's a variable reference
        if isinstance(items, str) and items.startswith("$"):
            items = context.variables.get(items[1:], [])
        
        # Limit iterations
        items = items[:max_iterations]
        
        results = []
        for item in items:
            # Set loop variable
            context.variables[variable] = item
            
            # Execute loop actions
            for loop_action in loop_actions:
                result = await self._execute_action(loop_action, event, context, token_data)
                results.append(result)
        
        return {
            "loop_count": len(items),
            "results": results
        }
    
    async def _execute_wait(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute wait action"""
        duration = action.get("duration", 1)
        max_wait = 60  # Maximum 60 seconds wait
        
        duration = min(duration, max_wait)
        await asyncio.sleep(duration)
        
        return {
            "waited": duration,
            "unit": "seconds"
        }
    
    async def _execute_variable_set(
        self,
        action: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Set variables in context"""
        variables = action.get("variables", {})
        
        for key, value in variables.items():
            # Substitute existing variables in value
            if isinstance(value, str):
                value = self._substitute_variables(value, context.variables)
            context.variables[key] = value
        
        return {
            "variables": variables
        }
    
    async def _trigger_chain_automations(
        self,
        automation: Automation,
        result: Any,
        capability_token: str,
        current_depth: int
    ):
        """Trigger chained automations"""
        for target_id in automation.chain_targets:
            # Load target automation
            target_automation = await self.event_bus.get_automation(target_id)
            
            if not target_automation:
                logger.warning(f"Chain target automation {target_id} not found")
                continue
            
            # Create chain event
            chain_event = Event(
                type=TriggerType.CHAIN.value,
                tenant=self.tenant_domain,
                user=automation.owner_id,
                data=result,
                metadata={
                    "parent_automation_id": automation.id,
                    "chain_depth": current_depth + 1
                }
            )
            
            # Execute chained automation
            try:
                await self.execute_chain(
                    target_automation,
                    chain_event,
                    capability_token,
                    current_depth + 1
                )
            except ChainDepthExceeded:
                logger.warning(f"Chain depth exceeded for automation {target_id}")
            except Exception as e:
                logger.error(f"Error executing chained automation {target_id}: {e}")
    
    def _get_constraint(
        self,
        token_data: Dict[str, Any],
        constraint_name: str,
        default: Any
    ) -> Any:
        """Get constraint value from capability token"""
        constraints = token_data.get("constraints", {})
        return constraints.get(constraint_name, default)
    
    def _is_action_allowed(
        self,
        action: Dict[str, Any],
        token_data: Dict[str, Any]
    ) -> bool:
        """Check if action is allowed by capabilities"""
        action_type = action.get("type")
        
        # Check specific action capabilities
        capabilities = token_data.get("capabilities", [])
        
        # Map action types to required capabilities
        required_capabilities = {
            "api_call": "automation:api_calls",
            "webhook": "automation:webhooks",
            "email": "automation:email",
            "data_transform": "automation:data_processing",
            "conditional": "automation:logic",
            "loop": "automation:logic"
        }
        
        required = required_capabilities.get(action_type)
        if not required:
            return True  # Allow unknown actions by default
        
        # Check if capability exists
        return any(
            cap.get("resource") == required
            for cap in capabilities
        )
    
    def _substitute_variables(
        self,
        template: Any,
        variables: Dict[str, Any]
    ) -> Any:
        """Substitute variables in template"""
        if not isinstance(template, str):
            return template
        
        # Simple variable substitution
        for key, value in variables.items():
            template = template.replace(f"${{{key}}}", str(value))
            template = template.replace(f"${key}", str(value))
        
        return template
    
    def _extract_path(self, data: Any, path: str) -> Any:
        """Extract value from nested data using path"""
        if not path:
            return data
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        
        return current
    
    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> bool:
        """Evaluate condition against variables"""
        left = condition.get("left")
        operator = condition.get("operator")
        right = condition.get("right")
        
        # Resolve variables
        if isinstance(left, str) and left.startswith("$"):
            left = variables.get(left[1:])
        if isinstance(right, str) and right.startswith("$"):
            right = variables.get(right[1:])
        
        # Evaluate
        try:
            if operator == "equals":
                return left == right
            elif operator == "not_equals":
                return left != right
            elif operator == "greater_than":
                return float(left) > float(right)
            elif operator == "less_than":
                return float(left) < float(right)
            elif operator == "contains":
                return right in left
            elif operator == "exists":
                return left is not None
            elif operator == "not_exists":
                return left is None
            else:
                return False
        except (ValueError, TypeError):
            return False
    
    async def _store_execution(
        self,
        context: ExecutionContext,
        result: Any
    ):
        """Store execution history to file system"""
        execution_record = {
            "automation_id": context.automation_id,
            "chain_depth": context.chain_depth,
            "parent_automation_id": context.parent_automation_id,
            "start_time": context.start_time.isoformat(),
            "total_duration_ms": context.get_total_duration(),
            "execution_history": context.execution_history,
            "variables": context.variables,
            "result": result if isinstance(result, (dict, list, str, int, float, bool)) else str(result)
        }
        
        # Create execution file
        execution_file = self.execution_path / f"{context.automation_id}_{context.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(execution_file, "w") as f:
            json.dump(execution_record, f, indent=2)
    
    async def get_execution_history(
        self,
        automation_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get execution history for automations"""
        executions = []
        
        # Get all execution files
        pattern = f"{automation_id}_*.json" if automation_id else "*.json"
        
        for execution_file in sorted(
            self.execution_path.glob(pattern),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]:
            try:
                with open(execution_file, "r") as f:
                    executions.append(json.load(f))
            except Exception as e:
                logger.error(f"Error loading execution {execution_file}: {e}")
        
        return executions