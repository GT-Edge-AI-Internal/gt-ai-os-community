"""
Teams API endpoints for GT 2.0 Tenant Backend

Provides team collaboration management with two-tier permissions:
- Tier 1 (Team-level): 'read' or 'share' set by team owner
- Tier 2 (Resource-level): 'read' or 'edit' set by resource sharer

Follows GT 2.0 principles:
- Perfect tenant isolation
- Admin bypass for tenant admins
- Fail-fast error handling
- PostgreSQL-first storage
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List
import logging

from app.core.security import get_current_user
from app.services.team_service import TeamService
from app.api.auth import get_tenant_user_uuid_by_email
from app.models.collaboration_team import (
    TeamCreate,
    TeamUpdate,
    Team,
    TeamListResponse,
    TeamResponse,
    TeamWithMembers,
    TeamWithMembersResponse,
    AddMemberRequest,
    UpdateMemberPermissionRequest,
    MemberListResponse,
    MemberResponse,
    ShareResourceRequest,
    SharedResourcesResponse,
    SharedResource,
    TeamInvitation,
    InvitationListResponse,
    ObservableRequest,
    ObservableRequestListResponse,
    TeamActivityMetrics,
    TeamActivityResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teams", tags=["teams"])


async def get_team_service_for_user(current_user: Dict[str, Any]) -> TeamService:
    """Helper function to create TeamService with proper tenant UUID mapping"""
    user_email = current_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="User email not found in token")

    tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
    if not tenant_user_uuid:
        raise HTTPException(status_code=404, detail=f"User {user_email} not found in tenant system")

    return TeamService(
        tenant_domain=current_user.get('tenant_domain', 'test-company'),
        user_id=tenant_user_uuid,
        user_email=user_email
    )


# ============================================================================
# TEAM CRUD ENDPOINTS
# ============================================================================

@router.get("", response_model=TeamListResponse)
async def list_teams(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all teams where the current user is owner or member.
    Returns teams with member counts and permission flags.

    Permission flags:
    - is_owner: User created this team
    - can_manage: User can manage team (owner or admin/developer)
    """
    logger.info(f"Listing teams for user {current_user['sub']}")

    try:
        service = await get_team_service_for_user(current_user)
        teams = await service.get_user_teams()

        return TeamListResponse(
            data=teams,
            total=len(teams)
        )

    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    team_data: TeamCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new team with the current user as owner.

    The creator is automatically the team owner with full management permissions.
    """
    logger.info(f"Creating team '{team_data.name}' for user {current_user['sub']}")

    try:
        service = await get_team_service_for_user(current_user)
        team = await service.create_team(
            name=team_data.name,
            description=team_data.description or ""
        )

        return TeamResponse(data=team)

    except Exception as e:
        logger.error(f"Error creating team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# TEAM INVITATION ENDPOINTS (must come before /{team_id} routes)
# ==============================================================================

@router.get("/invitations", response_model=InvitationListResponse)
async def list_my_invitations(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get current user's pending team invitations.

    Returns list of invitations with team details and inviter information.
    """
    try:
        service = await get_team_service_for_user(current_user)
        invitations = await service.get_pending_invitations()

        return InvitationListResponse(
            data=invitations,
            total=len(invitations)
        )

    except Exception as e:
        logger.error(f"Error listing invitations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invitations/{invitation_id}/accept", response_model=MemberResponse)
async def accept_team_invitation(
    invitation_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Accept a team invitation.

    Updates the invitation status to 'accepted' and grants team membership.
    """
    try:
        service = await get_team_service_for_user(current_user)
        member = await service.accept_invitation(invitation_id)

        return MemberResponse(data=member)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invitations/{invitation_id}/decline", status_code=204)
async def decline_team_invitation(
    invitation_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Decline a team invitation.

    Removes the invitation from the system.
    """
    try:
        service = await get_team_service_for_user(current_user)
        await service.decline_invitation(invitation_id)

        return None

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error declining invitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/observable-requests", response_model=ObservableRequestListResponse)
async def get_observable_requests(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get pending Observable requests for the current user.

    Returns list of teams requesting Observable access.
    """
    try:
        service = await get_team_service_for_user(current_user)
        requests = await service.get_observable_requests()

        return ObservableRequestListResponse(
            data=[ObservableRequest(**req) for req in requests],
            total=len(requests)
        )

    except Exception as e:
        logger.error(f"Error getting Observable requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# TEAM CRUD ENDPOINTS (dynamic routes with {team_id})
# ==============================================================================

@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get team details by ID.

    Only accessible to team members or tenant admins.
    """
    logger.info(f"Getting team {team_id} for user {current_user['sub']}")

    try:
        service = await get_team_service_for_user(current_user)
        team = await service.get_team_by_id(team_id)

        if not team:
            raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

        return TeamResponse(data=team)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    updates: TeamUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update team name/description.

    Requires: Team ownership or admin/developer role
    """
    logger.info(f"Updating team {team_id} for user {current_user['sub']}")

    try:
        service = await get_team_service_for_user(current_user)

        # Convert Pydantic model to dict, excluding None values
        update_dict = updates.model_dump(exclude_none=True)

        team = await service.update_team(team_id, update_dict)

        if not team:
            raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

        return TeamResponse(data=team)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a team and all its memberships (CASCADE).

    Requires: Team ownership or admin/developer role
    """
    logger.info(f"Deleting team {team_id} for user {current_user['sub']}")

    try:
        service = await get_team_service_for_user(current_user)
        success = await service.delete_team(team_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

        return None  # 204 No Content

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TEAM MEMBER ENDPOINTS
# ============================================================================

@router.get("/{team_id}/members", response_model=MemberListResponse)
async def list_team_members(
    team_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all members of a team with their permissions.

    Only accessible to team members or tenant admins.

    Returns:
    - user_id, user_email, user_name
    - team_permission: 'read' or 'share'
    - resource_permissions: JSONB dict of resource-level permissions
    """
    logger.info(f"Listing members for team {team_id}")

    try:
        service = await get_team_service_for_user(current_user)
        members = await service.get_team_members(team_id)

        return MemberListResponse(
            data=members,
            total=len(members)
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing team members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{team_id}/members", response_model=MemberResponse, status_code=201)
async def add_team_member(
    team_id: str,
    member_data: AddMemberRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Add a user to the team with specified permission.

    Requires: Team ownership or admin/developer role

    Team Permissions:
    - 'read': Can access resources shared to this team
    - 'share': Can access resources AND share own resources to this team

    Note: Observability access is automatically requested when inviting users.
    The invited user can approve or decline the observability request separately.
    """
    logger.info(f"Adding member {member_data.user_email} to team {team_id}")

    try:
        service = await get_team_service_for_user(current_user)
        member = await service.add_member(
            team_id=team_id,
            user_email=member_data.user_email,
            team_permission=member_data.team_permission
        )

        return MemberResponse(data=member)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{team_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_permission(
    team_id: str,
    user_id: str,
    permission_data: UpdateMemberPermissionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update a team member's permission level.

    Requires: Team ownership or admin/developer role

    Note: DB trigger auto-clears resource_permissions when downgraded from 'share' to 'read'
    """
    logger.info(f"PUT /teams/{team_id}/members/{user_id} - Permission update request")
    logger.info(f"Request body: {permission_data.model_dump()}")
    logger.info(f"Current user: {current_user.get('email')}")

    try:
        service = await get_team_service_for_user(current_user)
        member = await service.update_member_permission(
            team_id=team_id,
            user_id=user_id,
            new_permission=permission_data.team_permission
        )

        return MemberResponse(data=member)

    except PermissionError as e:
        logger.error(f"PermissionError updating member permission: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        logger.error(f"ValueError updating member permission: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"RuntimeError updating member permission: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating member permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(
    team_id: str,
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Remove a user from the team.

    Requires: Team ownership or admin/developer role
    """
    logger.info(f"Removing member {user_id} from team {team_id}")

    try:
        service = await get_team_service_for_user(current_user)
        success = await service.remove_member(team_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Member {user_id} not found in team {team_id}")

        return None  # 204 No Content

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RESOURCE SHARING ENDPOINTS
# ============================================================================

@router.post("/{team_id}/share", status_code=201)
async def share_resource_to_team(
    team_id: str,
    share_data: ShareResourceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Share a resource (agent/dataset) to team with per-user permissions.

    Requires: Team ownership or 'share' team permission

    Request body:
    {
        "resource_type": "agent" | "dataset",
        "resource_id": "uuid",
        "user_permissions": {
            "user_uuid_1": "read",
            "user_uuid_2": "edit"
        }
    }

    Resource Permissions:
    - 'read': View-only access to resource
    - 'edit': Full edit access to resource
    """
    logger.info(f"Sharing {share_data.resource_type}:{share_data.resource_id} to team {team_id}")

    try:
        service = await get_team_service_for_user(current_user)

        # Use new junction table method (Phase 2)
        await service.share_resource_to_teams(
            resource_id=share_data.resource_id,
            resource_type=share_data.resource_type,
            shared_by=current_user["user_id"],
            team_shares=[{
                "team_id": team_id,
                "user_permissions": share_data.user_permissions
            }]
        )

        return {"message": "Resource shared successfully", "success": True}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sharing resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{team_id}/share/{resource_type}/{resource_id}", status_code=204)
async def unshare_resource_from_team(
    team_id: str,
    resource_type: str,
    resource_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Remove resource sharing from team (removes from all members' resource_permissions).

    Requires: Team ownership or 'share' team permission
    """
    logger.info(f"Unsharing {resource_type}:{resource_id} from team {team_id}")

    try:
        service = await get_team_service_for_user(current_user)

        # Use new junction table method (Phase 2)
        await service.unshare_resource_from_team(
            resource_id=resource_id,
            resource_type=resource_type,
            team_id=team_id
        )

        return None  # 204 No Content

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error unsharing resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{team_id}/resources", response_model=SharedResourcesResponse)
async def list_shared_resources(
    team_id: str,
    resource_type: str = Query(None, description="Filter by resource type: 'agent' or 'dataset'"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all resources shared to a team.

    Only accessible to team members or tenant admins.

    Returns list of:
    {
        "resource_type": "agent" | "dataset",
        "resource_id": "uuid",
        "user_permissions": {"user_id": "read|edit", ...}
    }
    """
    logger.info(f"Listing shared resources for team {team_id}")

    try:
        service = await get_team_service_for_user(current_user)
        resources = await service.get_shared_resources(
            team_id=team_id,
            resource_type=resource_type
        )

        return SharedResourcesResponse(
            data=resources,
            total=len(resources)
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing shared resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/{team_id}/invitations", response_model=InvitationListResponse)
async def list_team_invitations(
    team_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get pending invitations for a team (owner view).

    Shows all users who have been invited but haven't accepted yet.
    Requires team ownership or admin role.
    """
    try:
        service = await get_team_service_for_user(current_user)
        invitations = await service.get_team_pending_invitations(team_id)

        return InvitationListResponse(
            data=invitations,
            total=len(invitations)
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing team invitations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{team_id}/invitations/{invitation_id}", status_code=204)
async def cancel_team_invitation(
    team_id: str,
    invitation_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Cancel a pending invitation (owner only).

    Removes the invitation before the user accepts it.
    Requires team ownership or admin role.
    """
    try:
        service = await get_team_service_for_user(current_user)
        await service.cancel_invitation(team_id, invitation_id)

        return None

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error canceling invitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Observable Member Management Endpoints
# ============================================================================

@router.post("/{team_id}/members/{user_id}/request-observable", status_code=200)
async def request_observable_access(
    team_id: str,
    user_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Request Observable access from a team member.

    Sets Observable status to pending for the target user.
    Requires owner or manager permission.
    """
    try:
        service = await get_team_service_for_user(current_user)
        result = await service.request_observable_status(team_id, user_id)

        return {"success": True, "data": result}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error requesting Observable access: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{team_id}/observable/approve", status_code=200)
async def approve_observable_request(
    team_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Approve Observable status for current user in a team.

    User explicitly consents to team managers viewing their activity.
    """
    try:
        service = await get_team_service_for_user(current_user)
        result = await service.approve_observable_consent(team_id)

        return {"success": True, "data": result}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error approving Observable request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{team_id}/observable", status_code=200)
async def revoke_observable_status(
    team_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Revoke Observable status for current user in a team.

    Immediately removes manager access to user's activity data.
    """
    try:
        service = await get_team_service_for_user(current_user)
        result = await service.revoke_observable_status(team_id)

        return {"success": True, "data": result}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error revoking Observable status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{team_id}/activity", response_model=TeamActivityResponse)
async def get_team_activity(
    team_id: str,
    days: int = Query(7, ge=1, le=365, description="Number of days to include in metrics"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get team activity metrics for Observable members.

    Returns aggregated activity data for team members who have approved Observable status.
    Requires owner or manager permission.

    Args:
        team_id: Team UUID
        days: Number of days to include (1-365, default 7)
    """
    try:
        service = await get_team_service_for_user(current_user)
        activity = await service.get_team_activity(team_id, days)

        return TeamActivityResponse(
            data=TeamActivityMetrics(**activity)
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting team activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))
