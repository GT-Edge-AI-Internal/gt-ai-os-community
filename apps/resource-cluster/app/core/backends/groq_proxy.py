"""
Groq Cloud LLM Proxy Backend

Provides high-availability LLM inference through Groq Cloud with:
- HAProxy load balancing across multiple endpoints
- Automatic failover handled by HAProxy
- Token usage tracking and cost calculation
- Streaming response support
- Circuit breaker pattern for enhanced reliability
"""

import asyncio
import json
import os
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import httpx
try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    # Groq not available in development mode
    AsyncGroq = None
    GROQ_AVAILABLE = False
import logging

from app.core.config import get_settings, get_model_configs
from app.services.model_service import get_model_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Groq Compound tool pricing (per request/execution)
# Source: https://groq.com/pricing (Dec 2, 2025)
COMPOUND_TOOL_PRICES = {
    # Web Search variants
    "search": 0.008,               # API returns "search" for web search
    "web_search": 0.008,           # $8 per 1K = $0.008 per request (Advanced Search)
    "advanced_search": 0.008,      # $8 per 1K requests
    "basic_search": 0.005,         # $5 per 1K requests
    # Other tools
    "visit_website": 0.001,        # $1 per 1K requests
    "python": 0.00005,             # API returns "python" for code execution
    "code_interpreter": 0.00005,   # Alternative API identifier
    "code_execution": 0.00005,     # Alias for backwards compatibility
    "browser_automation": 0.00002, # $0.08/hr ≈ $0.00002 per execution
}

# Model pricing per million tokens (input/output)
# Source: https://groq.com/pricing (Dec 2, 2025)
GROQ_MODEL_PRICES = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-4-maverick-17b-128e-instruct": {"input": 0.20, "output": 0.60},
    "meta-llama/llama-4-maverick-17b-128e-instruct": {"input": 0.20, "output": 0.60},
    "llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "llama-guard-4-12b": {"input": 0.20, "output": 0.20},
    "meta-llama/llama-guard-4-12b": {"input": 0.20, "output": 0.20},
    "gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "kimi-k2-instruct-0905": {"input": 1.00, "output": 3.00},
    "moonshotai/kimi-k2-instruct-0905": {"input": 1.00, "output": 3.00},
    "qwen3-32b": {"input": 0.29, "output": 0.59},
    # Compound models - 50/50 blended pricing from underlying models
    # compound: GPT-OSS-120B ($0.15/$0.60) + Llama 4 Scout ($0.11/$0.34) = $0.13/$0.47
    "compound": {"input": 0.13, "output": 0.47},
    "groq/compound": {"input": 0.13, "output": 0.47},
    "compound-beta": {"input": 0.13, "output": 0.47},
    # compound-mini: GPT-OSS-120B ($0.15/$0.60) + Llama 3.3 70B ($0.59/$0.79) = $0.37/$0.695
    "compound-mini": {"input": 0.37, "output": 0.695},
    "groq/compound-mini": {"input": 0.37, "output": 0.695},
    "compound-mini-beta": {"input": 0.37, "output": 0.695},
}


class GroqProxyBackend:
    """LLM inference via Groq Cloud with HAProxy load balancing"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.usage_metrics = {}
        self.circuit_breaker_status = {}
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Groq client to use HAProxy load balancer"""
        if not GROQ_AVAILABLE:
            logger.warning("Groq client not available - running in development mode")
            return
            
        if self.settings.groq_api_key:
            # Use HAProxy load balancer instead of direct Groq API
            haproxy_endpoint = self.settings.haproxy_groq_endpoint or "http://haproxy-groq-lb-service.gt-resource.svc.cluster.local"
            
            # Initialize client with HAProxy endpoint
            self.client = AsyncGroq(
                api_key=self.settings.groq_api_key,
                base_url=haproxy_endpoint,
                timeout=httpx.Timeout(30.0),  # Increased timeout for load balancing
                max_retries=1  # Let HAProxy handle retries
            )
            
            # Initialize circuit breaker
            self.circuit_breaker_status = {
                "state": "closed",  # closed, open, half_open
                "failure_count": 0,
                "last_failure_time": None,
                "failure_threshold": 5,
                "recovery_timeout": 60  # seconds
            }
            
            logger.info(f"Initialized Groq client with HAProxy endpoint: {haproxy_endpoint}")
    
    async def execute_inference(
        self,
        prompt: str,
        model: str = "llama-3.1-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        stream: bool = False,
        user_id: str = None,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """Execute LLM inference with HAProxy load balancing and circuit breaker"""
        
        # Check circuit breaker
        if not await self._is_circuit_closed():
            raise Exception("Circuit breaker is open - service temporarily unavailable")
        
        # Validate model and get configuration
        model_configs = get_model_configs(tenant_id)
        model_config = model_configs.get("groq", {}).get(model)
        if not model_config:
            # Try to get from model service registry
            model_service = get_model_service(tenant_id)
            model_info = await model_service.get_model(model)
            if not model_info:
                raise ValueError(f"Unsupported model: {model}")
            model_config = {
                "max_tokens": model_info["performance"]["max_tokens"],
                "cost_per_1k_tokens": model_info["performance"]["cost_per_1k_tokens"],
                "supports_streaming": model_info["capabilities"].get("streaming", False)
            }
        
        # Apply token limits
        max_tokens = min(max_tokens, model_config["max_tokens"])
        
        # Prepare messages
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Get tenant-specific API key
            if not tenant_id:
                raise ValueError("tenant_id is required for Groq inference")
            
            api_key = await self._get_tenant_api_key(tenant_id)
            client = self._get_client(api_key)
            
            start_time = time.time()
            
            if stream:
                return await self._stream_inference(
                    messages, model, temperature, max_tokens, user_id, tenant_id, client
                )
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                
                # Track successful usage
                latency = (time.time() - start_time) * 1000
                await self._track_usage(
                    user_id, tenant_id, model,
                    response.usage.total_tokens if response.usage else 0,
                    latency, model_config["cost_per_1k_tokens"]
                )
                
                # Track in model service
                model_service = get_model_service(tenant_id)
                await model_service.track_model_usage(
                    model_id=model,
                    success=True,
                    latency_ms=latency
                )
                
                # Reset circuit breaker on success
                await self._record_success()
                
                return {
                    "content": response.choices[0].message.content,
                    "model": model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                        "cost_cents": self._calculate_cost(
                            response.usage.total_tokens if response.usage else 0,
                            model_config["cost_per_1k_tokens"]
                        )
                    },
                    "latency_ms": latency,
                    "load_balanced": True,
                    "haproxy_backend": "groq_general_backend"
                }
        
        except Exception as e:
            logger.error(f"HAProxy Groq inference failed: {e}")
            
            # Track failure in model service
            await model_service.track_model_usage(
                model_id=model,
                success=False
            )
            
            # Record failure for circuit breaker
            await self._record_failure()
            
            # Re-raise the exception - no client-side fallback needed
            # HAProxy handles all failover logic
            raise Exception(f"Groq inference failed (via HAProxy): {str(e)}")
    
    async def _stream_inference(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        user_id: str,
        tenant_id: str,
        client: AsyncGroq = None
    ) -> AsyncGenerator[str, None]:
        """Stream LLM inference responses"""
        
        model_configs = get_model_configs(tenant_id)
        model_config = model_configs.get("groq", {}).get(model)
        start_time = time.time()
        total_tokens = 0
        
        try:
            # Use provided client or get tenant-specific client
            if not client:
                api_key = await self._get_tenant_api_key(tenant_id)
                client = self._get_client(api_key)
            
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_tokens += len(content.split())  # Approximate token count
                    
                    # Yield SSE formatted data
                    yield f"data: {json.dumps({'content': content})}\n\n"
            
            # Track usage after streaming completes
            latency = (time.time() - start_time) * 1000
            await self._track_usage(
                user_id, tenant_id, model,
                total_tokens, latency,
                model_config["cost_per_1k_tokens"]
            )
            
            # Send completion signal
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming inference error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health of HAProxy load balancer and circuit breaker status"""
        
        try:
            # Check HAProxy health via stats endpoint
            haproxy_stats_url = self.settings.haproxy_stats_endpoint or "http://haproxy-groq-lb-service.gt-resource.svc.cluster.local:8404/stats"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    haproxy_stats_url,
                    timeout=5.0,
                    auth=("admin", "gt2_haproxy_stats_password")
                )
                
                if response.status_code == 200:
                    # Parse HAProxy stats (simplified)
                    stats_healthy = "UP" in response.text
                    
                    return {
                        "haproxy_load_balancer": {
                            "healthy": stats_healthy,
                            "stats_accessible": True,
                            "last_check": datetime.utcnow().isoformat()
                        },
                        "circuit_breaker": {
                            "state": self.circuit_breaker_status["state"],
                            "failure_count": self.circuit_breaker_status["failure_count"],
                            "last_failure": self.circuit_breaker_status["last_failure_time"].isoformat() if self.circuit_breaker_status["last_failure_time"] else None
                        },
                        "groq_endpoints": {
                            "managed_by": "haproxy",
                            "failover_handled_by": "haproxy"
                        }
                    }
                else:
                    return {
                        "haproxy_load_balancer": {
                            "healthy": False,
                            "error": f"Stats endpoint returned {response.status_code}",
                            "last_check": datetime.utcnow().isoformat()
                        }
                    }
                    
        except Exception as e:
            return {
                "haproxy_load_balancer": {
                    "healthy": False,
                    "error": str(e),
                    "last_check": datetime.utcnow().isoformat()
                },
                "circuit_breaker": {
                    "state": self.circuit_breaker_status["state"],
                    "failure_count": self.circuit_breaker_status["failure_count"]
                }
            }
    
    async def _is_circuit_closed(self) -> bool:
        """Check if circuit breaker allows requests"""
        
        if self.circuit_breaker_status["state"] == "closed":
            return True
        
        if self.circuit_breaker_status["state"] == "open":
            # Check if recovery timeout has passed
            if self.circuit_breaker_status["last_failure_time"]:
                time_since_failure = (datetime.utcnow() - self.circuit_breaker_status["last_failure_time"]).total_seconds()
                if time_since_failure > self.circuit_breaker_status["recovery_timeout"]:
                    # Move to half-open state
                    self.circuit_breaker_status["state"] = "half_open"
                    logger.info("Circuit breaker moved to half-open state")
                    return True
            return False
        
        if self.circuit_breaker_status["state"] == "half_open":
            # Allow limited requests in half-open state
            return True
        
        return False
    
    async def _record_success(self):
        """Record successful request for circuit breaker"""
        
        if self.circuit_breaker_status["state"] == "half_open":
            # Success in half-open state closes the circuit
            self.circuit_breaker_status["state"] = "closed"
            self.circuit_breaker_status["failure_count"] = 0
            logger.info("Circuit breaker closed after successful request")
        
        # Reset failure count on any success
        self.circuit_breaker_status["failure_count"] = 0
    
    async def _record_failure(self):
        """Record failed request for circuit breaker"""
        
        self.circuit_breaker_status["failure_count"] += 1
        self.circuit_breaker_status["last_failure_time"] = datetime.utcnow()
        
        if self.circuit_breaker_status["failure_count"] >= self.circuit_breaker_status["failure_threshold"]:
            if self.circuit_breaker_status["state"] in ["closed", "half_open"]:
                self.circuit_breaker_status["state"] = "open"
                logger.warning(f"Circuit breaker opened after {self.circuit_breaker_status['failure_count']} failures")
    
    async def _track_usage(
        self,
        user_id: str,
        tenant_id: str,
        model: str,
        tokens: int,
        latency: float,
        cost_per_1k: float
    ):
        """Track usage metrics for billing and monitoring"""
        
        # Create usage key
        usage_key = f"{tenant_id}:{user_id}:{model}"
        
        # Initialize metrics if not exists
        if usage_key not in self.usage_metrics:
            self.usage_metrics[usage_key] = {
                "total_tokens": 0,
                "total_requests": 0,
                "total_cost_cents": 0,
                "average_latency": 0
            }
        
        # Update metrics
        metrics = self.usage_metrics[usage_key]
        metrics["total_tokens"] += tokens
        metrics["total_requests"] += 1
        metrics["total_cost_cents"] += self._calculate_cost(tokens, cost_per_1k)
        
        # Update average latency
        prev_avg = metrics["average_latency"]
        prev_count = metrics["total_requests"] - 1
        metrics["average_latency"] = (prev_avg * prev_count + latency) / metrics["total_requests"]
        
        # Log high-level metrics
        if metrics["total_requests"] % 100 == 0:
            logger.info(f"Usage milestone for {usage_key}: {metrics}")
    
    def _calculate_cost(self, tokens: int, cost_per_1k: float) -> int:
        """Calculate cost in cents"""
        return int((tokens / 1000) * cost_per_1k * 100)

    def _calculate_compound_cost(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate detailed cost breakdown for Groq Compound responses.

        Compound API returns usage_breakdown with per-model token counts
        and executed_tools list showing which tools were called.

        Returns:
            Dict with total cost in dollars and detailed breakdown
        """
        total_cost = 0.0
        breakdown = {"models": [], "tools": [], "total_cost_dollars": 0.0, "total_cost_cents": 0}

        # Parse usage_breakdown for per-model token costs
        usage_breakdown = response_data.get("usage_breakdown", {})
        models_usage = usage_breakdown.get("models", [])

        for model_usage in models_usage:
            model_name = model_usage.get("model", "")
            usage = model_usage.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            # Get model pricing (try multiple name formats)
            model_prices = GROQ_MODEL_PRICES.get(model_name)
            if not model_prices:
                # Try without provider prefix
                short_name = model_name.split("/")[-1] if "/" in model_name else model_name
                model_prices = GROQ_MODEL_PRICES.get(short_name, {"input": 0.15, "output": 0.60})

            # Calculate cost per million tokens
            input_cost = (prompt_tokens / 1_000_000) * model_prices["input"]
            output_cost = (completion_tokens / 1_000_000) * model_prices["output"]
            model_total = input_cost + output_cost

            breakdown["models"].append({
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "input_cost_dollars": round(input_cost, 6),
                "output_cost_dollars": round(output_cost, 6),
                "total_cost_dollars": round(model_total, 6)
            })
            total_cost += model_total

        # Parse executed_tools for tool costs
        executed_tools = response_data.get("executed_tools", [])

        for tool in executed_tools:
            # Handle both string and dict formats
            tool_name = tool if isinstance(tool, str) else tool.get("name", "unknown")
            tool_cost = COMPOUND_TOOL_PRICES.get(tool_name.lower(), 0.008)  # Default to advanced search

            breakdown["tools"].append({
                "tool": tool_name,
                "cost_dollars": round(tool_cost, 6)
            })
            total_cost += tool_cost

        breakdown["total_cost_dollars"] = round(total_cost, 6)
        breakdown["total_cost_cents"] = int(total_cost * 100)

        return breakdown

    def _is_compound_model(self, model: str) -> bool:
        """Check if model is a Groq Compound model"""
        model_lower = model.lower()
        return "compound" in model_lower or model_lower.startswith("groq/compound")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Groq models with their configurations"""
        models = []
        
        model_configs = get_model_configs()
        for model_id, config in model_configs.get("groq", {}).items():
            models.append({
                "id": model_id,
                "name": model_id.replace("-", " ").title(),
                "provider": "groq",
                "max_tokens": config["max_tokens"],
                "cost_per_1k_tokens": config["cost_per_1k_tokens"],
                "supports_streaming": config["supports_streaming"],
                "supports_function_calling": config["supports_function_calling"]
            })
        
        return models
    
    async def execute_inference_with_messages(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.1-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        stream: bool = False,
        user_id: str = None,
        tenant_id: str = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute LLM inference using messages format (conversation style)"""
        
        # Check circuit breaker
        if not await self._is_circuit_closed():
            raise Exception("Circuit breaker is open - service temporarily unavailable")
        
        # Validate model and get configuration
        model_configs = get_model_configs(tenant_id)
        model_config = model_configs.get("groq", {}).get(model)
        if not model_config:
            # Try to get from model service registry
            model_service = get_model_service(tenant_id)
            model_info = await model_service.get_model(model)
            if not model_info:
                raise ValueError(f"Unsupported model: {model}")
            model_config = {
                "max_tokens": model_info["performance"]["max_tokens"],
                "cost_per_1k_tokens": model_info["performance"]["cost_per_1k_tokens"],
                "supports_streaming": model_info["capabilities"].get("streaming", False)
            }
        
        # Apply token limits
        max_tokens = min(max_tokens, model_config["max_tokens"])
        
        try:
            # Get tenant-specific API key
            if not tenant_id:
                raise ValueError("tenant_id is required for Groq inference")
            
            api_key = await self._get_tenant_api_key(tenant_id)
            client = self._get_client(api_key)
            
            start_time = time.time()
            
            # Translate GT 2.0 "agent" role to OpenAI/Groq "assistant" for external API compatibility
            # Use dictionary unpacking to preserve ALL fields including tool_call_id
            external_messages = []
            for msg in messages:
                external_msg = {
                    **msg,  # Preserve ALL fields including tool_call_id, tool_calls, etc.
                    "role": "assistant" if msg.get("role") == "agent" else msg.get("role")
                }
                external_messages.append(external_msg)
            
            if stream:
                return await self._stream_inference_with_messages(
                    external_messages, model, temperature, max_tokens, user_id, tenant_id, client
                )
            else:
                # Prepare request parameters
                request_params = {
                    "model": model,
                    "messages": external_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }

                # Add tools if provided
                if tools:
                    request_params["tools"] = tools
                if tool_choice:
                    request_params["tool_choice"] = tool_choice

                # Debug: Log messages being sent to Groq
                logger.info(f"🔧 Sending {len(external_messages)} messages to Groq API")
                for i, msg in enumerate(external_messages):
                    if msg.get("role") == "tool":
                        logger.info(f"🔧 Groq Message {i}: role=tool, tool_call_id={msg.get('tool_call_id')}")
                    else:
                        logger.info(f"🔧 Groq Message {i}: role={msg.get('role')}, has_tool_calls={bool(msg.get('tool_calls'))}")

                response = await client.chat.completions.create(**request_params)

                # Track successful usage
                latency = (time.time() - start_time) * 1000
                await self._track_usage(
                    user_id, tenant_id, model,
                    response.usage.total_tokens if response.usage else 0,
                    latency, model_config["cost_per_1k_tokens"]
                )

                # Track in model service
                model_service = get_model_service(tenant_id)
                await model_service.track_model_usage(
                    model_id=model,
                    success=True,
                    latency_ms=latency
                )

                # Reset circuit breaker on success
                await self._record_success()

                # Build base response
                result = {
                    "content": response.choices[0].message.content,
                    "model": model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                        "cost_cents": self._calculate_cost(
                            response.usage.total_tokens if response.usage else 0,
                            model_config["cost_per_1k_tokens"]
                        )
                    },
                    "latency_ms": latency,
                    "load_balanced": True,
                    "haproxy_backend": "groq_general_backend"
                }

                # For Compound models, extract and calculate detailed cost breakdown
                if self._is_compound_model(model):
                    # Convert response to dict for processing
                    response_dict = response.model_dump() if hasattr(response, 'model_dump') else {}

                    # Extract usage_breakdown and executed_tools if present
                    usage_breakdown = getattr(response, 'usage_breakdown', None)
                    executed_tools = getattr(response, 'executed_tools', None)

                    if usage_breakdown or executed_tools:
                        compound_data = {
                            "usage_breakdown": usage_breakdown if isinstance(usage_breakdown, dict) else {},
                            "executed_tools": executed_tools if isinstance(executed_tools, list) else []
                        }

                        # Calculate detailed cost breakdown
                        cost_breakdown = self._calculate_compound_cost(compound_data)

                        # Add compound-specific data to response
                        result["usage_breakdown"] = compound_data.get("usage_breakdown", {})
                        result["executed_tools"] = compound_data.get("executed_tools", [])
                        result["cost_breakdown"] = cost_breakdown

                        # Update cost_cents with accurate compound calculation
                        if cost_breakdown["total_cost_cents"] > 0:
                            result["usage"]["cost_cents"] = cost_breakdown["total_cost_cents"]

                        logger.info(f"Compound model cost breakdown: {cost_breakdown}")

                return result
        
        except Exception as e:
            logger.error(f"HAProxy Groq inference with messages failed: {e}")
            
            # Track failure in model service
            await model_service.track_model_usage(
                model_id=model,
                success=False
            )
            
            # Record failure for circuit breaker
            await self._record_failure()
            
            # Re-raise the exception
            raise Exception(f"Groq inference with messages failed (via HAProxy): {str(e)}")
    
    async def _stream_inference_with_messages(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        user_id: str,
        tenant_id: str,
        client: AsyncGroq = None
    ) -> AsyncGenerator[str, None]:
        """Stream LLM inference responses using messages format"""
        
        model_configs = get_model_configs(tenant_id)
        model_config = model_configs.get("groq", {}).get(model)
        start_time = time.time()
        total_tokens = 0
        
        try:
            # Use provided client or get tenant-specific client
            if not client:
                api_key = await self._get_tenant_api_key(tenant_id)
                client = self._get_client(api_key)
            
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_tokens += len(content.split())  # Approximate token count
                    
                    # Yield just the content (SSE formatting handled by caller)
                    yield content
            
            # Track usage after streaming completes
            latency = (time.time() - start_time) * 1000
            await self._track_usage(
                user_id, tenant_id, model,
                total_tokens, latency,
                model_config["cost_per_1k_tokens"] if model_config else 0.0
            )
            
        except Exception as e:
            logger.error(f"Streaming inference with messages error: {e}")
            raise e
    
    async def _get_tenant_api_key(self, tenant_id: str) -> str:
        """
        Get API key for tenant from Control Panel database.

        NO environment variable fallback - per GT 2.0 NO FALLBACKS principle.
        API keys are managed in Control Panel and fetched via internal API.

        Args:
            tenant_id: Tenant domain string from X-Tenant-ID header

        Returns:
            Decrypted Groq API key

        Raises:
            ValueError: If no API key configured (results in HTTP 503 to client)
        """
        from app.clients.api_key_client import get_api_key_client, APIKeyNotConfiguredError

        client = get_api_key_client()

        try:
            key_info = await client.get_api_key(tenant_domain=tenant_id, provider="groq")
            return key_info["api_key"]
        except APIKeyNotConfiguredError as e:
            logger.error(f"No Groq API key for tenant '{tenant_id}': {e}")
            raise ValueError(str(e))
        except RuntimeError as e:
            logger.error(f"Control Panel error: {e}")
            raise ValueError(f"Unable to retrieve API key - service unavailable: {e}")
    
    def _get_client(self, api_key: str) -> AsyncGroq:
        """Get Groq client with specified API key"""
        if not GROQ_AVAILABLE:
            raise Exception("Groq client not available in development mode")
        
        haproxy_endpoint = self.settings.haproxy_groq_endpoint or "http://haproxy-groq-lb-service.gt-resource.svc.cluster.local"
        
        return AsyncGroq(
            api_key=api_key,
            base_url=haproxy_endpoint,
            timeout=httpx.Timeout(30.0),
            max_retries=1
        )