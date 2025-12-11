"""
Dataset Service for GT 2.0
Handles dataset CRUD operations with access control using PostgreSQL+PGVector storage
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import uuid
import logging

from app.models.access_group import AccessGroup
from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client
from app.core.permissions import get_user_role, validate_visibility_permission, can_edit_resource, can_delete_resource, is_effective_owner

# Storage multiplier for calculating actual disk usage from logical size
# Measured: 20.09 MB actual / 4.50 MB logical = 4.46x (includes indexes, TOAST, etc.)
DATASET_STORAGE_MULTIPLIER = 4.5

logger = logging.getLogger(__name__)

class DatasetService:
    """Service for dataset operations using PostgreSQL+PGVector storage"""
    
    def __init__(self, tenant_domain: str, user_id: str, user_email: str = None):
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.user_email = user_email or user_id  # Fallback to user_id if no email provided
        self.settings = get_settings()

        logger.info(f"Dataset service initialized with PostgreSQL for {tenant_domain}/{user_id} (email: {self.user_email})")
    
    async def get_owned_datasets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get datasets owned by user using PostgreSQL"""
        try:
            # Enhanced logging for UUID troubleshooting
            logger.info(f"🔍 get_owned_datasets called: user_id='{user_id}' (type: {type(user_id)}, length: {len(str(user_id))})")

            # Validate user_id to prevent UUID casting errors
            if not user_id or not user_id.strip():
                logger.error(f"🚨 get_owned_datasets EMPTY USER_ID: '{user_id}' - this will cause UUID casting errors")
                return []

            # Check if user_id looks like valid UUID format
            user_id_clean = str(user_id).strip()
            if len(user_id_clean) != 36 or user_id_clean.count('-') != 4:
                logger.warning(f"🚨 get_owned_datasets SUSPICIOUS USER_ID FORMAT: '{user_id_clean}' - not standard UUID format")

            pg_client = await get_postgresql_client()

            # Get user role to determine access level
            user_role = await get_user_role(pg_client, user_id, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Admins see ALL datasets, others see only their own or organization-level datasets
            if is_admin:
                where_clause = "WHERE d.tenant_id = (SELECT id FROM tenants WHERE domain = $1)"
                params = [self.tenant_domain]
            else:
                # Non-admin users see datasets they own OR organization-level datasets
                # Must include tenant context in user lookup to ensure correct UUID resolution
                where_clause = """WHERE d.tenant_id = (SELECT id FROM tenants WHERE domain = $1)
                  AND (d.created_by = (SELECT id FROM users WHERE email = $2 AND tenant_id = (SELECT id FROM tenants WHERE domain = $1))
                       OR LOWER(d.access_group) = 'organization')"""
                params = [self.tenant_domain, user_id]

            query = f"""
                SELECT
                    d.id, d.name, d.description, d.created_by as owner_id, d.access_group, d.team_members,
                    u.full_name as created_by_name,
                    COALESCE(doc_stats.document_count, 0) as document_count,
                    COALESCE(chunk_stats.chunk_count, 0) as chunk_count,
                    COALESCE(chunk_stats.chunk_count, 0) as vector_count,
                    (COALESCE(doc_stats.total_size_bytes, 0) +
                     COALESCE(chunk_stats.chunk_content_bytes, 0) +
                     COALESCE(chunk_stats.embedding_bytes, 0))/1024.0/1024.0 as storage_size_mb,
                    COALESCE(d.metadata->>'tags', '[]')::jsonb as tags, d.created_at, d.updated_at, d.metadata,
                    d.summary, d.summary_generated_at
                FROM datasets d
                LEFT JOIN users u ON d.created_by = u.id
                LEFT JOIN (
                    SELECT dataset_id, COUNT(*) as document_count, SUM(file_size_bytes) as total_size_bytes
                    FROM documents
                    WHERE dataset_id IS NOT NULL
                    GROUP BY dataset_id
                ) doc_stats ON d.id = doc_stats.dataset_id
                LEFT JOIN (
                    SELECT d2.dataset_id,
                           COUNT(dc.*) as chunk_count,
                           COALESCE(SUM(LENGTH(dc.content)), 0) as chunk_content_bytes,
                           COUNT(dc.*) * 4096 as embedding_bytes
                    FROM documents d2
                    LEFT JOIN document_chunks dc ON d2.id = dc.document_id
                    WHERE d2.dataset_id IS NOT NULL
                    GROUP BY d2.dataset_id
                ) chunk_stats ON d.id = chunk_stats.dataset_id
                {where_clause}
                ORDER BY d.updated_at DESC
            """

            # Execute query with enhanced error logging
            logger.info(f"🔍 get_owned_datasets executing query with user_id='{user_id}', tenant_domain='{self.tenant_domain}', is_admin={is_admin}")

            try:
                datasets_data = await pg_client.execute_query(query, *params)
                logger.info(f"🔍 get_owned_datasets query successful: returned {len(datasets_data)} datasets")
            except Exception as db_error:
                logger.error(f"🚨 get_owned_datasets DATABASE ERROR: {db_error}")
                logger.error(f"🚨 get_owned_datasets Query parameters: user_id='{user_id}' (type: {type(user_id)}), tenant_domain='{self.tenant_domain}'")

                # Check if this is the UUID casting error we're tracking
                if "invalid input syntax for type uuid" in str(db_error):
                    logger.error(f"🚨 FOUND THE UUID CASTING ERROR! user_id='{user_id}' cannot be cast to UUID")
                    logger.error(f"🚨 This is likely caused by corrupted session variables from failed RAG operations")

                    # Session contamination debugging removed - no longer using RLS

                raise

            # Get actual user UUID from database for comparison (user_role already fetched above)
            user_uuid_query = "SELECT id FROM users WHERE email = $1 AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)"
            user_uuid = await pg_client.fetch_scalar(user_uuid_query, user_id, self.tenant_domain)

            # Convert to proper format
            datasets = []
            for dataset in datasets_data:
                # Parse tags from JSONB
                tags = dataset["tags"]
                if isinstance(tags, str):
                    tags = json.loads(tags)
                elif tags is None:
                    tags = []

                # Determine if user can edit this dataset
                is_owner = is_effective_owner(str(dataset["owner_id"]), str(user_uuid), user_role)
                can_edit = can_edit_resource(str(dataset["owner_id"]), str(user_uuid), user_role, dataset["access_group"].lower())
                can_delete = can_delete_resource(str(dataset["owner_id"]), str(user_uuid), user_role)

                # Apply infrastructure overhead multiplier for accurate storage representation
                logical_storage_mb = float(dataset["storage_size_mb"] or 0)
                actual_storage_mb = logical_storage_mb * DATASET_STORAGE_MULTIPLIER

                datasets.append({
                    "id": str(dataset["id"]),
                    "name": dataset["name"],
                    "description": dataset["description"],
                    "owner_id": str(dataset["owner_id"]),
                    "created_by_name": dataset.get("created_by_name", "Unknown"),
                    "access_group": dataset["access_group"],
                    "team_members": dataset["team_members"] or [],
                    "document_count": dataset["document_count"] or 0,
                    "chunk_count": dataset["chunk_count"] or 0,
                    "vector_count": dataset["vector_count"] or 0,
                    "storage_size_mb": actual_storage_mb,
                    "tags": tags,
                    "created_at": dataset["created_at"].isoformat() if dataset["created_at"] else None,
                    "updated_at": dataset["updated_at"].isoformat() if dataset["updated_at"] else None,
                    "metadata": dataset["metadata"] or {},
                    "can_edit": can_edit,
                    "can_delete": can_delete,
                    "is_owner": is_owner
                })

            logger.info(f"Retrieved {len(datasets)} owned datasets from PostgreSQL for user {user_id}")
            return datasets
            
        except Exception as e:
            logger.error(f"Error getting owned datasets: {e}")
            return []
    
    async def get_team_datasets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get datasets shared with user via team access using PostgreSQL"""
        try:
            # Validate user_id to prevent UUID casting errors
            if not user_id or not user_id.strip():
                logger.error(f"get_team_datasets called with empty user_id: '{user_id}'")
                return []
            pg_client = await get_postgresql_client()
            
            query = """
                SELECT
                    d.id, d.name, d.description, d.created_by as owner_id, d.access_group, d.team_members,
                    COALESCE(doc_stats.document_count, 0) as document_count,
                    COALESCE(chunk_stats.chunk_count, 0) as chunk_count,
                    COALESCE(chunk_stats.chunk_count, 0) as vector_count,
                    (COALESCE(doc_stats.total_size_bytes, 0) +
                     COALESCE(chunk_stats.chunk_content_bytes, 0) +
                     COALESCE(chunk_stats.embedding_bytes, 0))/1024.0/1024.0 as storage_size_mb,
                    COALESCE(d.metadata->>'tags', '[]')::jsonb as tags, d.created_at, d.updated_at, d.metadata,
                    d.summary, d.summary_generated_at
                FROM datasets d
                LEFT JOIN (
                    SELECT dataset_id, COUNT(*) as document_count, SUM(file_size_bytes) as total_size_bytes
                    FROM documents
                    WHERE dataset_id IS NOT NULL
                    GROUP BY dataset_id
                ) doc_stats ON d.id = doc_stats.dataset_id
                LEFT JOIN (
                    SELECT d2.dataset_id,
                           COUNT(dc.*) as chunk_count,
                           COALESCE(SUM(LENGTH(dc.content)), 0) as chunk_content_bytes,
                           COUNT(dc.*) * 4096 as embedding_bytes
                    FROM documents d2
                    LEFT JOIN document_chunks dc ON d2.id = dc.document_id
                    WHERE d2.dataset_id IS NOT NULL
                    GROUP BY d2.dataset_id
                ) chunk_stats ON d.id = chunk_stats.dataset_id
                WHERE LOWER(d.access_group) = 'team'
                  AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                  AND d.created_by != (SELECT id FROM users WHERE email = $1)
                  AND (SELECT id FROM users WHERE email = $1) = ANY(d.team_members)
                ORDER BY d.updated_at DESC
            """
            
            datasets_data = await pg_client.execute_query(query, user_id, self.tenant_domain)
            
            # Convert to proper format
            datasets = []
            for dataset in datasets_data:
                # Parse tags from JSONB
                tags = dataset["tags"]
                if isinstance(tags, str):
                    tags = json.loads(tags)
                elif tags is None:
                    tags = []
                    
                # Apply infrastructure overhead multiplier for accurate storage representation
                logical_storage_mb = float(dataset["storage_size_mb"] or 0)
                actual_storage_mb = logical_storage_mb * DATASET_STORAGE_MULTIPLIER

                datasets.append({
                    "id": str(dataset["id"]),
                    "name": dataset["name"],
                    "description": dataset["description"],
                    "owner_id": str(dataset["owner_id"]),
                    "access_group": dataset["access_group"],
                    "team_members": dataset["team_members"] or [],
                    "document_count": dataset["document_count"] or 0,
                    "chunk_count": dataset["chunk_count"] or 0,
                    "vector_count": dataset["vector_count"] or 0,
                    "storage_size_mb": actual_storage_mb,
                    "tags": tags,
                    "created_at": dataset["created_at"].isoformat() if dataset["created_at"] else None,
                    "updated_at": dataset["updated_at"].isoformat() if dataset["updated_at"] else None,
                    "metadata": dataset["metadata"] or {}
                })

            logger.info(f"Retrieved {len(datasets)} team datasets from PostgreSQL for user {user_id}")
            return datasets

        except Exception as e:
            logger.error(f"Error getting team datasets: {e}")
            return []

    async def get_team_shared_datasets(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get datasets shared to teams where user is a member (via user_accessible_resources view).

        Uses the user_accessible_resources view for efficient lookups.

        Returns datasets with permission flags:
        - can_edit: True if user has 'edit' permission for this dataset
        - can_delete: False (only owner can delete)
        - is_owner: False (team-shared datasets)
        - shared_via_team: True (indicates team sharing)
        - shared_in_teams: Number of teams this dataset is shared with
        """
        try:
            if not user_id or not user_id.strip():
                logger.error(f"get_team_shared_datasets called with empty user_id: '{user_id}'")
                return []

            pg_client = await get_postgresql_client()

            # Query datasets using the efficient user_accessible_resources view
            # This view joins team_memberships -> team_resource_shares -> datasets
            query = """
                SELECT DISTINCT
                    d.id, d.name, d.description, d.created_by as owner_id, d.access_group, d.team_members,
                    u.full_name as created_by_name,
                    COALESCE(doc_stats.document_count, 0) as document_count,
                    COALESCE(chunk_stats.chunk_count, 0) as chunk_count,
                    COALESCE(chunk_stats.chunk_count, 0) as vector_count,
                    (COALESCE(doc_stats.total_size_bytes, 0) +
                     COALESCE(chunk_stats.chunk_content_bytes, 0) +
                     COALESCE(chunk_stats.embedding_bytes, 0))/1024.0/1024.0 as storage_size_mb,
                    COALESCE(d.metadata->>'tags', '[]')::jsonb as tags,
                    d.created_at, d.updated_at, d.metadata,
                    d.summary, d.summary_generated_at,
                    uar.best_permission as user_permission,
                    uar.shared_in_teams,
                    uar.team_ids
                FROM user_accessible_resources uar
                INNER JOIN datasets d ON d.id = uar.resource_id
                LEFT JOIN users u ON d.created_by = u.id
                LEFT JOIN (
                    SELECT dataset_id, COUNT(*) as document_count, SUM(file_size_bytes) as total_size_bytes
                    FROM documents
                    WHERE dataset_id IS NOT NULL
                    GROUP BY dataset_id
                ) doc_stats ON d.id = doc_stats.dataset_id
                LEFT JOIN (
                    SELECT d2.dataset_id,
                           COUNT(dc.*) as chunk_count,
                           COALESCE(SUM(LENGTH(dc.content)), 0) as chunk_content_bytes,
                           COUNT(dc.*) * 4096 as embedding_bytes
                    FROM documents d2
                    LEFT JOIN document_chunks dc ON d2.id = dc.document_id
                    WHERE d2.dataset_id IS NOT NULL
                    GROUP BY d2.dataset_id
                ) chunk_stats ON d.id = chunk_stats.dataset_id
                WHERE uar.user_id = $1::uuid
                  AND uar.resource_type = 'dataset'
                  AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                ORDER BY d.updated_at DESC
            """

            datasets_data = await pg_client.execute_query(query, user_id, self.tenant_domain)

            # Format datasets with team sharing metadata
            datasets = []
            for dataset in datasets_data:
                # Parse tags from JSONB
                tags = dataset["tags"]
                if isinstance(tags, str):
                    tags = json.loads(tags)
                elif tags is None:
                    tags = []

                # Get permission from view (will be "read" or "edit")
                user_permission = dataset.get("user_permission")
                can_edit = user_permission == "edit"

                # Get team sharing metadata
                shared_in_teams = dataset.get("shared_in_teams", 0)
                team_ids = dataset.get("team_ids", [])

                # Apply infrastructure overhead multiplier for accurate storage representation
                logical_storage_mb = float(dataset["storage_size_mb"] or 0)
                actual_storage_mb = logical_storage_mb * DATASET_STORAGE_MULTIPLIER

                datasets.append({
                    "id": str(dataset["id"]),
                    "name": dataset["name"],
                    "description": dataset["description"],
                    "owner_id": str(dataset["owner_id"]),
                    "created_by_name": dataset.get("created_by_name", "Unknown"),
                    "access_group": dataset["access_group"],
                    "team_members": dataset["team_members"] or [],
                    "document_count": dataset["document_count"] or 0,
                    "chunk_count": dataset["chunk_count"] or 0,
                    "vector_count": dataset["vector_count"] or 0,
                    "storage_size_mb": actual_storage_mb,
                    "tags": tags,
                    "created_at": dataset["created_at"].isoformat() if dataset["created_at"] else None,
                    "updated_at": dataset["updated_at"].isoformat() if dataset["updated_at"] else None,
                    "metadata": dataset["metadata"] or {},
                    "can_edit": can_edit,
                    "can_delete": False,  # Only owner can delete
                    "is_owner": False,  # Team-shared datasets
                    "shared_via_team": True,
                    "shared_in_teams": shared_in_teams,
                    "team_ids": [str(tid) for tid in team_ids] if team_ids else [],
                    "team_permission": user_permission
                })

            logger.info(f"Retrieved {len(datasets)} team-shared datasets for user {user_id}")
            return datasets

        except Exception as e:
            logger.error(f"Error fetching team-shared datasets for user {user_id}: {e}")
            return []

    async def get_org_datasets(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get datasets shared with entire organization using PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()

            query = """
                SELECT
                    d.id, d.name, d.description, d.created_by as owner_id, d.access_group, d.team_members,
                    COALESCE(doc_stats.document_count, 0) as document_count,
                    COALESCE(chunk_stats.chunk_count, 0) as chunk_count,
                    COALESCE(chunk_stats.chunk_count, 0) as vector_count,
                    (COALESCE(doc_stats.total_size_bytes, 0) +
                     COALESCE(chunk_stats.chunk_content_bytes, 0) +
                     COALESCE(chunk_stats.embedding_bytes, 0))/1024.0/1024.0 as storage_size_mb,
                    COALESCE(d.metadata->>'tags', '[]')::jsonb as tags, d.created_at, d.updated_at, d.metadata,
                    d.summary, d.summary_generated_at
                FROM datasets d
                LEFT JOIN (
                    SELECT dataset_id, COUNT(*) as document_count, SUM(file_size_bytes) as total_size_bytes
                    FROM documents
                    WHERE dataset_id IS NOT NULL
                    GROUP BY dataset_id
                ) doc_stats ON d.id = doc_stats.dataset_id
                LEFT JOIN (
                    SELECT d2.dataset_id,
                           COUNT(dc.*) as chunk_count,
                           COALESCE(SUM(LENGTH(dc.content)), 0) as chunk_content_bytes,
                           COUNT(dc.*) * 4096 as embedding_bytes
                    FROM documents d2
                    LEFT JOIN document_chunks dc ON d2.id = dc.document_id
                    WHERE d2.dataset_id IS NOT NULL
                    GROUP BY d2.dataset_id
                ) chunk_stats ON d.id = chunk_stats.dataset_id
                WHERE LOWER(d.access_group) = 'organization'
                  AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $1)
                ORDER BY d.updated_at DESC
            """
            
            datasets_data = await pg_client.execute_query(query, self.tenant_domain)
            
            # Convert to proper format
            datasets = []
            for dataset in datasets_data:
                # Parse tags from JSONB
                tags = dataset["tags"]
                if isinstance(tags, str):
                    tags = json.loads(tags)
                elif tags is None:
                    tags = []

                # Apply infrastructure overhead multiplier for accurate storage representation
                logical_storage_mb = float(dataset["storage_size_mb"] or 0)
                actual_storage_mb = logical_storage_mb * DATASET_STORAGE_MULTIPLIER

                datasets.append({
                    "id": str(dataset["id"]),
                    "name": dataset["name"],
                    "description": dataset["description"],
                    "owner_id": str(dataset["owner_id"]),
                    "access_group": dataset["access_group"],
                    "team_members": dataset["team_members"] or [],
                    "document_count": dataset["document_count"] or 0,
                    "chunk_count": dataset["chunk_count"] or 0,
                    "vector_count": dataset["vector_count"] or 0,
                    "storage_size_mb": actual_storage_mb,
                    "tags": tags,
                    "created_at": dataset["created_at"].isoformat() if dataset["created_at"] else None,
                    "updated_at": dataset["updated_at"].isoformat() if dataset["updated_at"] else None,
                    "metadata": dataset["metadata"] or {}
                })

            logger.info(f"Retrieved {len(datasets)} org datasets from PostgreSQL")
            return datasets
            
        except Exception as e:
            logger.error(f"Error getting org datasets: {e}")
            return []
    
    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get specific dataset by ID using PostgreSQL with team-based access control"""
        try:
            pg_client = await get_postgresql_client()

            # Get user ID
            user_lookup_query = """
                SELECT id FROM users
                WHERE (email = $1 OR id::text = $1 OR username = $1)
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                LIMIT 1
            """
            user_id = await pg_client.fetch_scalar(user_lookup_query, self.user_email, self.tenant_domain)
            if not user_id:
                user_id = await pg_client.fetch_scalar(user_lookup_query, self.user_id, self.tenant_domain)

            if not user_id:
                logger.warning(f"User not found: {self.user_email} in tenant {self.tenant_domain}")
                return None

            # Check if admin
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Query the dataset
            query = """
                SELECT
                    id, name, description, created_by as owner_id, access_group, team_members,
                    document_count, 0 as chunk_count, 0 as vector_count, total_size_bytes/1024/1024 as storage_size_mb,
                    COALESCE(metadata->>'tags', '[]')::jsonb as tags, created_at, updated_at, metadata
                FROM datasets
                WHERE id = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                LIMIT 1
            """

            dataset_data = await pg_client.fetch_one(query, dataset_id, self.tenant_domain)

            if not dataset_data:
                return None

            # Check access: admin, owner, organization, or team-based
            if not is_admin:
                is_owner = str(dataset_data["owner_id"]) == str(user_id)
                access_group = dataset_data["access_group"]
                is_org_wide = access_group and access_group.upper() == "ORGANIZATION"

                # Check team-based access if not owner or org-wide
                if not is_owner and not is_org_wide:
                    from app.services.team_service import TeamService
                    team_service = TeamService(self.tenant_domain, str(user_id), self.user_email)

                    has_team_access = await team_service.check_user_resource_permission(
                        user_id=str(user_id),
                        resource_type="dataset",
                        resource_id=dataset_id,
                        required_permission="read"
                    )

                    if not has_team_access:
                        logger.warning(f"User {user_id} denied access to dataset {dataset_id}")
                        return None

                    logger.info(f"User {user_id} has team-based access to dataset {dataset_id}")
                
            # Parse tags from JSONB
            tags = dataset_data["tags"]
            if isinstance(tags, str):
                tags = json.loads(tags)
            elif tags is None:
                tags = []
                
            dataset = {
                "id": str(dataset_data["id"]),
                "name": dataset_data["name"],
                "description": dataset_data["description"],
                "owner_id": str(dataset_data["owner_id"]),
                "access_group": dataset_data["access_group"],
                "team_members": dataset_data["team_members"] or [],
                "document_count": dataset_data["document_count"] or 0,
                "chunk_count": dataset_data["chunk_count"] or 0,
                "vector_count": dataset_data["vector_count"] or 0,
                "storage_size_mb": float(dataset_data["storage_size_mb"] or 0),
                "tags": tags,
                "created_at": dataset_data["created_at"].isoformat() if dataset_data["created_at"] else None,
                "updated_at": dataset_data["updated_at"].isoformat() if dataset_data["updated_at"] else None,
                "metadata": dataset_data["metadata"] or {}
            }
            
            logger.debug(f"Retrieved dataset {dataset_id} from PostgreSQL")
            return dataset
                
        except Exception as e:
            logger.error(f"Error getting dataset {dataset_id}: {e}")
            return None
    
    async def create_dataset(self, dataset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new dataset using PostgreSQL with permission checks"""
        try:
            pg_client = await get_postgresql_client()

            # Get user role and validate visibility permission
            access_group = dataset_data.get("access_group", "INDIVIDUAL")
            visibility = access_group.lower()  # Convert to lowercase for permission check

            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            validate_visibility_permission(visibility, user_role)
            logger.info(f"User {self.user_email} (role: {user_role}) creating dataset with visibility: {visibility}")

            # Create dataset in PostgreSQL
            query = """
                INSERT INTO datasets (
                    id, name, description, created_by, tenant_id, access_group,
                    team_members, metadata, document_count, total_size_bytes, collection_name, is_active
                ) VALUES (
                    $1, $2, $3,
                    (SELECT id FROM users WHERE email = $4),
                    (SELECT id FROM tenants WHERE domain = $5),
                    $6, $7, $8, $9, $10, $11, $12
                )
                RETURNING id, name, description, created_by as owner_id, access_group, team_members,
                          COALESCE(metadata->>'tags', '[]')::jsonb as tags, metadata, 
                          document_count, 0 as chunk_count, 0 as vector_count,
                          total_size_bytes/1024/1024 as storage_size_mb, created_at, updated_at, is_active
            """
            
            # Prepare metadata with tags
            metadata = dataset_data.get("metadata", {})
            metadata["tags"] = dataset_data.get("tags", [])
            
            # Generate collection name for ChromaDB compatibility
            collection_name = f"dataset_{dataset_data['id'].replace('-', '_')}"
            
            result = await pg_client.fetch_one(
                query,
                dataset_data["id"], dataset_data["name"], dataset_data.get("description"),
                dataset_data["owner_id"], self.tenant_domain, dataset_data["access_group"],
                dataset_data.get("team_members", []), json.dumps(metadata),
                dataset_data.get("document_count", 0), 
                int(dataset_data.get("storage_size_mb", 0.0) * 1024 * 1024),  # Convert MB to bytes
                collection_name, True  # is_active = True
            )
            
            if not result:
                raise RuntimeError("Failed to create dataset - no data returned")
            
            # Convert to proper format
            # Parse tags from JSONB
            tags = result["tags"]
            if isinstance(tags, str):
                tags = json.loads(tags)
            elif tags is None:
                tags = []
                
            created_dataset = {
                "id": str(result["id"]),
                "name": result["name"],
                "description": result["description"],
                "owner_id": str(result["owner_id"]),
                "access_group": result["access_group"],
                "team_members": result["team_members"] or [],
                "tags": tags,
                "metadata": result["metadata"] or {},
                "document_count": result["document_count"] or 0,
                "chunk_count": result["chunk_count"] or 0,
                "vector_count": result["vector_count"] or 0,
                "storage_size_mb": float(result["storage_size_mb"] or 0),
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat()
            }
            
            logger.info(f"Created dataset {dataset_data['id']} in PostgreSQL")
            return created_dataset
            
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            raise
    
    async def update_dataset(self, dataset_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing dataset using PostgreSQL with permission checks"""
        try:
            pg_client = await get_postgresql_client()

            # Get user role for permission checks
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)

            # If updating access_group (visibility), validate permission
            if "access_group" in update_data:
                visibility = update_data["access_group"].lower()
                validate_visibility_permission(visibility, user_role)
                logger.info(f"User {self.user_email} (role: {user_role}) updating dataset visibility to: {visibility}")

            # Build dynamic UPDATE query based on provided updates
            set_clauses = []
            params = []
            param_idx = 1

            # Handle each update field
            for field, value in update_data.items():
                if field in ["name", "description", "access_group"]:
                    set_clauses.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field == "team_members":
                    set_clauses.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field == "tags":
                    # Tags are stored in metadata JSONB field
                    set_clauses.append(f"metadata = jsonb_set(COALESCE(metadata, '{{}}'), '{{tags}}', ${param_idx}::jsonb)")
                    params.append(json.dumps(value))
                    param_idx += 1
                elif field == "document_count":
                    set_clauses.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field in ["chunk_count", "vector_count"]:
                    # These are calculated fields, not stored directly - skip updating
                    pass
                elif field == "storage_size_mb":
                    # Convert to bytes and update total_size_bytes
                    set_clauses.append(f"total_size_bytes = ${param_idx}")
                    params.append(int(value * 1024 * 1024))  # Convert MB to bytes
                    param_idx += 1
                elif field == "metadata":
                    set_clauses.append(f"metadata = ${param_idx}::jsonb")
                    params.append(json.dumps(value))
                    param_idx += 1
            
            if not set_clauses:
                # No valid update fields, just return current dataset
                return await self.get_dataset(dataset_id)
            
            # Add updated_at timestamp
            set_clauses.append(f"updated_at = NOW()")

            # Check if user is admin - admins can update any dataset
            is_admin = user_role in ["admin", "developer"]

            # Build final query - admins can update any dataset, others only their own
            if is_admin:
                query = f"""
                    UPDATE datasets
                    SET {', '.join(set_clauses)}
                    WHERE id = ${param_idx}
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = ${param_idx + 1})
                    RETURNING id, name, description, created_by as owner_id, access_group, team_members,
                              COALESCE(metadata->>'tags', '[]')::jsonb as tags, metadata, document_count,
                              0 as chunk_count, 0 as vector_count, total_size_bytes/1024/1024 as storage_size_mb,
                              created_at, updated_at
                """
                params.extend([dataset_id, self.tenant_domain])
            else:
                query = f"""
                    UPDATE datasets
                    SET {', '.join(set_clauses)}
                    WHERE id = ${param_idx}
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = ${param_idx + 1})
                      AND created_by = (SELECT id FROM users WHERE email = ${param_idx + 2})
                    RETURNING id, name, description, created_by as owner_id, access_group, team_members,
                              COALESCE(metadata->>'tags', '[]')::jsonb as tags, metadata, document_count,
                              0 as chunk_count, 0 as vector_count, total_size_bytes/1024/1024 as storage_size_mb,
                              created_at, updated_at
                """
                params.extend([dataset_id, self.tenant_domain, self.user_email])
            
            # Execute update
            result = await pg_client.fetch_one(query, *params)
            
            if not result:
                raise ValueError(f"Dataset {dataset_id} not found or update failed")
                
            # Convert to proper format
            # Parse tags from JSONB
            tags = result["tags"]
            if isinstance(tags, str):
                tags = json.loads(tags)
            elif tags is None:
                tags = []
                
            updated_dataset = {
                "id": str(result["id"]),
                "name": result["name"],
                "description": result["description"],
                "owner_id": str(result["owner_id"]),
                "access_group": result["access_group"],
                "team_members": result["team_members"] or [],
                "tags": tags,
                "metadata": result["metadata"] or {},
                "document_count": result["document_count"] or 0,
                "chunk_count": result["chunk_count"] or 0,
                "vector_count": result["vector_count"] or 0,
                "storage_size_mb": float(result["storage_size_mb"] or 0),
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat()
            }
            
            logger.info(f"Updated dataset {dataset_id} in PostgreSQL")
            return updated_dataset
            
        except Exception as e:
            logger.error(f"Error updating dataset {dataset_id}: {e}")
            raise
    
    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete dataset and associated files using PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()

            # Get user role to check if admin
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Delete in PostgreSQL - admins can delete any dataset, others only their own
            if is_admin:
                query = """
                    DELETE FROM datasets
                    WHERE id = $1
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                    RETURNING id
                """
                deleted_id = await pg_client.fetch_scalar(query, dataset_id, self.tenant_domain)
            else:
                query = """
                    DELETE FROM datasets
                    WHERE id = $1
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                      AND created_by = (SELECT id FROM users WHERE email = $3)
                    RETURNING id
                """
                deleted_id = await pg_client.fetch_scalar(query, dataset_id, self.tenant_domain, self.user_email)
            
            if deleted_id:
                logger.info(f"Deleted dataset {dataset_id} from PostgreSQL")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting dataset {dataset_id}: {e}")
            raise
    
    async def can_user_access_dataset(self, user_id: str, dataset_id: str) -> bool:
        """Check if user can access dataset using PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()
            
            query = """
                SELECT COUNT(*) as has_access
                FROM datasets d
                WHERE d.id = $1
                  AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $3)
                  AND (
                    -- Owner access
                    d.created_by = (SELECT id FROM users WHERE email = $2)
                    OR
                    -- Team access
                    (LOWER(d.access_group) = 'team' AND (SELECT id FROM users WHERE email = $2) = ANY(d.team_members))
                    OR
                    -- Organization access
                    LOWER(d.access_group) = 'organization'
                  )
            """
            
            result = await pg_client.fetch_one(query, dataset_id, user_id, self.tenant_domain)
            
            has_access = result and result["has_access"] > 0
            logger.debug(f"User {user_id} access to dataset {dataset_id}: {has_access}")
            return has_access
            
        except Exception as e:
            logger.error(f"Error checking access for dataset {dataset_id}: {e}")
            return False
    
    async def can_user_modify_dataset(self, user_id: str, dataset_id: str) -> bool:
        """Check if user can modify dataset (owner or admin/developer) using PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()

            # Get user role
            from app.core.permissions import get_user_role
            user_role = await get_user_role(pg_client, user_id, self.tenant_domain)

            # Admin and developer can modify any dataset
            if user_role in ["admin", "developer"]:
                logger.info(f"User {user_id} with role {user_role} has admin permission to modify dataset {dataset_id}")
                return True

            # Check if user is owner
            query = """
                SELECT COUNT(*) as is_owner
                FROM datasets d
                WHERE d.id = $1
                  AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $3)
                  AND d.created_by = (SELECT id FROM users WHERE email = $2)
            """

            result = await pg_client.fetch_one(query, dataset_id, user_id, self.tenant_domain)

            is_owner = result and result["is_owner"] > 0
            logger.info(f"User {user_id} ownership check for dataset {dataset_id}: {is_owner}")
            return is_owner

        except Exception as e:
            logger.error(f"Error checking modify access for dataset {dataset_id}: {e}")
            return False
    
    async def add_documents_to_dataset(self, dataset_id: str, document_ids: List[str]) -> Dict[str, Any]:
        """Add documents to dataset using PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()
            
            # Get current document IDs from dataset
            dataset = await self.get_dataset(dataset_id)
            if not dataset:
                raise ValueError(f"Dataset {dataset_id} not found")
            
            current_docs = dataset.get("metadata", {}).get("document_ids", [])
            new_docs = [doc_id for doc_id in document_ids if doc_id not in current_docs]
            
            if new_docs:
                # Update dataset metadata with new document IDs
                updated_metadata = dataset.get("metadata", {})
                updated_metadata["document_ids"] = current_docs + new_docs
                
                update_data = {
                    "metadata": updated_metadata,
                    "document_count": len(updated_metadata["document_ids"])
                }
                
                await self.update_dataset(dataset_id, update_data)
                
                logger.info(f"Added {len(new_docs)} documents to dataset {dataset_id}")
            
            return {
                "added": new_docs,
                "failed": [],
                "total_documents": len(current_docs + new_docs)
            }
            
        except Exception as e:
            logger.error(f"Error adding documents to dataset {dataset_id}: {e}")
            raise
    
    async def get_dataset_stats(self, dataset_id: str) -> Dict[str, Any]:
        """Get detailed dataset statistics using PostgreSQL"""
        try:
            dataset = await self.get_dataset(dataset_id)
            if not dataset:
                raise ValueError(f"Dataset {dataset_id} not found")
            
            # Basic stats from PostgreSQL
            stats = {
                "dataset_id": dataset_id,
                "name": dataset.get("name"),
                "document_count": dataset.get("document_count", 0),
                "chunk_count": dataset.get("chunk_count", 0),
                "vector_count": dataset.get("vector_count", 0),
                "storage_size_mb": dataset.get("storage_size_mb", 0.0),
                "created_at": dataset.get("created_at"),
                "updated_at": dataset.get("updated_at"),
                "access_group": dataset.get("access_group"),
                "team_member_count": len(dataset.get("team_members", [])),
                "tags": dataset.get("tags", [])
            }
            
            # TODO: Add real-time stats from PGVector document_chunks table
            # pg_client = await get_postgresql_client()
            # realtime_query = """
            #     SELECT COUNT(*) as chunk_count, 
            #            AVG(vector_dims(embedding)) as avg_dimensions
            #     FROM document_chunks
            #     WHERE dataset_id = $1
            # """
            
            return stats

        except Exception as e:
            logger.error(f"Error getting dataset stats {dataset_id}: {e}")
            raise

    async def get_complete_user_summary(self, user_id: str) -> Dict[str, Any]:
        """Get complete summary statistics including all documents (assigned and unassigned)"""
        try:
            # Validate user_id is not empty
            if not user_id or not user_id.strip():
                raise ValueError(f"Empty or invalid user_id provided: '{user_id}'")

            pg_client = await get_postgresql_client()

            # Get user UUID from email
            user_uuid_query = "SELECT id FROM users WHERE email = $1"
            user_uuid_result = await pg_client.fetch_one(user_uuid_query, user_id.strip())
            if not user_uuid_result:
                raise ValueError(f"User not found: {user_id}")
            user_uuid = str(user_uuid_result["id"])

            # Get user role for permission checks
            user_role = await get_user_role(pg_client, user_id, self.tenant_domain)
            is_admin = user_role in ["admin", "developer", "super_admin"]

            # Get all datasets accessible to user
            datasets = []
            datasets.extend(await self.get_owned_datasets(user_id))
            datasets.extend(await self.get_team_datasets(user_id))
            datasets.extend(await self.get_org_datasets(self.tenant_domain))

            # Remove duplicates
            unique_datasets = {}
            for dataset in datasets:
                unique_datasets[dataset["id"]] = dataset

            # Calculate dataset statistics - Using effective ownership (admins count as owners)
            total_datasets = len(unique_datasets)
            owned_datasets = sum(1 for d in unique_datasets.values() if is_effective_owner(str(d.get("owner_id")), user_uuid, user_role))
            team_datasets = sum(1 for d in unique_datasets.values() if d.get("access_group") == "team" and not is_effective_owner(str(d.get("owner_id")), user_uuid, user_role))
            org_datasets = sum(1 for d in unique_datasets.values() if d.get("access_group") == "organization" and not is_effective_owner(str(d.get("owner_id")), user_uuid, user_role))

            # Get user's document storage (including chunk content and embeddings)
            user_docs_query = """
                SELECT
                    COUNT(*) as total_documents,
                    (COALESCE(SUM(d.file_size_bytes), 0) +
                     COALESCE((SELECT SUM(LENGTH(dc.content)) FROM document_chunks dc
                               WHERE dc.document_id IN (SELECT id FROM documents WHERE user_id = (SELECT id FROM users WHERE email = $1))), 0) +
                     COALESCE((SELECT COUNT(*) * 4096 FROM document_chunks dc
                               WHERE dc.document_id IN (SELECT id FROM documents WHERE user_id = (SELECT id FROM users WHERE email = $1))), 0)
                    )/1024.0/1024.0 as doc_storage_mb
                FROM documents d
                WHERE d.user_id = (SELECT id FROM users WHERE email = $1)
            """
            user_docs_result = await pg_client.fetch_one(user_docs_query, user_id)

            # Get user's dataset metadata storage (datasets owned by this user)
            user_datasets_query = """
                SELECT
                    COALESCE(SUM(total_size_bytes), 0)/1024.0/1024.0 as dataset_storage_mb
                FROM datasets
                WHERE created_by = (SELECT id FROM users WHERE email = $1)
            """
            user_datasets_result = await pg_client.fetch_one(user_datasets_query, user_id)

            # Calculate total personal storage (documents + dataset metadata)
            # Apply infrastructure overhead multiplier for accurate storage representation
            personal_storage_mb_logical = float(user_docs_result["doc_storage_mb"] or 0) + float(user_datasets_result["dataset_storage_mb"] or 0)
            personal_storage_mb = personal_storage_mb_logical * DATASET_STORAGE_MULTIPLIER

            # Base summary for all users
            summary = {
                "total_datasets": total_datasets,
                "owned_datasets": owned_datasets,
                "team_datasets": team_datasets,
                "org_datasets": org_datasets,
                "total_documents": user_docs_result["total_documents"] or 0,
                "total_storage_mb": personal_storage_mb,
                "is_admin": is_admin
            }

            # Add admin-specific total tenant storage
            if is_admin:
                # Tenant document storage (including chunk content and embeddings)
                tenant_docs_query = """
                    SELECT (
                        COALESCE(SUM(d.file_size_bytes), 0) +
                        COALESCE((SELECT SUM(LENGTH(dc.content)) FROM document_chunks dc
                                  JOIN documents doc ON dc.document_id = doc.id
                                  JOIN users u2 ON doc.user_id = u2.id
                                  JOIN tenants t2 ON u2.tenant_id = t2.id
                                  WHERE t2.domain = $1), 0) +
                        COALESCE((SELECT COUNT(*) * 4096 FROM document_chunks dc
                                  JOIN documents doc ON dc.document_id = doc.id
                                  JOIN users u2 ON doc.user_id = u2.id
                                  JOIN tenants t2 ON u2.tenant_id = t2.id
                                  WHERE t2.domain = $1), 0)
                    )/1024.0/1024.0 as total_docs_mb
                    FROM documents d
                    JOIN users u ON d.user_id = u.id
                    JOIN tenants t ON u.tenant_id = t.id
                    WHERE t.domain = $1
                """
                tenant_docs_result = await pg_client.fetch_one(tenant_docs_query, self.tenant_domain)

                tenant_datasets_query = """
                    SELECT COALESCE(SUM(total_size_bytes), 0)/1024.0/1024.0 as total_datasets_mb
                    FROM datasets d
                    JOIN tenants t ON d.tenant_id = t.id
                    WHERE t.domain = $1
                """
                tenant_datasets_result = await pg_client.fetch_one(tenant_datasets_query, self.tenant_domain)

                # Apply infrastructure overhead multiplier for accurate storage representation
                total_tenant_storage_mb_logical = float(tenant_docs_result["total_docs_mb"] or 0) + float(tenant_datasets_result["total_datasets_mb"] or 0)
                total_tenant_storage_mb = total_tenant_storage_mb_logical * DATASET_STORAGE_MULTIPLIER
                summary["total_tenant_storage_mb"] = total_tenant_storage_mb

            logger.info(f"Complete summary for {user_id}: {summary['total_documents']} total docs, {summary['total_datasets']} datasets ({owned_datasets} owned), {personal_storage_mb:.2f}MB personal storage")
            return summary

        except Exception as e:
            logger.error(f"Error getting complete user summary: {e}")
            return {
                "total_datasets": 0,
                "owned_datasets": 0,
                "team_datasets": 0,
                "org_datasets": 0,
                "total_documents": 0,
                "assigned_documents": 0,
                "unassigned_documents": 0,
                "total_storage_mb": 0,
                "assigned_storage_mb": 0,
                "unassigned_storage_mb": 0
            }