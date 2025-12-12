"""
Category API endpoints for GT 2.0 Tenant Backend

Provides tenant-scoped agent category management with CRUD operations.
Supports Issue #215 requirements for editable/deletable categories.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
import logging

from app.core.security import get_current_user
from app.services.category_service import CategoryService
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


async def get_category_service(current_user: Dict[str, Any]) -> CategoryService:
    """Helper function to create CategoryService with proper context"""
    user_email = current_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="User email not found in token")

    # Get user ID from token or lookup
    user_id = current_user.get('sub', current_user.get('user_id', user_email))
    tenant_domain = current_user.get('tenant_domain', 'test-company')

    return CategoryService(
        tenant_domain=tenant_domain,
        user_id=str(user_id),
        user_email=user_email
    )


@router.get("", response_model=CategoryListResponse)
async def list_categories(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get all categories for the tenant.

    Returns all active categories with permission flags indicating
    whether the current user can edit/delete each category.
    """
    try:
        service = await get_category_service(current_user)
        categories = await service.get_all_categories()

        return CategoryListResponse(
            categories=[CategoryResponse(**cat) for cat in categories],
            total=len(categories)
        )

    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get a specific category by ID.
    """
    try:
        service = await get_category_service(current_user)
        category = await service.get_category_by_id(category_id)

        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        return CategoryResponse(**category)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting category {category_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    current_user: Dict = Depends(get_current_user)
):
    """
    Create a new custom category.

    The creating user becomes the owner and can edit/delete the category.
    All users in the tenant can use the category for their agents.
    """
    try:
        service = await get_category_service(current_user)
        category = await service.create_category(
            name=data.name,
            description=data.description,
            icon=data.icon
        )

        return CategoryResponse(**category)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    data: CategoryUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """
    Update a category.

    Requires permission: admin/developer role OR be the category creator.
    """
    try:
        service = await get_category_service(current_user)
        category = await service.update_category(
            category_id=category_id,
            name=data.name,
            description=data.description,
            icon=data.icon
        )

        return CategoryResponse(**category)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating category {category_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete a category (soft delete).

    Requires permission: admin/developer role OR be the category creator.
    Note: Agents using this category will retain their category value,
    but the category will no longer appear in selection lists.
    """
    try:
        service = await get_category_service(current_user)
        await service.delete_category(category_id)

        return {"message": "Category deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting category {category_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
