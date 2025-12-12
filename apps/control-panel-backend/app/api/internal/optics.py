"""
Internal API for service-to-service Optics settings retrieval
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional

from app.core.database import get_db
from app.models.tenant import Tenant
from app.core.config import settings

router = APIRouter(prefix="/internal/optics", tags=["Internal Optics"])


async def verify_service_auth(
    x_service_auth: str = Header(None),
    x_service_name: str = Header(None)
) -> bool:
    """Verify service-to-service authentication"""

    if not x_service_auth or not x_service_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication required"
        )

    # Verify service token (in production, use proper service mesh auth)
    expected_token = settings.SERVICE_AUTH_TOKEN or "internal-service-token"
    if x_service_auth != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service authentication"
        )

    # Verify service is allowed
    allowed_services = ["resource-cluster", "tenant-backend"]
    if x_service_name not in allowed_services:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Service {x_service_name} not authorized"
        )

    return True


@router.get("/tenant/{tenant_domain}/settings")
async def get_tenant_optics_settings(
    tenant_domain: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Internal endpoint for tenant backend to get Optics settings.

    Returns:
        - enabled: Whether Optics is enabled for this tenant
        - storage_pricing: Storage cost rates per tier (in cents per MB per month)
        - budget: Budget limits and thresholds
    """

    # Query tenant by domain
    result = await db.execute(
        select(Tenant).where(Tenant.domain == tenant_domain)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant not found: {tenant_domain}"
        )

    # Hot tier default: $0.15/GiB/month = ~0.0146 cents/MiB
    HOT_TIER_DEFAULT_CENTS_PER_MIB = 0.146484375  # $0.15/GiB = $0.15/1024 per MiB * 100 cents

    return {
        "enabled": tenant.optics_enabled or False,
        "storage_pricing": {
            "dataset_hot": float(tenant.storage_price_dataset_hot) if tenant.storage_price_dataset_hot else HOT_TIER_DEFAULT_CENTS_PER_MIB,
            "conversation_hot": float(tenant.storage_price_conversation_hot) if tenant.storage_price_conversation_hot else HOT_TIER_DEFAULT_CENTS_PER_MIB,
        },
        "cold_allocation": {
            "allocated_tibs": float(tenant.cold_storage_allocated_tibs) if tenant.cold_storage_allocated_tibs else None,
            "price_per_tib": float(tenant.cold_storage_price_per_tib) if tenant.cold_storage_price_per_tib else 10.00,
        },
        "budget": {
            "monthly_budget_cents": tenant.monthly_budget_cents,
            "warning_threshold": tenant.budget_warning_threshold or 80,
            "critical_threshold": tenant.budget_critical_threshold or 90,
            "enforcement_enabled": tenant.budget_enforcement_enabled or False
        },
        "tenant_id": tenant.id,
        "tenant_name": tenant.name
    }


@router.get("/model-pricing")
async def get_model_pricing(
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Internal endpoint for tenant backend to get model pricing.

    Returns all model pricing from model_configs table.
    """
    from app.models.model_config import ModelConfig

    result = await db.execute(
        select(ModelConfig).where(ModelConfig.is_active == True)
    )
    models = result.scalars().all()

    pricing = {}
    for model in models:
        pricing[model.model_id] = {
            "name": model.name,
            "provider": model.provider,
            "cost_per_million_input": model.cost_per_million_input or 0.0,
            "cost_per_million_output": model.cost_per_million_output or 0.0
        }

    return {
        "models": pricing,
        "default_pricing": {
            "cost_per_million_input": 0.10,
            "cost_per_million_output": 0.10
        }
    }


@router.get("/tenant/{tenant_domain}/embedding-usage")
async def get_tenant_embedding_usage(
    tenant_domain: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Internal endpoint for tenant backend to get embedding usage for billing.

    Queries the embedding_usage_logs table for a tenant within a date range.
    This enables Issue #241 - Embedding Model Pricing.

    Args:
        tenant_domain: Tenant domain (e.g., 'test-company')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        {
            "total_tokens": int,
            "total_cost_cents": float,
            "embedding_count": int,
            "by_model": [{"model": str, "tokens": int, "cost_cents": float, "count": int}]
        }
    """
    from datetime import datetime, timedelta

    try:
        # Parse string dates to datetime objects for asyncpg
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # Include full end day

        # Query embedding usage aggregated by model
        query = text("""
            SELECT
                model,
                COALESCE(SUM(tokens_used), 0) as total_tokens,
                COALESCE(SUM(cost_cents), 0) as total_cost_cents,
                COALESCE(SUM(embedding_count), 0) as embedding_count,
                COUNT(*) as request_count
            FROM public.embedding_usage_logs
            WHERE tenant_id = :tenant_domain
              AND timestamp >= :start_dt
              AND timestamp <= :end_dt
            GROUP BY model
            ORDER BY total_cost_cents DESC
        """)

        result = await db.execute(
            query,
            {
                "tenant_domain": tenant_domain,
                "start_dt": start_dt,
                "end_dt": end_dt
            }
        )

        rows = result.fetchall()

        # Aggregate results
        total_tokens = 0
        total_cost_cents = 0.0
        total_embedding_count = 0
        by_model = []

        for row in rows:
            model_data = {
                "model": row.model or "unknown",
                "tokens": int(row.total_tokens),
                "cost_cents": float(row.total_cost_cents),
                "count": int(row.embedding_count),
                "requests": int(row.request_count)
            }
            by_model.append(model_data)
            total_tokens += model_data["tokens"]
            total_cost_cents += model_data["cost_cents"]
            total_embedding_count += model_data["count"]

        return {
            "total_tokens": total_tokens,
            "total_cost_cents": round(total_cost_cents, 4),
            "embedding_count": total_embedding_count,
            "by_model": by_model
        }

    except Exception as e:
        # Log but return empty response on error (don't block billing)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching embedding usage for {tenant_domain}: {e}")

        return {
            "total_tokens": 0,
            "total_cost_cents": 0.0,
            "embedding_count": 0,
            "by_model": []
        }
