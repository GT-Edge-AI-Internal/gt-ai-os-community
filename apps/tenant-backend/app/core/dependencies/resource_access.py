"""
Resource Access Control Dependencies for FastAPI

Provides declarative access control for agents and datasets using team-based permissions.
"""

from typing import Callable
from uuid import UUID
from fastapi import Depends, HTTPException
from app.api.dependencies import get_current_user
from app.services.team_service import TeamService
from app.core.permissions import get_user_role
from app.core.postgresql_client import get_postgresql_client
import logging

logger = logging.getLogger(__name__)


def require_resource_access(
    resource_type: str,
    required_permission: str = "read"
) -> Callable:
    """
    FastAPI dependency factory for resource access control.

    Creates a dependency that verifies user has required permission on a resource
    via ownership, organization visibility, or team membership.

    Args:
        resource_type: 'agent' or 'dataset'
        required_permission: 'read' or 'edit' (default: 'read')

    Returns:
        FastAPI dependency function

    Usage:
        @router.get("/agents/{agent_id}")
        async def get_agent(
            agent_id: str,
            _: None = Depends(require_resource_access("agent", "read"))
        ):
            # User has read access if we reach here
            ...

        @router.put("/agents/{agent_id}")
        async def update_agent(
            agent_id: str,
            _: None = Depends(require_resource_access("agent", "edit"))
        ):
            # User has edit access if we reach here
            ...
    """

    async def check_access(
        resource_id: str,
        current_user: dict = Depends(get_current_user)
    ) -> None:
        """
        Verify user has required permission on resource.

        Raises HTTPException(403) if access denied.
        """
        user_id = current_user["user_id"]
        tenant_domain = current_user["tenant_domain"]
        user_email = current_user.get("email", user_id)

        try:
            pg_client = await get_postgresql_client()

            # Check if admin/developer (bypass all checks)
            user_role = await get_user_role(pg_client, user_email, tenant_domain)
            if user_role in ["admin", "developer"]:
                logger.debug(f"Admin/developer {user_id} has full access to {resource_type} {resource_id}")
                return

            # Check if user owns the resource
            ownership_query = f"""
                SELECT created_by FROM {resource_type}s
                WHERE id = $1::uuid
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            """
            owner_id = await pg_client.fetch_scalar(ownership_query, resource_id, tenant_domain)

            if owner_id and str(owner_id) == str(user_id):
                logger.debug(f"User {user_id} owns {resource_type} {resource_id}")
                return

            # Check if resource is organization-wide
            visibility_query = f"""
                SELECT visibility FROM {resource_type}s
                WHERE id = $1::uuid
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            """
            visibility = await pg_client.fetch_scalar(visibility_query, resource_id, tenant_domain)

            if visibility == "organization":
                logger.debug(f"{resource_type.capitalize()} {resource_id} is organization-wide")
                return

            # Check team-based access using TeamService
            team_service = TeamService(tenant_domain, user_id, user_email)
            has_permission = await team_service.check_user_resource_permission(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                required_permission=required_permission
            )

            if has_permission:
                logger.debug(f"User {user_id} has {required_permission} permission on {resource_type} {resource_id} via team")
                return

            # Access denied
            logger.warning(f"Access denied: User {user_id} cannot access {resource_type} {resource_id} (required: {required_permission})")
            raise HTTPException(
                status_code=403,
                detail=f"You do not have {required_permission} permission for this {resource_type}"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking resource access: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error verifying {resource_type} access"
            )

    return check_access


def require_agent_access(required_permission: str = "read") -> Callable:
    """
    Convenience wrapper for agent access control.

    Usage:
        @router.get("/agents/{agent_id}")
        async def get_agent(
            agent_id: str,
            _: None = Depends(require_agent_access("read"))
        ):
            ...
    """
    return require_resource_access("agent", required_permission)


def require_dataset_access(required_permission: str = "read") -> Callable:
    """
    Convenience wrapper for dataset access control.

    Usage:
        @router.get("/datasets/{dataset_id}")
        async def get_dataset(
            dataset_id: str,
            _: None = Depends(require_dataset_access("read"))
        ):
            ...
    """
    return require_resource_access("dataset", required_permission)


async def check_agent_edit_permission(
    agent_id: str,
    user_id: str,
    tenant_domain: str,
    user_email: str = None
) -> bool:
    """
    Helper function to check if user can edit an agent.

    Can be used in service layer without FastAPI dependency injection.

    Args:
        agent_id: UUID of the agent
        user_id: UUID of the user
        tenant_domain: Tenant domain
        user_email: User email (optional)

    Returns:
        True if user can edit agent
    """
    try:
        pg_client = await get_postgresql_client()

        # Check if admin/developer
        user_role = await get_user_role(pg_client, user_email or user_id, tenant_domain)
        if user_role in ["admin", "developer"]:
            return True

        # Check ownership
        query = """
            SELECT created_by FROM agents
            WHERE id = $1::uuid
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        """
        owner_id = await pg_client.fetch_scalar(query, agent_id, tenant_domain)

        if owner_id and str(owner_id) == str(user_id):
            return True

        # Check team edit permission
        team_service = TeamService(tenant_domain, user_id, user_email or user_id)
        return await team_service.check_user_resource_permission(
            user_id=user_id,
            resource_type="agent",
            resource_id=agent_id,
            required_permission="edit"
        )

    except Exception as e:
        logger.error(f"Error checking agent edit permission: {e}")
        return False


async def check_dataset_edit_permission(
    dataset_id: str,
    user_id: str,
    tenant_domain: str,
    user_email: str = None
) -> bool:
    """
    Helper function to check if user can edit a dataset.

    Can be used in service layer without FastAPI dependency injection.

    Args:
        dataset_id: UUID of the dataset
        user_id: UUID of the user
        tenant_domain: Tenant domain
        user_email: User email (optional)

    Returns:
        True if user can edit dataset
    """
    try:
        pg_client = await get_postgresql_client()

        # Check if admin/developer
        user_role = await get_user_role(pg_client, user_email or user_id, tenant_domain)
        if user_role in ["admin", "developer"]:
            return True

        # Check ownership
        query = """
            SELECT user_id FROM datasets
            WHERE id = $1::uuid
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        """
        owner_id = await pg_client.fetch_scalar(query, dataset_id, tenant_domain)

        if owner_id and str(owner_id) == str(user_id):
            return True

        # Check team edit permission
        team_service = TeamService(tenant_domain, user_id, user_email or user_id)
        return await team_service.check_user_resource_permission(
            user_id=user_id,
            resource_type="dataset",
            resource_id=dataset_id,
            required_permission="edit"
        )

    except Exception as e:
        logger.error(f"Error checking dataset edit permission: {e}")
        return False
