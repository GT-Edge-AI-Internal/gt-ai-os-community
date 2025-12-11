import json
import uuid
from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client
from app.core.permissions import get_user_role, is_effective_owner
import logging

logger = logging.getLogger(__name__)

# Import for event logging
EVENT_LOGGING_AVAILABLE = False
try:
    from app.services.event_service import EventType
    EVENT_LOGGING_AVAILABLE = True
except ImportError:
    logger.warning("EventService not available - team events will not be logged")

class TeamService:
    """GT 2.0 Team Collaboration Service with Perfect Tenant Isolation"""

    def __init__(self, tenant_domain: str, user_id: str, user_email: str = None):
        """Initialize with tenant and user isolation using PostgreSQL storage"""
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.user_email = user_email or user_id  # Fallback to user_id if no email provided
        self.settings = get_settings()

        logger.info(f"Team service initialized for {tenant_domain}/{user_id} (email: {self.user_email})")

    async def _get_user_id(self, pg_client, user_identifier: Optional[str] = None) -> str:
        """
        Get user UUID from email/username/uuid with tenant isolation.
        Follows AgentService pattern for flexible user lookup.
        """
        identifier = user_identifier or self.user_email

        user_lookup_query = """
            SELECT id FROM users
            WHERE (LOWER(email) = LOWER($1) OR id::text = $1 OR LOWER(username) = LOWER($1))
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            LIMIT 1
        """

        user_id = await pg_client.fetch_scalar(user_lookup_query, identifier, self.tenant_domain)
        if not user_id and user_identifier is None:
            # Only fallback to self.user_id when looking up current user (no identifier provided)
            user_id = await pg_client.fetch_scalar(user_lookup_query, self.user_id, self.tenant_domain)

        if not user_id:
            raise RuntimeError(f"User not found: {identifier} in tenant {self.tenant_domain}")

        logger.info(f"Found user ID: {user_id} for identifier: {identifier}")
        return str(user_id)

    async def is_team_owner(self, team_id: str, user_id: str) -> bool:
        """Check if user is the team owner"""
        pg_client = await get_postgresql_client()

        query = """
            SELECT owner_id FROM teams
            WHERE id = $1::uuid
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        """

        owner_id = await pg_client.fetch_scalar(query, team_id, self.tenant_domain)
        return str(owner_id) == str(user_id) if owner_id else False

    async def can_manage_team(self, team_id: str, user_id: str) -> bool:
        """
        Check if user can manage team (owner, manager, or admin/developer).
        Follows GT 2.0 pattern of admin bypass.
        """
        pg_client = await get_postgresql_client()

        # Check if admin/developer (can manage all teams)
        user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
        if user_role in ["admin", "developer"]:
            logger.info(f"User {user_id} has admin/developer role, can manage all teams")
            return True

        # Check if team owner
        if await self.is_team_owner(team_id, user_id):
            return True

        # Check if user has manager permission
        query = """
            SELECT team_permission
            FROM team_memberships
            WHERE team_id = $1 AND user_id = $2 AND status = 'accepted'
        """
        membership = await pg_client.fetch_one(query, UUID(team_id), UUID(user_id))
        if membership and membership["team_permission"] == "manager":
            logger.info(f"User {user_id} has manager permission for team {team_id}")
            return True

        return False

    async def can_share_to_team(self, team_id: str, user_id: str) -> bool:
        """
        Check if user can share resources to team.
        Requires 'share' or 'manager' team_permission, team ownership, or admin/developer role.
        """
        pg_client = await get_postgresql_client()

        # Admin/developer bypass
        user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
        if user_role in ["admin", "developer"]:
            return True

        # Team owner can always share
        if await self.is_team_owner(team_id, user_id):
            return True

        # Check team membership with 'share' or 'manager' permission
        query = """
            SELECT team_permission FROM team_memberships
            WHERE team_id = $1::uuid
              AND user_id = $2::uuid
        """

        permission = await pg_client.fetch_scalar(query, team_id, user_id)
        return permission in ['share', 'manager']

    async def create_team(
        self,
        name: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a new team with the current user as owner"""
        try:
            pg_client = await get_postgresql_client()

            # Validate user exists
            user_id = await self._get_user_id(pg_client)

            # Generate team ID
            team_id = str(uuid.uuid4())

            # Create team in PostgreSQL
            query = """
                INSERT INTO teams (
                    id, name, description, tenant_id, owner_id, created_at, updated_at
                ) VALUES (
                    $1::uuid, $2, $3,
                    (SELECT id FROM tenants WHERE domain = $4 LIMIT 1),
                    $5::uuid, NOW(), NOW()
                )
                RETURNING id, name, description, tenant_id, owner_id, created_at, updated_at
            """

            team_data = await pg_client.fetch_one(
                query,
                team_id, name, description, self.tenant_domain, user_id
            )

            if not team_data:
                raise RuntimeError("Failed to create team")

            logger.info(f"Created team {team_id}: {name} for user {user_id}")

            return {
                "id": str(team_data["id"]),
                "name": team_data["name"],
                "description": team_data["description"],
                "tenant_id": str(team_data["tenant_id"]),
                "owner_id": str(team_data["owner_id"]),
                "is_owner": True,
                "can_manage": True,
                "member_count": 0,  # No members yet besides owner
                "shared_resource_count": 0,  # No shared resources yet
                "created_at": team_data["created_at"].isoformat() if team_data["created_at"] else None,
                "updated_at": team_data["updated_at"].isoformat() if team_data["updated_at"] else None
            }

        except Exception as e:
            logger.error(f"Error creating team: {e}")
            raise

    async def get_user_teams(self) -> List[Dict[str, Any]]:
        """
        Get all teams where user is owner or member.
        Returns teams with member counts and permission flags.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get user ID
            user_id = await self._get_user_id(pg_client)

            # Get user role for admin bypass
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Query teams - admins see all teams, regular users see only teams they own or are members of
            if is_admin:
                query = """
                    SELECT DISTINCT
                        t.id, t.name, t.description, t.tenant_id, t.owner_id,
                        t.created_at, t.updated_at,
                        u.full_name as owner_name,
                        u.email as owner_email,
                        tm_current.team_permission as user_permission,
                        COUNT(DISTINCT CASE WHEN tm.status = 'accepted' THEN tm.user_id END) as member_count,
                        COUNT(DISTINCT trs.resource_id) as shared_resource_count
                    FROM teams t
                    LEFT JOIN users u ON t.owner_id = u.id
                    LEFT JOIN team_memberships tm ON t.id = tm.team_id
                    LEFT JOIN team_memberships tm_current ON t.id = tm_current.team_id
                        AND tm_current.user_id = $2::uuid
                    LEFT JOIN team_resource_shares trs ON t.id = trs.team_id
                    WHERE t.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                    GROUP BY t.id, t.name, t.description, t.tenant_id, t.owner_id,
                             t.created_at, t.updated_at, u.full_name, u.email, tm_current.team_permission
                    ORDER BY t.updated_at DESC
                """
            else:
                query = """
                    SELECT DISTINCT
                        t.id, t.name, t.description, t.tenant_id, t.owner_id,
                        t.created_at, t.updated_at,
                        u.full_name as owner_name,
                        u.email as owner_email,
                        tm_current.team_permission as user_permission,
                        COUNT(DISTINCT CASE WHEN tm.status = 'accepted' THEN tm.user_id END) as member_count,
                        COUNT(DISTINCT trs.resource_id) as shared_resource_count
                    FROM teams t
                    LEFT JOIN users u ON t.owner_id = u.id
                    LEFT JOIN team_memberships tm ON t.id = tm.team_id
                    LEFT JOIN team_memberships tm_current ON t.id = tm_current.team_id
                        AND tm_current.user_id = $2::uuid
                    LEFT JOIN team_resource_shares trs ON t.id = trs.team_id
                    WHERE t.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                      AND (t.owner_id = $2::uuid OR EXISTS (
                          SELECT 1 FROM team_memberships tm2
                          WHERE tm2.team_id = t.id AND tm2.user_id = $2::uuid
                          AND tm2.status = 'accepted'
                      ))
                    GROUP BY t.id, t.name, t.description, t.tenant_id, t.owner_id,
                             t.created_at, t.updated_at, u.full_name, u.email, tm_current.team_permission
                    ORDER BY t.updated_at DESC
                """

            teams_data = await pg_client.execute_query(query, self.tenant_domain, user_id)

            # Format teams with permission flags
            teams = []
            for team in teams_data:
                is_owner = str(team["owner_id"]) == str(user_id)
                can_manage = is_admin or is_owner

                teams.append({
                    "id": str(team["id"]),
                    "name": team["name"],
                    "description": team["description"],
                    "tenant_id": str(team["tenant_id"]),
                    "owner_id": str(team["owner_id"]),
                    "owner_name": team.get("owner_name", "Unknown"),
                    "owner_email": team.get("owner_email"),
                    "is_owner": is_owner,
                    "can_manage": can_manage,
                    "user_permission": team.get("user_permission"),  # None if owner (not in team_memberships)
                    "member_count": int(team["member_count"]) if team.get("member_count") else 0,
                    "shared_resource_count": int(team["shared_resource_count"]) if team.get("shared_resource_count") else 0,
                    "created_at": team["created_at"].isoformat() if team["created_at"] else None,
                    "updated_at": team["updated_at"].isoformat() if team["updated_at"] else None
                })

            logger.info(f"Retrieved {len(teams)} teams for user {user_id}")
            return teams

        except Exception as e:
            logger.error(f"Error getting user teams: {e}")
            return []

    async def get_team_by_id(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific team by ID with member details"""
        try:
            pg_client = await get_postgresql_client()

            # Get user ID
            user_id = await self._get_user_id(pg_client)

            # Query team with owner info
            query = """
                SELECT
                    t.id, t.name, t.description, t.tenant_id, t.owner_id,
                    t.created_at, t.updated_at,
                    u.full_name as owner_name,
                    u.email as owner_email
                FROM teams t
                LEFT JOIN users u ON t.owner_id = u.id
                WHERE t.id = $1::uuid
                  AND t.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            """

            team_data = await pg_client.fetch_one(query, team_id, self.tenant_domain)

            if not team_data:
                logger.warning(f"Team {team_id} not found in tenant {self.tenant_domain}")
                return None

            # Get user role for admin bypass
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            is_owner = str(team_data["owner_id"]) == str(user_id)
            can_manage = is_admin or is_owner

            # Get member count (only accepted members)
            member_count_query = """
                SELECT COUNT(*) FROM team_memberships
                WHERE team_id = $1::uuid AND status = 'accepted'
            """
            member_count = await pg_client.fetch_scalar(member_count_query, team_id) or 0

            # Get shared resource count
            shared_resource_count_query = """
                SELECT COUNT(DISTINCT resource_id) FROM team_resource_shares
                WHERE team_id = $1::uuid
            """
            shared_resource_count = await pg_client.fetch_scalar(shared_resource_count_query, team_id) or 0

            return {
                "id": str(team_data["id"]),
                "name": team_data["name"],
                "description": team_data["description"],
                "tenant_id": str(team_data["tenant_id"]),
                "owner_id": str(team_data["owner_id"]),
                "owner_name": team_data.get("owner_name", "Unknown"),
                "owner_email": team_data.get("owner_email"),
                "is_owner": is_owner,
                "can_manage": can_manage,
                "member_count": int(member_count),
                "shared_resource_count": int(shared_resource_count),
                "created_at": team_data["created_at"].isoformat() if team_data["created_at"] else None,
                "updated_at": team_data["updated_at"].isoformat() if team_data["updated_at"] else None
            }

        except Exception as e:
            logger.error(f"Error getting team {team_id}: {e}")
            return None

    async def update_team(
        self,
        team_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update team name/description.
        Requires team ownership (managers cannot update team details).
        Admin/developer roles can also update.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user is admin/developer (they can update any team)
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Check if user is team owner
            is_owner = await self.is_team_owner(team_id, user_id)

            # Only owners and admins can update team details
            if not is_owner and not is_admin:
                raise PermissionError("Only team owners can update team details")

            # Build UPDATE query dynamically
            allowed_fields = ["name", "description"]
            update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

            if not update_fields:
                logger.warning("No valid fields to update")
                return await self.get_team_by_id(team_id)

            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(update_fields.keys())])
            values = list(update_fields.values()) + [team_id, self.tenant_domain]

            query = f"""
                UPDATE teams
                SET {set_clause}, updated_at = NOW()
                WHERE id = ${len(update_fields)+1}::uuid
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = ${len(update_fields)+2} LIMIT 1)
                RETURNING id
            """

            result = await pg_client.fetch_one(query, *values)

            if not result:
                raise RuntimeError(f"Failed to update team {team_id}")

            logger.info(f"Updated team {team_id}: {update_fields}")

            # Return updated team
            return await self.get_team_by_id(team_id)

        except Exception as e:
            logger.error(f"Error updating team {team_id}: {e}")
            raise

    async def delete_team(self, team_id: str) -> bool:
        """
        Delete a team and all its memberships (CASCADE).
        Requires team ownership or admin/developer role.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get user ID
            user_id = await self._get_user_id(pg_client)

            # Check permission
            if not await self.can_manage_team(team_id, user_id):
                raise PermissionError(f"User {user_id} cannot delete team {team_id}")

            # Delete team (CASCADE will delete team_memberships)
            query = """
                DELETE FROM teams
                WHERE id = $1::uuid
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                RETURNING id
            """

            result = await pg_client.fetch_one(query, team_id, self.tenant_domain)

            if not result:
                logger.warning(f"Team {team_id} not found or already deleted")
                return False

            logger.info(f"Deleted team {team_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting team {team_id}: {e}")
            raise

    async def add_member(
        self,
        team_id: str,
        user_email: str,
        team_permission: str = "read"
    ) -> Dict[str, Any]:
        """
        Add a user to the team with specified permission.
        Requires team ownership or admin/developer role.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            current_user_id = await self._get_user_id(pg_client)

            # Check permission to manage team
            if not await self.can_manage_team(team_id, current_user_id):
                raise PermissionError(f"User {current_user_id} cannot manage team {team_id}")

            # Get target user ID
            target_user_id = await self._get_user_id(pg_client, user_email)

            # Check if trying to invite the team owner
            team_query = "SELECT owner_id FROM teams WHERE id = $1::uuid"
            team_data = await pg_client.fetch_one(team_query, team_id)
            if not team_data:
                raise ValueError(f"Team {team_id} not found")

            if str(team_data["owner_id"]) == str(target_user_id):
                raise ValueError("Cannot invite the team owner - they are already a member")

            # Validate team_permission
            if team_permission not in ["read", "share", "manager"]:
                raise ValueError(f"Invalid team_permission: {team_permission}. Must be 'read', 'share', or 'manager'")

            # Insert team membership with pending status (invitation)
            # Automatically request observability for all invitations
            query = """
                INSERT INTO team_memberships (
                    id, team_id, user_id, team_permission, resource_permissions,
                    status, invited_at, is_observable, observable_consent_status,
                    created_at, updated_at
                ) VALUES (
                    $1::uuid, $2::uuid, $3::uuid, $4, '{}'::jsonb,
                    'pending', NOW(), true, 'pending',
                    NOW(), NOW()
                )
                ON CONFLICT (team_id, user_id) DO UPDATE
                SET team_permission = EXCLUDED.team_permission,
                    status = 'pending',
                    invited_at = NOW(),
                    is_observable = true,
                    observable_consent_status = 'pending',
                    updated_at = NOW()
                RETURNING id, team_id, user_id, team_permission, resource_permissions,
                          status, invited_at, responded_at, is_observable,
                          observable_consent_status, created_at, updated_at
            """

            member_id = str(uuid.uuid4())
            member_data = await pg_client.fetch_one(
                query,
                member_id, team_id, target_user_id, team_permission
            )

            if not member_data:
                raise RuntimeError(f"Failed to send invitation to {user_email} for team {team_id}")

            # Get user details for response
            user_query = """
                SELECT email, full_name FROM users WHERE id = $1::uuid
            """
            user_data = await pg_client.fetch_one(user_query, target_user_id)

            logger.info(f"Sent invitation to {user_email} for team {team_id} with permission {team_permission}")

            # Log events for invitation creation and observability request
            if EVENT_LOGGING_AVAILABLE:
                try:
                    # Get tenant_id for event logging
                    tenant_query = "SELECT id FROM tenants WHERE domain = $1 LIMIT 1"
                    tenant_data = await pg_client.fetch_one(tenant_query, self.tenant_domain)
                    tenant_id = str(tenant_data["id"]) if tenant_data else None

                    if tenant_id:
                        # Import dynamically to avoid circular dependency
                        from app.services.event_service import get_event_service
                        event_service = await get_event_service()

                        # Log team invitation created event
                        await event_service.emit_event(
                            event_type=EventType.TEAM_INVITATION_CREATED,
                            user_id=current_user_id,
                            tenant_id=tenant_id,
                            data={
                                "team_id": team_id,
                                "invited_user_id": target_user_id,
                                "invited_user_email": user_email,
                                "team_permission": team_permission,
                                "invitation_id": str(member_data["id"])
                            },
                            metadata={"inviter_id": current_user_id}
                        )

                        # Log observability request event
                        await event_service.emit_event(
                            event_type=EventType.TEAM_OBSERVABLE_REQUESTED,
                            user_id=target_user_id,  # Target user receives the request
                            tenant_id=tenant_id,
                            data={
                                "team_id": team_id,
                                "requested_by_user_id": current_user_id,
                                "invitation_id": str(member_data["id"])
                            },
                            metadata={"requested_by": current_user_id}
                        )

                        logger.info(f"Logged team events for invitation {member_data['id']}")
                except Exception as e:
                    # Don't fail the invitation if event logging fails
                    logger.warning(f"Failed to log team events: {e}")

            # Parse JSONB resource_permissions to dict
            resource_perms = member_data["resource_permissions"]
            if isinstance(resource_perms, str):
                resource_perms = json.loads(resource_perms)
            elif resource_perms is None:
                resource_perms = {}

            return {
                "id": str(member_data["id"]),
                "team_id": str(member_data["team_id"]),
                "user_id": str(member_data["user_id"]),
                "user_email": user_data["email"] if user_data else user_email,
                "user_name": user_data["full_name"] if user_data else "Unknown",
                "team_permission": member_data["team_permission"],
                "resource_permissions": resource_perms,
                "is_observable": member_data.get("is_observable", False),
                "observable_consent_status": member_data.get("observable_consent_status", "none"),
                "status": member_data["status"],
                "invited_at": member_data["invited_at"].isoformat() if member_data["invited_at"] else None,
                "responded_at": member_data["responded_at"].isoformat() if member_data["responded_at"] else None,
                "created_at": member_data["created_at"].isoformat() if member_data["created_at"] else None,
                "updated_at": member_data["updated_at"].isoformat() if member_data["updated_at"] else None
            }

        except Exception as e:
            logger.error(f"Error adding member to team {team_id}: {e}")
            raise

    async def update_member_permission(
        self,
        team_id: str,
        user_id: str,
        new_permission: str
    ) -> Dict[str, Any]:
        """
        Update a team member's permission level.
        Requires team ownership or admin/developer role.
        Note: DB trigger will auto-clear resource_permissions if downgraded from 'share' to 'read'
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            current_user_id = await self._get_user_id(pg_client)

            # Check permission to manage team
            if not await self.can_manage_team(team_id, current_user_id):
                raise PermissionError(f"User {current_user_id} cannot manage team {team_id}")

            # Validate new_permission
            if new_permission not in ["read", "share", "manager"]:
                raise ValueError(f"Invalid permission: {new_permission}. Must be 'read', 'share', or 'manager'")

            # Check if current user is team owner
            is_owner = await self.is_team_owner(team_id, current_user_id)

            # Get target member's current permission
            member_query = """
                SELECT team_permission FROM team_memberships
                WHERE team_id = $1::uuid AND user_id = $2::uuid
            """
            member_data = await pg_client.fetch_one(member_query, team_id, user_id)
            if not member_data:
                raise RuntimeError(f"Member {user_id} not found in team {team_id}")

            current_permission = member_data["team_permission"]

            # Manager restrictions:
            # - Only owners can promote to/from manager
            # - Managers cannot change their own permission
            # - Managers cannot change other managers' permissions
            if not is_owner:
                # Prevent managers from promoting to manager
                if new_permission == "manager":
                    raise PermissionError("Only team owners can promote members to manager")

                # Prevent managers from demoting other managers
                if current_permission == "manager":
                    raise PermissionError("Only team owners can demote managers")

                # Prevent managers from changing their own permission
                if str(user_id) == str(current_user_id):
                    raise PermissionError("Managers cannot change their own permission")

            # Update team membership
            # Note: DB trigger 'trigger_auto_unshare' will automatically clear resource_permissions
            # if downgrading from 'share' to 'read'
            query = """
                UPDATE team_memberships
                SET team_permission = $1, updated_at = NOW()
                WHERE team_id = $2::uuid AND user_id = $3::uuid
                RETURNING id, team_id, user_id, team_permission, resource_permissions,
                          status, invited_at, responded_at, is_observable,
                          observable_consent_status, observable_consent_at,
                          created_at, updated_at
            """

            member_data = await pg_client.fetch_one(query, new_permission, team_id, user_id)

            if not member_data:
                raise RuntimeError(f"Member {user_id} not found in team {team_id}")

            # Get user details
            user_query = """
                SELECT email, full_name FROM users WHERE id = $1::uuid
            """
            user_data = await pg_client.fetch_one(user_query, user_id)

            logger.info(f"Updated member {user_id} permission to {new_permission} in team {team_id}")

            # Parse JSONB resource_permissions
            resource_perms = member_data["resource_permissions"]
            if isinstance(resource_perms, str):
                resource_perms = json.loads(resource_perms)
            elif resource_perms is None:
                resource_perms = {}

            return {
                "id": str(member_data["id"]),
                "team_id": str(member_data["team_id"]),
                "user_id": str(member_data["user_id"]),
                "user_email": user_data["email"] if user_data else "Unknown",
                "user_name": user_data["full_name"] if user_data else "Unknown",
                "team_permission": member_data["team_permission"],
                "resource_permissions": resource_perms,
                "is_owner": False,  # Members being updated are never owners
                "is_observable": member_data.get("is_observable", False),
                "observable_consent_status": member_data.get("observable_consent_status", "none"),
                "observable_consent_at": member_data["observable_consent_at"].isoformat() if member_data.get("observable_consent_at") else None,
                "status": member_data.get("status", "accepted"),
                "invited_at": member_data["invited_at"].isoformat() if member_data.get("invited_at") else None,
                "responded_at": member_data["responded_at"].isoformat() if member_data.get("responded_at") else None,
                "joined_at": member_data["responded_at"].isoformat() if (member_data.get("status") == "accepted" and member_data.get("responded_at")) else None,
                "created_at": member_data["created_at"].isoformat() if member_data.get("created_at") else None,
                "updated_at": member_data["updated_at"].isoformat() if member_data.get("updated_at") else None
            }

        except Exception as e:
            logger.error(f"Error updating member permission in team {team_id}: {e}")
            raise

    async def remove_member(self, team_id: str, user_id: str) -> bool:
        """
        Remove a user from the team.
        Allows self-removal (users can leave teams they're members of).
        Team owners cannot remove themselves - they must delete the team or transfer ownership.
        Admins can remove any member.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            current_user_id = await self._get_user_id(pg_client)

            # Get target user ID (normalize to UUID format for accurate comparison)
            target_user_id = await self._get_user_id(pg_client, user_id)

            # Check if user is removing themselves (self-removal / leaving team)
            is_self_removal = str(current_user_id) == str(target_user_id)

            if is_self_removal:
                # Check if user is the team owner
                team_query = """
                    SELECT owner_id FROM teams WHERE id = $1::uuid
                """
                team_data = await pg_client.fetch_one(team_query, team_id)

                if team_data and str(team_data['owner_id']) == str(current_user_id):
                    raise PermissionError("Team owners cannot leave their own team. Delete the team or transfer ownership first.")

                # Allow self-removal for non-owners
                logger.info(f"User {current_user_id} is leaving team {team_id}")
            else:
                # Removing another user - check permission to manage team
                if not await self.can_manage_team(team_id, current_user_id):
                    raise PermissionError(f"User {current_user_id} cannot manage team {team_id}")

                # Check if current user is team owner
                is_owner = await self.is_team_owner(team_id, current_user_id)

                # Get target member's current permission
                member_query = """
                    SELECT team_permission FROM team_memberships
                    WHERE team_id = $1::uuid AND user_id = $2::uuid
                """
                member_data = await pg_client.fetch_one(member_query, team_id, target_user_id)

                # Manager restrictions: Only owners can remove other managers
                if not is_owner and member_data and member_data["team_permission"] == "manager":
                    raise PermissionError("Only team owners can remove managers")

            # Delete team membership
            query = """
                DELETE FROM team_memberships
                WHERE team_id = $1::uuid AND user_id = $2::uuid
                RETURNING id
            """

            result = await pg_client.fetch_one(query, team_id, target_user_id)

            if not result:
                logger.warning(f"Member {target_user_id} not found in team {team_id}")
                return False

            logger.info(f"Removed member {target_user_id} from team {team_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing member from team {team_id}: {e}")
            raise

    # ==============================================================================
    # INVITATION MANAGEMENT METHODS
    # ==============================================================================

    async def get_pending_invitations(self) -> List[Dict[str, Any]]:
        """
        Get current user's pending team invitations.
        Returns invitations with team and owner details.

        IMPORTANT: This method returns ONLY invitations for the specific user,
        with NO admin bypass. Invitations are personal and should not be visible
        to admins or other users.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID - NO admin bypass, use the actual logged-in user
            user_id = await self._get_user_id(pg_client)

            logger.info(f"Fetching pending invitations for user_id={user_id}, user_email={self.user_email}")

            # Query pending invitations - filtered strictly by user_id
            query = """
                SELECT
                    tm.id, tm.team_id, tm.team_permission, tm.invited_at,
                    t.name as team_name, t.description as team_description,
                    u.full_name as owner_name, u.email as owner_email
                FROM team_memberships tm
                JOIN teams t ON tm.team_id = t.id
                JOIN users u ON t.owner_id = u.id
                WHERE tm.user_id = $1::uuid
                  AND tm.status = 'pending'
                ORDER BY tm.invited_at DESC
            """

            invitations_data = await pg_client.execute_query(query, user_id)

            invitations = []
            for inv in invitations_data:
                invitations.append({
                    "id": str(inv["id"]),
                    "team_id": str(inv["team_id"]),
                    "team_name": inv["team_name"],
                    "team_description": inv.get("team_description"),
                    "owner_name": inv["owner_name"],
                    "owner_email": inv["owner_email"],
                    "team_permission": inv["team_permission"],
                    "invited_at": inv["invited_at"].isoformat() if inv["invited_at"] else None
                })

            logger.info(f"Retrieved {len(invitations)} pending invitations for user {user_id} (email: {self.user_email})")
            return invitations

        except Exception as e:
            logger.error(f"Error getting pending invitations: {e}")
            return []

    async def accept_invitation(self, invitation_id: str) -> Dict[str, Any]:
        """
        Accept a team invitation.
        Updates status to 'accepted' and sets responded_at timestamp.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # DIAGNOSTIC: Check invitation state before attempting update
            check_query = """
                SELECT id, user_id, status, team_id
                FROM team_memberships
                WHERE id = $1::uuid
            """
            existing = await pg_client.fetch_one(check_query, invitation_id)

            logger.info(f"🔍 Accept invitation attempt: invitation_id={invitation_id}, current_user_id={user_id}")

            if not existing:
                logger.error(f"❌ Invitation {invitation_id} does not exist in database")
                raise ValueError(f"Invitation {invitation_id} not found")

            logger.info(f"📋 Existing invitation: user_id={existing['user_id']}, status={existing['status']}, team_id={existing['team_id']}")

            if str(existing['user_id']) != str(user_id):
                logger.error(f"❌ User mismatch: invitation is for {existing['user_id']}, but current user is {user_id}")
                raise ValueError(f"Invitation {invitation_id} belongs to a different user")

            if existing['status'] != 'pending':
                logger.error(f"❌ Status mismatch: invitation status is '{existing['status']}', expected 'pending'")
                raise ValueError(f"Invitation {invitation_id} has already been {existing['status']}")

            # Update invitation status
            query = """
                UPDATE team_memberships
                SET status = 'accepted', responded_at = NOW(), updated_at = NOW()
                WHERE id = $1::uuid
                  AND user_id = $2::uuid
                  AND status = 'pending'
                RETURNING id, team_id, user_id, team_permission, resource_permissions,
                          status, invited_at, responded_at, created_at, updated_at,
                          is_observable, observable_consent_status, observable_consent_at
            """

            membership_data = await pg_client.fetch_one(query, invitation_id, user_id)

            if not membership_data:
                logger.error(f"❌ UPDATE returned no rows despite checks passing - race condition?")
                raise ValueError(f"Invitation {invitation_id} could not be accepted - please try again")

            # Get user details for response
            user_query = """
                SELECT email, full_name FROM users WHERE id = $1::uuid
            """
            user_data = await pg_client.fetch_one(user_query, user_id)

            logger.info(f"User {user_id} accepted invitation {invitation_id}")

            # Auto-grant read access to all resources already shared to this team
            team_id = membership_data["team_id"]
            grant_query = """
                SELECT resource_type, resource_id
                FROM team_resource_shares
                WHERE team_id = $1::uuid
            """
            shared_resources = await pg_client.execute_query(grant_query, team_id)

            if shared_resources and len(shared_resources) > 0:
                logger.info(f"Auto-granting read access to {len(shared_resources)} pre-shared resources for user {user_id}")

                # Build resource_permissions dict with read access for all pre-shared resources
                auto_permissions = {}
                for resource in shared_resources:
                    resource_key = f"{resource['resource_type']}:{resource['resource_id']}"
                    auto_permissions[resource_key] = 'read'

                # Update the user's resource_permissions JSONB field
                update_perms_query = """
                    UPDATE team_memberships
                    SET resource_permissions = $1::jsonb, updated_at = NOW()
                    WHERE id = $2::uuid
                """
                import json
                await pg_client.execute_query(update_perms_query, json.dumps(auto_permissions), invitation_id)

                logger.info(f"✅ Granted read access to {len(auto_permissions)} resources for new team member")

            # Parse JSONB resource_permissions to dict (same pattern as add_member)
            # Re-fetch to get the updated resource_permissions
            refetch_query = """
                SELECT resource_permissions FROM team_memberships WHERE id = $1::uuid
            """
            refetch_data = await pg_client.fetch_one(refetch_query, invitation_id)
            resource_perms = refetch_data["resource_permissions"] if refetch_data else membership_data["resource_permissions"]
            if isinstance(resource_perms, str):
                import json
                resource_perms = json.loads(resource_perms)
            elif resource_perms is None:
                resource_perms = {}

            return {
                "id": str(membership_data["id"]),
                "team_id": str(membership_data["team_id"]),
                "user_id": str(membership_data["user_id"]),
                "user_email": user_data["email"] if user_data else "Unknown",
                "user_name": user_data["full_name"] if user_data else "Unknown",
                "team_permission": membership_data["team_permission"],
                "resource_permissions": resource_perms,
                "status": membership_data["status"],
                "invited_at": membership_data["invited_at"].isoformat() if membership_data["invited_at"] else None,
                "responded_at": membership_data["responded_at"].isoformat() if membership_data["responded_at"] else None,
                "created_at": membership_data["created_at"].isoformat() if membership_data["created_at"] else None,
                "updated_at": membership_data["updated_at"].isoformat() if membership_data["updated_at"] else None,
                # Observable fields (required by TeamMember schema)
                "is_observable": membership_data.get("is_observable", False),
                "observable_consent_status": membership_data.get("observable_consent_status", "none"),
                "observable_consent_at": membership_data["observable_consent_at"].isoformat() if membership_data.get("observable_consent_at") else None
            }

        except Exception as e:
            logger.error(f"Error accepting invitation {invitation_id}: {e}")
            raise

    async def decline_invitation(self, invitation_id: str) -> None:
        """
        Decline a team invitation.
        Deletes the invitation record.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Delete invitation
            query = """
                DELETE FROM team_memberships
                WHERE id = $1::uuid
                  AND user_id = $2::uuid
                  AND status = 'pending'
                RETURNING id
            """

            result = await pg_client.fetch_one(query, invitation_id, user_id)

            if not result:
                raise ValueError(f"Invitation {invitation_id} not found or already processed")

            logger.info(f"User {user_id} declined invitation {invitation_id}")

        except Exception as e:
            logger.error(f"Error declining invitation {invitation_id}: {e}")
            raise

    async def cancel_invitation(self, team_id: str, invitation_id: str) -> None:
        """
        Cancel a pending invitation (team owner only).
        Deletes the invitation record.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            current_user_id = await self._get_user_id(pg_client)

            # Check permission to manage team
            if not await self.can_manage_team(team_id, current_user_id):
                raise PermissionError(f"User {current_user_id} cannot manage team {team_id}")

            # Delete invitation
            query = """
                DELETE FROM team_memberships
                WHERE id = $1::uuid
                  AND team_id = $2::uuid
                  AND status = 'pending'
                RETURNING id
            """

            result = await pg_client.fetch_one(query, invitation_id, team_id)

            if not result:
                raise ValueError(f"Invitation {invitation_id} not found or already processed")

            logger.info(f"Team owner {current_user_id} canceled invitation {invitation_id}")

        except Exception as e:
            logger.error(f"Error canceling invitation {invitation_id}: {e}")
            raise

    async def get_team_pending_invitations(self, team_id: str) -> List[Dict[str, Any]]:
        """
        Get pending invitations for a team (owner view).
        Shows invited users who haven't accepted yet.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            current_user_id = await self._get_user_id(pg_client)

            # Check permission to manage team
            if not await self.can_manage_team(team_id, current_user_id):
                raise PermissionError(f"User {current_user_id} cannot view team {team_id} invitations")

            # Query pending invitations
            query = """
                SELECT
                    tm.id, tm.team_id, tm.user_id, tm.team_permission, tm.invited_at,
                    u.email, u.full_name
                FROM team_memberships tm
                JOIN users u ON tm.user_id = u.id
                WHERE tm.team_id = $1::uuid
                  AND tm.status = 'pending'
                ORDER BY tm.invited_at DESC
            """

            invitations_data = await pg_client.execute_query(query, team_id)

            invitations = []
            for inv in invitations_data:
                invitations.append({
                    "id": str(inv["id"]),
                    "team_id": str(inv["team_id"]),
                    "user_id": str(inv["user_id"]),
                    "user_email": inv["email"],
                    "user_name": inv["full_name"],
                    "team_permission": inv["team_permission"],
                    "invited_at": inv["invited_at"].isoformat() if inv["invited_at"] else None
                })

            logger.info(f"Retrieved {len(invitations)} pending invitations for team {team_id}")
            return invitations

        except Exception as e:
            logger.error(f"Error getting team pending invitations: {e}")
            return []

    async def get_team_members(self, team_id: str) -> List[Dict[str, Any]]:
        """
        Get all members of a team with their permissions.
        Only accessible to team members or admins.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user can view team (member or admin)
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            if not is_admin:
                # Check if user is owner or member
                check_query = """
                    SELECT 1 FROM teams t
                    LEFT JOIN team_memberships tm ON t.id = tm.team_id
                    WHERE t.id = $1::uuid
                      AND (t.owner_id = $2::uuid OR tm.user_id = $2::uuid)
                    LIMIT 1
                """
                has_access = await pg_client.fetch_scalar(check_query, team_id, user_id)

                if not has_access:
                    raise PermissionError(f"User {user_id} cannot view team {team_id}")

            # Query team members (including pending and accepted)
            query = """
                SELECT
                    tm.id, tm.team_id, tm.user_id, tm.team_permission, tm.resource_permissions,
                    tm.status, tm.invited_at, tm.responded_at, tm.created_at, tm.updated_at,
                    tm.is_observable, tm.observable_consent_status, tm.observable_consent_at,
                    u.email, u.full_name,
                    t.owner_id
                FROM team_memberships tm
                LEFT JOIN users u ON tm.user_id = u.id
                LEFT JOIN teams t ON tm.team_id = t.id
                WHERE tm.team_id = $1::uuid
                ORDER BY tm.created_at ASC
            """

            members_data = await pg_client.execute_query(query, team_id)

            # Get team owner information to include them in the members list
            owner_query = """
                SELECT
                    t.id as team_id, t.owner_id, t.created_at,
                    u.email, u.full_name
                FROM teams t
                JOIN users u ON t.owner_id = u.id
                WHERE t.id = $1::uuid
            """
            owner_data = await pg_client.fetch_one(owner_query, team_id)

            # Format members
            members = []

            # Add owner as first member
            if owner_data:
                owner_member = {
                    "id": str(owner_data["owner_id"]),  # Use owner_id as id for consistency
                    "team_id": str(owner_data["team_id"]),
                    "user_id": str(owner_data["owner_id"]),
                    "user_email": owner_data.get("email", "Unknown"),
                    "user_name": owner_data.get("full_name", "Unknown"),
                    "team_permission": "share",  # Owners have full share permissions
                    "resource_permissions": {},
                    "is_owner": True,
                    "is_observable": False,  # Owners don't have observable status
                    "observable_consent_status": "none",
                    "observable_consent_at": None,
                    "status": "accepted",
                    "invited_at": None,
                    "responded_at": None,
                    "joined_at": owner_data["created_at"].isoformat() if owner_data.get("created_at") else None,
                    "created_at": owner_data["created_at"].isoformat() if owner_data.get("created_at") else None,
                    "updated_at": owner_data["created_at"].isoformat() if owner_data.get("created_at") else None
                }
                logger.info(f"Adding owner as member: is_owner={owner_member['is_owner']}, user_id={owner_member['user_id']}")
                members.append(owner_member)

            # Add regular members (skip owner - already added above)
            for member in members_data:
                # Skip if this member is the owner (already added)
                if str(member["user_id"]) == str(owner_data["owner_id"]):
                    continue

                # Parse JSONB resource_permissions
                resource_perms = member["resource_permissions"]
                if isinstance(resource_perms, str):
                    resource_perms = json.loads(resource_perms)
                elif resource_perms is None:
                    resource_perms = {}

                # Determine if this user is the team owner
                is_owner = str(member["user_id"]) == str(member.get("owner_id"))

                # Use responded_at for joined_at if accepted, otherwise created_at
                joined_at = None
                if member.get("status") == "accepted":
                    joined_at = member.get("responded_at") or member.get("created_at")

                members.append({
                    "id": str(member["id"]),
                    "team_id": str(member["team_id"]),
                    "user_id": str(member["user_id"]),
                    "user_email": member.get("email", "Unknown"),
                    "user_name": member.get("full_name", "Unknown"),
                    "team_permission": member["team_permission"],
                    "resource_permissions": resource_perms,
                    "is_owner": is_owner,
                    "is_observable": member.get("is_observable", False),
                    "observable_consent_status": member.get("observable_consent_status", "none"),
                    "observable_consent_at": member["observable_consent_at"].isoformat() if member.get("observable_consent_at") else None,
                    "status": member.get("status", "accepted"),
                    "invited_at": member["invited_at"].isoformat() if member.get("invited_at") else None,
                    "responded_at": member["responded_at"].isoformat() if member.get("responded_at") else None,
                    "joined_at": joined_at.isoformat() if joined_at else None,
                    "created_at": member["created_at"].isoformat() if member["created_at"] else None,
                    "updated_at": member["updated_at"].isoformat() if member["updated_at"] else None
                })

            logger.info(f"Retrieved {len(members)} members for team {team_id}")
            return members

        except Exception as e:
            logger.error(f"Error getting team members for {team_id}: {e}")
            return []

    async def share_resource(
        self,
        team_id: str,
        resource_type: str,
        resource_id: str,
        user_permissions: Dict[str, str]
    ) -> bool:
        """
        Share a resource (agent/dataset) to team with per-user permissions.
        Requires team ownership or 'share' permission.

        Args:
            team_id: Team UUID
            resource_type: 'agent' or 'dataset'
            resource_id: Resource UUID
            user_permissions: Dict mapping user_id -> permission ('read' or 'edit')
                              e.g., {"user_uuid_1": "read", "user_uuid_2": "edit"}
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user can share to team
            if not await self.can_share_to_team(team_id, user_id):
                raise PermissionError(f"User {user_id} cannot share resources to team {team_id}")

            # Validate resource_type
            if resource_type not in ["agent", "dataset"]:
                raise ValueError(f"Invalid resource_type: {resource_type}. Must be 'agent' or 'dataset'")

            # Validate all permissions are 'read' or 'edit'
            for perm in user_permissions.values():
                if perm not in ["read", "edit"]:
                    raise ValueError(f"Invalid permission: {perm}. Must be 'read' or 'edit'")

            # Update resource_permissions JSONB for each user
            resource_key = f"{resource_type}:{resource_id}"

            for member_user_id, permission in user_permissions.items():
                query = """
                    UPDATE team_memberships
                    SET resource_permissions = jsonb_set(
                        COALESCE(resource_permissions, '{}'::jsonb),
                        $1::text[],
                        $2::jsonb,
                        true
                    ),
                    updated_at = NOW()
                    WHERE team_id = $3::uuid AND user_id = $4::uuid
                    RETURNING id
                """

                # jsonb_set path as array
                path = [resource_key]

                result = await pg_client.fetch_one(
                    query,
                    path,
                    json.dumps(permission),  # Convert to JSON string
                    team_id,
                    member_user_id
                )

                if not result:
                    logger.warning(f"Member {member_user_id} not found in team {team_id}, skipping")

            logger.info(f"Shared {resource_type}:{resource_id} to team {team_id} with {len(user_permissions)} user permissions")
            return True

        except Exception as e:
            logger.error(f"Error sharing resource to team {team_id}: {e}")
            raise

    async def unshare_resource(
        self,
        team_id: str,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """
        Remove resource sharing from team (removes from all members' resource_permissions).
        Requires team ownership or 'share' permission.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user can share to team
            if not await self.can_share_to_team(team_id, user_id):
                raise PermissionError(f"User {user_id} cannot unshare resources from team {team_id}")

            # Validate resource_type
            if resource_type not in ["agent", "dataset"]:
                raise ValueError(f"Invalid resource_type: {resource_type}. Must be 'agent' or 'dataset'")

            # Remove resource key from all members' resource_permissions JSONB
            resource_key = f"{resource_type}:{resource_id}"

            query = """
                UPDATE team_memberships
                SET resource_permissions = resource_permissions - $1::text,
                    updated_at = NOW()
                WHERE team_id = $2::uuid
                RETURNING id
            """

            await pg_client.execute_query(query, resource_key, team_id)

            logger.info(f"Unshared {resource_type}:{resource_id} from team {team_id}")
            return True

        except Exception as e:
            logger.error(f"Error unsharing resource from team {team_id}: {e}")
            raise

    async def get_shared_resources(
        self,
        team_id: str,
        resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all resources shared to a team.
        Returns list of {resource_type, resource_id, user_permissions} dicts.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user can view team
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            if not is_admin:
                check_query = """
                    SELECT 1 FROM teams t
                    LEFT JOIN team_memberships tm ON t.id = tm.team_id
                    WHERE t.id = $1::uuid
                      AND (t.owner_id = $2::uuid OR tm.user_id = $2::uuid)
                    LIMIT 1
                """
                has_access = await pg_client.fetch_scalar(check_query, team_id, user_id)

                if not has_access:
                    raise PermissionError(f"User {user_id} cannot view team {team_id}")

            # Query all resource_permissions from team members
            query = """
                SELECT user_id, resource_permissions
                FROM team_memberships
                WHERE team_id = $1::uuid
            """

            members_data = await pg_client.execute_query(query, team_id)

            # Aggregate all shared resources
            shared_resources = {}  # {resource_key: {user_id: permission}}

            for member in members_data:
                resource_perms = member["resource_permissions"]
                if isinstance(resource_perms, str):
                    resource_perms = json.loads(resource_perms)
                elif resource_perms is None:
                    resource_perms = {}

                for resource_key, permission in resource_perms.items():
                    # Parse resource_key like "agent:uuid" or "dataset:uuid"
                    if ":" not in resource_key:
                        continue

                    res_type, res_id = resource_key.split(":", 1)

                    # Filter by resource_type if specified
                    if resource_type and res_type != resource_type:
                        continue

                    if resource_key not in shared_resources:
                        shared_resources[resource_key] = {
                            "resource_type": res_type,
                            "resource_id": res_id,
                            "user_permissions": {}
                        }

                    shared_resources[resource_key]["user_permissions"][str(member["user_id"])] = permission

            result = list(shared_resources.values())

            # Fetch resource names and owners for agents and datasets
            agent_ids = [r["resource_id"] for r in result if r["resource_type"] == "agent"]
            dataset_ids = [r["resource_id"] for r in result if r["resource_type"] == "dataset"]

            # Map resource IDs to names and owners
            resource_names = {}
            resource_owners = {}

            # Fetch agent names and owners
            if agent_ids:
                agent_query = """
                    SELECT a.id, a.name, u.full_name as owner_name, u.email as owner_email
                    FROM agents a
                    LEFT JOIN users u ON a.created_by = u.id
                    WHERE a.id = ANY($1::uuid[])
                """
                agent_rows = await pg_client.execute_query(agent_query, agent_ids)
                for row in agent_rows:
                    resource_key = f"agent:{row['id']}"
                    resource_names[resource_key] = row['name']
                    resource_owners[resource_key] = row['owner_name'] or row['owner_email']

            # Fetch dataset names and owners
            if dataset_ids:
                dataset_query = """
                    SELECT d.id, d.name, u.full_name as owner_name, u.email as owner_email
                    FROM datasets d
                    LEFT JOIN users u ON d.created_by = u.id
                    WHERE d.id = ANY($1::uuid[])
                """
                dataset_rows = await pg_client.execute_query(dataset_query, dataset_ids)
                for row in dataset_rows:
                    resource_key = f"dataset:{row['id']}"
                    resource_names[resource_key] = row['name']
                    resource_owners[resource_key] = row['owner_name'] or row['owner_email']

            # Add names and owners to result
            for resource in result:
                resource_key = f"{resource['resource_type']}:{resource['resource_id']}"
                resource['resource_name'] = resource_names.get(resource_key, 'Unknown')
                resource['resource_owner'] = resource_owners.get(resource_key, 'Unknown')

            logger.info(f"Retrieved {len(result)} shared resources for team {team_id}")
            return result

        except Exception as e:
            logger.error(f"Error getting shared resources for team {team_id}: {e}")
            return []

    # =========================================================================
    # RESOURCE ACCESS METHODS (Phase 2: Junction Table Integration)
    # =========================================================================

    async def get_resource_teams(
        self,
        resource_type: str,
        resource_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all teams this resource is shared with.

        Args:
            resource_type: 'agent' or 'dataset'
            resource_id: UUID of the resource

        Returns:
            List of teams with sharing metadata
        """
        try:
            pg_client = await get_postgresql_client()

            query = """
                SELECT
                    t.id,
                    t.name,
                    t.description,
                    t.owner_id,
                    trs.shared_by,
                    trs.created_at,
                    COUNT(DISTINCT tm.user_id) as member_count
                FROM team_resource_shares trs
                JOIN teams t ON t.id = trs.team_id
                LEFT JOIN team_memberships tm ON tm.team_id = trs.team_id
                WHERE trs.resource_type = $1
                  AND trs.resource_id = $2::uuid
                  AND t.tenant_id = (SELECT id FROM tenants WHERE domain = $3 LIMIT 1)
                GROUP BY t.id, t.name, t.description, t.owner_id, trs.shared_by, trs.created_at
                ORDER BY trs.created_at DESC
            """

            teams = await pg_client.execute_query(query, resource_type, resource_id, self.tenant_domain)
            logger.info(f"Found {len(teams)} teams for {resource_type}:{resource_id}")
            return teams

        except Exception as e:
            logger.error(f"Error getting teams for resource {resource_type}:{resource_id}: {e}")
            return []

    async def get_resource_teams_batch(
        self,
        resource_type: str,
        resource_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all teams for multiple resources in a single query.
        Fixes N+1 query pattern in agents.py and datasets.py list endpoints.

        Args:
            resource_type: 'agent' or 'dataset'
            resource_ids: List of resource UUIDs

        Returns:
            Dict mapping resource_id -> list of teams with sharing metadata
        """
        if not resource_ids:
            return {}

        try:
            pg_client = await get_postgresql_client()

            # Create placeholder string for IN clause: $3, $4, $5, etc.
            # $1 = resource_type, $2 = tenant_domain, $3+ = resource_ids
            placeholders = ', '.join(f'${i+3}::uuid' for i in range(len(resource_ids)))

            query = f"""
                SELECT
                    trs.resource_id::text,
                    t.id,
                    t.name,
                    t.description,
                    t.owner_id,
                    trs.shared_by,
                    trs.created_at,
                    COUNT(DISTINCT tm.user_id) as member_count
                FROM team_resource_shares trs
                JOIN teams t ON t.id = trs.team_id
                LEFT JOIN team_memberships tm ON tm.team_id = trs.team_id
                WHERE trs.resource_type = $1
                  AND trs.resource_id IN ({placeholders})
                  AND t.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                GROUP BY trs.resource_id, t.id, t.name, t.description, t.owner_id, trs.shared_by, trs.created_at
                ORDER BY trs.created_at DESC
            """

            # Build params: resource_type, tenant_domain, then all resource_ids
            params = [resource_type, self.tenant_domain] + list(resource_ids)
            rows = await pg_client.execute_query(query, *params)

            # Group results by resource_id
            result: Dict[str, List[Dict[str, Any]]] = {rid: [] for rid in resource_ids}
            for row in rows:
                resource_id = row.get('resource_id')
                if resource_id in result:
                    # Build team dict without resource_id
                    team_data = {
                        'id': row.get('id'),
                        'name': row.get('name'),
                        'description': row.get('description'),
                        'owner_id': row.get('owner_id'),
                        'shared_by': row.get('shared_by'),
                        'created_at': row.get('created_at'),
                        'member_count': row.get('member_count')
                    }
                    result[resource_id].append(team_data)

            logger.info(f"Batch fetched teams for {len(resource_ids)} {resource_type}s")
            return result

        except Exception as e:
            logger.error(f"Error batch getting teams for {resource_type}s: {e}")
            # Return empty lists for all requested IDs on error
            return {rid: [] for rid in resource_ids}

    async def get_user_accessible_resources(
        self,
        user_id: str,
        resource_type: str
    ) -> List[Dict[str, Any]]:
        """
        Get all resources accessible to user via team memberships.
        Uses the user_accessible_resources view for efficiency.

        Args:
            user_id: UUID of the user
            resource_type: 'agent' or 'dataset'

        Returns:
            List of accessible resources with permission metadata
        """
        try:
            pg_client = await get_postgresql_client()

            # Check if admin/developer (can access all)
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            if is_admin:
                logger.info(f"User {user_id} is admin/developer, has access to all {resource_type}s")
                # Return empty list - admin check happens at agent/dataset service level
                return []

            query = """
                SELECT
                    resource_id,
                    resource_type,
                    best_permission,
                    shared_in_teams,
                    team_ids,
                    first_shared_at
                FROM user_accessible_resources
                WHERE user_id = $1::uuid
                  AND resource_type = $2
            """

            resources = await pg_client.execute_query(query, user_id, resource_type)
            logger.info(f"User {user_id} has access to {len(resources)} {resource_type}s via teams")
            return resources

        except Exception as e:
            logger.error(f"Error getting accessible {resource_type}s for user {user_id}: {e}")
            return []

    async def check_user_resource_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        required_permission: str = 'read'
    ) -> bool:
        """
        Check if user has required permission on resource via team membership.
        Uses the user_resource_access view for fast lookup.

        Args:
            user_id: UUID of the user
            resource_type: 'agent' or 'dataset'
            resource_id: UUID of the resource
            required_permission: 'read' or 'edit'

        Returns:
            True if user has required permission
        """
        try:
            pg_client = await get_postgresql_client()

            # Check if admin/developer (can access all)
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            if user_role in ["admin", "developer"]:
                logger.info(f"User {user_id} is admin/developer, has full access")
                return True

            query = """
                SELECT permission::text as permission
                FROM user_resource_access
                WHERE user_id = $1::uuid
                  AND resource_type = $2
                  AND resource_id = $3::uuid
                LIMIT 1
            """

            result = await pg_client.fetch_scalar(query, user_id, resource_type, resource_id)

            if not result:
                logger.debug(f"User {user_id} has no access to {resource_type}:{resource_id}")
                return False

            # Remove quotes from JSONB string value
            user_permission = result.strip('"')

            # Check permission level
            if required_permission == 'read':
                has_permission = user_permission in ['read', 'edit']
            elif required_permission == 'edit':
                has_permission = user_permission == 'edit'
            else:
                has_permission = False

            logger.debug(f"User {user_id} permission on {resource_type}:{resource_id}: {user_permission} (required: {required_permission}) = {has_permission}")
            return has_permission

        except Exception as e:
            logger.error(f"Error checking permission for user {user_id} on {resource_type}:{resource_id}: {e}")
            return False

    async def share_resource_to_teams(
        self,
        resource_id: str,
        resource_type: str,
        shared_by: str,
        team_shares: List[Dict[str, Any]]
    ) -> None:
        """
        Share a resource to multiple teams with per-user permissions.

        Args:
            resource_id: UUID of the resource
            resource_type: 'agent' or 'dataset'
            shared_by: User ID (will be converted to UUID if needed)
            team_shares: List of {team_id, user_permissions: {user_id: 'read'|'edit'}}
                        If user_permissions is empty, auto-populates all team members with 'read' access

        Raises:
            PermissionError: If user doesn't have 'share' permission on any team
            ValueError: If team_shares is invalid
        """
        try:
            pg_client = await get_postgresql_client()

            # Convert shared_by to UUID if it's not already
            shared_by_uuid = await self._get_user_id(pg_client, shared_by)

            for share in team_shares:
                team_id = share.get('team_id')
                user_permissions = share.get('user_permissions', {})

                if not team_id:
                    raise ValueError("team_id is required in team_shares")

                # Auto-populate read access for all team members if permissions are empty (first-time share)
                if not user_permissions or len(user_permissions) == 0:
                    logger.info(f"Auto-populating read access for all members of team {team_id}")

                    # Fetch all team members (accepted only)
                    members_query = """
                        SELECT user_id FROM team_memberships
                        WHERE team_id = $1::uuid AND status = 'accepted'
                    """
                    members = await pg_client.execute_query(members_query, team_id)

                    # Create user_permissions dict with read access for all members
                    user_permissions = {str(member['user_id']): 'read' for member in members}
                    share['user_permissions'] = user_permissions  # Update the share object

                    # Allow sharing to teams with no members - permissions will be granted when members join
                    if len(user_permissions) == 0:
                        logger.info(f"Team {team_id} has no accepted members yet - resource will be accessible when members join")
                    else:
                        logger.info(f"Auto-populated {len(user_permissions)} team members with read access")

                # Verify user has share permission on this team
                can_share = await self.can_share_to_team(team_id, shared_by_uuid)
                if not can_share:
                    raise PermissionError(f"User {shared_by_uuid} does not have share permission on team {team_id}")

                # Insert into team_resource_shares
                insert_share_query = """
                    INSERT INTO team_resource_shares (team_id, resource_type, resource_id, shared_by)
                    VALUES ($1::uuid, $2, $3::uuid, $4::uuid)
                    ON CONFLICT (team_id, resource_type, resource_id)
                    DO UPDATE SET shared_by = EXCLUDED.shared_by
                    RETURNING id
                """

                await pg_client.execute_query(
                    insert_share_query,
                    team_id, resource_type, resource_id, shared_by_uuid
                )

                # Update resource_permissions for each user in team
                for user_id, permission in user_permissions.items():
                    if permission not in ['read', 'edit']:
                        logger.warning(f"Invalid permission '{permission}' for user {user_id}, skipping")
                        continue

                    resource_key = f"{resource_type}:{resource_id}"

                    update_permission_query = """
                        UPDATE team_memberships
                        SET resource_permissions = COALESCE(resource_permissions, '{}'::jsonb) || jsonb_build_object($1::text, $2::text)
                        WHERE team_id = $3::uuid
                          AND user_id = $4::uuid
                    """

                    await pg_client.execute_query(
                        update_permission_query,
                        resource_key, permission, team_id, user_id
                    )

                logger.info(f"Shared {resource_type}:{resource_id} to team {team_id} with {len(user_permissions)} user permissions")

            # Sync agent visibility field when sharing to teams
            if resource_type == 'agent':
                try:
                    await pg_client.execute_query(
                        "UPDATE agents SET visibility = 'team' WHERE id = $1::uuid AND visibility != 'team'",
                        resource_id
                    )
                    logger.info(f"Updated agent {resource_id} visibility to 'team'")
                except Exception as vis_error:
                    logger.warning(f"Failed to update agent visibility: {vis_error}")
                    # Don't fail the sharing operation if visibility update fails

            # Sync dataset visibility and access_group fields when sharing to teams
            if resource_type == 'dataset':
                try:
                    await pg_client.execute_query(
                        "UPDATE datasets SET visibility = 'team', access_group = 'team' WHERE id = $1::uuid AND (visibility != 'team' OR access_group != 'team')",
                        resource_id
                    )
                    logger.info(f"Updated dataset {resource_id} visibility and access_group to 'team'")
                except Exception as vis_error:
                    logger.warning(f"Failed to update dataset visibility: {vis_error}")
                    # Don't fail the sharing operation if visibility update fails

        except Exception as e:
            logger.error(f"Error sharing {resource_type}:{resource_id} to teams: {e}")
            raise

    async def unshare_resource_from_team(
        self,
        resource_id: str,
        resource_type: str,
        team_id: str
    ) -> None:
        """
        Remove resource from team (triggers cleanup of member permissions).
        Requires team ownership or 'share' permission.

        Args:
            resource_id: UUID of the resource
            resource_type: 'agent' or 'dataset'
            team_id: UUID of the team

        Note: The cleanup_resource_permissions trigger handles removing
              permissions from team members automatically.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user can share to team (which also means they can unshare)
            if not await self.can_share_to_team(team_id, user_id):
                raise PermissionError(f"User {user_id} cannot unshare resources from team {team_id}")

            query = """
                DELETE FROM team_resource_shares
                WHERE team_id = $1::uuid
                  AND resource_type = $2
                  AND resource_id = $3::uuid
            """

            await pg_client.execute_query(query, team_id, resource_type, resource_id)
            logger.info(f"Unshared {resource_type}:{resource_id} from team {team_id}")

            # Check if this was the last team share for this agent
            if resource_type == 'agent':
                try:
                    remaining_shares = await pg_client.fetch_scalar(
                        "SELECT COUNT(*) FROM team_resource_shares WHERE resource_type = $1 AND resource_id = $2::uuid",
                        resource_type, resource_id
                    )

                    if remaining_shares == 0:
                        # No more teams have access, reset visibility to individual
                        await pg_client.execute_query(
                            "UPDATE agents SET visibility = 'individual' WHERE id = $1::uuid AND visibility = 'team'",
                            resource_id
                        )
                        logger.info(f"Reset agent {resource_id} visibility to 'individual' (no remaining team shares)")
                except Exception as vis_error:
                    logger.warning(f"Failed to reset agent visibility: {vis_error}")
                    # Don't fail the unsharing operation if visibility update fails

            # Check if this was the last team share for this dataset
            if resource_type == 'dataset':
                try:
                    remaining_shares = await pg_client.fetch_scalar(
                        "SELECT COUNT(*) FROM team_resource_shares WHERE resource_type = $1 AND resource_id = $2::uuid",
                        resource_type, resource_id
                    )

                    if remaining_shares == 0:
                        # No more teams have access, reset visibility and access_group to individual
                        await pg_client.execute_query(
                            "UPDATE datasets SET visibility = 'individual', access_group = 'individual' WHERE id = $1::uuid AND (visibility = 'team' OR access_group = 'team')",
                            resource_id
                        )
                        logger.info(f"Reset dataset {resource_id} visibility and access_group to 'individual' (no remaining team shares)")
                except Exception as vis_error:
                    logger.warning(f"Failed to reset dataset visibility: {vis_error}")
                    # Don't fail the unsharing operation if visibility update fails

        except Exception as e:
            logger.error(f"Error unsharing {resource_type}:{resource_id} from team {team_id}: {e}")
            raise

    async def get_team_shared_resource_ids(
        self,
        team_id: str,
        resource_type: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get all resource IDs shared with a specific team.
        Used for team-scoped observability filtering.

        Args:
            team_id: UUID of the team
            resource_type: Optional filter for 'agent' or 'dataset'. If None, returns both.

        Returns:
            Dict with 'agents' and/or 'datasets' keys containing lists of UUIDs.
            Example: {"agents": ["uuid1", "uuid2"], "datasets": ["uuid3"]}

        Raises:
            RuntimeError: If database query fails
        """
        try:
            pg_client = await get_postgresql_client()
            result = {"agents": [], "datasets": []}

            if resource_type is None:
                # Fetch both types
                query = """
                    SELECT resource_type, resource_id::text
                    FROM team_resource_shares
                    WHERE team_id = $1::uuid
                    ORDER BY resource_type, created_at DESC
                """
                rows = await pg_client.fetch_rows(query, team_id)

                for row in rows:
                    r_type = row['resource_type']
                    r_id = row['resource_id']
                    if r_type == 'agent':
                        result['agents'].append(str(r_id))
                    elif r_type == 'dataset':
                        result['datasets'].append(str(r_id))

            else:
                # Fetch specific type
                query = """
                    SELECT resource_id::text
                    FROM team_resource_shares
                    WHERE team_id = $1::uuid
                      AND resource_type = $2
                    ORDER BY created_at DESC
                """
                rows = await pg_client.fetch_rows(query, team_id, resource_type)
                resource_ids = [str(row['resource_id']) for row in rows]

                if resource_type == 'agent':
                    result['agents'] = resource_ids
                elif resource_type == 'dataset':
                    result['datasets'] = resource_ids

            logger.debug(f"Team {team_id} shared resources: {result}")
            return result

        except Exception as e:
            logger.error(f"Error fetching team shared resources for team {team_id}: {e}")
            raise RuntimeError(f"Failed to fetch team shared resources: {e}")

    # ============================================================================
    # Observable Member Management
    # ============================================================================

    async def can_view_observability(self, team_id: str, user_id: str) -> bool:
        """
        Check if user can view Observable member activity.
        Requires owner or 'manager' team_permission.
        NOTE: Admin/developer do NOT get automatic Observable access (use platform observability instead).
        """
        pg_client = await get_postgresql_client()

        # Team owner can view Observable members
        if await self.is_team_owner(team_id, user_id):
            return True

        # Check for 'manager' permission
        query = """
            SELECT team_permission FROM team_memberships
            WHERE team_id = $1::uuid
              AND user_id = $2::uuid
              AND status = 'accepted'
        """

        permission = await pg_client.fetch_scalar(query, team_id, user_id)
        return permission == 'manager'

    async def can_manage_members(self, team_id: str, manager_id: str, target_member_id: str) -> bool:
        """
        Check if manager can manage a specific team member.
        - Owner can manage all members
        - Manager can manage non-owner members
        - Admin/developer can manage all (system role bypass)
        """
        pg_client = await get_postgresql_client()

        # Admin/developer bypass
        user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
        if user_role in ["admin", "developer"]:
            return True

        # Owner can manage all members
        if await self.is_team_owner(team_id, manager_id):
            return True

        # Check if manager has 'manager' permission
        manager_perm_query = """
            SELECT team_permission FROM team_memberships
            WHERE team_id = $1::uuid
              AND user_id = $2::uuid
              AND status = 'accepted'
        """

        manager_permission = await pg_client.fetch_scalar(manager_perm_query, team_id, manager_id)
        if manager_permission != 'manager':
            return False

        # Manager cannot modify the team owner
        is_target_owner = await self.is_team_owner(team_id, target_member_id)
        return not is_target_owner

    async def request_observable_status(self, team_id: str, target_user_id: str) -> Dict[str, Any]:
        """
        Request Observable access from a team member.
        Can be called by owner or manager.
        Sets observable_consent_status='pending', is_observable=true.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user can view observability (owner or manager)
            if not await self.can_view_observability(team_id, user_id):
                raise PermissionError(f"User {user_id} does not have permission to request Observable access")

            # Check if target user is a member
            member_check_query = """
                SELECT id, team_permission, is_observable, observable_consent_status
                FROM team_memberships
                WHERE team_id = $1::uuid
                  AND user_id = $2::uuid
                  AND status = 'accepted'
            """

            member = await pg_client.fetch_one(member_check_query, team_id, target_user_id)
            if not member:
                raise ValueError(f"User {target_user_id} is not an accepted member of team {team_id}")

            # Check if already Observable
            if member["is_observable"] and member["observable_consent_status"] == 'approved':
                raise ValueError(f"User {target_user_id} is already Observable")

            # Update Observable status to pending
            update_query = """
                UPDATE team_memberships
                SET is_observable = true,
                    observable_consent_status = 'pending',
                    updated_at = NOW()
                WHERE team_id = $1::uuid
                  AND user_id = $2::uuid
                RETURNING id, is_observable, observable_consent_status
            """

            result = await pg_client.fetch_one(update_query, team_id, target_user_id)
            if not result:
                raise RuntimeError("Failed to request Observable status")

            logger.info(f"Observable access requested for user {target_user_id} in team {team_id}")

            return {
                "team_id": team_id,
                "user_id": target_user_id,
                "is_observable": result["is_observable"],
                "observable_consent_status": result["observable_consent_status"],
                "message": "Observable access request sent"
            }

        except Exception as e:
            logger.error(f"Error requesting Observable status: {e}")
            raise

    async def get_observable_requests(self) -> List[Dict[str, Any]]:
        """
        Get pending Observable requests for the current user.
        Returns teams where user has pending Observable consent.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            query = """
                SELECT
                    t.id as team_id,
                    t.name as team_name,
                    u.full_name as requested_by_name,
                    u.email as requested_by_email,
                    tm.updated_at as requested_at
                FROM team_memberships tm
                JOIN teams t ON tm.team_id = t.id
                JOIN users u ON t.owner_id = u.id
                WHERE tm.user_id = $1::uuid
                  AND tm.is_observable = true
                  AND tm.observable_consent_status = 'pending'
                  AND t.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                ORDER BY tm.updated_at DESC
            """

            results = await pg_client.execute_query(query, user_id, self.tenant_domain)

            requests = []
            for row in results:
                requests.append({
                    "team_id": str(row["team_id"]),
                    "team_name": row["team_name"],
                    "requested_by_name": row["requested_by_name"],
                    "requested_by_email": row["requested_by_email"],
                    "requested_at": row["requested_at"].isoformat() if row["requested_at"] else None
                })

            logger.info(f"Retrieved {len(requests)} Observable requests for user {user_id}")
            return requests

        except Exception as e:
            logger.error(f"Error getting Observable requests: {e}")
            return []

    async def approve_observable_consent(self, team_id: str) -> Dict[str, Any]:
        """
        Approve Observable status for the current user in a team.
        Sets observable_consent_status='approved', observable_consent_at=NOW().
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if there's a pending request
            check_query = """
                SELECT id, is_observable, observable_consent_status
                FROM team_memberships
                WHERE team_id = $1::uuid
                  AND user_id = $2::uuid
                  AND is_observable = true
                  AND observable_consent_status = 'pending'
            """

            membership = await pg_client.fetch_one(check_query, team_id, user_id)
            if not membership:
                raise ValueError(f"No pending Observable request found for user {user_id} in team {team_id}")

            # Approve Observable status
            update_query = """
                UPDATE team_memberships
                SET observable_consent_status = 'approved',
                    observable_consent_at = NOW(),
                    updated_at = NOW()
                WHERE team_id = $1::uuid
                  AND user_id = $2::uuid
                RETURNING id, is_observable, observable_consent_status, observable_consent_at
            """

            result = await pg_client.fetch_one(update_query, team_id, user_id)
            if not result:
                raise RuntimeError("Failed to approve Observable status")

            logger.info(f"User {user_id} approved Observable status in team {team_id}")

            return {
                "team_id": team_id,
                "user_id": user_id,
                "is_observable": result["is_observable"],
                "observable_consent_status": result["observable_consent_status"],
                "observable_consent_at": result["observable_consent_at"].isoformat() if result["observable_consent_at"] else None,
                "message": "Observable status approved"
            }

        except Exception as e:
            logger.error(f"Error approving Observable consent: {e}")
            raise

    async def revoke_observable_status(self, team_id: str) -> Dict[str, Any]:
        """
        Revoke Observable status for the current user in a team.
        Sets is_observable=false, observable_consent_status='revoked'.
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check if user is Observable
            check_query = """
                SELECT id, is_observable, observable_consent_status
                FROM team_memberships
                WHERE team_id = $1::uuid
                  AND user_id = $2::uuid
                  AND is_observable = true
            """

            membership = await pg_client.fetch_one(check_query, team_id, user_id)
            if not membership:
                raise ValueError(f"User {user_id} is not Observable in team {team_id}")

            # Revoke Observable status
            update_query = """
                UPDATE team_memberships
                SET is_observable = false,
                    observable_consent_status = 'revoked',
                    updated_at = NOW()
                WHERE team_id = $1::uuid
                  AND user_id = $2::uuid
                RETURNING id, is_observable, observable_consent_status
            """

            result = await pg_client.fetch_one(update_query, team_id, user_id)
            if not result:
                raise RuntimeError("Failed to revoke Observable status")

            logger.info(f"User {user_id} revoked Observable status in team {team_id}")

            return {
                "team_id": team_id,
                "user_id": user_id,
                "is_observable": result["is_observable"],
                "observable_consent_status": result["observable_consent_status"],
                "message": "Observable status revoked"
            }

        except Exception as e:
            logger.error(f"Error revoking Observable status: {e}")
            raise

    async def get_team_activity(self, team_id: str, days: int = 7) -> Dict[str, Any]:
        """
        Get aggregated activity for Observable team members.
        Requires can_view_observability permission.
        Returns team metrics + per-member breakdowns (Observable only).
        """
        try:
            pg_client = await get_postgresql_client()

            # Get current user ID
            user_id = await self._get_user_id(pg_client)

            # Check permission
            if not await self.can_view_observability(team_id, user_id):
                raise PermissionError(f"User {user_id} does not have permission to view team activity")

            # Get team info
            team = await self.get_team_by_id(team_id)
            if not team:
                raise ValueError(f"Team {team_id} not found")

            # Get Observable members
            observable_members_query = """
                SELECT user_id
                FROM team_memberships
                WHERE team_id = $1::uuid
                  AND is_observable = true
                  AND observable_consent_status = 'approved'
                  AND status = 'accepted'
            """

            observable_members = await pg_client.execute_query(observable_members_query, team_id)
            observable_user_ids = [str(row["user_id"]) for row in observable_members]

            if not observable_user_ids:
                # No Observable members
                return {
                    "team_id": team_id,
                    "team_name": team["name"],
                    "date_range_days": days,
                    "observable_member_count": 0,
                    "total_member_count": team.get("member_count", 0),
                    "team_totals": {
                        "conversations": 0,
                        "messages": 0,
                        "tokens": 0
                    },
                    "member_breakdown": [],
                    "time_series": []
                }

            # Get activity from v_user_activity_summary for Observable members
            activity_query = """
                SELECT
                    user_id::text,
                    email,
                    full_name,
                    total_conversations,
                    total_messages,
                    total_tokens,
                    last_conversation_at
                FROM v_user_activity_summary
                WHERE user_id::text = ANY($1::text[])
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                ORDER BY total_conversations DESC
            """

            activity_data = await pg_client.execute_query(activity_query, observable_user_ids, self.tenant_domain)

            # Calculate team totals
            team_totals = {
                "conversations": 0,
                "messages": 0,
                "tokens": 0
            }

            member_breakdown = []
            for row in activity_data:
                team_totals["conversations"] += row["total_conversations"] or 0
                team_totals["messages"] += row["total_messages"] or 0
                team_totals["tokens"] += row["total_tokens"] or 0

                member_breakdown.append({
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "full_name": row["full_name"],
                    "conversations": row["total_conversations"] or 0,
                    "messages": row["total_messages"] or 0,
                    "tokens": row["total_tokens"] or 0,
                    "last_activity": row["last_conversation_at"].isoformat() if row["last_conversation_at"] else None
                })

            # Get time series data (daily for last N days)
            time_series_query = """
                SELECT
                    date,
                    SUM(conversation_count) as conversations,
                    SUM(total_messages) as messages,
                    SUM(total_tokens) as tokens
                FROM v_daily_usage_stats
                WHERE tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY date
                ORDER BY date ASC
            """ % days

            time_series_data = await pg_client.execute_query(time_series_query, self.tenant_domain)

            time_series = []
            for row in time_series_data:
                time_series.append({
                    "date": row["date"].isoformat() if row["date"] else None,
                    "conversations": row["conversations"] or 0,
                    "messages": row["messages"] or 0,
                    "tokens": row["tokens"] or 0
                })

            logger.info(f"Retrieved team activity for {len(observable_user_ids)} Observable members in team {team_id}")

            return {
                "team_id": team_id,
                "team_name": team["name"],
                "date_range_days": days,
                "observable_member_count": len(observable_user_ids),
                "total_member_count": team.get("member_count", 0),
                "team_totals": team_totals,
                "member_breakdown": member_breakdown,
                "time_series": time_series
            }

        except Exception as e:
            logger.error(f"Error getting team activity: {e}")
            raise
