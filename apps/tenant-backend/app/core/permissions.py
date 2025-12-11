"""
GT 2.0 Role-Based Permissions
Enforces organization-level resource sharing based on user roles.

Visibility Levels:
- individual: Only the creator can see and edit
- organization: All users can read, only admins/developers can create and edit
"""

from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

# Role hierarchy: admin/developer > analyst > student
ADMIN_ROLES = ["admin", "developer"]

# Visibility levels
VISIBILITY_INDIVIDUAL = "individual"
VISIBILITY_ORGANIZATION = "organization"


async def get_user_role(pg_client, user_email: str, tenant_domain: str) -> str:
    """
    Get the role for a user in the tenant database.
    Returns: 'admin', 'developer', 'analyst', or 'student'
    """
    query = """
        SELECT role FROM users
        WHERE email = $1
          AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
        LIMIT 1
    """
    role = await pg_client.fetch_scalar(query, user_email, tenant_domain)
    return role or "student"


def can_share_to_organization(user_role: str) -> bool:
    """
    Check if a user can share resources at the organization level.
    Only admin and developer roles can share to organization.
    """
    return user_role in ADMIN_ROLES


def validate_visibility_permission(visibility: str, user_role: str) -> None:
    """
    Validate that the user has permission to set the given visibility level.
    Raises HTTPException if not authorized.

    Rules:
    - admin/developer: Can set individual or organization visibility
    - analyst/student: Can only set individual visibility
    """
    if visibility == VISIBILITY_ORGANIZATION and not can_share_to_organization(user_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only admin and developer users can share resources to organization. Your role: {user_role}"
        )


def can_edit_resource(resource_creator_id: str, current_user_id: str, user_role: str, resource_visibility: str) -> bool:
    """
    Check if user can edit a resource.

    Rules:
    - Owner can always edit their own resources
    - Admin/developer can edit any resource
    - Organization-shared resources: read-only for non-admins who didn't create it
    """
    # Admin and developer can edit anything
    if user_role in ADMIN_ROLES:
        return True

    # Owner can always edit
    if resource_creator_id == current_user_id:
        return True

    # Organization resources are read-only for non-admins
    return False


def can_delete_resource(resource_creator_id: str, current_user_id: str, user_role: str) -> bool:
    """
    Check if user can delete a resource.

    Rules:
    - Owner can delete their own resources
    - Admin/developer can delete any resource
    - Others cannot delete
    """
    # Admin and developer can delete anything
    if user_role in ADMIN_ROLES:
        return True

    # Owner can delete
    if resource_creator_id == current_user_id:
        return True

    return False


def is_effective_owner(resource_creator_id: str, current_user_id: str, user_role: str) -> bool:
    """
    Check if user is effective owner of a resource.

    Effective owners have identical access to actual owners:
    - Actual resource creator
    - Admin/developer users (tenant admins)

    This determines whether user gets owner-level field visibility in ResponseFilter
    and whether they can perform owner-only actions like sharing.

    Note: Tenant isolation is enforced at query level via tenant_id checks.
    This function only determines ownership semantics within the tenant.

    Args:
        resource_creator_id: UUID of resource creator
        current_user_id: UUID of current user
        user_role: User's role in tenant (admin, developer, analyst, student)

    Returns:
        True if user should have owner-level access

    Examples:
        >>> is_effective_owner("user123", "admin456", "admin")
        True  # Admin has owner-level access to all resources
        >>> is_effective_owner("user123", "user123", "student")
        True  # Actual owner
        >>> is_effective_owner("user123", "user456", "analyst")
        False  # Different user, not admin
    """
    # Admins and developers have identical access to owners
    if user_role in ADMIN_ROLES:
        return True

    # Actual owner
    return resource_creator_id == current_user_id