"""
Optics Cost Tracking API Endpoints

Provides cost visibility for inference and storage usage.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
import logging

from app.core.postgresql_client import get_postgresql_client
from app.api.v1.observability import get_current_user, get_user_role

from app.services.optics_service import (
    fetch_optics_settings,
    get_optics_cost_summary,
    STORAGE_COST_PER_MB_CENTS
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/optics", tags=["Optics Cost Tracking"])


# Response models
class OpticsSettingsResponse(BaseModel):
    enabled: bool
    storage_cost_per_mb_cents: float
    show_to_admins_only: bool = True


class ModelCostBreakdown(BaseModel):
    model_id: str
    model_name: str
    tokens: int
    conversations: int
    messages: int
    cost_cents: float
    cost_display: str
    percentage: float


class UserCostBreakdown(BaseModel):
    user_id: str
    email: str
    tokens: int
    cost_cents: float
    cost_display: str
    percentage: float


class OpticsCostResponse(BaseModel):
    enabled: bool
    inference_cost_cents: float
    storage_cost_cents: float
    total_cost_cents: float
    inference_cost_display: str
    storage_cost_display: str
    total_cost_display: str
    total_tokens: int
    total_storage_mb: float
    document_count: int
    dataset_count: int
    by_model: List[ModelCostBreakdown]
    by_user: Optional[List[UserCostBreakdown]] = None
    period_start: str
    period_end: str


@router.get("/settings", response_model=OpticsSettingsResponse)
async def get_optics_settings(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Check if Optics is enabled for the current tenant.

    This endpoint is used by the frontend to determine whether
    to show the Optics tab in the observability dashboard.
    """
    tenant_domain = current_user.get("tenant_domain", "test-company")

    try:
        settings = await fetch_optics_settings(tenant_domain)

        return OpticsSettingsResponse(
            enabled=settings.get("enabled", False),
            storage_cost_per_mb_cents=settings.get("storage_cost_per_mb_cents", STORAGE_COST_PER_MB_CENTS),
            show_to_admins_only=True  # Only admins can see user breakdown
        )

    except Exception as e:
        logger.error(f"Error fetching optics settings: {str(e)}")
        return OpticsSettingsResponse(
            enabled=False,
            storage_cost_per_mb_cents=STORAGE_COST_PER_MB_CENTS,
            show_to_admins_only=True
        )


@router.get("/costs", response_model=OpticsCostResponse)
async def get_optics_costs(
    days: Optional[int] = Query(30, ge=1, le=365, description="Number of days to look back"),
    start_date: Optional[str] = Query(None, description="Custom start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Custom end date (ISO format)"),
    user_id: Optional[str] = Query(None, description="Filter by user ID (admin only)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get Optics cost breakdown for the current tenant.

    Returns inference costs calculated from token usage and model pricing,
    plus storage costs at the configured rate (default 4 cents/MB).

    - **days**: Number of days to look back (default 30)
    - **start_date**: Custom start date (overrides days)
    - **end_date**: Custom end date
    - **user_id**: Filter by specific user (admin only)
    """
    tenant_domain = current_user.get("tenant_domain", "test-company")

    # Check if Optics is enabled
    settings = await fetch_optics_settings(tenant_domain)
    if not settings.get("enabled", False):
        return OpticsCostResponse(
            enabled=False,
            inference_cost_cents=0,
            storage_cost_cents=0,
            total_cost_cents=0,
            inference_cost_display="$0.00",
            storage_cost_display="$0.00",
            total_cost_display="$0.00",
            total_tokens=0,
            total_storage_mb=0,
            document_count=0,
            dataset_count=0,
            by_model=[],
            by_user=None,
            period_start=datetime.utcnow().isoformat(),
            period_end=datetime.utcnow().isoformat()
        )

    pg_client = await get_postgresql_client()

    # Get user role for permission checks
    user_email = current_user.get("email", "")
    user_role = await get_user_role(pg_client, user_email, tenant_domain)

    is_admin = user_role in ["admin", "developer"]

    # Handle user filter - only admins can filter by user
    filter_user_id = None
    if user_id:
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can filter by user"
            )
        filter_user_id = user_id
    elif not is_admin:
        # Non-admins can only see their own data
        # Get user UUID from email
        user_query = f"""
            SELECT id FROM tenant_{tenant_domain.replace('-', '_')}.users
            WHERE email = $1 LIMIT 1
        """
        user_result = await pg_client.execute_query(user_query, user_email)
        if user_result:
            filter_user_id = str(user_result[0]["id"])

    # Calculate date range
    date_end = datetime.utcnow()
    date_start = date_end - timedelta(days=days)

    if start_date:
        try:
            date_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format."
            )

    if end_date:
        try:
            date_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format."
            )

    try:
        cost_summary = await get_optics_cost_summary(
            pg_client=pg_client,
            tenant_domain=tenant_domain,
            date_start=date_start,
            date_end=date_end,
            user_id=filter_user_id,
            include_user_breakdown=is_admin and not filter_user_id  # Only include breakdown for platform view
        )

        # Convert to response model
        by_model = [
            ModelCostBreakdown(**item)
            for item in cost_summary.get("by_model", [])
        ]

        by_user = None
        if cost_summary.get("by_user"):
            by_user = [
                UserCostBreakdown(**item)
                for item in cost_summary["by_user"]
            ]

        return OpticsCostResponse(
            enabled=True,
            inference_cost_cents=cost_summary["inference_cost_cents"],
            storage_cost_cents=cost_summary["storage_cost_cents"],
            total_cost_cents=cost_summary["total_cost_cents"],
            inference_cost_display=cost_summary["inference_cost_display"],
            storage_cost_display=cost_summary["storage_cost_display"],
            total_cost_display=cost_summary["total_cost_display"],
            total_tokens=cost_summary["total_tokens"],
            total_storage_mb=cost_summary["total_storage_mb"],
            document_count=cost_summary["document_count"],
            dataset_count=cost_summary["dataset_count"],
            by_model=by_model,
            by_user=by_user,
            period_start=cost_summary["period_start"],
            period_end=cost_summary["period_end"]
        )

    except Exception as e:
        logger.error(f"Error calculating optics costs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate costs"
        )
