"""
Gen Two Observability API
Tenant admin dashboard endpoints for usage observability, conversation viewing, and data export.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import csv
import io
import json
import logging

from app.core.security import get_current_user
from app.core.permissions import get_user_role

# Storage multipliers for calculating actual disk usage from logical size
DATASET_STORAGE_MULTIPLIER = 4.5       # Measured: 20.09 MB actual / 4.50 MB logical = 4.46x
CONVERSATION_STORAGE_MULTIPLIER = 19   # Measured: 7.39 MB actual / 0.39 MB logical = 18.9x (index-heavy)
EMBEDDING_SIZE_BYTES = 4096            # 1024 floats × 4 bytes per float32 (PGVector)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/observability", tags=["observability"])


# ============================================================================
# Request/Response Models
# ============================================================================

class OverviewMetrics(BaseModel):
    """Summary metrics for dashboard overview."""
    total_conversations: int
    total_messages: int
    total_tokens: int
    unique_users: int
    date_range_start: datetime
    date_range_end: datetime


class TimeSeriesDataPoint(BaseModel):
    """Single data point in time series."""
    date: str
    conversation_count: int
    message_count: int
    token_count: int
    unique_users: int


class BreakdownItem(BaseModel):
    """Breakdown item (user, agent, or model)."""
    id: str
    label: str
    value: int
    percentage: float
    metadata: Optional[Dict[str, Any]] = None


class UsageAnalytics(BaseModel):
    """Comprehensive usage analytics response."""
    overview: OverviewMetrics
    time_series: List[TimeSeriesDataPoint]
    breakdown_by_user: List[BreakdownItem]
    breakdown_by_agent: List[BreakdownItem]
    breakdown_by_model: List[BreakdownItem]


class ConversationListItem(BaseModel):
    """Conversation item in list view."""
    id: str
    title: str
    user_id: str
    user_email: str
    user_name: str
    agent_id: str
    agent_name: str
    total_messages: int
    input_tokens: int
    output_tokens: int
    created_at: datetime
    updated_at: datetime
    is_archived: bool


class MessageDetail(BaseModel):
    """Individual message in conversation."""
    id: str
    role: str
    content: str
    content_type: str
    token_count: int
    model_used: Optional[str]
    created_at: datetime


class ConversationDetail(BaseModel):
    """Full conversation with all messages."""
    id: str
    title: str
    user_email: str
    user_name: str
    agent_name: str
    agent_model: str
    total_messages: int
    total_tokens: int
    created_at: datetime
    updated_at: datetime
    messages: List[MessageDetail]


class StorageOverview(BaseModel):
    """Storage metrics overview."""
    total_documents: int
    total_storage_mb: float
    total_datasets: int
    average_document_size_mb: float


class DatasetStorageItem(BaseModel):
    """Storage breakdown by dataset."""
    id: str
    label: str
    document_count: int
    storage_mb: float
    percentage: float


class UserStorageItem(BaseModel):
    """Storage breakdown by user with billing-accurate metrics."""
    id: str
    label: str
    # Dataset storage
    document_count: int
    dataset_storage_mb: float
    # Conversation storage
    conversation_count: int
    conversation_storage_mb: float
    # Totals
    total_storage_mb: float
    percentage: float


class FileTypeBreakdown(BaseModel):
    """File type distribution."""
    file_type: str
    document_count: int
    storage_mb: float
    percentage: float


class UploadTimelineData(BaseModel):
    """Upload activity over time."""
    date: str
    document_count: int
    storage_mb: float


class FileInfo(BaseModel):
    """Individual file information."""
    file_name: str
    file_size_mb: float
    file_type: str
    uploaded_at: datetime


class DatasetFileDetails(BaseModel):
    """Dataset with detailed file listing."""
    dataset_id: str
    dataset_name: str
    total_size_mb: float
    file_count: int
    files: List[FileInfo]


class StorageMetrics(BaseModel):
    """Comprehensive storage metrics response."""
    overview: StorageOverview
    breakdown_by_dataset: List[DatasetStorageItem]
    breakdown_by_user: Optional[List[UserStorageItem]] = None
    file_type_breakdown: List[FileTypeBreakdown]
    dataset_file_details: List[DatasetFileDetails]


class UserListItem(BaseModel):
    """User item for dropdown filters."""
    id: str
    email: str
    full_name: Optional[str]
    role: str


class AgentListItem(BaseModel):
    """Agent item for dropdown filters."""
    id: str
    name: str
    model: Optional[str]


class TeamListItem(BaseModel):
    """Minimal team info for filter dropdowns."""
    id: str
    name: str
    observable_count: int


class ObservableMembersResponse(BaseModel):
    """Response model for Observable members endpoints."""
    members: List[UserListItem]


class FilterOptions(BaseModel):
    """Complete unfiltered lists for dropdown options."""
    users: List[UserListItem]
    agents: List[AgentListItem]
    teams: Optional[List[TeamListItem]] = None  # Only for team observers


# ============================================================================
# Permission Helpers
# ============================================================================

async def get_filtered_user_id(current_user: Dict[str, Any]) -> Optional[str]:
    """
    Get user_id filter based on role and team observer status for observability data access.

    Returns:
        None for admin/developer roles (see all tenant data)
        None for team observers (see team observable members - filtered separately)
        user_id (UUID from tenant database) for regular users (see only own data)

    This enforces role-based and team-based data isolation:
    - Admins and developers can view all platform activity
    - Team owners and managers can view their team's observable members
    - Regular users can only view their personal activity
    """
    user_email = current_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    from app.core.postgresql_client import get_postgresql_client

    tenant_domain = current_user.get('tenant_domain', 'test-company')
    pg_client = await get_postgresql_client()

    # Get role from database (authoritative source)
    user_role = await get_user_role(pg_client, user_email, tenant_domain)

    # Admin and developer roles can see all data
    if user_role in ['admin', 'developer']:
        logger.info(f"[Observability] User {user_email} with role {user_role} granted full platform access")
        return None

    # Check if user is a team observer (owner or manager with observable members)
    is_observer_query = """
        SELECT EXISTS(
            SELECT 1 FROM team_memberships tm
            WHERE tm.user_id = (
                SELECT id FROM users
                WHERE email = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                LIMIT 1
            )
            AND tm.team_permission = 'manager'
            AND tm.status = 'accepted'
        ) OR EXISTS(
            SELECT 1 FROM teams t
            WHERE t.owner_id = (
                SELECT id FROM users
                WHERE email = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                LIMIT 1
            )
        ) as is_observer
    """

    is_observer = await pg_client.fetch_scalar(is_observer_query, user_email, tenant_domain)

    if is_observer:
        logger.info(f"[Observability] User {user_email} is team observer - granted team observable member access")
        return None  # Will filter to team observable members in queries

    # All other roles (analyst, student) can only see their own data
    # Look up the UUID user_id from tenant database by email (not from JWT token which has integer ID)
    query = """
        SELECT id::text FROM users
        WHERE email = $1
          AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        LIMIT 1
    """
    user_id = await pg_client.fetch_scalar(query, user_email, tenant_domain)

    if not user_id:
        raise HTTPException(status_code=404, detail="User not found in tenant database")

    logger.info(f"[Observability] User {user_email} with role {user_role} restricted to personal data (user_id: {user_id})")
    return user_id


async def require_admin_role(current_user: Dict[str, Any]) -> str:
    """
    Verify user has admin role (admin or developer).
    DEPRECATED: Use get_filtered_user_id() for new observability endpoints.
    """
    user_email = current_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    from app.core.postgresql_client import get_postgresql_client

    tenant_domain = current_user.get('tenant_domain', 'test-company')
    pg_client = await get_postgresql_client()

    user_role = await get_user_role(pg_client, user_email, tenant_domain)

    if user_role not in ["admin", "developer"]:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. This feature is only available to tenant administrators."
        )

    return user_role


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/overview", response_model=OverviewMetrics)
async def get_overview_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get high-level overview metrics for dashboard.
    Admin-only endpoint.
    """
    from app.core.postgresql_client import get_postgresql_client

    await require_admin_role(current_user)

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')
    date_start = datetime.now() - timedelta(days=days)

    # Aggregate metrics from conversations and messages using inline tenant_id subquery
    query = f"""
        WITH conversation_stats AS (
            SELECT
                COUNT(DISTINCT c.id) AS total_conversations,
                COUNT(DISTINCT c.user_id) AS unique_users,
                COUNT(DISTINCT c.agent_id) AS unique_agents,
                COALESCE(SUM(c.total_messages), 0) AS total_messages,
                COALESCE(SUM(c.total_tokens), 0) AS total_tokens
            FROM conversations c
            WHERE
                c.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                AND c.created_at >= $2
        )
        SELECT * FROM conversation_stats;
    """

    result = await pg_client.execute_query(query, tenant_domain, date_start)

    if not result:
        return OverviewMetrics(
            total_conversations=0,
            total_messages=0,
            total_tokens=0,
            unique_users=0,
            unique_agents=0,
            date_range_start=date_start,
            date_range_end=datetime.now()
        )

    data = result[0]
    return OverviewMetrics(
        total_conversations=data["total_conversations"],
        total_messages=data["total_messages"],
        total_tokens=data["total_tokens"],
        unique_users=data["unique_users"],
        date_range_start=date_start,
        date_range_end=datetime.now()
    )


@router.get("/usage", response_model=UsageAnalytics)
async def get_usage_analytics(
    days: Optional[int] = Query(None, ge=1, le=3650, description="Number of days to look back (omit for all time)"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD or ISO timestamp: YYYY-MM-DDTHH:MM:SSZ)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD or ISO timestamp: YYYY-MM-DDTHH:MM:SSZ)"),
    user_id: Optional[str] = Query(None, description="Filter by specific user (admin only)"),
    agent_id: Optional[str] = Query(None, description="Filter by specific agent"),
    model: Optional[str] = Query(None, description="Filter by specific model"),
    team_id: Optional[str] = Query(None, description="Filter by team (team observers only)"),
    observable_member_id: Optional[str] = Query(None, description="Filter by specific Observable member (team observers only)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get comprehensive usage analytics with time series and breakdowns.
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: See all platform activity, can filter by user
    - Team Observers (owners/managers): See Observable team members' activity, can filter by team
    - Analysts/Students: See only their personal activity

    Date filtering options:
    - days: Look back N days from now (default behavior if nothing specified: 30 days)
    - start_date + end_date: Custom date range (supports both date-only YYYY-MM-DD and time-of-day ISO timestamps)
    - Omit all date params for all-time data

    Time filtering examples:
    - Date-only: start_date=2025-01-15&end_date=2025-01-16 (full days)
    - Hour:minute: start_date=2025-01-15T14:30:00Z&end_date=2025-01-15T16:45:00Z (specific time range)
    """
    from app.core.postgresql_client import get_postgresql_client

    # Get role-based user_id filter (None for admins, user_id for regular users)
    filtered_user_id = await get_filtered_user_id(current_user)

    # Diagnostic logging
    logger.info(f"[Usage Debug] ===== GET_USAGE_DATA CALLED =====")
    logger.info(f"[Usage Debug] Received parameters:")
    logger.info(f"[Usage Debug]   team_id: {team_id}")
    logger.info(f"[Usage Debug]   user_id: {user_id}")
    logger.info(f"[Usage Debug]   days: {days}")
    logger.info(f"[Usage Debug]   start_date: {start_date}")
    logger.info(f"[Usage Debug]   end_date: {end_date}")
    logger.info(f"[Usage Debug] Current user: {current_user.get('email')}")
    logger.info(f"[Usage Debug] filtered_user_id: {filtered_user_id}")

    # For non-admin users, override any user_id parameter with their own ID
    # This prevents users from seeing other users' data via URL manipulation
    if filtered_user_id is not None:
        user_id = filtered_user_id

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')

    # Determine date range
    if start_date and end_date:
        # Custom date range - handle both date-only strings (YYYY-MM-DD) and ISO timestamps with time (YYYY-MM-DDTHH:MM:SSZ)
        try:
            # Try parsing as ISO timestamp with time first (for hour:minute filtering)
            if 'T' in start_date:
                date_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                date_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                logger.info(f"[Usage Debug] Parsed ISO timestamps with time - start: {date_start}, end: {date_end}")
            else:
                # Date-only string - set to start/end of day
                date_start = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999)
                logger.info(f"[Usage Debug] Parsed date-only strings - start: {date_start}, end: {date_end}")
        except ValueError as e:
            logger.error(f"[Usage Debug] Date parsing error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD or ISO timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    elif days is not None:
        # Days-based range
        date_start = datetime.now() - timedelta(days=days)
        date_end = datetime.now()
    else:
        # All time - query for actual first and last conversation dates
        date_range_query = """
            SELECT
                MIN(created_at) as first_date,
                MAX(created_at) as last_date
            FROM conversations
            WHERE tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
        """
        date_range_result = await pg_client.execute_query(date_range_query, tenant_domain)
        if date_range_result and date_range_result[0]["first_date"]:
            date_start = date_range_result[0]["first_date"]
            date_end = date_range_result[0]["last_date"] or datetime.now()
        else:
            # No conversations yet - use current time for both
            date_start = datetime.now()
            date_end = datetime.now()

    # Build filter conditions using inline tenant_id subquery
    filters = ["c.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)", "c.created_at >= $2", "c.created_at <= $3"]
    params = [tenant_domain, date_start, date_end]

    # Check if user is a team observer (not admin/developer) and in observability mode
    # Three modes: individual (no team_id from frontend), specific team (team_id = UUID), or "All Teams" (team_id = 'all')
    # Note: Frontend needs to send team_id = 'all' for All Teams mode to distinguish from individual mode
    if filtered_user_id is None:
        user_role = await get_user_role(pg_client, current_user.get('email'), tenant_domain)
        logger.info(f"[Usage Debug] User role: {user_role}")
        if user_role not in ['admin', 'developer']:
            user_email = current_user.get('email')
            logger.info(f"[Usage Debug] Team observer detected: {user_email}, role: {user_role}")

            if team_id and team_id != 'all':
                # Specific team mode - filter to Observable members of this team
                logger.info(f"[Usage Debug] EXECUTING: Specific team mode (team_id={team_id})")
                logger.info(f"[Observability] Team observer {user_email} in team mode (team_id={team_id}) - filtering to Observable members")

                # Build Observable members filter for specific team
                # Note: tenant_domain is already in params[0] as $1
                # Fixed: Check team ownership independently from team membership
                observable_filter_parts = [
                "c.user_id IN (",
                "    SELECT DISTINCT tm_observed.user_id",
                "    FROM team_memberships tm_observed",
                f"    WHERE tm_observed.team_id = ${len(params) + 2}::uuid",  # Direct team filter
                "    AND tm_observed.is_observable = true",
                "    AND tm_observed.observable_consent_status = 'approved'",
                "    AND tm_observed.status = 'accepted'",
                "    AND (",
                "        -- Observer is team owner (works even if owner not in team_memberships)",
                "        EXISTS(",
                "            SELECT 1 FROM teams t",
                f"            WHERE t.id = ${len(params) + 2}::uuid",
                "              AND t.owner_id = (",
                "                  SELECT id FROM users",
                f"                  WHERE email = ${len(params) + 1}",
                "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                "                  LIMIT 1",
                "              )",
                "        )",
                "        OR",
                "        -- Observer is team manager",
                "        EXISTS(",
                "            SELECT 1 FROM team_memberships tm_mgr",
                f"            WHERE tm_mgr.team_id = ${len(params) + 2}::uuid",
                "              AND tm_mgr.user_id = (",
                "                  SELECT id FROM users",
                f"                  WHERE email = ${len(params) + 1}",
                "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                "                  LIMIT 1",
                "              )",
                "              AND tm_mgr.team_permission = 'manager'",
                "              AND tm_mgr.status = 'accepted'",
                "        )",
                "    )",
                ")"
                ]

                # Add parameters: user_email and team_id (tenant_domain already in params)
                params.extend([user_email, team_id])

                # Note: observable_filter_parts already has balanced parentheses ending on line 506
                # No need to append additional closing parenthesis
                observable_filter = "\n".join(observable_filter_parts)
                filters.append(observable_filter)
                logger.info(f"[Observability] Applied Observable member filter for team_id: {team_id}")
                logger.debug(f"[Observability] Observable filter SQL: {observable_filter}")
                logger.debug(f"[Observability] Current params count: {len(params)}, params: {params}")

                # Add team-scoped resource filtering (agents/datasets shared to this team)
                team_resource_filter_parts = [
                    "(",
                    "    -- Agent is shared to this team",
                    "    c.agent_id IN (",
                    "        SELECT resource_id FROM team_resource_shares",
                    f"        WHERE team_id = ${len(params)}::uuid",  # Use team_id from params
                    "          AND resource_type = 'agent'",
                    "    )",
                    "    OR",
                    "    -- Agent uses a dataset shared to this team",
                    "    c.agent_id IN (",
                    "        SELECT ad.agent_id",
                    "        FROM agent_datasets ad",
                    "        WHERE ad.dataset_id IN (",
                    "            SELECT resource_id FROM team_resource_shares",
                    f"            WHERE team_id = ${len(params)}::uuid",
                    "              AND resource_type = 'dataset'",
                    "        )",
                    "    )",
                    ")"
                ]
                team_resource_filter = "\n".join(team_resource_filter_parts)
                filters.append(team_resource_filter)
                logger.info(f"[Observability] Applied team resource filter for team_id: {team_id}")
                logger.debug(f"[Observability] Team resource filter SQL: {team_resource_filter}")
            elif team_id == 'all':
                # "All Teams" mode - filter to Observable members across all managed teams
                logger.info(f"[Usage Debug] EXECUTING: All Teams mode")
                logger.info(f"[Observability] Team observer {user_email} in 'All Teams' mode - filtering to all Observable members")

                observable_filter_parts = [
                    "c.user_id IN (",
                    "    SELECT DISTINCT tm_observed.user_id",
                    "    FROM team_memberships tm_observed",
                    "    JOIN teams t ON t.id = tm_observed.team_id",
                    "    WHERE tm_observed.is_observable = true",
                    "    AND tm_observed.observable_consent_status = 'approved'",
                    "    AND tm_observed.status = 'accepted'",
                    "    AND (",
                    "        -- Observer is team owner",
                    "        t.owner_id = (",
                    "            SELECT id FROM users",
                    f"            WHERE email = ${len(params) + 1}",
                    "              AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "            LIMIT 1",
                    "        )",
                    "        OR",
                    "        -- Observer is team manager",
                    "        EXISTS(",
                    "            SELECT 1 FROM team_memberships tm_mgr",
                    "            WHERE tm_mgr.team_id = t.id",
                    "              AND tm_mgr.user_id = (",
                    "                  SELECT id FROM users",
                    f"                  WHERE email = ${len(params) + 1}",
                    "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                  LIMIT 1",
                    "              )",
                    "              AND tm_mgr.team_permission = 'manager'",
                    "              AND tm_mgr.status = 'accepted'",
                    "        )",
                    "    )",
                    ")"
                ]

                params.append(user_email)
                # Note: observable_filter_parts already has balanced parentheses ending on line 556
                # No need to append additional closing parenthesis
                observable_filter = "\n".join(observable_filter_parts)
                filters.append(observable_filter)
                logger.info(f"[Observability] Applied 'All Teams' Observable member filter")
                logger.debug(f"[Observability] All Teams filter SQL: {observable_filter}")
                logger.debug(f"[Observability] Current params count: {len(params)}, params: {params}")

                # Add team-scoped resource filtering for all managed teams
                team_resource_filter_parts = [
                    "(",
                    "    -- Agent is shared to ANY team the observer manages",
                    "    c.agent_id IN (",
                    "        SELECT DISTINCT trs.resource_id",
                    "        FROM team_resource_shares trs",
                    "        JOIN teams t ON t.id = trs.team_id",
                    "        WHERE trs.resource_type = 'agent'",
                    "          AND (",
                    "              -- Observer is team owner",
                    "              t.owner_id = (",
                    "                  SELECT id FROM users",
                    f"                  WHERE email = ${len(params)}",
                    "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                  LIMIT 1",
                    "              )",
                    "              OR",
                    "              -- Observer is team manager",
                    "              EXISTS(",
                    "                  SELECT 1 FROM team_memberships tm_mgr",
                    "                  WHERE tm_mgr.team_id = t.id",
                    "                    AND tm_mgr.user_id = (",
                    "                        SELECT id FROM users",
                    f"                        WHERE email = ${len(params)}",
                    "                          AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                        LIMIT 1",
                    "                    )",
                    "                    AND tm_mgr.team_permission = 'manager'",
                    "                    AND tm_mgr.status = 'accepted'",
                    "              )",
                    "          )",
                    "    )",
                    "    OR",
                    "    -- Agent uses a dataset shared to ANY team the observer manages",
                    "    c.agent_id IN (",
                    "        SELECT DISTINCT ad.agent_id",
                    "        FROM agent_datasets ad",
                    "        WHERE ad.dataset_id IN (",
                    "            SELECT DISTINCT trs.resource_id",
                    "            FROM team_resource_shares trs",
                    "            JOIN teams t ON t.id = trs.team_id",
                    "            WHERE trs.resource_type = 'dataset'",
                    "              AND (",
                    "                  -- Observer is team owner",
                    "                  t.owner_id = (",
                    "                      SELECT id FROM users",
                    f"                      WHERE email = ${len(params)}",
                    "                        AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                      LIMIT 1",
                    "                  )",
                    "                  OR",
                    "                  -- Observer is team manager",
                    "                  EXISTS(",
                    "                      SELECT 1 FROM team_memberships tm_mgr",
                    "                      WHERE tm_mgr.team_id = t.id",
                    "                        AND tm_mgr.user_id = (",
                    "                            SELECT id FROM users",
                    f"                            WHERE email = ${len(params)}",
                    "                              AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                            LIMIT 1",
                    "                        )",
                    "                        AND tm_mgr.team_permission = 'manager'",
                    "                        AND tm_mgr.status = 'accepted'",
                    "                  )",
                    "              )",
                    "        )",
                    "    )",
                    ")"
                ]
                team_resource_filter = "\n".join(team_resource_filter_parts)
                filters.append(team_resource_filter)
                logger.info(f"[Observability] Applied 'All Teams' resource filter")
                logger.debug(f"[Observability] All Teams resource filter SQL: {team_resource_filter}")
            else:
                # Individual mode (no team_id) - restrict to their own data
                logger.info(f"[Usage Debug] EXECUTING: Individual mode for team observer")
                # Get the user's UUID from tenant database
                user_uuid_query = """
                    SELECT id::text FROM users
                    WHERE email = $1
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                    LIMIT 1
                """
                user_uuid = await pg_client.fetch_scalar(user_uuid_query, user_email, tenant_domain)
                if user_uuid:
                    filters.append(f"c.user_id = ${len(params) + 1}")
                    params.append(user_uuid)
                    logger.info(f"[Usage Debug] Applied individual mode filter: user_uuid={user_uuid}")
                    logger.info(f"[Observability] Team observer {user_email} in individual mode - showing personal data only")
                else:
                    logger.warning(f"[Usage Debug] Could not find UUID for user {user_email}")

    logger.info(f"[Usage Debug] Checking additional user_id parameter: {user_id}")
    if user_id:
        logger.info(f"[Usage Debug] Adding additional user_id filter: {user_id}")
        filters.append(f"c.user_id = ${len(params) + 1}")
        params.append(user_id)

    # Observable member ID filtering (for team observers selecting specific Observable member)
    if observable_member_id and team_id:
        logger.info(f"[Observability] Filtering to specific Observable member: {observable_member_id}")
        filters.append(f"c.user_id = ${len(params) + 1}")
        params.append(observable_member_id)

    if agent_id:
        filters.append(f"c.agent_id = ${len(params) + 1}")
        params.append(agent_id)

    where_clause = " AND ".join(filters)

    # Final diagnostic logging before query execution
    logger.info(f"[Usage Debug] Final filters array: {filters}")
    logger.info(f"[Usage Debug] Final params array: {params}")
    logger.info(f"[Usage Debug] Final WHERE clause: {where_clause}")
    logger.info(f"[Usage Debug] =====================================")

    # Get overview
    overview_query = f"""
        SELECT
            COUNT(DISTINCT c.id) AS total_conversations,
            COUNT(DISTINCT c.user_id) AS unique_users,
            COUNT(DISTINCT c.agent_id) AS unique_agents,
            COALESCE(SUM(c.total_messages), 0) AS total_messages,
            COALESCE(SUM(c.total_tokens), 0) AS total_tokens
        FROM conversations c
        WHERE {where_clause};
    """
    overview_result = await pg_client.execute_query(overview_query, *params)
    overview_data = overview_result[0] if overview_result else {}

    overview = OverviewMetrics(
        total_conversations=overview_data.get("total_conversations", 0),
        total_messages=overview_data.get("total_messages", 0),
        total_tokens=overview_data.get("total_tokens", 0),
        unique_users=overview_data.get("unique_users", 0),
        date_range_start=date_start,
        date_range_end=date_end
    )

    # Get time series with smart sampling based on date range
    # Determine appropriate granularity to balance detail and performance
    # Calculate actual days span
    days_span = (date_end - date_start).days if days is None else days

    if days_span <= 3:
        # Short range: minute-level detail with hourly zero-fill
        time_series_query = f"""
            WITH time_buckets AS (
                SELECT
                    DATE_TRUNC('minute', c.created_at) AS bucket_time,
                    COUNT(DISTINCT c.id) AS conversation_count,
                    COALESCE(SUM(c.total_messages), 0) AS message_count,
                    COALESCE(SUM(c.total_tokens), 0) AS token_count,
                    COUNT(DISTINCT c.user_id) AS unique_users
                FROM conversations c
                WHERE {{where_clause}}
                GROUP BY DATE_TRUNC('minute', c.created_at)
            ),
            hour_series AS (
                SELECT generate_series(
                    DATE_TRUNC('hour', $2::timestamp),
                    DATE_TRUNC('hour', $3::timestamp),
                    interval '1 hour'
                ) AS hour_point
            ),
            hours_with_data AS (
                SELECT DISTINCT DATE_TRUNC('hour', bucket_time) AS hour_point
                FROM time_buckets
            )
            -- Return all minute-level data
            SELECT
                bucket_time AS date,
                conversation_count,
                message_count,
                token_count,
                unique_users
            FROM time_buckets

            UNION ALL

            -- Add zero points for hours with no activity
            SELECT
                hs.hour_point AS date,
                0 AS conversation_count,
                0 AS message_count,
                0 AS token_count,
                0 AS unique_users
            FROM hour_series hs
            LEFT JOIN hours_with_data hwd ON hs.hour_point = hwd.hour_point
            WHERE hwd.hour_point IS NULL

            ORDER BY date ASC;
        """
    elif days_span <= 7:
        # Week: hourly aggregation with daily zero-fill
        time_series_query = f"""
            WITH time_buckets AS (
                SELECT
                    DATE_TRUNC('hour', c.created_at) AS bucket_time,
                    COUNT(DISTINCT c.id) AS conversation_count,
                    COALESCE(SUM(c.total_messages), 0) AS message_count,
                    COALESCE(SUM(c.total_tokens), 0) AS token_count,
                    COUNT(DISTINCT c.user_id) AS unique_users
                FROM conversations c
                WHERE {{where_clause}}
                GROUP BY DATE_TRUNC('hour', c.created_at)
            ),
            day_series AS (
                SELECT generate_series(
                    DATE_TRUNC('day', $2::timestamp),
                    DATE_TRUNC('day', $3::timestamp),
                    interval '1 day'
                ) AS day_point
            ),
            days_with_data AS (
                SELECT DISTINCT DATE_TRUNC('day', bucket_time) AS day_point
                FROM time_buckets
            )
            -- Return all hourly data
            SELECT
                bucket_time AS date,
                conversation_count,
                message_count,
                token_count,
                unique_users
            FROM time_buckets

            UNION ALL

            -- Add zero points for days with no activity
            SELECT
                ds.day_point AS date,
                0 AS conversation_count,
                0 AS message_count,
                0 AS token_count,
                0 AS unique_users
            FROM day_series ds
            LEFT JOIN days_with_data dwd ON ds.day_point = dwd.day_point
            WHERE dwd.day_point IS NULL

            ORDER BY date ASC;
        """
    elif days_span <= 30:
        # Month: 4-hour blocks with daily zero-fill
        time_series_query = f"""
            WITH time_buckets AS (
                SELECT
                    DATE_TRUNC('day', c.created_at) +
                    INTERVAL '1 hour' * (EXTRACT(HOUR FROM c.created_at)::int / 4 * 4) AS bucket_time,
                    COUNT(DISTINCT c.id) AS conversation_count,
                    COALESCE(SUM(c.total_messages), 0) AS message_count,
                    COALESCE(SUM(c.total_tokens), 0) AS token_count,
                    COUNT(DISTINCT c.user_id) AS unique_users
                FROM conversations c
                WHERE {{where_clause}}
                GROUP BY DATE_TRUNC('day', c.created_at) +
                         INTERVAL '1 hour' * (EXTRACT(HOUR FROM c.created_at)::int / 4 * 4)
            ),
            day_series AS (
                SELECT generate_series(
                    DATE_TRUNC('day', $2::timestamp),
                    DATE_TRUNC('day', $3::timestamp),
                    interval '1 day'
                ) AS day_point
            ),
            days_with_data AS (
                SELECT DISTINCT DATE_TRUNC('day', bucket_time) AS day_point
                FROM time_buckets
            )
            -- Return all 4-hour block data
            SELECT
                bucket_time AS date,
                conversation_count,
                message_count,
                token_count,
                unique_users
            FROM time_buckets

            UNION ALL

            -- Add zero points for days with no activity
            SELECT
                ds.day_point AS date,
                0 AS conversation_count,
                0 AS message_count,
                0 AS token_count,
                0 AS unique_users
            FROM day_series ds
            LEFT JOIN days_with_data dwd ON ds.day_point = dwd.day_point
            WHERE dwd.day_point IS NULL

            ORDER BY date ASC;
        """
    else:
        # Longer: daily aggregation with zero-fill for all days
        time_series_query = f"""
            WITH time_buckets AS (
                SELECT
                    DATE_TRUNC('day', c.created_at) AS bucket_time,
                    COUNT(DISTINCT c.id) AS conversation_count,
                    COALESCE(SUM(c.total_messages), 0) AS message_count,
                    COALESCE(SUM(c.total_tokens), 0) AS token_count,
                    COUNT(DISTINCT c.user_id) AS unique_users
                FROM conversations c
                WHERE {{where_clause}}
                GROUP BY DATE_TRUNC('day', c.created_at)
            ),
            day_series AS (
                SELECT generate_series(
                    DATE_TRUNC('day', $2::timestamp),
                    DATE_TRUNC('day', $3::timestamp),
                    interval '1 day'
                ) AS day_point
            )
            -- Return all data with zero-fill
            SELECT
                COALESCE(tb.bucket_time, ds.day_point) AS date,
                COALESCE(tb.conversation_count, 0) AS conversation_count,
                COALESCE(tb.message_count, 0) AS message_count,
                COALESCE(tb.token_count, 0) AS token_count,
                COALESCE(tb.unique_users, 0) AS unique_users
            FROM day_series ds
            LEFT JOIN time_buckets tb ON ds.day_point = tb.bucket_time
            ORDER BY date ASC;
        """

    time_series_query = time_series_query.format(where_clause=where_clause)
    time_series_result = await pg_client.execute_query(time_series_query, *params)
    time_series = [
        TimeSeriesDataPoint(
            date=str(row["date"]),
            conversation_count=row["conversation_count"],
            message_count=row["message_count"],
            token_count=row["token_count"],
            unique_users=row["unique_users"]
        )
        for row in time_series_result
    ]

    # Get breakdown by user
    user_breakdown_query = f"""
        SELECT
            c.user_id AS id,
            u.email AS label,
            COUNT(DISTINCT c.id) AS value,
            COALESCE(SUM(c.total_tokens), 0) AS tokens
        FROM conversations c
        JOIN users u ON c.user_id = u.id AND c.tenant_id = u.tenant_id
        WHERE {where_clause}
        GROUP BY c.user_id, u.email
        ORDER BY value DESC
        LIMIT 20;
    """
    user_breakdown_result = await pg_client.execute_query(user_breakdown_query, *params)
    total_conversations = overview.total_conversations or 1
    breakdown_by_user = [
        BreakdownItem(
            id=str(row["id"]),
            label=row["label"],
            value=row["value"],
            percentage=(row["value"] / total_conversations) * 100,
            metadata={"tokens": row["tokens"]}
        )
        for row in user_breakdown_result
    ]

    # Get breakdown by agent
    agent_breakdown_query = f"""
        SELECT
            c.agent_id AS id,
            a.name AS label,
            COUNT(DISTINCT c.id) AS value,
            COALESCE(SUM(c.total_messages), 0) AS messages,
            COALESCE(SUM(c.total_tokens), 0) AS tokens
        FROM conversations c
        JOIN agents a ON c.agent_id = a.id AND c.tenant_id = a.tenant_id
        WHERE {where_clause}
        GROUP BY c.agent_id, a.name
        ORDER BY value DESC
        LIMIT 20;
    """
    agent_breakdown_result = await pg_client.execute_query(agent_breakdown_query, *params)
    breakdown_by_agent = [
        BreakdownItem(
            id=str(row["id"]),
            label=row["label"],
            value=row["value"],
            percentage=(row["value"] / total_conversations) * 100,
            metadata={"messages": row["messages"], "tokens": row["tokens"]}
        )
        for row in agent_breakdown_result
    ]

    # Get breakdown by model
    model_breakdown_query = f"""
        SELECT
            m.model_used AS id,
            m.model_used AS label,
            COUNT(DISTINCT c.id) AS conversations,
            COUNT(DISTINCT m.id) AS messages,
            COALESCE(SUM(m.token_count), 0) AS tokens
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE {where_clause} AND m.model_used IS NOT NULL AND m.model_used != ''
        GROUP BY m.model_used
        ORDER BY conversations DESC
        LIMIT 20;
    """
    model_breakdown_result = await pg_client.execute_query(model_breakdown_query, *params)
    total_model_conversations = sum(row["conversations"] for row in model_breakdown_result) or 1
    breakdown_by_model = [
        BreakdownItem(
            id=row["id"],
            label=row["label"],
            value=row["conversations"],
            percentage=(row["conversations"] / total_model_conversations) * 100,
            metadata={"messages": row["messages"], "tokens": row["tokens"]}
        )
        for row in model_breakdown_result
    ]

    return UsageAnalytics(
        overview=overview,
        time_series=time_series,
        breakdown_by_user=breakdown_by_user,
        breakdown_by_agent=breakdown_by_agent,
        breakdown_by_model=breakdown_by_model
    )


@router.get("/conversations", response_model=List[ConversationListItem])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    days: Optional[int] = Query(None, ge=1, description="Number of days to look back"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD or ISO timestamp: YYYY-MM-DDTHH:MM:SSZ)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD or ISO timestamp: YYYY-MM-DDTHH:MM:SSZ)"),
    specific_date: Optional[str] = Query(None, description="Filter to specific date (YYYY-MM-DD or ISO timestamp)"),
    user_id: Optional[str] = Query(None, description="Filter by specific user (admin only)"),
    agent_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None, description="Filter by model name"),
    search: Optional[str] = Query(None, description="Search in conversation titles and message content"),
    team_id: Optional[str] = Query(None, description="Filter by team (team observers only)"),
    observable_member_id: Optional[str] = Query(None, description="Filter by specific Observable member (team observers only)"),
    order_by: Literal["created_at", "updated_at", "total_messages", "input_tokens", "output_tokens"] = Query("created_at"),
    order_direction: Literal["asc", "desc"] = Query("desc"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all conversations with metadata (paginated).
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: See all conversations, can filter by user
    - Team Observers (owners/managers): See Observable team members' conversations in team mode, or own conversations in individual mode
    - Analysts/Students: See only their personal conversations

    Date filtering options:
    - days: Look back N days from now
    - start_date + end_date: Custom date range (supports both date-only and time-of-day filtering)
    - specific_date: Filter to a specific date (for chart click navigation)
    - Omit all for all-time data

    Time filtering examples:
    - Date-only: start_date=2025-01-15&end_date=2025-01-16 (full days)
    - Hour:minute: start_date=2025-01-15T14:30:00Z&end_date=2025-01-15T16:45:00Z (specific time range)
    """
    from app.core.postgresql_client import get_postgresql_client

    # Get role-based user_id filter (None for admins, user_id for regular users)
    filtered_user_id = await get_filtered_user_id(current_user)

    # For non-admin users, override any user_id parameter with their own ID
    if filtered_user_id is not None:
        user_id = filtered_user_id

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')

    # Build filters using inline tenant_id subquery
    filters = ["c.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)"]
    params = [tenant_domain]

    # Handle date filtering
    if specific_date:
        # Filter to specific date (for chart clicks)
        try:
            # Try parsing as ISO timestamp with time first
            if 'T' in specific_date:
                specific_dt = datetime.fromisoformat(specific_date.replace('Z', '+00:00'))
                # Match the entire day from the timestamp
                filters.append(f"DATE(c.created_at) = DATE(${len(params) + 1}::timestamp)")
                params.append(specific_dt)
            else:
                # Date-only string
                specific_dt = datetime.strptime(specific_date, '%Y-%m-%d')
                filters.append(f"DATE(c.created_at) = DATE(${len(params) + 1}::timestamp)")
                params.append(specific_dt)
        except ValueError as e:
            logger.error(f"[Conversations Debug] Date parsing error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD or ISO timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    elif start_date and end_date:
        # Custom date range - handle both date-only strings and ISO timestamps with time
        try:
            if 'T' in start_date:
                # ISO timestamp with time - use full datetime precision for hour:minute filtering
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                filters.append(f"c.created_at >= ${len(params) + 1}")
                params.append(start_dt)
                filters.append(f"c.created_at <= ${len(params) + 1}")
                params.append(end_dt)
                logger.info(f"[Conversations Debug] Using datetime filtering - start: {start_dt}, end: {end_dt}")
            else:
                # Date-only format - use DATE() for timezone-agnostic day comparison
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                filters.append(f"DATE(c.created_at) >= ${len(params) + 1}")
                params.append(start_dt)
                filters.append(f"DATE(c.created_at) <= ${len(params) + 1}")
                params.append(end_dt)
                logger.info(f"[Conversations Debug] Using date filtering - start: {start_dt}, end: {end_dt}")
        except ValueError as e:
            logger.error(f"[Conversations Debug] Date parsing error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD or ISO timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    elif days is not None:
        # Days-based range
        date_start = datetime.now() - timedelta(days=days)
        filters.append(f"c.created_at >= ${len(params) + 1}")
        params.append(date_start)
    # else: all time (no date filter)

    # Check if user is a team observer (not admin/developer) AND handle mode-based filtering
    # Three modes: individual (no team_id from frontend), specific team (team_id = UUID), or "All Teams" (team_id = 'all')
    # Note: Frontend needs to send team_id = 'all' for All Teams mode to distinguish from individual mode
    if filtered_user_id is None:
        user_role = await get_user_role(pg_client, current_user.get('email'), tenant_domain)
        if user_role not in ['admin', 'developer']:
            user_email = current_user.get('email')

            if team_id and team_id != 'all':
                # Specific team mode - filter to Observable members of this team
                logger.info(f"[Observability] Team observer {user_email} in team mode (conversations) - filtering to Observable members")

                # Build Observable members filter for specific team
                # Fixed: Check team ownership independently from team membership
                observable_filter_parts = [
                    "c.user_id IN (",
                    "    SELECT DISTINCT tm_observed.user_id",
                    "    FROM team_memberships tm_observed",
                    f"    WHERE tm_observed.team_id = ${len(params) + 2}::uuid",  # Direct team filter
                    "    AND tm_observed.is_observable = true",
                    "    AND tm_observed.observable_consent_status = 'approved'",
                    "    AND tm_observed.status = 'accepted'",
                    "    AND (",
                    "        -- Observer is team owner (works even if owner not in team_memberships)",
                    "        EXISTS(",
                    "            SELECT 1 FROM teams t",
                    f"            WHERE t.id = ${len(params) + 2}::uuid",
                    "              AND t.owner_id = (",
                    "                  SELECT id FROM users",
                    f"                  WHERE email = ${len(params) + 1}",
                    "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                  LIMIT 1",
                    "              )",
                    "        )",
                    "        OR",
                    "        -- Observer is team manager",
                    "        EXISTS(",
                    "            SELECT 1 FROM team_memberships tm_mgr",
                    f"            WHERE tm_mgr.team_id = ${len(params) + 2}::uuid",
                    "              AND tm_mgr.user_id = (",
                    "                  SELECT id FROM users",
                    f"                  WHERE email = ${len(params) + 1}",
                    "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                  LIMIT 1",
                    "              )",
                    "              AND tm_mgr.team_permission = 'manager'",
                    "              AND tm_mgr.status = 'accepted'",
                    "        )",
                    "    )",
                    ")"
                ]

                observable_filter = "\n".join(observable_filter_parts)
                filters.append(observable_filter)
                params.extend([user_email, team_id])
                logger.info(f"[Observability] Applied Observable member filter for team_id: {team_id} (conversations)")

                # Add team-scoped resource filtering (agents/datasets shared to this team)
                team_resource_filter_parts = [
                    "(",
                    "    -- Agent is shared to this team",
                    "    c.agent_id IN (",
                    "        SELECT resource_id FROM team_resource_shares",
                    f"        WHERE team_id = ${len(params)}::uuid",  # Use team_id from params
                    "          AND resource_type = 'agent'",
                    "    )",
                    "    OR",
                    "    -- Agent uses a dataset shared to this team",
                    "    c.agent_id IN (",
                    "        SELECT ad.agent_id",
                    "        FROM agent_datasets ad",
                    "        WHERE ad.dataset_id IN (",
                    "            SELECT resource_id FROM team_resource_shares",
                    f"            WHERE team_id = ${len(params)}::uuid",
                    "              AND resource_type = 'dataset'",
                    "        )",
                    "    )",
                    ")"
                ]
                team_resource_filter = "\n".join(team_resource_filter_parts)
                filters.append(team_resource_filter)
                logger.info(f"[Observability] Applied team resource filter for team_id: {team_id} (conversations)")
            elif team_id == 'all':
                # "All Teams" mode - filter to Observable members across all managed teams
                logger.info(f"[Observability] Team observer {user_email} in 'All Teams' mode (conversations) - filtering to all Observable members")

                observable_filter_parts = [
                    "c.user_id IN (",
                    "    SELECT DISTINCT tm_observed.user_id",
                    "    FROM team_memberships tm_observed",
                    "    JOIN teams t ON t.id = tm_observed.team_id",
                    "    WHERE tm_observed.is_observable = true",
                    "    AND tm_observed.observable_consent_status = 'approved'",
                    "    AND tm_observed.status = 'accepted'",
                    "    AND (",
                    "        -- Observer is team owner",
                    "        t.owner_id = (",
                    "            SELECT id FROM users",
                    f"            WHERE email = ${len(params) + 1}",
                    "              AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "            LIMIT 1",
                    "        )",
                    "        OR",
                    "        -- Observer is team manager",
                    "        EXISTS(",
                    "            SELECT 1 FROM team_memberships tm_mgr",
                    "            WHERE tm_mgr.team_id = t.id",
                    "              AND tm_mgr.user_id = (",
                    "                  SELECT id FROM users",
                    f"                  WHERE email = ${len(params) + 1}",
                    "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                  LIMIT 1",
                    "              )",
                    "              AND tm_mgr.team_permission = 'manager'",
                    "              AND tm_mgr.status = 'accepted'",
                    "        )",
                    "    )",
                    ")"
                ]

                params.append(user_email)
                observable_filter = "\n".join(observable_filter_parts)
                filters.append(observable_filter)
                logger.info(f"[Observability] Applied 'All Teams' Observable member filter (conversations)")

                # Add team-scoped resource filtering for all managed teams
                team_resource_filter_parts = [
                    "(",
                    "    -- Agent is shared to ANY team the observer manages",
                    "    c.agent_id IN (",
                    "        SELECT DISTINCT trs.resource_id",
                    "        FROM team_resource_shares trs",
                    "        JOIN teams t ON t.id = trs.team_id",
                    "        WHERE trs.resource_type = 'agent'",
                    "          AND (",
                    "              -- Observer is team owner",
                    "              t.owner_id = (",
                    "                  SELECT id FROM users",
                    f"                  WHERE email = ${len(params)}",
                    "                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                  LIMIT 1",
                    "              )",
                    "              OR",
                    "              -- Observer is team manager",
                    "              EXISTS(",
                    "                  SELECT 1 FROM team_memberships tm_mgr",
                    "                  WHERE tm_mgr.team_id = t.id",
                    "                    AND tm_mgr.user_id = (",
                    "                        SELECT id FROM users",
                    f"                        WHERE email = ${len(params)}",
                    "                          AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                        LIMIT 1",
                    "                    )",
                    "                    AND tm_mgr.team_permission = 'manager'",
                    "                    AND tm_mgr.status = 'accepted'",
                    "              )",
                    "          )",
                    "    )",
                    "    OR",
                    "    -- Agent uses a dataset shared to ANY team the observer manages",
                    "    c.agent_id IN (",
                    "        SELECT DISTINCT ad.agent_id",
                    "        FROM agent_datasets ad",
                    "        WHERE ad.dataset_id IN (",
                    "            SELECT DISTINCT trs.resource_id",
                    "            FROM team_resource_shares trs",
                    "            JOIN teams t ON t.id = trs.team_id",
                    "            WHERE trs.resource_type = 'dataset'",
                    "              AND (",
                    "                  -- Observer is team owner",
                    "                  t.owner_id = (",
                    "                      SELECT id FROM users",
                    f"                      WHERE email = ${len(params)}",
                    "                        AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                      LIMIT 1",
                    "                  )",
                    "                  OR",
                    "                  -- Observer is team manager",
                    "                  EXISTS(",
                    "                      SELECT 1 FROM team_memberships tm_mgr",
                    "                      WHERE tm_mgr.team_id = t.id",
                    "                        AND tm_mgr.user_id = (",
                    "                            SELECT id FROM users",
                    f"                            WHERE email = ${len(params)}",
                    "                              AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)",
                    "                            LIMIT 1",
                    "                        )",
                    "                        AND tm_mgr.team_permission = 'manager'",
                    "                        AND tm_mgr.status = 'accepted'",
                    "                  )",
                    "              )",
                    "        )",
                    "    )",
                    ")"
                ]
                team_resource_filter = "\n".join(team_resource_filter_parts)
                filters.append(team_resource_filter)
                logger.info(f"[Observability] Applied 'All Teams' resource filter (conversations)")
            else:
                # Individual mode (no team_id) - restrict to their own data
                # Get the user's UUID from tenant database
                user_uuid_query = """
                    SELECT id::text FROM users
                    WHERE email = $1
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                    LIMIT 1
                """
                user_uuid = await pg_client.fetch_scalar(user_uuid_query, user_email, tenant_domain)
                if user_uuid:
                    filters.append(f"c.user_id = ${len(params) + 1}")
                    params.append(user_uuid)
                    logger.info(f"[Observability] Team observer {user_email} in individual mode (conversations) - showing personal data only")

    if user_id:
        filters.append(f"c.user_id = ${len(params) + 1}")
        params.append(user_id)

    # Observable member ID filtering (for team observers selecting specific Observable member)
    if observable_member_id and team_id:
        logger.info(f"[Observability] Filtering conversations to specific Observable member: {observable_member_id}")
        filters.append(f"c.user_id = ${len(params) + 1}")
        params.append(observable_member_id)

    if agent_id:
        filters.append(f"c.agent_id = ${len(params) + 1}")
        params.append(agent_id)
    if model:
        filters.append(f"a.model = ${len(params) + 1}")
        params.append(model)
    if search:
        search_pattern = f"%{search}%"
        filters.append(f"""(c.title ILIKE ${len(params) + 1}
         OR EXISTS (
           SELECT 1 FROM messages m
           WHERE m.conversation_id = c.id
           AND m.content ILIKE ${len(params) + 1}
         ))""")
        params.append(search_pattern)

    where_clause = " AND ".join(filters)

    query = f"""
        SELECT
            c.id::text,
            c.title,
            c.user_id::text,
            u.email AS user_email,
            u.full_name AS user_name,
            c.agent_id::text,
            a.name AS agent_name,
            c.total_messages,
            COALESCE((SELECT SUM(m.token_count) FROM messages m
                      WHERE m.conversation_id = c.id AND m.role = 'user'), 0)::int AS input_tokens,
            COALESCE((SELECT SUM(m.token_count) FROM messages m
                      WHERE m.conversation_id = c.id AND m.role = 'agent'), 0)::int AS output_tokens,
            c.created_at,
            c.updated_at,
            c.is_archived
        FROM conversations c
        JOIN users u ON c.user_id = u.id AND c.tenant_id = u.tenant_id
        JOIN agents a ON c.agent_id = a.id AND c.tenant_id = a.tenant_id
        WHERE {where_clause}
        ORDER BY {order_by} {order_direction.upper()}
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2};
    """

    params.extend([limit, skip])
    result = await pg_client.execute_query(query, *params)

    return [
        ConversationListItem(
            id=row["id"],
            title=row["title"],
            user_id=row["user_id"],
            user_email=row["user_email"],
            user_name=row["user_name"] or row["user_email"],
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            total_messages=row["total_messages"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_archived=row["is_archived"]
        )
        for row in result
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_detail(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get full conversation with all messages (including content).
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: Can view any conversation
    - Analysts/Students: Can only view their own conversations
    """
    from app.core.postgresql_client import get_postgresql_client

    # Get role-based user_id filter (None for admins, user_id for regular users)
    filtered_user_id = await get_filtered_user_id(current_user)

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')

    # Build query with optional user_id filter for non-admin users
    # Use inline subquery for tenant_id to avoid type conversion issues
    if filtered_user_id is not None:
        # Non-admin users can only see their own conversations
        conv_query = f"""
            SELECT
                c.id::text,
                c.title,
                u.email AS user_email,
                u.full_name AS user_name,
                a.name AS agent_name,
                a.model AS agent_model,
                c.total_messages,
                c.total_tokens,
                c.created_at,
                c.updated_at
            FROM conversations c
            JOIN users u ON c.user_id = u.id AND c.tenant_id = u.tenant_id
            JOIN agents a ON c.agent_id = a.id AND c.tenant_id = a.tenant_id
            WHERE c.id = $1
              AND c.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
              AND c.user_id = $3;
        """
        conv_result = await pg_client.execute_query(conv_query, conversation_id, tenant_domain, filtered_user_id)
    else:
        # Admin users can see all conversations
        conv_query = f"""
            SELECT
                c.id::text,
                c.title,
                u.email AS user_email,
                u.full_name AS user_name,
                a.name AS agent_name,
                a.model AS agent_model,
                c.total_messages,
                c.total_tokens,
                c.created_at,
                c.updated_at
            FROM conversations c
            JOIN users u ON c.user_id = u.id AND c.tenant_id = u.tenant_id
            JOIN agents a ON c.agent_id = a.id AND c.tenant_id = a.tenant_id
            WHERE c.id = $1
              AND c.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1);
        """
        conv_result = await pg_client.execute_query(conv_query, conversation_id, tenant_domain)

    if not conv_result:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_data = conv_result[0]

    # Get all messages
    msg_query = f"""
        SELECT
            id::text,
            role,
            content,
            content_type,
            token_count,
            model_used,
            created_at
        FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at ASC;
    """

    msg_result = await pg_client.execute_query(msg_query, conversation_id)

    messages = [
        MessageDetail(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            content_type=row["content_type"],
            token_count=row["token_count"] or 0,
            model_used=row["model_used"],
            created_at=row["created_at"]
        )
        for row in msg_result
    ]

    return ConversationDetail(
        id=conv_data["id"],
        title=conv_data["title"],
        user_email=conv_data["user_email"],
        user_name=conv_data["user_name"] or conv_data["user_email"],
        agent_name=conv_data["agent_name"],
        agent_model=conv_data["agent_model"],
        total_messages=conv_data["total_messages"],
        total_tokens=conv_data["total_tokens"],
        created_at=conv_data["created_at"],
        updated_at=conv_data["updated_at"],
        messages=messages
    )


@router.get("/export")
async def export_analytics_data(
    format: Literal["csv", "json"] = Query("csv", description="Export format"),
    days: Optional[int] = Query(None, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Custom range start date (YYYY-MM-DD or ISO timestamp: YYYY-MM-DDTHH:MM:SSZ)"),
    end_date: Optional[str] = Query(None, description="Custom range end date (YYYY-MM-DD or ISO timestamp: YYYY-MM-DDTHH:MM:SSZ)"),
    specific_date: Optional[str] = Query(None, description="Filter to specific date (YYYY-MM-DD or ISO timestamp)"),
    include_content: bool = Query(False, description="Include message content (increases size)"),
    user_id: Optional[str] = Query(None, description="Filter by specific user (admin only)"),
    agent_id: Optional[str] = Query(None),
    conversation_id: Optional[str] = Query(None, description="Export single conversation by ID"),
    search: Optional[str] = Query(None, description="Search filter for conversations"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Export analytics data as CSV or JSON.
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: Can export all platform data
    - Analysts/Students: Can only export their personal data

    Time filtering examples:
    - Date-only: start_date=2025-01-15&end_date=2025-01-16 (full days)
    - Hour:minute: start_date=2025-01-15T14:30:00Z&end_date=2025-01-15T16:45:00Z (specific time range)
    - Specific date: specific_date=2025-01-15 (filter to single day)
    """
    from app.core.postgresql_client import get_postgresql_client

    # Get role-based user_id filter (None for admins, user_id for regular users)
    filtered_user_id = await get_filtered_user_id(current_user)

    # For non-admin users, override any user_id parameter with their own ID
    if filtered_user_id is not None:
        user_id = filtered_user_id

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')

    # Determine date range using inline tenant_id subquery
    filters = ["c.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)"]
    params = [tenant_domain]

    # Initialize date range variables for JSON export metadata
    date_range_start = None
    date_range_end = None

    # Handle date filtering - specific_date takes priority, then custom range, then preset days
    if specific_date:
        # Filter to specific date (for chart clicks)
        try:
            if 'T' in specific_date:
                # ISO timestamp with time - extract the date
                specific_dt = datetime.fromisoformat(specific_date.replace('Z', '+00:00'))
                filters.append(f"DATE(c.created_at) = DATE(${len(params) + 1}::timestamp)")
                params.append(specific_dt)
                date_range_start = datetime.combine(specific_dt.date(), datetime.min.time())
                date_range_end = datetime.combine(specific_dt.date(), datetime.max.time())
            else:
                # Date-only string
                specific_dt = datetime.strptime(specific_date, '%Y-%m-%d')
                filters.append(f"DATE(c.created_at) = DATE(${len(params) + 1}::timestamp)")
                params.append(specific_dt)
                date_range_start = datetime.combine(specific_dt.date(), datetime.min.time())
                date_range_end = datetime.combine(specific_dt.date(), datetime.max.time())
            logger.info(f"[Export Debug] Using specific date filtering - date: {specific_dt}")
        except ValueError as e:
            logger.error(f"[Export Debug] Date parsing error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD or ISO timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    elif start_date and end_date:
        # Custom date range - handle both date-only strings and ISO timestamps with time
        try:
            if 'T' in start_date:
                # ISO timestamp with time - use full datetime precision for hour:minute filtering
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                date_range_start = start_dt
                date_range_end = end_dt
                filters.append(f"c.created_at >= ${len(params) + 1}")
                params.append(start_dt)
                filters.append(f"c.created_at <= ${len(params) + 1}")
                params.append(end_dt)
                logger.info(f"[Export Debug] Using datetime filtering - start: {start_dt}, end: {end_dt}")
            else:
                # Date-only format - use DATE() for timezone-agnostic day comparison
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                date_range_start = datetime.combine(start_dt, datetime.min.time())
                date_range_end = datetime.combine(end_dt, datetime.max.time())
                filters.append(f"DATE(c.created_at) >= ${len(params) + 1}")
                params.append(start_dt)
                filters.append(f"DATE(c.created_at) <= ${len(params) + 1}")
                params.append(end_dt)
                logger.info(f"[Export Debug] Using date filtering - start: {start_dt}, end: {end_dt}")
        except ValueError as e:
            logger.error(f"[Export Debug] Date parsing error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD or ISO timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    elif days is not None:
        # Preset days range
        date_start = datetime.now() - timedelta(days=days)
        date_range_start = date_start
        date_range_end = datetime.now()
        filters.append(f"c.created_at >= ${len(params) + 1}")
        params.append(date_start)
    # else: All time - no date filter

    if user_id:
        filters.append(f"c.user_id = ${len(params) + 1}")
        params.append(user_id)
    if agent_id:
        filters.append(f"c.agent_id = ${len(params) + 1}")
        params.append(agent_id)
    if conversation_id:
        filters.append(f"c.id = ${len(params) + 1}")
        params.append(conversation_id)
    if search:
        search_pattern = f"%{search}%"
        filters.append(f"""(c.title ILIKE ${len(params) + 1}
         OR EXISTS (
           SELECT 1 FROM messages m
           WHERE m.conversation_id = c.id
           AND m.content ILIKE ${len(params) + 1}
         ))""")
        params.append(search_pattern)

    where_clause = " AND ".join(filters)

    # Query for export data
    if include_content:
        query = f"""
            SELECT
                c.id AS conversation_id,
                c.title AS conversation_title,
                c.created_at AS conversation_created_at,
                u.email AS user_email,
                u.full_name AS user_name,
                u.role AS user_role,
                a.name AS agent_name,
                a.model AS agent_model,
                m.id AS message_id,
                m.role AS message_role,
                m.content AS message_content,
                m.token_count AS message_tokens,
                m.model_used AS message_model,
                m.created_at AS message_created_at
            FROM conversations c
            JOIN users u ON c.user_id = u.id AND c.tenant_id = u.tenant_id
            JOIN agents a ON c.agent_id = a.id AND c.tenant_id = a.tenant_id
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE {where_clause}
            ORDER BY c.created_at DESC, m.created_at ASC;
        """
    else:
        query = f"""
            SELECT
                c.id AS conversation_id,
                c.title AS conversation_title,
                c.created_at AS conversation_created_at,
                u.email AS user_email,
                u.full_name AS user_name,
                u.role AS user_role,
                a.name AS agent_name,
                a.model AS agent_model,
                c.total_messages,
                c.total_tokens
            FROM conversations c
            JOIN users u ON c.user_id = u.id AND c.tenant_id = u.tenant_id
            JOIN agents a ON c.agent_id = a.id AND c.tenant_id = a.tenant_id
            WHERE {where_clause}
            ORDER BY c.created_at DESC;
        """

    result = await pg_client.execute_query(query, *params)

    if format == "csv":
        # Generate CSV with proper quoting to handle commas and quotes in fields
        output = io.StringIO()
        if result:
            fieldnames = list(result[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(result)

        csv_content = output.getvalue()

        # Generate appropriate filename based on export scope
        if conversation_id:
            filename_prefix = f"conversation_{conversation_id[:8]}"
        elif search:
            filename_prefix = "filtered_conversations"
        else:
            filename_prefix = "analytics_export"
        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    else:  # JSON
        export_data = {
            "tenant_domain": tenant_domain,
            "export_date": datetime.now().isoformat(),
            "date_range_start": date_range_start.isoformat() if date_range_start else None,
            "date_range_end": date_range_end.isoformat() if date_range_end else None,
            "filters": {
                "user_id": user_id,
                "agent_id": agent_id,
                "include_content": include_content
            },
            "data": result
        }

        # Generate appropriate filename based on export scope
        if conversation_id:
            filename_prefix = f"conversation_{conversation_id[:8]}"
        elif search:
            filename_prefix = "filtered_conversations"
        else:
            filename_prefix = "analytics_export"
        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return Response(
            content=json.dumps(export_data, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )


@router.get("/storage", response_model=StorageMetrics)
async def get_storage_metrics(
    user_id: Optional[str] = Query(None, description="Filter by specific user (admin only)"),
    dataset_id: Optional[str] = Query(None, description="Filter by specific dataset"),
    team_id: Optional[str] = Query(None, description="Filter by team (team observers only)"),
    view: str = Query("dataset", description="View type: 'dataset' or 'user'"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get storage and file metrics for documents and datasets.
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: See all storage data, can filter by user
    - Team Observers (owners/managers): See storage for team-shared datasets in team mode
    - Analysts/Students: See only their personal storage data

    Optionally filter by user_id, dataset_id, or team_id to show storage for specific contexts.
    View parameter controls whether breakdown is by dataset or by user.
    """
    from app.core.postgresql_client import get_postgresql_client
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"[Observability] Storage metrics requested with filters - user_id: {user_id}, dataset_id: {dataset_id}")

    # Get role-based user_id filter (None for admins, user_id for regular users)
    filtered_user_id = await get_filtered_user_id(current_user)

    # For non-admin users, override any user_id parameter with their own ID
    if filtered_user_id is not None:
        user_id = filtered_user_id
        logger.info(f"[Observability] Non-admin user restricted to their own data: {user_id}")

    # IMPORTANT: If in individual mode (no team_id) and user is a team observer (filtered_user_id is None),
    # we still need to filter to their personal data, not all tenant data
    elif filtered_user_id is None and not team_id and not user_id:
        # Team observer in individual mode - get their user_id
        pg_client = await get_postgresql_client()
        tenant_domain = current_user.get('tenant_domain', 'test-company')
        user_email = current_user.get('email')

        user_role = await get_user_role(pg_client, user_email, tenant_domain)
        if user_role not in ['admin', 'developer']:
            # Not an admin, so get their user_id for individual filtering
            user_uuid_query = """
                SELECT id::text FROM users
                WHERE email = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                LIMIT 1
            """
            user_id = await pg_client.fetch_scalar(user_uuid_query, user_email, tenant_domain)
            logger.info(f"[Observability] Team observer in individual mode restricted to their own data: {user_id}")

    pg_client = await get_postgresql_client()

    # Build WHERE clause for filters
    # Logic based on user requirements:
    # - user_id only: Show all documents in datasets CREATED BY that user
    # - dataset_id only: Show all documents in that specific dataset (any owner)
    # - both: Show all documents in that dataset (must be owned by user)
    # - team_id only: Show all documents in datasets shared with team
    filters = []
    params = []

    if user_id and not dataset_id and not team_id:
        # User filter only: documents in datasets owned by this user
        filters.append(f"d.dataset_id IN (SELECT id FROM datasets WHERE created_by = ${len(params) + 1})")
        params.append(user_id)
        logger.info(f"[Observability] Filter: datasets created by user {user_id}")

    elif dataset_id and not user_id:
        # Dataset filter only: all documents in this dataset
        filters.append(f"d.dataset_id = ${len(params) + 1}")
        params.append(dataset_id)
        logger.info(f"[Observability] Filter: dataset {dataset_id} (any owner)")

    elif user_id and dataset_id:
        # Both filters: documents in this dataset (must be owned by user)
        filters.append(f"d.dataset_id = ${len(params) + 1}")
        filters.append(f"EXISTS (SELECT 1 FROM datasets ds WHERE ds.id = d.dataset_id AND ds.created_by = ${len(params) + 2})")
        params.extend([dataset_id, user_id])
        logger.info(f"[Observability] Filter: dataset {dataset_id} owned by user {user_id}")

    # Team mode filtering - show only datasets shared with the team
    elif team_id and not user_id and not dataset_id:
        tenant_domain = current_user.get('tenant_domain', 'test-company')

        if team_id == 'all':
            # "All Teams" mode - show datasets shared with any team the observer manages
            user_email = current_user.get('email')
            filters.append("""
                d.dataset_id IN (
                    SELECT DISTINCT trs.resource_id
                    FROM team_resource_shares trs
                    JOIN teams t ON t.id = trs.team_id
                    WHERE trs.resource_type = 'dataset'
                      AND (
                          -- Observer is team owner
                          t.owner_id = (
                              SELECT id FROM users
                              WHERE email = $1
                                AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                              LIMIT 1
                          )
                          OR
                          -- Observer is team manager
                          EXISTS(
                              SELECT 1 FROM team_memberships tm_mgr
                              WHERE tm_mgr.team_id = t.id
                                AND tm_mgr.user_id = (
                                    SELECT id FROM users
                                    WHERE email = $1
                                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                                    LIMIT 1
                                )
                                AND tm_mgr.team_permission = 'manager'
                                AND tm_mgr.status = 'accepted'
                          )
                      )
                )
            """)
            params.extend([user_email, tenant_domain])
            logger.info(f"[Observability] Filter: datasets shared with all managed teams")
        else:
            # Specific team mode - show datasets shared with this team
            filters.append(f"""
                d.dataset_id IN (
                    SELECT resource_id FROM team_resource_shares
                    WHERE team_id = ${len(params) + 1}::uuid
                      AND resource_type = 'dataset'
                )
            """)
            params.append(team_id)
            logger.info(f"[Observability] Filter: datasets shared with team {team_id}")

    user_filter = " WHERE " + " AND ".join(filters) if filters else ""
    logger.info(f"[Observability] Built filter clause: {user_filter}, params: {params}")

    # Get overall storage metrics (file_size + chunk content + embeddings)
    overview_query = f"""
        SELECT
            COUNT(d.id) as total_documents,
            (
                COALESCE(SUM(d.file_size_bytes), 0) +
                COALESCE((SELECT SUM(LENGTH(dc.content)) FROM document_chunks dc JOIN documents doc ON dc.document_id = doc.id), 0) +
                COALESCE((SELECT COUNT(*) * {EMBEDDING_SIZE_BYTES} FROM document_chunks dc JOIN documents doc ON dc.document_id = doc.id), 0)
            ) / 1024.0 / 1024.0 as total_storage_mb,
            COUNT(DISTINCT d.dataset_id) as total_datasets,
            COALESCE(AVG(d.file_size_bytes) / 1024.0 / 1024.0, 0) as avg_document_size_mb
        FROM documents d
        {user_filter}
    """
    overview_row = await pg_client.fetch_one(overview_query, *params) if params else await pg_client.fetch_one(overview_query)

    overview = StorageOverview(
        total_documents=overview_row['total_documents'] or 0,
        total_storage_mb=float(overview_row['total_storage_mb'] or 0) * DATASET_STORAGE_MULTIPLIER,
        total_datasets=overview_row['total_datasets'] or 0,
        average_document_size_mb=float(overview_row['avg_document_size_mb'] or 0) * DATASET_STORAGE_MULTIPLIER
    )

    breakdown = []
    user_breakdown = None

    # Build dataset-based filters for queries that start with FROM datasets
    # This is needed for both the dataset breakdown AND the file details queries
    dataset_filters = []
    breakdown_params = []

    if user_id and not dataset_id and not team_id:
        # User only: show datasets created by user
        dataset_filters.append(f"ds.created_by = ${len(breakdown_params) + 1}")
        breakdown_params.append(user_id)
    elif dataset_id and not user_id and not team_id:
        # Dataset only: show specific dataset
        dataset_filters.append(f"ds.id = ${len(breakdown_params) + 1}")
        breakdown_params.append(dataset_id)
    elif user_id and dataset_id:
        # Both: show specific dataset owned by user
        dataset_filters.append(f"ds.id = ${len(breakdown_params) + 1}")
        dataset_filters.append(f"ds.created_by = ${len(breakdown_params) + 2}")
        breakdown_params.extend([dataset_id, user_id])
    elif team_id and not user_id and not dataset_id:
        # Team mode: show datasets shared with the team
        if team_id == 'all':
            # "All Teams" mode
            user_email = current_user.get('email')
            dataset_filters.append("""
                ds.id IN (
                    SELECT DISTINCT trs.resource_id
                    FROM team_resource_shares trs
                    JOIN teams t ON t.id = trs.team_id
                    WHERE trs.resource_type = 'dataset'
                      AND (
                          t.owner_id = (
                              SELECT id FROM users
                              WHERE email = $1
                                AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                              LIMIT 1
                          )
                          OR
                          EXISTS(
                              SELECT 1 FROM team_memberships tm_mgr
                              WHERE tm_mgr.team_id = t.id
                                AND tm_mgr.user_id = (
                                    SELECT id FROM users
                                    WHERE email = $1
                                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                                    LIMIT 1
                                )
                                AND tm_mgr.team_permission = 'manager'
                                AND tm_mgr.status = 'accepted'
                          )
                      )
                )
            """)
            breakdown_params.extend([user_email, tenant_domain])
        else:
            # Specific team mode
            dataset_filters.append(f"""
                ds.id IN (
                    SELECT resource_id FROM team_resource_shares
                    WHERE team_id = ${len(breakdown_params) + 1}::uuid
                      AND resource_type = 'dataset'
                )
            """)
            breakdown_params.append(team_id)

    dataset_user_filter = " WHERE " + " AND ".join(dataset_filters) if dataset_filters else ""

    if view == "user":
        # Get breakdown by user with billing-accurate calculations
        # Includes: dataset storage (files + chunks + embeddings) and conversation storage (messages + files + embeddings)
        # Applies proper multipliers: DATASET_STORAGE_MULTIPLIER (4.5x) and CONVERSATION_STORAGE_MULTIPLIER (19x)
        user_breakdown_query = f"""
            WITH dataset_by_user AS (
                SELECT
                    d.user_id,
                    COUNT(DISTINCT d.id) as document_count,
                    (
                        COALESCE(SUM(d.file_size_bytes), 0) +
                        COALESCE((
                            SELECT SUM(LENGTH(dc.content))
                            FROM document_chunks dc
                            JOIN documents doc ON dc.document_id = doc.id
                            WHERE doc.user_id = d.user_id
                        ), 0) +
                        COALESCE((
                            SELECT COUNT(*) * {EMBEDDING_SIZE_BYTES}
                            FROM document_chunks dc
                            JOIN documents doc ON dc.document_id = doc.id
                            WHERE doc.user_id = d.user_id
                        ), 0)
                    ) / 1048576.0 * {DATASET_STORAGE_MULTIPLIER} as dataset_storage_mb
                FROM documents d
                GROUP BY d.user_id
            ),
            conversation_by_user AS (
                SELECT
                    c.user_id,
                    COUNT(DISTINCT c.id) as conversation_count,
                    (
                        COALESCE((
                            SELECT SUM(LENGTH(m.content))
                            FROM messages m
                            JOIN conversations conv ON m.conversation_id = conv.id
                            WHERE conv.user_id = c.user_id
                        ), 0) +
                        COALESCE((
                            SELECT SUM(cf.file_size_bytes)
                            FROM conversation_files cf
                            JOIN conversations conv ON cf.conversation_id = conv.id
                            WHERE conv.user_id = c.user_id
                        ), 0) +
                        COALESCE((
                            SELECT COUNT(*) * {EMBEDDING_SIZE_BYTES}
                            FROM conversation_files cf
                            JOIN conversations conv ON cf.conversation_id = conv.id
                            WHERE conv.user_id = c.user_id AND cf.embeddings IS NOT NULL
                        ), 0)
                    ) / 1048576.0 * {CONVERSATION_STORAGE_MULTIPLIER} as conversation_storage_mb
                FROM conversations c
                GROUP BY c.user_id
            ),
            totals AS (
                SELECT COALESCE(
                    (SELECT SUM(dataset_storage_mb) FROM dataset_by_user), 0
                ) + COALESCE(
                    (SELECT SUM(conversation_storage_mb) FROM conversation_by_user), 0
                ) as total_mb
            )
            SELECT
                u.id::text as user_id,
                u.email as user_email,
                u.full_name as user_name,
                COALESCE(ds.document_count, 0) as document_count,
                COALESCE(ds.dataset_storage_mb, 0) as dataset_storage_mb,
                COALESCE(cv.conversation_count, 0) as conversation_count,
                COALESCE(cv.conversation_storage_mb, 0) as conversation_storage_mb,
                COALESCE(ds.dataset_storage_mb, 0) + COALESCE(cv.conversation_storage_mb, 0) as total_storage_mb,
                CASE
                    WHEN (SELECT total_mb FROM totals) > 0
                    THEN ((COALESCE(ds.dataset_storage_mb, 0) + COALESCE(cv.conversation_storage_mb, 0)) * 100.0 / (SELECT total_mb FROM totals))
                    ELSE 0
                END as percentage
            FROM users u
            LEFT JOIN dataset_by_user ds ON u.id = ds.user_id
            LEFT JOIN conversation_by_user cv ON u.id = cv.user_id
            WHERE COALESCE(ds.dataset_storage_mb, 0) > 0 OR COALESCE(cv.conversation_storage_mb, 0) > 0
            ORDER BY total_storage_mb DESC
            LIMIT 20
        """
        logger.info("[Observability] Executing billing-accurate user storage breakdown query")
        user_breakdown_rows = await pg_client.execute_query(user_breakdown_query)

        user_breakdown = [
            UserStorageItem(
                id=row['user_id'],
                label=row['user_name'] or row['user_email'],
                document_count=int(row['document_count']),
                dataset_storage_mb=round(float(row['dataset_storage_mb']), 2),
                conversation_count=int(row['conversation_count']),
                conversation_storage_mb=round(float(row['conversation_storage_mb']), 2),
                total_storage_mb=round(float(row['total_storage_mb']), 2),
                percentage=round(float(row['percentage']), 1)
            )
            for row in user_breakdown_rows
        ]
        logger.info(f"[Observability] Found {len(user_breakdown)} users with storage")
    else:
        # Get breakdown by dataset (file_size + chunk content + embeddings per dataset)

        # Use CTE for correct percentage calculation
        breakdown_query = f"""
            WITH dataset_storage AS (
                SELECT
                    ds.id as dataset_id,
                    ds.name as dataset_name,
                    COUNT(DISTINCT d.id) as document_count,
                    (
                        COALESCE(SUM(d.file_size_bytes), 0) +
                        COALESCE((
                            SELECT SUM(LENGTH(dc.content))
                            FROM document_chunks dc
                            JOIN documents doc ON dc.document_id = doc.id
                            WHERE doc.dataset_id = ds.id
                        ), 0) +
                        COALESCE((
                            SELECT COUNT(*) * {EMBEDDING_SIZE_BYTES}
                            FROM document_chunks dc
                            JOIN documents doc ON dc.document_id = doc.id
                            WHERE doc.dataset_id = ds.id
                        ), 0)
                    ) as total_bytes
                FROM datasets ds
                LEFT JOIN documents d ON d.dataset_id = ds.id
                {dataset_user_filter}
                GROUP BY ds.id, ds.name
            ),
            filtered_total AS (
                SELECT COALESCE(SUM(total_bytes), 0) as total_bytes FROM dataset_storage
            )
            SELECT
                dataset_id::text,
                dataset_name,
                document_count,
                total_bytes / 1024.0 / 1024.0 as storage_mb,
                CASE
                    WHEN (SELECT total_bytes FROM filtered_total) > 0
                    THEN (total_bytes * 100.0 / (SELECT total_bytes FROM filtered_total))
                    ELSE 0
                END as percentage
            FROM dataset_storage
            WHERE document_count > 0
            ORDER BY storage_mb DESC
            LIMIT 20
        """
        logger.info(f"[Observability] Executing dataset breakdown query with {len(breakdown_params)} params")
        breakdown_rows = await pg_client.execute_query(breakdown_query, *breakdown_params) if breakdown_params else await pg_client.execute_query(breakdown_query)
        logger.info(f"[Observability] Found {len(breakdown_rows)} datasets in breakdown")

        breakdown = [
            DatasetStorageItem(
                id=row['dataset_id'],
                label=row['dataset_name'],
                document_count=row['document_count'],
                storage_mb=float(row['storage_mb']) * DATASET_STORAGE_MULTIPLIER,
                percentage=float(row['percentage'])
            )
            for row in breakdown_rows
        ]

    # Get file type breakdown with CTE for correct percentage calculation
    file_type_query = f"""
        WITH filtered_total AS (
            SELECT COALESCE(SUM(file_size_bytes), 0) as total_bytes
            FROM documents d
            {user_filter}
        )
        SELECT
            d.file_type,
            COUNT(d.id) as document_count,
            COALESCE(SUM(d.file_size_bytes) / 1024.0 / 1024.0, 0) as storage_mb,
            CASE
                WHEN (SELECT total_bytes FROM filtered_total) > 0
                THEN (COALESCE(SUM(d.file_size_bytes), 0) * 100.0 / (SELECT total_bytes FROM filtered_total))
                ELSE 0
            END as percentage
        FROM documents d
        {user_filter}
        GROUP BY d.file_type
        ORDER BY storage_mb DESC
        LIMIT 15
    """
    logger.info(f"[Observability] Executing file type breakdown query with {len(params)} params")
    file_type_rows = await pg_client.execute_query(file_type_query, *params) if params else await pg_client.execute_query(file_type_query)
    logger.info(f"[Observability] Found {len(file_type_rows)} file types")

    file_type_breakdown = [
        FileTypeBreakdown(
            file_type=row['file_type'] or 'unknown',
            document_count=row['document_count'],
            storage_mb=float(row['storage_mb']) * DATASET_STORAGE_MULTIPLIER,
            percentage=float(row['percentage'])
        )
        for row in file_type_rows
    ]

    # Get dataset file details - list all files per dataset with proper filtering
    # Shows detailed file listing for each dataset matching the filter
    # Use the same dataset-based filter logic as the breakdown query
    # Total size includes file_size + chunks + embeddings per dataset
    dataset_files_query = f"""
        SELECT
            ds.id::text as dataset_id,
            ds.name as dataset_name,
            (
                COALESCE(SUM(d.file_size_bytes), 0) +
                COALESCE((
                    SELECT SUM(LENGTH(dc.content))
                    FROM document_chunks dc
                    JOIN documents doc ON dc.document_id = doc.id
                    WHERE doc.dataset_id = ds.id
                ), 0) +
                COALESCE((
                    SELECT COUNT(*) * {EMBEDDING_SIZE_BYTES}
                    FROM document_chunks dc
                    JOIN documents doc ON dc.document_id = doc.id
                    WHERE doc.dataset_id = ds.id
                ), 0)
            ) / 1024.0 / 1024.0 as total_size_mb,
            COUNT(d.id) as file_count,
            COALESCE(
                json_agg(
                    json_build_object(
                        'file_name', d.filename,
                        'file_size_mb', d.file_size_bytes / 1024.0 / 1024.0,
                        'file_type', d.file_type,
                        'uploaded_at', d.created_at
                    ) ORDER BY d.file_size_bytes DESC
                ) FILTER (WHERE d.id IS NOT NULL),
                '[]'::json
            ) as files
        FROM datasets ds
        LEFT JOIN documents d ON d.dataset_id = ds.id
        {dataset_user_filter}
        GROUP BY ds.id, ds.name
        HAVING COUNT(d.id) > 0
        ORDER BY total_size_mb DESC
        LIMIT 20
    """
    logger.info(f"[Observability] Executing dataset file details query with {len(breakdown_params)} params")
    dataset_files_rows = await pg_client.execute_query(dataset_files_query, *breakdown_params) if breakdown_params else await pg_client.execute_query(dataset_files_query)
    logger.info(f"[Observability] Found {len(dataset_files_rows)} datasets with file details")

    dataset_file_details = [
        DatasetFileDetails(
            dataset_id=row['dataset_id'],
            dataset_name=row['dataset_name'],
            total_size_mb=float(row['total_size_mb']) * DATASET_STORAGE_MULTIPLIER,
            file_count=row['file_count'],
            files=[
                FileInfo(
                    file_name=f['file_name'],
                    file_size_mb=float(f['file_size_mb']) * DATASET_STORAGE_MULTIPLIER,
                    file_type=f['file_type'],
                    uploaded_at=f['uploaded_at']
                )
                for f in (json.loads(row['files']) if isinstance(row['files'], str) else row['files'] if row['files'] else [])
            ]
        )
        for row in dataset_files_rows
    ]

    return StorageMetrics(
        overview=overview,
        breakdown_by_dataset=breakdown,
        breakdown_by_user=user_breakdown,
        file_type_breakdown=file_type_breakdown,
        dataset_file_details=dataset_file_details
    )


@router.get("/users", response_model=List[UserListItem])
async def get_users_list(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get list of all users in the tenant for filtering purposes.
    Admin-only endpoint.
    """
    from app.core.postgresql_client import get_postgresql_client

    await require_admin_role(current_user)

    pg_client = await get_postgresql_client()

    # Get all users in the tenant (context already isolated)
    users_query = """
        SELECT
            u.id::text,
            u.email,
            u.full_name,
            u.role
        FROM users u
        ORDER BY u.email ASC
    """
    users_rows = await pg_client.execute_query(users_query)

    users = [
        UserListItem(
            id=row['id'],
            email=row['email'],
            full_name=row['full_name'],
            role=row['role']
        )
        for row in users_rows
    ]

    return users


@router.get("/filters", response_model=FilterOptions)
async def get_filter_options(
    team_id: Optional[str] = Query(None, description="Filter by team (team observers only)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get lists of users and agents for dropdown filter options.
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: See all users and all agents
    - Team Observers (in team mode): See Observable members' agents + own agents
    - Analysts/Students: See only themselves and only agents from their conversations

    This ensures filter dropdowns only show options relevant to conversations the user can view.
    """
    from app.core.postgresql_client import get_postgresql_client

    # Get role-based user_id filter (None for admins, user_id for regular users)
    filtered_user_id = await get_filtered_user_id(current_user)

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')

    # Get users based on role
    if filtered_user_id is not None:
        # Non-admin users: only show themselves
        users_query = """
            SELECT
                u.id::text,
                u.email,
                u.full_name,
                u.role
            FROM users u
            WHERE u.id = $1
            ORDER BY u.email ASC
        """
        users_rows = await pg_client.execute_query(users_query, filtered_user_id)
    else:
        # Admin users: show all users in the tenant
        users_query = """
            SELECT
                u.id::text,
                u.email,
                u.full_name,
                u.role
            FROM users u
            ORDER BY u.email ASC
        """
        users_rows = await pg_client.execute_query(users_query)

    users = [
        UserListItem(
            id=row['id'],
            email=row['email'],
            full_name=row['full_name'],
            role=row['role']
        )
        for row in users_rows
    ]

    # Get agents based on role and observability mode
    if filtered_user_id is not None:
        # Non-admin users in individual mode: show only agents from their own conversations
        logger.info(f"[Observability Filters] Filtering agents for non-admin user in individual mode")
        logger.info(f"[Observability Filters] user_id: {filtered_user_id}, tenant: {tenant_domain}")

        # Query agents from conversations the user has access to
        agents_query = """
            SELECT DISTINCT
                a.id::text,
                a.name,
                a.model
            FROM agents a
            INNER JOIN conversations c ON c.agent_id = a.id
            WHERE c.user_id = $1
              AND c.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            ORDER BY a.name ASC
        """
        agents_rows = await pg_client.execute_query(agents_query, filtered_user_id, tenant_domain)
        logger.info(f"[Observability Filters] Found {len(agents_rows)} agents from user's conversations")

        if len(agents_rows) == 0:
            logger.warning(f"[Observability Filters] No agents found - user may have no conversations")
    else:
        # Admin or team observer
        user_role = await get_user_role(pg_client, current_user.get('email'), tenant_domain)

        if user_role not in ['admin', 'developer']:
            # Team observer - filter based on team mode
            user_email = current_user.get('email')

            if team_id and team_id != 'all':
                # Specific team mode - show ONLY agents shared to this team
                logger.info(f"[Observability Filters] Team observer in specific team mode (team_id={team_id})")

                agents_query = """
                    SELECT DISTINCT
                        a.id::text,
                        a.name,
                        a.model
                    FROM agents a
                    WHERE a.id IN (
                        -- Only agents shared to this team via team_resource_shares
                        SELECT resource_id FROM team_resource_shares
                        WHERE team_id = $2::uuid
                          AND resource_type = 'agent'
                    )
                      AND a.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                    ORDER BY a.name ASC
                """
                agents_rows = await pg_client.execute_query(agents_query, tenant_domain, team_id)
                logger.info(f"[Observability Filters] Found {len(agents_rows)} team-shared agents for team {team_id}")

            elif team_id == 'all':
                # "All Teams" mode - show agents shared to ANY team the observer manages
                logger.info(f"[Observability Filters] Team observer in 'All Teams' mode")

                agents_query = """
                    SELECT DISTINCT
                        a.id::text,
                        a.name,
                        a.model
                    FROM agents a
                    WHERE a.id IN (
                        -- Agents shared to teams where user is owner or manager
                        SELECT DISTINCT trs.resource_id
                        FROM team_resource_shares trs
                        JOIN teams t ON t.id = trs.team_id
                        WHERE trs.resource_type = 'agent'
                          AND (
                              -- Observer is team owner
                              t.owner_id = (
                                  SELECT id FROM users
                                  WHERE email = $2
                                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                                  LIMIT 1
                              )
                              OR
                              -- Observer is team manager
                              EXISTS(
                                  SELECT 1 FROM team_memberships tm_mgr
                                  WHERE tm_mgr.team_id = t.id
                                    AND tm_mgr.user_id = (
                                        SELECT id FROM users
                                        WHERE email = $2
                                          AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                                        LIMIT 1
                                    )
                                    AND tm_mgr.team_permission = 'manager'
                                    AND tm_mgr.status = 'accepted'
                              )
                          )
                    )
                      AND a.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                    ORDER BY a.name ASC
                """
                agents_rows = await pg_client.execute_query(agents_query, tenant_domain, user_email)
                logger.info(f"[Observability Filters] Found {len(agents_rows)} team-shared agents across all managed teams")

            else:
                # Individual mode for team observer - show only their own agents
                logger.info(f"[Observability Filters] Team observer in individual mode")

                agents_query = """
                    SELECT DISTINCT
                        a.id::text,
                        a.name,
                        a.model
                    FROM agents a
                    INNER JOIN conversations c ON c.agent_id = a.id
                    WHERE c.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                      AND c.user_id = (
                          SELECT id FROM users
                          WHERE email = $2
                            AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                          LIMIT 1
                      )
                    ORDER BY a.name ASC
                """
                agents_rows = await pg_client.execute_query(agents_query, tenant_domain, user_email)
                logger.info(f"[Observability Filters] Found {len(agents_rows)} agents from manager's own conversations")
        else:
            # Admin users: show all agents in the tenant
            logger.info(f"[Observability Filters] Admin user - returning all agents")
            agents_query = """
                SELECT
                    a.id::text,
                    a.name,
                    a.model
                FROM agents a
                ORDER BY a.name ASC
            """
            agents_rows = await pg_client.execute_query(agents_query)
            logger.info(f"[Observability Filters] Found {len(agents_rows)} total agents")

    agents = [
        AgentListItem(
            id=row['id'],
            name=row['name'],
            model=row['model']
        )
        for row in agents_rows
    ]

    # Get teams for team observers (non-admin with manager permission or owner status)
    teams = None
    if filtered_user_id is None:
        user_email = current_user.get('email')
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        if user_role not in ['admin', 'developer']:
            # Team observer - get teams they can observe with Observable member counts
            logger.info(f"[Observability Filters] Team observer {user_email} - fetching Observable teams")

            teams_query = """
                SELECT DISTINCT
                    t.id::text,
                    t.name,
                    (
                        SELECT COUNT(*)
                        FROM team_memberships tm_obs
                        WHERE tm_obs.team_id = t.id
                          AND tm_obs.is_observable = true
                          AND tm_obs.observable_consent_status = 'approved'
                          AND tm_obs.status = 'accepted'
                    ) as observable_count
                FROM teams t
                JOIN team_memberships tm ON tm.team_id = t.id
                WHERE (
                    -- User is team owner
                    t.owner_id = (
                        SELECT id FROM users
                        WHERE email = $1
                          AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                        LIMIT 1
                    )
                    OR (
                        -- User has manager permission
                        tm.user_id = (
                            SELECT id FROM users
                            WHERE email = $1
                              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                            LIMIT 1
                        )
                        AND tm.team_permission = 'manager'
                        AND tm.status = 'accepted'
                    )
                )
                ORDER BY t.name ASC
            """
            teams_rows = await pg_client.execute_query(teams_query, user_email, tenant_domain)

            teams = [
                TeamListItem(
                    id=row['id'],
                    name=row['name'],
                    observable_count=row['observable_count']
                )
                for row in teams_rows
                if row['observable_count'] > 0  # Only include teams with Observable members
            ]

            logger.info(f"[Observability Filters] Found {len(teams)} teams with Observable members")

    return FilterOptions(users=users, agents=agents, teams=teams)


@router.get("/teams/{team_id}/observable-members", response_model=ObservableMembersResponse)
async def get_team_observable_members(
    team_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get Observable members for a specific team.
    Only team owners and managers can access this endpoint.
    Returns object with members array of users who are Observable in the specified team.
    """
    from app.core.postgresql_client import get_postgresql_client
    from app.services.team_service import TeamService

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')
    team_service = TeamService(tenant_domain, current_user.get('email'))

    # Verify permission to view team observability
    user_id_query = """
        SELECT id FROM users
        WHERE email = $1
          AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        LIMIT 1
    """
    user_row = await pg_client.execute_query(user_id_query, current_user.get('email'), tenant_domain)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user_row[0]['id'])

    # Check if user can view observability for this team
    can_view = await team_service.can_view_observability(team_id, user_id)
    if not can_view:
        raise HTTPException(
            status_code=403,
            detail="Only team owners and managers can view Observable members"
        )

    # Get Observable members for this team
    observable_members_query = """
        SELECT
            u.id::text,
            u.email,
            u.full_name,
            u.role
        FROM users u
        JOIN team_memberships tm ON tm.user_id = u.id
        WHERE tm.team_id = $1::uuid
          AND tm.is_observable = true
          AND tm.observable_consent_status = 'approved'
          AND tm.status = 'accepted'
        ORDER BY u.email ASC
    """
    members_rows = await pg_client.execute_query(observable_members_query, team_id)

    logger.info(f"[Observability] Team {team_id} has {len(members_rows)} Observable members")

    members_list = [
        UserListItem(
            id=row['id'],
            email=row['email'],
            full_name=row['full_name'],
            role=row['role']
        )
        for row in members_rows
    ]

    return ObservableMembersResponse(members=members_list)


@router.get("/teams/observable-members", response_model=ObservableMembersResponse)
async def get_all_observable_members(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all Observable members across all teams the user manages.
    Only team owners and managers can access this endpoint.
    Returns object with members array containing deduplicated list of all unique Observable members from all managed teams.
    """
    from app.core.postgresql_client import get_postgresql_client

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')
    user_email = current_user.get('email')

    # Get user ID
    user_id_query = """
        SELECT id FROM users
        WHERE email = $1
          AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        LIMIT 1
    """
    user_row = await pg_client.execute_query(user_id_query, user_email, tenant_domain)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user_row[0]['id'])

    # Get all Observable members from teams the user owns or manages
    observable_members_query = """
        SELECT DISTINCT
            u.id::text,
            u.email,
            u.full_name,
            u.role
        FROM users u
        JOIN team_memberships tm ON tm.user_id = u.id
        JOIN teams t ON t.id = tm.team_id
        WHERE tm.is_observable = true
          AND tm.observable_consent_status = 'approved'
          AND tm.status = 'accepted'
          AND (
              -- User is team owner
              t.owner_id = $1::uuid
              OR
              -- User is team manager
              EXISTS(
                  SELECT 1 FROM team_memberships tm_mgr
                  WHERE tm_mgr.team_id = t.id
                    AND tm_mgr.user_id = $1::uuid
                    AND tm_mgr.team_permission = 'manager'
                    AND tm_mgr.status = 'accepted'
              )
          )
        ORDER BY u.email ASC
    """
    members_rows = await pg_client.execute_query(observable_members_query, user_id)

    logger.info(f"[Observability] User {user_email} has {len(members_rows)} total Observable members across all teams")

    members_list = [
        UserListItem(
            id=row['id'],
            email=row['email'],
            full_name=row['full_name'],
            role=row['role']
        )
        for row in members_rows
    ]

    return ObservableMembersResponse(members=members_list)


@router.get("/datasets")
async def get_datasets_list(
    team_id: Optional[str] = Query(None, description="Filter by team (team observers only)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get list of datasets with ownership info for filtering purposes.
    Available to all authenticated users with role-based data filtering:
    - Admins/Developers: See all datasets (in individual mode) or Observable members' datasets (in team mode)
    - Team Observers: See Observable members' datasets (in team mode) or own datasets (in individual mode)
    - Regular users: See only their own datasets
    Returns datasets with creator information for filter dropdown population.
    """
    from app.core.postgresql_client import get_postgresql_client
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"[Observability] Datasets list requested (team_id: {team_id})")

    pg_client = await get_postgresql_client()
    tenant_domain = current_user.get('tenant_domain', 'test-company')
    user_email = current_user.get('email')

    # Get user role
    user_role = await get_user_role(pg_client, user_email, tenant_domain)

    # Build query with role-based and team-based filtering
    if team_id and team_id != 'all':
        # Specific team mode - filter to datasets shared with this team
        logger.info(f"[Observability] Team mode - filtering datasets shared with team {team_id}")
        datasets_query = """
            SELECT DISTINCT
                d.id::text,
                d.name,
                d.created_by::text,
                u.email as creator_email,
                u.full_name as creator_name
            FROM datasets d
            JOIN users u ON d.created_by = u.id
            WHERE d.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
              AND d.id IN (
                  SELECT resource_id FROM team_resource_shares
                  WHERE team_id = $2::uuid
                    AND resource_type = 'dataset'
              )
            ORDER BY d.name ASC
        """
        datasets_rows = await pg_client.execute_query(datasets_query, tenant_domain, team_id)
        logger.info(f"[Observability] Team mode - found {len(datasets_rows)} team-shared datasets")
    elif team_id == 'all':
        # "All Teams" mode - filter to datasets shared with any team the observer manages
        logger.info(f"[Observability] 'All Teams' mode - filtering datasets shared with managed teams")
        datasets_query = """
            SELECT DISTINCT
                d.id::text,
                d.name,
                d.created_by::text,
                u.email as creator_email,
                u.full_name as creator_name
            FROM datasets d
            JOIN users u ON d.created_by = u.id
            WHERE d.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
              AND d.id IN (
                  SELECT DISTINCT trs.resource_id
                  FROM team_resource_shares trs
                  JOIN teams t ON t.id = trs.team_id
                  WHERE trs.resource_type = 'dataset'
                    AND (
                        -- Observer is team owner
                        t.owner_id = (
                            SELECT id FROM users
                            WHERE email = $2
                              AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                            LIMIT 1
                        )
                        OR
                        -- Observer is team manager
                        EXISTS(
                            SELECT 1 FROM team_memberships tm_mgr
                            WHERE tm_mgr.team_id = t.id
                              AND tm_mgr.user_id = (
                                  SELECT id FROM users
                                  WHERE email = $2
                                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                                  LIMIT 1
                              )
                              AND tm_mgr.team_permission = 'manager'
                              AND tm_mgr.status = 'accepted'
                        )
                    )
              )
            ORDER BY d.name ASC
        """
        datasets_rows = await pg_client.execute_query(datasets_query, tenant_domain, user_email)
        logger.info(f"[Observability] 'All Teams' mode - found {len(datasets_rows)} team-shared datasets")
    elif user_role in ['admin', 'developer']:
        # Individual mode - Admins see all datasets
        datasets_query = """
            SELECT
                d.id::text,
                d.name,
                d.created_by::text,
                u.email as creator_email,
                u.full_name as creator_name
            FROM datasets d
            JOIN users u ON d.created_by = u.id
            WHERE d.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
            ORDER BY d.name ASC
        """
        datasets_rows = await pg_client.execute_query(datasets_query, tenant_domain)
        logger.info(f"[Observability] Admin viewing all datasets - found {len(datasets_rows)} datasets")
    else:
        # Individual mode - Regular users see only their own datasets
        datasets_query = """
            SELECT
                d.id::text,
                d.name,
                d.created_by::text,
                u.email as creator_email,
                u.full_name as creator_name
            FROM datasets d
            JOIN users u ON d.created_by = u.id
            WHERE d.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
              AND d.created_by = (
                  SELECT id FROM users
                  WHERE email = $2
                    AND tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                  LIMIT 1
              )
            ORDER BY d.name ASC
        """
        datasets_rows = await pg_client.execute_query(datasets_query, tenant_domain, user_email)
        logger.info(f"[Observability] User {user_email} viewing own datasets - found {len(datasets_rows)} datasets")

    datasets = [
        {
            "id": row['id'],
            "name": row['name'],
            "created_by": row['created_by'],
            "creator_email": row['creator_email'],
            "creator_name": row['creator_name']
        }
        for row in datasets_rows
    ]

    return datasets


@router.post("/refresh")
async def refresh_materialized_views(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Manually refresh analytics materialized views.
    Admin-only endpoint.
    """
    from app.core.postgresql_client import get_postgresql_client

    await require_admin_role(current_user)

    pg_client = await get_postgresql_client()

    try:
        await pg_client.execute_query("SELECT refresh_analytics_views();")
        return {"success": True, "message": "Analytics views refreshed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh analytics views: {str(e)}"
        )
