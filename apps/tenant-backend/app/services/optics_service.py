"""
Optics Cost Calculation Service

Calculates inference and storage costs for the Optics feature.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import httpx
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Storage cost rate
STORAGE_COST_PER_MB_CENTS = 4.0  # $0.04 per MB

# Fallback pricing for unknown models
DEFAULT_MODEL_PRICING = {
    "cost_per_1k_input": 0.10,
    "cost_per_1k_output": 0.10
}


class OpticsPricingCache:
    """Simple in-memory cache for model pricing"""
    _pricing: Optional[Dict[str, Any]] = None
    _expires_at: Optional[datetime] = None
    _ttl_seconds: int = 300  # 5 minutes

    @classmethod
    def get(cls) -> Optional[Dict[str, Any]]:
        if cls._pricing and cls._expires_at and datetime.utcnow() < cls._expires_at:
            return cls._pricing
        return None

    @classmethod
    def set(cls, pricing: Dict[str, Any]):
        cls._pricing = pricing
        cls._expires_at = datetime.utcnow() + timedelta(seconds=cls._ttl_seconds)

    @classmethod
    def clear(cls):
        cls._pricing = None
        cls._expires_at = None


async def fetch_optics_settings(tenant_domain: str) -> Dict[str, Any]:
    """
    Fetch Optics settings from Control Panel for a tenant.

    Returns:
        dict with 'enabled', 'storage_cost_per_mb_cents'
    """
    settings = get_settings()
    control_panel_url = settings.control_panel_url or "http://gentwo-control-panel-backend:8001"
    service_token = settings.service_auth_token or "internal-service-token"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{control_panel_url}/internal/optics/tenant/{tenant_domain}/settings",
                headers={
                    "X-Service-Auth": service_token,
                    "X-Service-Name": "tenant-backend"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Tenant {tenant_domain} not found in Control Panel")
                return {"enabled": False, "storage_cost_per_mb_cents": STORAGE_COST_PER_MB_CENTS}
            else:
                logger.error(f"Failed to fetch optics settings: {response.status_code}")
                return {"enabled": False, "storage_cost_per_mb_cents": STORAGE_COST_PER_MB_CENTS}

    except Exception as e:
        logger.error(f"Error fetching optics settings: {str(e)}")
        # Default to disabled on error
        return {"enabled": False, "storage_cost_per_mb_cents": STORAGE_COST_PER_MB_CENTS}


async def fetch_model_pricing() -> Dict[str, Dict[str, float]]:
    """
    Fetch model pricing from Control Panel.
    Uses caching to avoid repeated requests.

    Returns:
        dict mapping model_id -> {cost_per_1k_input, cost_per_1k_output}
    """
    # Check cache first
    cached = OpticsPricingCache.get()
    if cached:
        return cached

    settings = get_settings()
    control_panel_url = settings.control_panel_url or "http://gentwo-control-panel-backend:8001"
    service_token = settings.service_auth_token or "internal-service-token"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{control_panel_url}/internal/optics/model-pricing",
                headers={
                    "X-Service-Auth": service_token,
                    "X-Service-Name": "tenant-backend"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                pricing = data.get("models", {})
                OpticsPricingCache.set(pricing)
                return pricing
            else:
                logger.error(f"Failed to fetch model pricing: {response.status_code}")
                return {}

    except Exception as e:
        logger.error(f"Error fetching model pricing: {str(e)}")
        return {}


def get_model_cost_per_1k(model_id: str, pricing_map: Dict[str, Dict[str, float]]) -> float:
    """
    Get combined cost per 1k tokens for a model.

    Args:
        model_id: Model identifier (e.g., 'llama-3.3-70b-versatile')
        pricing_map: Map of model_id -> pricing info

    Returns:
        Combined input + output cost per 1k tokens in dollars
    """
    pricing = pricing_map.get(model_id)
    if pricing:
        return (pricing.get("cost_per_1k_input", 0.0) + pricing.get("cost_per_1k_output", 0.0))

    # Try variations of the model ID
    # Sometimes model_used might have provider prefix like "groq:model-name"
    if ":" in model_id:
        model_name = model_id.split(":", 1)[1]
        pricing = pricing_map.get(model_name)
        if pricing:
            return (pricing.get("cost_per_1k_input", 0.0) + pricing.get("cost_per_1k_output", 0.0))

    # Return default pricing
    return DEFAULT_MODEL_PRICING["cost_per_1k_input"] + DEFAULT_MODEL_PRICING["cost_per_1k_output"]


def calculate_inference_cost_cents(tokens: int, cost_per_1k: float) -> float:
    """
    Calculate inference cost in cents from token count.

    Args:
        tokens: Total token count
        cost_per_1k: Cost per 1000 tokens in dollars

    Returns:
        Cost in cents
    """
    return (tokens / 1000) * cost_per_1k * 100


def calculate_storage_cost_cents(total_mb: float, cost_per_mb_cents: float = STORAGE_COST_PER_MB_CENTS) -> float:
    """
    Calculate storage cost in cents.

    Args:
        total_mb: Total storage in megabytes
        cost_per_mb_cents: Cost per MB in cents (default 4 cents = $0.04)

    Returns:
        Cost in cents
    """
    return total_mb * cost_per_mb_cents


def format_cost_display(cents: float) -> str:
    """Format cost in cents to a display string like '$12.34'"""
    dollars = cents / 100
    return f"${dollars:,.2f}"


async def get_optics_cost_summary(
    pg_client,
    tenant_domain: str,
    date_start: datetime,
    date_end: datetime,
    user_id: Optional[str] = None,
    include_user_breakdown: bool = False
) -> Dict[str, Any]:
    """
    Calculate full Optics cost summary for a tenant.

    Args:
        pg_client: PostgreSQL client
        tenant_domain: Tenant domain
        date_start: Start date for cost calculation
        date_end: End date for cost calculation
        user_id: Optional user ID filter
        include_user_breakdown: Whether to include per-user breakdown

    Returns:
        Complete cost summary with breakdowns
    """
    schema = f"tenant_{tenant_domain.replace('-', '_')}"

    # Fetch model pricing
    pricing_map = await fetch_model_pricing()

    # Build user filter
    user_filter = ""
    params = [date_start, date_end]
    param_idx = 3

    if user_id:
        user_filter = f"AND c.user_id = ${param_idx}::uuid"
        params.append(user_id)
        param_idx += 1

    # Query token usage by model
    token_query = f"""
        SELECT
            COALESCE(m.model_used, 'unknown') as model_id,
            COALESCE(SUM(m.token_count), 0) as total_tokens,
            COUNT(DISTINCT c.id) as conversations,
            COUNT(m.id) as messages
        FROM {schema}.messages m
        JOIN {schema}.conversations c ON m.conversation_id = c.id
        WHERE c.created_at >= $1 AND c.created_at <= $2
          AND m.model_used IS NOT NULL AND m.model_used != ''
          {user_filter}
        GROUP BY m.model_used
        ORDER BY total_tokens DESC
    """

    token_results = await pg_client.execute_query(token_query, *params)

    # Calculate inference costs by model
    by_model = []
    total_inference_cents = 0.0
    total_tokens = 0

    for row in token_results or []:
        model_id = row["model_id"]
        tokens = int(row["total_tokens"])
        total_tokens += tokens

        cost_per_1k = get_model_cost_per_1k(model_id, pricing_map)
        cost_cents = calculate_inference_cost_cents(tokens, cost_per_1k)
        total_inference_cents += cost_cents

        # Clean up model name for display
        model_name = model_id.split(":")[-1] if ":" in model_id else model_id

        by_model.append({
            "model_id": model_id,
            "model_name": model_name,
            "tokens": tokens,
            "conversations": row["conversations"],
            "messages": row["messages"],
            "cost_cents": round(cost_cents, 2),
            "cost_display": format_cost_display(cost_cents)
        })

    # Calculate percentages
    for item in by_model:
        item["percentage"] = round((item["cost_cents"] / total_inference_cents * 100) if total_inference_cents > 0 else 0, 1)

    # Query storage
    storage_params = []
    storage_user_filter = ""
    if user_id:
        storage_user_filter = f"WHERE d.user_id = $1::uuid"
        storage_params.append(user_id)

    storage_query = f"""
        SELECT
            COALESCE(SUM(d.file_size_bytes), 0) / 1048576.0 as total_mb,
            COUNT(d.id) as document_count,
            COUNT(DISTINCT d.dataset_id) as dataset_count
        FROM {schema}.documents d
        {storage_user_filter}
    """

    storage_result = await pg_client.execute_query(storage_query, *storage_params) if storage_params else await pg_client.execute_query(storage_query)
    storage_data = storage_result[0] if storage_result else {"total_mb": 0, "document_count": 0, "dataset_count": 0}

    total_storage_mb = float(storage_data.get("total_mb", 0))
    storage_cost_cents = calculate_storage_cost_cents(total_storage_mb)

    # Total cost
    total_cost_cents = total_inference_cents + storage_cost_cents

    # User breakdown (admin only)
    by_user = []
    if include_user_breakdown:
        user_query = f"""
            SELECT
                c.user_id,
                u.email,
                COALESCE(SUM(m.token_count), 0) as tokens
            FROM {schema}.messages m
            JOIN {schema}.conversations c ON m.conversation_id = c.id
            JOIN {schema}.users u ON c.user_id = u.id
            WHERE c.created_at >= $1 AND c.created_at <= $2
            GROUP BY c.user_id, u.email
            ORDER BY tokens DESC
        """

        user_results = await pg_client.execute_query(user_query, date_start, date_end)

        for row in user_results or []:
            user_tokens = int(row["tokens"])
            # Use average model cost for user breakdown
            avg_cost_per_1k = (total_inference_cents / total_tokens * 10) if total_tokens > 0 else 0.2
            user_cost_cents = (user_tokens / 1000) * avg_cost_per_1k

            by_user.append({
                "user_id": str(row["user_id"]),
                "email": row["email"],
                "tokens": user_tokens,
                "cost_cents": round(user_cost_cents, 2),
                "cost_display": format_cost_display(user_cost_cents),
                "percentage": round((user_tokens / total_tokens * 100) if total_tokens > 0 else 0, 1)
            })

    return {
        "inference_cost_cents": round(total_inference_cents, 2),
        "storage_cost_cents": round(storage_cost_cents, 2),
        "total_cost_cents": round(total_cost_cents, 2),
        "inference_cost_display": format_cost_display(total_inference_cents),
        "storage_cost_display": format_cost_display(storage_cost_cents),
        "total_cost_display": format_cost_display(total_cost_cents),
        "total_tokens": total_tokens,
        "total_storage_mb": round(total_storage_mb, 2),
        "document_count": storage_data.get("document_count", 0),
        "dataset_count": storage_data.get("dataset_count", 0),
        "by_model": by_model,
        "by_user": by_user if include_user_breakdown else None,
        "period_start": date_start.isoformat(),
        "period_end": date_end.isoformat()
    }
