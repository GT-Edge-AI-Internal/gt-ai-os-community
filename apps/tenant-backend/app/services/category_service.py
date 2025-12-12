"""
Category Service for GT 2.0 Tenant Backend

Provides tenant-scoped agent category management with permission-based
editing and deletion. Supports Issue #215 requirements.

Permission Model:
- Admins/developers can edit/delete ANY category
- Regular users can only edit/delete categories they created
- All users can view and use all tenant categories
"""

import uuid
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client
from app.core.permissions import get_user_role
import logging

logger = logging.getLogger(__name__)

# Admin roles that can manage all categories
ADMIN_ROLES = ["admin", "developer"]


class CategoryService:
    """GT 2.0 Category Management Service with Tenant Isolation"""

    def __init__(self, tenant_domain: str, user_id: str, user_email: str = None):
        """Initialize with tenant and user isolation using PostgreSQL storage"""
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.user_email = user_email or user_id
        self.settings = get_settings()

        logger.info(f"Category service initialized for {tenant_domain}/{user_id}")

    def _generate_slug(self, name: str) -> str:
        """Generate URL-safe slug from category name"""
        # Convert to lowercase, replace non-alphanumeric with hyphens
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower())
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug or 'category'

    async def _get_user_id(self, pg_client) -> str:
        """Get user UUID from email/username/uuid with tenant isolation"""
        identifier = self.user_email

        user_lookup_query = """
            SELECT id FROM users
            WHERE (email = $1 OR id::text = $1 OR username = $1)
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            LIMIT 1
        """

        user_id = await pg_client.fetch_scalar(user_lookup_query, identifier, self.tenant_domain)
        if not user_id:
            user_id = await pg_client.fetch_scalar(user_lookup_query, self.user_id, self.tenant_domain)

        if not user_id:
            raise RuntimeError(f"User not found: {identifier} in tenant {self.tenant_domain}")

        return str(user_id)

    async def _get_tenant_id(self, pg_client) -> str:
        """Get tenant UUID from domain"""
        query = "SELECT id FROM tenants WHERE domain = $1 LIMIT 1"
        tenant_id = await pg_client.fetch_scalar(query, self.tenant_domain)
        if not tenant_id:
            raise RuntimeError(f"Tenant not found: {self.tenant_domain}")
        return str(tenant_id)

    async def _can_manage_category(self, pg_client, category: Dict) -> tuple:
        """
        Check if current user can manage (edit/delete) a category.
        Returns (can_edit, can_delete) tuple.
        """
        # Get user role
        user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
        is_admin = user_role in ADMIN_ROLES

        # Get current user ID
        current_user_id = await self._get_user_id(pg_client)

        # Admins can manage all categories
        if is_admin:
            return (True, True)

        # Check if user created this category
        created_by = category.get('created_by')
        if created_by and str(created_by) == current_user_id:
            return (True, True)

        # Regular users cannot manage other users' categories or defaults
        return (False, False)

    async def get_all_categories(self) -> List[Dict[str, Any]]:
        """
        Get all active categories for the tenant.
        Returns categories with permission flags for current user.
        """
        try:
            pg_client = await get_postgresql_client()
            user_id = await self._get_user_id(pg_client)
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ADMIN_ROLES

            query = """
                SELECT
                    c.id, c.name, c.slug, c.description, c.icon,
                    c.is_default, c.created_by, c.sort_order,
                    c.created_at, c.updated_at,
                    u.full_name as created_by_name
                FROM categories c
                LEFT JOIN users u ON c.created_by = u.id
                WHERE c.tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                  AND c.is_deleted = FALSE
                ORDER BY c.sort_order ASC, c.name ASC
            """

            rows = await pg_client.execute_query(query, self.tenant_domain)

            categories = []
            for row in rows:
                # Determine permissions
                can_edit = False
                can_delete = False

                if is_admin:
                    can_edit = True
                    can_delete = True
                elif row.get('created_by') and str(row['created_by']) == user_id:
                    can_edit = True
                    can_delete = True

                categories.append({
                    "id": str(row["id"]),
                    "name": row["name"],
                    "slug": row["slug"],
                    "description": row.get("description"),
                    "icon": row.get("icon"),
                    "is_default": row.get("is_default", False),
                    "created_by": str(row["created_by"]) if row.get("created_by") else None,
                    "created_by_name": row.get("created_by_name"),
                    "can_edit": can_edit,
                    "can_delete": can_delete,
                    "sort_order": row.get("sort_order", 0),
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                    "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
                })

            logger.info(f"Retrieved {len(categories)} categories for tenant {self.tenant_domain}")
            return categories

        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            raise

    async def get_category_by_id(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get a single category by ID"""
        try:
            pg_client = await get_postgresql_client()

            query = """
                SELECT
                    c.id, c.name, c.slug, c.description, c.icon,
                    c.is_default, c.created_by, c.sort_order,
                    c.created_at, c.updated_at,
                    u.full_name as created_by_name
                FROM categories c
                LEFT JOIN users u ON c.created_by = u.id
                WHERE c.id = $1::uuid
                  AND c.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                  AND c.is_deleted = FALSE
            """

            row = await pg_client.fetch_one(query, category_id, self.tenant_domain)

            if not row:
                return None

            can_edit, can_delete = await self._can_manage_category(pg_client, dict(row))

            return {
                "id": str(row["id"]),
                "name": row["name"],
                "slug": row["slug"],
                "description": row.get("description"),
                "icon": row.get("icon"),
                "is_default": row.get("is_default", False),
                "created_by": str(row["created_by"]) if row.get("created_by") else None,
                "created_by_name": row.get("created_by_name"),
                "can_edit": can_edit,
                "can_delete": can_delete,
                "sort_order": row.get("sort_order", 0),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }

        except Exception as e:
            logger.error(f"Error getting category {category_id}: {e}")
            raise

    async def get_category_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a single category by slug"""
        try:
            pg_client = await get_postgresql_client()

            query = """
                SELECT
                    c.id, c.name, c.slug, c.description, c.icon,
                    c.is_default, c.created_by, c.sort_order,
                    c.created_at, c.updated_at,
                    u.full_name as created_by_name
                FROM categories c
                LEFT JOIN users u ON c.created_by = u.id
                WHERE c.slug = $1
                  AND c.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                  AND c.is_deleted = FALSE
            """

            row = await pg_client.fetch_one(query, slug.lower(), self.tenant_domain)

            if not row:
                return None

            can_edit, can_delete = await self._can_manage_category(pg_client, dict(row))

            return {
                "id": str(row["id"]),
                "name": row["name"],
                "slug": row["slug"],
                "description": row.get("description"),
                "icon": row.get("icon"),
                "is_default": row.get("is_default", False),
                "created_by": str(row["created_by"]) if row.get("created_by") else None,
                "created_by_name": row.get("created_by_name"),
                "can_edit": can_edit,
                "can_delete": can_delete,
                "sort_order": row.get("sort_order", 0),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }

        except Exception as e:
            logger.error(f"Error getting category by slug {slug}: {e}")
            raise

    async def create_category(
        self,
        name: str,
        description: Optional[str] = None,
        icon: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new custom category.
        The creating user becomes the owner and can edit/delete it.
        """
        try:
            pg_client = await get_postgresql_client()
            user_id = await self._get_user_id(pg_client)
            tenant_id = await self._get_tenant_id(pg_client)

            # Generate slug
            slug = self._generate_slug(name)

            # Check if slug already exists
            existing = await self.get_category_by_slug(slug)
            if existing:
                raise ValueError(f"A category with name '{name}' already exists")

            # Generate category ID
            category_id = str(uuid.uuid4())

            # Get next sort_order (after all existing categories)
            sort_query = """
                SELECT COALESCE(MAX(sort_order), 0) + 10 as next_order
                FROM categories
                WHERE tenant_id = $1::uuid
            """
            next_order = await pg_client.fetch_scalar(sort_query, tenant_id)

            # Create category
            query = """
                INSERT INTO categories (
                    id, tenant_id, name, slug, description, icon,
                    is_default, created_by, sort_order, is_deleted,
                    created_at, updated_at
                ) VALUES (
                    $1::uuid, $2::uuid, $3, $4, $5, $6,
                    FALSE, $7::uuid, $8, FALSE,
                    NOW(), NOW()
                )
                RETURNING id, name, slug, description, icon, is_default,
                          created_by, sort_order, created_at, updated_at
            """

            row = await pg_client.fetch_one(
                query,
                category_id, tenant_id, name, slug, description, icon,
                user_id, next_order
            )

            if not row:
                raise RuntimeError("Failed to create category")

            logger.info(f"Created category {category_id}: {name} for user {user_id}")

            # Get creator name
            user_query = "SELECT full_name FROM users WHERE id = $1::uuid"
            created_by_name = await pg_client.fetch_scalar(user_query, user_id)

            return {
                "id": str(row["id"]),
                "name": row["name"],
                "slug": row["slug"],
                "description": row.get("description"),
                "icon": row.get("icon"),
                "is_default": False,
                "created_by": user_id,
                "created_by_name": created_by_name,
                "can_edit": True,
                "can_delete": True,
                "sort_order": row.get("sort_order", 0),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            raise

    async def update_category(
        self,
        category_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a category.
        Requires permission (admin or category creator).
        """
        try:
            pg_client = await get_postgresql_client()

            # Get existing category
            existing = await self.get_category_by_id(category_id)
            if not existing:
                raise ValueError("Category not found")

            # Check permissions
            can_edit, _ = await self._can_manage_category(pg_client, existing)
            if not can_edit:
                raise PermissionError("You do not have permission to edit this category")

            # Build update fields
            updates = []
            params = [category_id, self.tenant_domain]
            param_idx = 3

            if name is not None:
                new_slug = self._generate_slug(name)
                # Check if new slug conflicts with another category
                slug_check = await self.get_category_by_slug(new_slug)
                if slug_check and slug_check["id"] != category_id:
                    raise ValueError(f"A category with name '{name}' already exists")
                updates.append(f"name = ${param_idx}")
                params.append(name)
                param_idx += 1
                updates.append(f"slug = ${param_idx}")
                params.append(new_slug)
                param_idx += 1

            if description is not None:
                updates.append(f"description = ${param_idx}")
                params.append(description)
                param_idx += 1

            if icon is not None:
                updates.append(f"icon = ${param_idx}")
                params.append(icon)
                param_idx += 1

            if not updates:
                return existing

            updates.append("updated_at = NOW()")

            query = f"""
                UPDATE categories
                SET {', '.join(updates)}
                WHERE id = $1::uuid
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                  AND is_deleted = FALSE
                RETURNING id
            """

            result = await pg_client.fetch_scalar(query, *params)
            if not result:
                raise RuntimeError("Failed to update category")

            logger.info(f"Updated category {category_id}")

            # Return updated category
            return await self.get_category_by_id(category_id)

        except (ValueError, PermissionError):
            raise
        except Exception as e:
            logger.error(f"Error updating category {category_id}: {e}")
            raise

    async def delete_category(self, category_id: str) -> bool:
        """
        Soft delete a category.
        Requires permission (admin or category creator).
        """
        try:
            pg_client = await get_postgresql_client()

            # Get existing category
            existing = await self.get_category_by_id(category_id)
            if not existing:
                raise ValueError("Category not found")

            # Check permissions
            _, can_delete = await self._can_manage_category(pg_client, existing)
            if not can_delete:
                raise PermissionError("You do not have permission to delete this category")

            # Soft delete
            query = """
                UPDATE categories
                SET is_deleted = TRUE, updated_at = NOW()
                WHERE id = $1::uuid
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            """

            await pg_client.execute_command(query, category_id, self.tenant_domain)

            logger.info(f"Deleted category {category_id}")
            return True

        except (ValueError, PermissionError):
            raise
        except Exception as e:
            logger.error(f"Error deleting category {category_id}: {e}")
            raise

    async def get_or_create_category(
        self,
        slug: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get existing category by slug or create it if not exists.
        Used for agent import to auto-create missing categories.

        If the category was soft-deleted, it will be restored.

        Args:
            slug: Category slug (lowercase, hyphenated)
            description: Optional description for new/restored categories
        """
        try:
            # Try to get existing active category
            existing = await self.get_category_by_slug(slug)
            if existing:
                return existing

            # Check if there's a soft-deleted category with this slug
            pg_client = await get_postgresql_client()
            deleted_query = """
                SELECT id FROM categories
                WHERE slug = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                  AND is_deleted = TRUE
            """
            deleted_id = await pg_client.fetch_scalar(deleted_query, slug.lower(), self.tenant_domain)

            if deleted_id:
                # Restore the soft-deleted category
                user_id = await self._get_user_id(pg_client)
                restore_query = """
                    UPDATE categories
                    SET is_deleted = FALSE,
                        updated_at = NOW(),
                        created_by = $3::uuid
                    WHERE id = $1::uuid
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                """
                await pg_client.execute_command(restore_query, str(deleted_id), self.tenant_domain, user_id)
                logger.info(f"Restored soft-deleted category: {slug}")

                # Return the restored category
                return await self.get_category_by_slug(slug)

            # Auto-create with importing user as creator
            name = slug.replace('-', ' ').title()
            return await self.create_category(
                name=name,
                description=description,  # Use provided description or None
                icon=None
            )

        except Exception as e:
            logger.error(f"Error in get_or_create_category for slug {slug}: {e}")
            raise
