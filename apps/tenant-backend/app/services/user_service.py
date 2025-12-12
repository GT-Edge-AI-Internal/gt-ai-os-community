"""
GT 2.0 User Service - User Preferences Management

Manages user preferences including favorite agents using PostgreSQL + PGVector backend.
Perfect tenant isolation - each tenant has separate user data.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client

logger = logging.getLogger(__name__)


class UserService:
    """GT 2.0 PostgreSQL User Service with Perfect Tenant Isolation"""

    def __init__(self, tenant_domain: str, user_id: str, user_email: str = None):
        """Initialize with tenant and user isolation using PostgreSQL storage"""
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.user_email = user_email or user_id
        self.settings = get_settings()

        logger.info(f"User service initialized for {tenant_domain}/{user_id} (email: {self.user_email})")

    async def _get_user_id(self, pg_client) -> Optional[str]:
        """Get user ID from email or user_id with fallback"""
        user_lookup_query = """
            SELECT id FROM users
            WHERE (email = $1 OR id::text = $1 OR username = $1)
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            LIMIT 1
        """

        user_id = await pg_client.fetch_scalar(user_lookup_query, self.user_email, self.tenant_domain)
        if not user_id:
            # If not found by email, try by user_id
            user_id = await pg_client.fetch_scalar(user_lookup_query, self.user_id, self.tenant_domain)

        return user_id

    async def get_user_preferences(self) -> Dict[str, Any]:
        """Get user preferences from PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()
            user_id = await self._get_user_id(pg_client)

            if not user_id:
                logger.warning(f"User not found: {self.user_email} (or {self.user_id}) in tenant {self.tenant_domain}")
                return {}

            query = """
                SELECT preferences
                FROM users
                WHERE id = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            """

            result = await pg_client.fetch_one(query, user_id, self.tenant_domain)

            if result and result["preferences"]:
                prefs = result["preferences"]
                # Handle both dict and JSON string
                if isinstance(prefs, str):
                    return json.loads(prefs)
                return prefs

            return {}

        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}

    async def update_user_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Update user preferences in PostgreSQL (merges with existing)"""
        try:
            pg_client = await get_postgresql_client()
            user_id = await self._get_user_id(pg_client)

            if not user_id:
                logger.warning(f"User not found: {self.user_email} (or {self.user_id}) in tenant {self.tenant_domain}")
                return False

            # Merge with existing preferences using PostgreSQL JSONB || operator
            query = """
                UPDATE users
                SET preferences = COALESCE(preferences, '{}'::jsonb) || $1::jsonb,
                    updated_at = NOW()
                WHERE id = $2
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $3 LIMIT 1)
                RETURNING id
            """

            updated_id = await pg_client.fetch_scalar(
                query,
                json.dumps(preferences),
                user_id,
                self.tenant_domain
            )

            if updated_id:
                logger.info(f"Updated preferences for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False

    async def get_favorite_agent_ids(self) -> List[str]:
        """Get user's favorited agent IDs"""
        try:
            preferences = await self.get_user_preferences()
            favorite_ids = preferences.get("favorite_agent_ids", [])

            # Ensure it's a list
            if not isinstance(favorite_ids, list):
                return []

            logger.info(f"Retrieved {len(favorite_ids)} favorite agent IDs for user {self.user_id}")
            return favorite_ids

        except Exception as e:
            logger.error(f"Error getting favorite agent IDs: {e}")
            return []

    async def update_favorite_agent_ids(self, agent_ids: List[str]) -> bool:
        """Update user's favorited agent IDs"""
        try:
            # Validate agent_ids is a list
            if not isinstance(agent_ids, list):
                logger.error(f"Invalid agent_ids type: {type(agent_ids)}")
                return False

            # Update preferences with new favorite_agent_ids
            success = await self.update_user_preferences({
                "favorite_agent_ids": agent_ids
            })

            if success:
                logger.info(f"Updated {len(agent_ids)} favorite agent IDs for user {self.user_id}")

            return success

        except Exception as e:
            logger.error(f"Error updating favorite agent IDs: {e}")
            return False

    async def add_favorite_agent(self, agent_id: str) -> bool:
        """Add a single agent to favorites"""
        try:
            current_favorites = await self.get_favorite_agent_ids()

            if agent_id not in current_favorites:
                current_favorites.append(agent_id)
                return await self.update_favorite_agent_ids(current_favorites)

            # Already in favorites
            return True

        except Exception as e:
            logger.error(f"Error adding favorite agent: {e}")
            return False

    async def remove_favorite_agent(self, agent_id: str) -> bool:
        """Remove a single agent from favorites"""
        try:
            current_favorites = await self.get_favorite_agent_ids()

            if agent_id in current_favorites:
                current_favorites.remove(agent_id)
                return await self.update_favorite_agent_ids(current_favorites)

            # Not in favorites
            return True

        except Exception as e:
            logger.error(f"Error removing favorite agent: {e}")
            return False

    async def get_custom_categories(self) -> List[Dict[str, Any]]:
        """Get user's custom agent categories"""
        try:
            preferences = await self.get_user_preferences()
            custom_categories = preferences.get("custom_categories", [])

            # Ensure it's a list
            if not isinstance(custom_categories, list):
                return []

            logger.info(f"Retrieved {len(custom_categories)} custom categories for user {self.user_id}")
            return custom_categories

        except Exception as e:
            logger.error(f"Error getting custom categories: {e}")
            return []

    async def update_custom_categories(self, categories: List[Dict[str, Any]]) -> bool:
        """Update user's custom agent categories (replaces entire list)"""
        try:
            # Validate categories is a list
            if not isinstance(categories, list):
                logger.error(f"Invalid categories type: {type(categories)}")
                return False

            # Convert Pydantic models to dicts if needed
            category_dicts = []
            for cat in categories:
                if hasattr(cat, 'dict'):
                    category_dicts.append(cat.dict())
                elif isinstance(cat, dict):
                    category_dicts.append(cat)
                else:
                    logger.error(f"Invalid category type: {type(cat)}")
                    return False

            # Update preferences with new custom_categories
            success = await self.update_user_preferences({
                "custom_categories": category_dicts
            })

            if success:
                logger.info(f"Updated {len(category_dicts)} custom categories for user {self.user_id}")

            return success

        except Exception as e:
            logger.error(f"Error updating custom categories: {e}")
            return False
