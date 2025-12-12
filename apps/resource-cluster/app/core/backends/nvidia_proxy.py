"""
NVIDIA NIM LLM Proxy Backend

Provides LLM inference through NVIDIA NIM with:
- OpenAI-compatible API format (build.nvidia.com)
- Token usage tracking and cost calculation
- Streaming response support
- Circuit breaker pattern for enhanced reliability
"""

import json
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import httpx
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# NVIDIA NIM Model pricing per million tokens (input/output)
# Source: build.nvidia.com (Dec 2025 pricing estimates)
# Note: Actual pricing may vary - check build.nvidia.com for current rates
NVIDIA_MODEL_PRICES = {
    # Llama Nemotron family
    "nvidia/llama-3.1-nemotron-ultra-253b-v1": {"input": 2.0, "output": 6.0},
    "nvidia/llama-3.1-nemotron-super-49b-v1": {"input": 0.5, "output": 1.5},
    "nvidia/llama-3.1-nemotron-nano-8b-v1": {"input": 0.1, "output": 0.3},
    # Standard Llama models via NIM
    "meta/llama-3.1-8b-instruct": {"input": 0.1, "output": 0.3},
    "meta/llama-3.1-70b-instruct": {"input": 0.5, "output": 1.0},
    "meta/llama-3.1-405b-instruct": {"input": 2.0, "output": 6.0},
    # Mistral models
    "mistralai/mistral-7b-instruct-v0.3": {"input": 0.1, "output": 0.2},
    "mistralai/mixtral-8x7b-instruct-v0.1": {"input": 0.3, "output": 0.6},
    # Default fallback
    "default": {"input": 0.5, "output": 1.5},
}


class NvidiaProxyBackend:
    """LLM inference via NVIDIA NIM with OpenAI-compatible API"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = getattr(self.settings, 'nvidia_nim_endpoint', None) or "https://integrate.api.nvidia.com/v1"
        self.usage_metrics = {}
        self.circuit_breaker_status = {
            "state": "closed",  # closed, open, half_open
            "failure_count": 0,
            "last_failure_time": None,
            "failure_threshold": 5,
            "recovery_timeout": 60  # seconds
        }
        logger.info(f"Initialized NVIDIA NIM backend with endpoint: {self.base_url}")

    async def _get_tenant_api_key(self, tenant_id: str) -> str:
        """
        Get API key for tenant from Control Panel database.

        NO environment variable fallback - per GT 2.0 NO FALLBACKS principle.
        API keys are managed in Control Panel and fetched via internal API.

        Args:
            tenant_id: Tenant domain string from X-Tenant-ID header

        Returns:
            Decrypted NVIDIA API key

        Raises:
            ValueError: If no API key configured (results in HTTP 503 to client)
        """
        from app.clients.api_key_client import get_api_key_client, APIKeyNotConfiguredError

        client = get_api_key_client()

        try:
            key_info = await client.get_api_key(tenant_domain=tenant_id, provider="nvidia")
            return key_info["api_key"]
        except APIKeyNotConfiguredError as e:
            logger.error(f"No NVIDIA API key for tenant '{tenant_id}': {e}")
            raise ValueError(str(e))
        except RuntimeError as e:
            logger.error(f"Control Panel error: {e}")
            raise ValueError(f"Unable to retrieve API key - service unavailable: {e}")

    def _get_client(self, api_key: str) -> httpx.AsyncClient:
        """Get configured HTTP client for NVIDIA NIM API"""
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(120.0)  # Longer timeout for large models
        )

    async def execute_inference(
        self,
        prompt: str,
        model: str = "nvidia/llama-3.1-nemotron-super-49b-v1",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        stream: bool = False,
        user_id: str = None,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """Execute LLM inference with simple prompt"""

        messages = [{"role": "user", "content": prompt}]

        return await self.execute_inference_with_messages(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            user_id=user_id,
            tenant_id=tenant_id
        )

    async def execute_inference_with_messages(
        self,
        messages: List[Dict[str, str]],
        model: str = "nvidia/llama-3.1-nemotron-super-49b-v1",
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
            raise Exception("Circuit breaker is open - NVIDIA NIM service temporarily unavailable")

        if not tenant_id:
            raise ValueError("tenant_id is required for NVIDIA NIM inference")

        try:
            api_key = await self._get_tenant_api_key(tenant_id)

            # Translate GT 2.0 "agent" role to OpenAI "assistant" for external API compatibility
            external_messages = []
            for msg in messages:
                external_msg = {
                    **msg,  # Preserve ALL fields including tool_call_id, tool_calls, etc.
                    "role": "assistant" if msg.get("role") == "agent" else msg.get("role")
                }
                external_messages.append(external_msg)

            # Build request payload
            request_data = {
                "model": model,
                "messages": external_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }

            # Add tools if provided
            if tools:
                request_data["tools"] = tools
            if tool_choice:
                request_data["tool_choice"] = tool_choice

            start_time = time.time()

            async with self._get_client(api_key) as client:
                if stream:
                    # Return generator for streaming
                    return self._stream_inference_with_messages(
                        client, request_data, user_id, tenant_id, model
                    )

                # Non-streaming request
                response = await client.post("/chat/completions", json=request_data)
                response.raise_for_status()
                data = response.json()

            latency = (time.time() - start_time) * 1000

            # Calculate cost
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            model_prices = NVIDIA_MODEL_PRICES.get(model, NVIDIA_MODEL_PRICES["default"])
            input_cost = (prompt_tokens / 1_000_000) * model_prices["input"]
            output_cost = (completion_tokens / 1_000_000) * model_prices["output"]
            cost_cents = int((input_cost + output_cost) * 100)

            # Track usage
            await self._track_usage(user_id, tenant_id, model, total_tokens, latency, cost_cents)

            # Reset circuit breaker on success
            await self._record_success()

            # Build response
            result = {
                "content": data["choices"][0]["message"]["content"],
                "model": model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_cents": cost_cents
                },
                "latency_ms": latency,
                "provider": "nvidia"
            }

            # Include tool calls if present
            message = data["choices"][0]["message"]
            if message.get("tool_calls"):
                result["tool_calls"] = message["tool_calls"]

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"NVIDIA NIM API error: {e.response.status_code} - {e.response.text}")
            await self._record_failure()
            raise Exception(f"NVIDIA NIM inference failed: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"NVIDIA NIM inference failed: {e}")
            await self._record_failure()
            raise Exception(f"NVIDIA NIM inference failed: {str(e)}")

    async def _stream_inference_with_messages(
        self,
        client: httpx.AsyncClient,
        request_data: Dict[str, Any],
        user_id: str,
        tenant_id: str,
        model: str
    ) -> AsyncGenerator[str, None]:
        """Stream LLM inference responses"""

        start_time = time.time()
        total_tokens = 0

        try:
            async with client.stream("POST", "/chat/completions", json=request_data) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                                content = chunk["choices"][0]["delta"]["content"]
                                total_tokens += len(content.split())  # Approximate
                                yield content
                        except json.JSONDecodeError:
                            continue

            # Track usage after streaming completes
            latency = (time.time() - start_time) * 1000
            model_prices = NVIDIA_MODEL_PRICES.get(model, NVIDIA_MODEL_PRICES["default"])
            cost_cents = int((total_tokens / 1_000_000) * model_prices["output"] * 100)
            await self._track_usage(user_id, tenant_id, model, total_tokens, latency, cost_cents)

            await self._record_success()

        except Exception as e:
            logger.error(f"NVIDIA NIM streaming error: {e}")
            await self._record_failure()
            raise e

    async def check_health(self) -> Dict[str, Any]:
        """Check health of NVIDIA NIM backend and circuit breaker status"""

        return {
            "nvidia_nim": {
                "endpoint": self.base_url,
                "status": "available" if self.circuit_breaker_status["state"] == "closed" else "degraded",
                "last_check": datetime.utcnow().isoformat()
            },
            "circuit_breaker": {
                "state": self.circuit_breaker_status["state"],
                "failure_count": self.circuit_breaker_status["failure_count"],
                "last_failure": self.circuit_breaker_status["last_failure_time"].isoformat()
                    if self.circuit_breaker_status["last_failure_time"] else None
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
                    logger.info("NVIDIA NIM circuit breaker moved to half-open state")
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
            logger.info("NVIDIA NIM circuit breaker closed after successful request")

        # Reset failure count on any success
        self.circuit_breaker_status["failure_count"] = 0

    async def _record_failure(self):
        """Record failed request for circuit breaker"""

        self.circuit_breaker_status["failure_count"] += 1
        self.circuit_breaker_status["last_failure_time"] = datetime.utcnow()

        if self.circuit_breaker_status["failure_count"] >= self.circuit_breaker_status["failure_threshold"]:
            if self.circuit_breaker_status["state"] in ["closed", "half_open"]:
                self.circuit_breaker_status["state"] = "open"
                logger.warning(f"NVIDIA NIM circuit breaker opened after {self.circuit_breaker_status['failure_count']} failures")

    async def _track_usage(
        self,
        user_id: str,
        tenant_id: str,
        model: str,
        tokens: int,
        latency: float,
        cost_cents: int
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
        metrics["total_cost_cents"] += cost_cents

        # Update average latency
        prev_avg = metrics["average_latency"]
        prev_count = metrics["total_requests"] - 1
        metrics["average_latency"] = (prev_avg * prev_count + latency) / metrics["total_requests"]

        # Log high-level metrics periodically
        if metrics["total_requests"] % 100 == 0:
            logger.info(f"NVIDIA NIM usage milestone for {usage_key}: {metrics}")

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> int:
        """Calculate cost in cents based on token usage"""
        model_prices = NVIDIA_MODEL_PRICES.get(model, NVIDIA_MODEL_PRICES["default"])
        input_cost = (prompt_tokens / 1_000_000) * model_prices["input"]
        output_cost = (completion_tokens / 1_000_000) * model_prices["output"]
        return int((input_cost + output_cost) * 100)

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available NVIDIA NIM models with their configurations"""
        models = []

        for model_id, prices in NVIDIA_MODEL_PRICES.items():
            if model_id == "default":
                continue

            models.append({
                "id": model_id,
                "name": model_id.split("/")[-1].replace("-", " ").title(),
                "provider": "nvidia",
                "max_tokens": 4096,  # Default for most NIM models
                "cost_per_1k_input": prices["input"],
                "cost_per_1k_output": prices["output"],
                "supports_streaming": True,
                "supports_function_calling": True
            })

        return models
