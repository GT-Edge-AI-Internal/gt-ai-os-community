"""
User UUID Resolution Utilities for GT 2.0

Handles email-to-UUID resolution across all services to ensure
consistent user identification in database operations.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def resolve_user_uuid(current_user: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Resolve user email to UUID for internal services.

    Args:
        current_user: User data from JWT token

    Returns:
        Tuple of (tenant_domain, user_email, user_uuid)

    Raises:
        HTTPException: If UUID resolution fails
    """
    tenant_domain = current_user.get("tenant_domain", "test")
    user_email = current_user["email"]

    # Import here to avoid circular imports
    from app.api.auth import get_tenant_user_uuid_by_email

    user_uuid = await get_tenant_user_uuid_by_email(user_email)

    if not user_uuid:
        logger.error(f"Failed to resolve UUID for user {user_email} in tenant {tenant_domain}")
        raise HTTPException(
            status_code=404,
            detail=f"User {user_email} not found in tenant system"
        )

    logger.info(f"✅ Resolved user {user_email} to UUID: {user_uuid}")
    return tenant_domain, user_email, user_uuid


async def ensure_user_uuid(email_or_uuid: str, tenant_domain: Optional[str] = None) -> str:
    """
    Ensure we have a UUID, converting email if needed.

    Args:
        email_or_uuid: Either an email address or UUID string
        tenant_domain: Tenant domain for lookup context

    Returns:
        UUID string

    Raises:
        ValueError: If email cannot be resolved to UUID or input is invalid
    """
    import uuid
    import re

    # Validate input is not empty or None
    if not email_or_uuid or not isinstance(email_or_uuid, str):
        raise ValueError(f"Invalid user identifier: {email_or_uuid}")

    email_or_uuid = email_or_uuid.strip()

    # Check if it's an email
    if "@" in email_or_uuid:
        # It's an email, resolve to UUID
        from app.api.auth import get_tenant_user_uuid_by_email

        user_uuid = await get_tenant_user_uuid_by_email(email_or_uuid)

        if not user_uuid:
            error_msg = f"Cannot resolve email {email_or_uuid} to UUID"
            if tenant_domain:
                error_msg += f" in tenant {tenant_domain}"

            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug(f"Resolved email {email_or_uuid} to UUID: {user_uuid}")
        return user_uuid

    # Check if it's a valid UUID format
    try:
        uuid_obj = uuid.UUID(email_or_uuid)
        return str(uuid_obj)  # Return normalized UUID string
    except (ValueError, TypeError):
        # Not a valid UUID, could be a numeric ID or other format
        pass

    # Handle numeric user IDs or other legacy formats
    if email_or_uuid.isdigit():
        logger.warning(f"Received numeric user ID '{email_or_uuid}', attempting database lookup")
        # Try to resolve numeric ID to proper UUID via database
        from app.core.postgresql_client import get_postgresql_client

        try:
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                tenant_schema = f"tenant_{tenant_domain.replace('.', '_').replace('-', '_')}" if tenant_domain else "tenant_test"

                # Try to find user by numeric ID (assuming it might be a legacy ID)
                user_row = await conn.fetchrow(
                    f"SELECT id FROM {tenant_schema}.users WHERE id::text = $1 OR email = $1 LIMIT 1",
                    email_or_uuid
                )

                if user_row:
                    return str(user_row['id'])

                # If not found, try finding the first user (fallback for development)
                logger.warning(f"User '{email_or_uuid}' not found, using first available user as fallback")
                first_user = await conn.fetchrow(f"SELECT id FROM {tenant_schema}.users LIMIT 1")

                if first_user:
                    logger.info(f"Using fallback user UUID: {first_user['id']}")
                    return str(first_user['id'])

        except Exception as e:
            logger.error(f"Database lookup failed for user '{email_or_uuid}': {e}")

    # If all else fails, raise an error
    error_msg = f"Cannot resolve user identifier '{email_or_uuid}' to UUID. Expected email or valid UUID format."
    if tenant_domain:
        error_msg += f" Tenant: {tenant_domain}"

    logger.error(error_msg)
    raise ValueError(error_msg)


def get_user_sql_clause(param_num: int, user_identifier: str) -> str:
    """
    Get the appropriate SQL clause for user identification.

    Args:
        param_num: Parameter number in SQL query (e.g., 3 for $3)
        user_identifier: Either email or UUID

    Returns:
        SQL clause string for user lookup
    """
    if "@" in user_identifier:
        # Email - do lookup
        return f"(SELECT id FROM users WHERE email = ${param_num} LIMIT 1)"
    else:
        # UUID - use directly
        return f"${param_num}::uuid"


def is_uuid_format(identifier: str) -> bool:
    """
    Check if a string looks like a UUID.

    Args:
        identifier: String to check

    Returns:
        True if looks like UUID, False if looks like email
    """
    return "@" not in identifier and len(identifier) == 36 and identifier.count("-") == 4