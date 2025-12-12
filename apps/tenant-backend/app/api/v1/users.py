"""
User API endpoints for GT 2.0 Tenant Backend

Handles user preferences and favorite agents management.
Follows GT 2.0 principles: no mocks, real implementations, fail fast.
"""

import structlog
from fastapi import APIRouter, HTTPException, status, Depends, Header
from typing import Optional

from app.services.user_service import UserService
from app.schemas.user import (
    UserPreferencesResponse,
    UpdateUserPreferencesRequest,
    FavoriteAgentsResponse,
    UpdateFavoriteAgentsRequest,
    AddFavoriteAgentRequest,
    RemoveFavoriteAgentRequest,
    CustomCategoriesResponse,
    UpdateCustomCategoriesRequest
)

logger = structlog.get_logger()
router = APIRouter(prefix="/users", tags=["users"])


def get_user_context(
    x_tenant_domain: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None)
) -> tuple[str, str, str]:
    """Extract user context from headers"""
    if not x_tenant_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Domain header is required"
        )
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-ID header is required"
        )

    return x_tenant_domain, x_user_id, x_user_email or x_user_id


# User Preferences Endpoints

@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    user_context: tuple = Depends(get_user_context)
):
    """
    Get current user's preferences from PostgreSQL.

    Returns all user preferences stored in the JSONB preferences column.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info("Getting user preferences", user_id=user_id, tenant_domain=tenant_domain)

        service = UserService(tenant_domain, user_id, user_email)
        preferences = await service.get_user_preferences()

        return UserPreferencesResponse(preferences=preferences)

    except Exception as e:
        logger.error("Failed to get user preferences", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user preferences"
        )


@router.put("/me/preferences")
async def update_user_preferences(
    request: UpdateUserPreferencesRequest,
    user_context: tuple = Depends(get_user_context)
):
    """
    Update current user's preferences in PostgreSQL.

    Merges provided preferences with existing preferences using JSONB || operator.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info("Updating user preferences", user_id=user_id, tenant_domain=tenant_domain)

        service = UserService(tenant_domain, user_id, user_email)
        success = await service.update_user_preferences(request.preferences)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {"success": True, "message": "Preferences updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update user preferences", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user preferences"
        )


# Favorite Agents Endpoints

@router.get("/me/favorite-agents", response_model=FavoriteAgentsResponse)
async def get_favorite_agents(
    user_context: tuple = Depends(get_user_context)
):
    """
    Get current user's favorited agent IDs from PostgreSQL.

    Returns list of agent UUIDs that the user has marked as favorites.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info("Getting favorite agent IDs", user_id=user_id, tenant_domain=tenant_domain)

        service = UserService(tenant_domain, user_id, user_email)
        favorite_ids = await service.get_favorite_agent_ids()

        return FavoriteAgentsResponse(favorite_agent_ids=favorite_ids)

    except Exception as e:
        logger.error("Failed to get favorite agents", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve favorite agents"
        )


@router.put("/me/favorite-agents")
async def update_favorite_agents(
    request: UpdateFavoriteAgentsRequest,
    user_context: tuple = Depends(get_user_context)
):
    """
    Update current user's favorite agent IDs in PostgreSQL.

    Replaces the entire list of favorite agent IDs with the provided list.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info(
            "Updating favorite agent IDs",
            user_id=user_id,
            tenant_domain=tenant_domain,
            agent_count=len(request.agent_ids)
        )

        service = UserService(tenant_domain, user_id, user_email)
        success = await service.update_favorite_agent_ids(request.agent_ids)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "message": "Favorite agents updated successfully",
            "favorite_agent_ids": request.agent_ids
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update favorite agents", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update favorite agents"
        )


@router.post("/me/favorite-agents/add")
async def add_favorite_agent(
    request: AddFavoriteAgentRequest,
    user_context: tuple = Depends(get_user_context)
):
    """
    Add a single agent to user's favorites.

    Idempotent - does nothing if agent is already in favorites.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info(
            "Adding agent to favorites",
            user_id=user_id,
            tenant_domain=tenant_domain,
            agent_id=request.agent_id
        )

        service = UserService(tenant_domain, user_id, user_email)
        success = await service.add_favorite_agent(request.agent_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "message": "Agent added to favorites",
            "agent_id": request.agent_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add favorite agent", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add favorite agent"
        )


@router.post("/me/favorite-agents/remove")
async def remove_favorite_agent(
    request: RemoveFavoriteAgentRequest,
    user_context: tuple = Depends(get_user_context)
):
    """
    Remove a single agent from user's favorites.

    Idempotent - does nothing if agent is not in favorites.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info(
            "Removing agent from favorites",
            user_id=user_id,
            tenant_domain=tenant_domain,
            agent_id=request.agent_id
        )

        service = UserService(tenant_domain, user_id, user_email)
        success = await service.remove_favorite_agent(request.agent_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "message": "Agent removed from favorites",
            "agent_id": request.agent_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove favorite agent", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove favorite agent"
        )


# Custom Categories Endpoints

@router.get("/me/custom-categories", response_model=CustomCategoriesResponse)
async def get_custom_categories(
    user_context: tuple = Depends(get_user_context)
):
    """
    Get current user's custom agent categories from PostgreSQL.

    Returns list of custom categories with name and description.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info("Getting custom categories", user_id=user_id, tenant_domain=tenant_domain)

        service = UserService(tenant_domain, user_id, user_email)
        categories = await service.get_custom_categories()

        return CustomCategoriesResponse(categories=categories)

    except Exception as e:
        logger.error("Failed to get custom categories", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve custom categories"
        )


@router.put("/me/custom-categories")
async def update_custom_categories(
    request: UpdateCustomCategoriesRequest,
    user_context: tuple = Depends(get_user_context)
):
    """
    Update current user's custom agent categories in PostgreSQL.

    Replaces the entire list of custom categories with the provided list.
    """
    tenant_domain, user_id, user_email = user_context

    try:
        logger.info(
            "Updating custom categories",
            user_id=user_id,
            tenant_domain=tenant_domain,
            category_count=len(request.categories)
        )

        service = UserService(tenant_domain, user_id, user_email)
        success = await service.update_custom_categories(request.categories)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "message": "Custom categories updated successfully",
            "categories": [cat.dict() for cat in request.categories]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update custom categories", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update custom categories"
        )
