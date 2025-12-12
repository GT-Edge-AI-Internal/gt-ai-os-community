"""
User schemas for GT 2.0 Tenant Backend

Pydantic models for user-related API request/response validation.
Implements user preferences management per GT 2.0 specifications.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class CustomCategory(BaseModel):
    """User-defined custom category with metadata"""
    name: str = Field(..., description="Category name (lowercase, unique per user)")
    description: str = Field(..., description="Category description")
    created_at: Optional[str] = Field(None, description="ISO timestamp when category was created")


class UserPreferences(BaseModel):
    """User preferences stored in JSONB"""
    favorite_agent_ids: Optional[List[str]] = Field(default_factory=list, description="List of favorited agent UUIDs")
    custom_categories: Optional[List[CustomCategory]] = Field(default_factory=list, description="User's custom agent categories")
    # Future preferences can be added here


class UserPreferencesResponse(BaseModel):
    """Response for getting user preferences"""
    preferences: Dict[str, Any] = Field(..., description="User preferences dictionary")


class UpdateUserPreferencesRequest(BaseModel):
    """Request to update user preferences (merges with existing)"""
    preferences: Dict[str, Any] = Field(..., description="Preferences to merge with existing")


class FavoriteAgentsResponse(BaseModel):
    """Response for getting favorite agent IDs"""
    favorite_agent_ids: List[str] = Field(..., description="List of favorited agent UUIDs")


class UpdateFavoriteAgentsRequest(BaseModel):
    """Request to update favorite agent IDs (replaces existing list)"""
    agent_ids: List[str] = Field(..., description="List of agent UUIDs to set as favorites")


class AddFavoriteAgentRequest(BaseModel):
    """Request to add a single agent to favorites"""
    agent_id: str = Field(..., description="Agent UUID to add to favorites")


class RemoveFavoriteAgentRequest(BaseModel):
    """Request to remove a single agent from favorites"""
    agent_id: str = Field(..., description="Agent UUID to remove from favorites")


class CustomCategoriesResponse(BaseModel):
    """Response for getting custom categories"""
    categories: List[CustomCategory] = Field(..., description="List of user's custom categories")


class UpdateCustomCategoriesRequest(BaseModel):
    """Request to update custom categories (replaces entire list)"""
    categories: List[CustomCategory] = Field(..., description="Complete list of custom categories")
