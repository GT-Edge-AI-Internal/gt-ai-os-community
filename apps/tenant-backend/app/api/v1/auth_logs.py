"""
Authentication Logs API Endpoints
Issue: #152

Provides endpoints for querying authentication event logs including:
- User logins
- User logouts
- Failed login attempts

Used by observability dashboard for security monitoring and audit trails.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog

from app.core.security import get_current_user
from app.core.database import get_postgresql_client

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/auth-logs")
async def get_auth_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type: login, logout, failed_login"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering (ISO format)"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get authentication logs with optional filtering.

    Returns paginated list of authentication events including logins, logouts,
    and failed login attempts.
    """
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        schema_name = f"tenant_{tenant_domain.replace('-', '_')}"

        # Build query conditions
        conditions = []
        params = []
        param_counter = 1

        if event_type:
            if event_type not in ['login', 'logout', 'failed_login']:
                raise HTTPException(status_code=400, detail="Invalid event_type. Must be: login, logout, or failed_login")
            conditions.append(f"event_type = ${param_counter}")
            params.append(event_type)
            param_counter += 1

        if start_date:
            conditions.append(f"created_at >= ${param_counter}")
            params.append(start_date)
            param_counter += 1

        if end_date:
            conditions.append(f"created_at <= ${param_counter}")
            params.append(end_date)
            param_counter += 1

        if user_email:
            conditions.append(f"email = ${param_counter}")
            params.append(user_email)
            param_counter += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Get total count
        client = await get_postgresql_client()
        count_query = f"""
            SELECT COUNT(*) as total
            FROM {schema_name}.auth_logs
            {where_clause}
        """
        count_result = await client.fetch_one(count_query, *params)
        total_count = count_result['total'] if count_result else 0

        # Get paginated results
        query = f"""
            SELECT
                id,
                user_id,
                email,
                event_type,
                success,
                failure_reason,
                ip_address,
                user_agent,
                tenant_domain,
                created_at,
                metadata
            FROM {schema_name}.auth_logs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """
        params.extend([limit, offset])

        logs = await client.fetch_all(query, *params)

        # Format results
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                "id": str(log['id']),
                "user_id": log['user_id'],
                "email": log['email'],
                "event_type": log['event_type'],
                "success": log['success'],
                "failure_reason": log['failure_reason'],
                "ip_address": log['ip_address'],
                "user_agent": log['user_agent'],
                "tenant_domain": log['tenant_domain'],
                "created_at": log['created_at'].isoformat() if log['created_at'] else None,
                "metadata": log['metadata']
            })

        logger.info(
            "Retrieved authentication logs",
            tenant=tenant_domain,
            count=len(formatted_logs),
            filters={"event_type": event_type, "user_email": user_email}
        )

        return {
            "logs": formatted_logs,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve auth logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth-logs/summary")
async def get_auth_logs_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to summarize"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get authentication log summary statistics.

    Returns aggregated counts of login events by type for the specified time period.
    """
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        schema_name = f"tenant_{tenant_domain.replace('-', '_')}"

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        client = await get_postgresql_client()
        query = f"""
            SELECT
                event_type,
                success,
                COUNT(*) as count
            FROM {schema_name}.auth_logs
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY event_type, success
            ORDER BY event_type, success
        """

        results = await client.fetch_all(query, start_date, end_date)

        # Format summary
        summary = {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "events": {
                "successful_logins": 0,
                "failed_logins": 0,
                "logouts": 0,
                "total": 0
            }
        }

        for row in results:
            event_type = row['event_type']
            success = row['success']
            count = row['count']

            if event_type == 'login' and success:
                summary['events']['successful_logins'] = count
            elif event_type == 'failed_login' or (event_type == 'login' and not success):
                summary['events']['failed_logins'] += count
            elif event_type == 'logout':
                summary['events']['logouts'] = count

            summary['events']['total'] += count

        logger.info(
            "Retrieved auth logs summary",
            tenant=tenant_domain,
            days=days,
            total_events=summary['events']['total']
        )

        return summary

    except Exception as e:
        logger.error(f"Failed to retrieve auth logs summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
