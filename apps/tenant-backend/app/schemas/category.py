"""
Category schemas for GT 2.0 Tenant Backend

Pydantic models for agent category API request/response validation.
Supports tenant-scoped editable/deletable categories per Issue #215.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
import re


class CategoryCreate(BaseModel):
    """Request to create a new category"""
    name: str = Field(..., min_length=1, max_length=100, description="Category display name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    icon: Optional[str] = Field(None, max_length=10, description="Category icon (emoji)")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Category name cannot be empty')
        # Check for invalid characters (allow alphanumeric, spaces, hyphens, underscores)
        if not re.match(r'^[\w\s\-]+$', v):
            raise ValueError('Category name can only contain letters, numbers, spaces, hyphens, and underscores')
        return v


class CategoryUpdate(BaseModel):
    """Request to update a category"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New category name")
    description: Optional[str] = Field(None, max_length=500, description="New category description")
    icon: Optional[str] = Field(None, max_length=10, description="New category icon")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError('Category name cannot be empty')
        if not re.match(r'^[\w\s\-]+$', v):
            raise ValueError('Category name can only contain letters, numbers, spaces, hyphens, and underscores')
        return v


class CategoryResponse(BaseModel):
    """Response for category operations"""
    id: str = Field(..., description="Category UUID")
    name: str = Field(..., description="Category display name")
    slug: str = Field(..., description="URL-safe category identifier")
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Category icon (emoji)")
    is_default: bool = Field(..., description="Whether this is a system default category")
    created_by: Optional[str] = Field(None, description="UUID of user who created the category")
    created_by_name: Optional[str] = Field(None, description="Name of user who created the category")
    can_edit: bool = Field(..., description="Whether current user can edit this category")
    can_delete: bool = Field(..., description="Whether current user can delete this category")
    sort_order: int = Field(..., description="Display sort order")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CategoryListResponse(BaseModel):
    """Response for listing categories"""
    categories: List[CategoryResponse] = Field(default_factory=list, description="List of categories")
    total: int = Field(..., description="Total number of categories")
