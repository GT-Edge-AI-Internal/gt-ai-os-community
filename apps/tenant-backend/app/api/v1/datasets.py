"""
Dataset CRUD API for GT 2.0
Provides access-controlled dataset management with tenant isolation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.core.response_filter import ResponseFilter
from app.api.v1.search import get_user_context
from app.models.access_group import AccessGroup, Resource
from app.services.dataset_service import DatasetService
from app.services.dataset_summarizer import DatasetSummarizer
from app.services.agent_service import AgentService
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])

# Request/Response Models
class CreateDatasetRequest(BaseModel):
    """Request to create a new dataset"""
    name: str = Field(..., min_length=1, max_length=100, description="Dataset name")
    description: Optional[str] = Field(None, max_length=500, description="Dataset description")
    access_group: AccessGroup = Field(AccessGroup.INDIVIDUAL, description="Access level")
    team_members: Optional[List[str]] = Field(None, description="Team members for TEAM access")
    tags: Optional[List[str]] = Field(None, description="Dataset tags")
    team_shares: Optional[List[Dict[str, Any]]] = Field(None, description="Team sharing configuration with per-user permissions")
    
class UpdateDatasetRequest(BaseModel):
    """Request to update a dataset"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    access_group: Optional[AccessGroup] = None
    team_members: Optional[List[str]] = None
    chunking_strategy: Optional[str] = Field(None, description="Chunking strategy: hybrid, semantic, or fixed")
    chunk_size: Optional[int] = Field(None, ge=100, le=2000, description="Chunk size in tokens")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=200, description="Chunk overlap in tokens")
    embedding_model: Optional[str] = Field(None, description="Embedding model name")
    team_shares: Optional[List[Dict[str, Any]]] = Field(None, description="Update team sharing configuration")

class ShareDatasetRequest(BaseModel):
    """Request to share a dataset"""
    access_group: AccessGroup = Field(..., description="New access level")
    team_members: Optional[List[str]] = Field(None, description="Team members for TEAM access")

class DatasetResponse(BaseModel):
    """Dataset response model"""
    id: str
    name: str
    description: Optional[str]
    owner_id: Optional[str] = None  # Only visible to owners (security filtered)
    created_by_name: Optional[str] = None  # Full name of the creator
    owner_name: Optional[str] = None  # Alias for frontend compatibility
    access_group: str
    team_members: Optional[List[str]] = None  # Only visible to owners (security filtered)
    document_count: int
    chunk_count: int  # Stats visible to all (informational, not sensitive)
    vector_count: int
    storage_size_mb: float
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    # Chunking configuration (only visible to owners - security filtered)
    chunking_strategy: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    embedding_model: Optional[str] = None

    # Dataset summary (visible to viewers and owners)
    summary: Optional[str] = None
    summary_generated_at: Optional[datetime] = None

    # Access indicators for UI (always present)
    is_owner: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_share: bool = False

    # Team sharing indicators
    shared_via_team: Optional[bool] = Field(None, description="True if user is viewing this via team share (not as owner)")
    team_shares: Optional[List[Dict[str, Any]]] = Field(None, description="Team sharing configuration with per-user permissions")

    # Internal fields - only for specific use cases (security filtered)
    agent_has_access: Optional[bool] = None
    user_owns: Optional[bool] = None


@router.get("/", response_model=List[DatasetResponse])
async def list_datasets(
    access_filter: Optional[str] = Query(None, description="Filter: all|mine|team|org"),
    include_stats: bool = Query(True, description="Include document/vector counts"),
    current_user: Dict = Depends(get_current_user)
) -> List[DatasetResponse]:
    """
    List datasets based on user access rights
    """
    try:
        # Enhanced logging for authentication troubleshooting
        logger.info(f"🔍 list_datasets called with current_user keys: {list(current_user.keys())}")
        logger.info(f"🔍 list_datasets current_user content: {current_user}")

        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")

        logger.info(f"🔍 list_datasets extracted: tenant_domain='{tenant_domain}', user_email='{user_email}'")

        if not user_email:
            logger.error(f"🚨 list_datasets MISSING USER EMAIL: current_user={current_user}")
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email

        # Get user UUID for permission comparison
        from app.core.user_resolver import ensure_user_uuid
        user_uuid = await ensure_user_uuid(user_id, tenant_domain)
        
        datasets = []

        # Filter based on access level - exclusive filters for clarity
        if access_filter == "mine":
            # Only user-owned datasets (excludes org/team datasets)
            owned = await service.get_owned_datasets(user_id)
            datasets.extend(owned)
        elif access_filter == "team":
            # Only team-shared datasets (both old and new team systems)
            team_datasets = await service.get_team_datasets(user_id)
            datasets.extend(team_datasets)
            team_shared_datasets = await service.get_team_shared_datasets(user_uuid)
            datasets.extend(team_shared_datasets)
        elif access_filter == "org":
            # Only organization-wide datasets
            org_datasets = await service.get_org_datasets(tenant_domain)
            datasets.extend(org_datasets)
        else:
            # "all" or None - show everything accessible to user
            owned = await service.get_owned_datasets(user_id)
            datasets.extend(owned)
            team_datasets = await service.get_team_datasets(user_id)
            datasets.extend(team_datasets)
            team_shared_datasets = await service.get_team_shared_datasets(user_uuid)
            datasets.extend(team_shared_datasets)
            org_datasets = await service.get_org_datasets(tenant_domain)
            datasets.extend(org_datasets)

        # Get user role for permission checks
        from app.core.permissions import get_user_role, can_edit_resource, can_delete_resource, is_effective_owner

        user_role = await get_user_role(
            await __import__('app.core.postgresql_client', fromlist=['get_postgresql_client']).get_postgresql_client(),
            user_email,
            tenant_domain
        )

        # Remove duplicates first
        unique_datasets = {}
        for dataset in datasets:
            if dataset["id"] not in unique_datasets:
                unique_datasets[dataset["id"]] = dataset

        # OPTIMIZATION: Batch fetch team shares for all owned datasets (fixes N+1 query)
        # First pass: identify owned datasets
        owned_dataset_ids = []
        for dataset in unique_datasets.values():
            is_owner = is_effective_owner(dataset["owner_id"], user_uuid, user_role)
            dataset["is_owner"] = is_owner
            if is_owner:
                owned_dataset_ids.append(dataset["id"])

        # Single batch query for all team shares
        team_shares_map = {}
        if owned_dataset_ids:
            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=tenant_domain,
                user_id=user_uuid,
                user_email=user_email
            )
            raw_team_shares = await team_service.get_resource_teams_batch('dataset', owned_dataset_ids)

            # Convert to frontend format
            for dataset_id, teams in raw_team_shares.items():
                team_shares_map[dataset_id] = [
                    {
                        'team_id': team_data['id'],
                        'team_name': team_data.get('name', 'Unknown Team'),
                        'user_permissions': team_data.get('user_permissions', {})
                    }
                    for team_data in teams
                ]

        # Second pass: add permissions and team shares
        for dataset in unique_datasets.values():
            is_owner = dataset["is_owner"]

            # Use permission helper functions - admins/developers can edit/delete any resource
            dataset["can_edit"] = can_edit_resource(
                dataset["owner_id"],
                user_uuid,
                user_role,
                dataset.get("access_group", "individual").lower()
            )
            dataset["can_delete"] = can_delete_resource(
                dataset["owner_id"],
                user_uuid,
                user_role
            )
            dataset["can_share"] = is_effective_owner(dataset["owner_id"], user_uuid, user_role)

            # Map created_by_name to owner_name for frontend consistency
            if "created_by_name" in dataset:
                dataset["owner_name"] = dataset["created_by_name"]

            # Get team shares from batch lookup (instead of per-dataset query)
            dataset["team_shares"] = team_shares_map.get(dataset["id"]) if is_owner else None

            logger.info(f"🔍 Dataset '{dataset['name']}': owner={is_owner}, can_edit={dataset['can_edit']}, can_delete={dataset['can_delete']}, role={user_role}")

        # Apply security filtering to remove sensitive fields
        filtered_datasets = []
        for dataset in unique_datasets.values():
            is_owner = dataset.get("is_owner", False)
            can_view = dataset.get("can_edit", False) or is_owner

            filtered_dataset = ResponseFilter.filter_dataset_response(
                dataset,
                is_owner=is_owner,
                can_view=can_view
            )
            filtered_datasets.append(filtered_dataset)

        return filtered_datasets
        
    except Exception as e:
        logger.error(f"Error listing datasets: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


# Internal service endpoint for MCP tools
@router.get("/internal/list", response_model=List[DatasetResponse])
async def list_datasets_internal(
    user_context: Dict = Depends(get_user_context)
) -> List[DatasetResponse]:
    """
    List datasets for internal service calls (MCP tools)
    Uses X-Tenant-Domain and X-User-ID headers instead of JWT
    """
    try:
        tenant_domain = user_context.get("tenant_domain", "test")
        user_id = user_context.get("id", user_context.get("sub", ""))
        user_email = user_context.get("email", user_id)

        # Validate we have proper UUID format for user_id
        import uuid
        try:
            uuid.UUID(user_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid UUID format for user_id: {user_id}")
            raise HTTPException(400, f"Invalid user ID format: {user_id}")

        # Ensure we have a valid email for the service
        if not user_email or user_email == user_id:
            # Try to get email from database
            from app.core.postgresql_client import get_postgresql_client
            client = await get_postgresql_client()
            async with client.get_connection() as conn:
                schema_name = f"tenant_{tenant_domain.replace('.', '_').replace('-', '_')}"
                user_row = await conn.fetchrow(f"SELECT email FROM {schema_name}.users WHERE id = $1", user_id)
                if user_row:
                    user_email = user_row['email']
                else:
                    logger.warning(f"Could not find email for user_id {user_id}, using UUID as email")
                    user_email = user_id

        service = DatasetService(tenant_domain, user_email)

        # Get all datasets user has access to
        datasets = []

        # Get owned datasets
        owned = await service.get_owned_datasets(user_email)
        datasets.extend(owned)

        # Get team datasets
        team_datasets = await service.get_team_datasets(user_email)
        datasets.extend(team_datasets)

        # Get org datasets
        org_datasets = await service.get_org_datasets(tenant_domain)
        datasets.extend(org_datasets)

        # Get user role for permission checks
        from app.core.postgresql_client import get_postgresql_client
        from app.core.permissions import get_user_role, is_effective_owner

        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        # Remove duplicates and add access indicators
        unique_datasets = {}
        for dataset in datasets:
            if dataset["id"] not in unique_datasets:
                # Add access indicators using effective ownership
                is_owner = is_effective_owner(dataset["owner_id"], user_id, user_role)
                dataset["is_owner"] = is_owner
                dataset["can_edit"] = is_owner
                dataset["can_delete"] = is_owner
                dataset["can_share"] = is_owner

                # Add chunking configuration fields if not present
                if "chunking_strategy" not in dataset:
                    dataset["chunking_strategy"] = "hybrid"
                if "chunk_size" not in dataset:
                    dataset["chunk_size"] = 512
                if "chunk_overlap" not in dataset:
                    dataset["chunk_overlap"] = 50
                if "embedding_model" not in dataset:
                    dataset["embedding_model"] = "BAAI/bge-m3"

                unique_datasets[dataset["id"]] = dataset

        # Apply security filtering (internal endpoints can see more, but still filter)
        filtered_datasets = []
        for dataset in unique_datasets.values():
            is_owner = dataset.get("is_owner", False)
            # Internal endpoints get viewer-level access even if not owner
            can_view = True

            filtered_dataset = ResponseFilter.filter_dataset_response(
                dataset,
                is_owner=is_owner,
                can_view=can_view
            )
            filtered_datasets.append(filtered_dataset)

        logger.info(f"Internal service listed {len(filtered_datasets)} datasets for user {user_id}")
        return filtered_datasets

    except Exception as e:
        logger.error(f"Error in internal dataset listing: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    current_user: Dict = Depends(get_current_user)
) -> DatasetResponse:
    """Get specific dataset details"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email

        # Get user UUID for permission comparison
        from app.core.user_resolver import ensure_user_uuid
        user_uuid = await ensure_user_uuid(user_id, tenant_domain)

        dataset = await service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(404, "Dataset not found")

        # Check access
        if not await service.can_user_access_dataset(user_id, dataset_id):
            raise HTTPException(403, "Access denied")

        # Get user role for permission checks
        from app.core.postgresql_client import get_postgresql_client
        from app.core.permissions import get_user_role, is_effective_owner

        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        # Add access indicators using effective ownership
        is_owner = is_effective_owner(dataset["owner_id"], user_uuid, user_role)
        dataset["is_owner"] = is_owner
        dataset["can_edit"] = is_owner
        dataset["can_delete"] = is_owner
        dataset["can_share"] = is_owner

        # Get team shares if owner (for edit mode)
        if is_owner:
            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=tenant_domain,
                user_id=user_id,
                user_email=user_email
            )
            resource_teams = await team_service.get_resource_teams('dataset', dataset_id)

            # Convert to frontend format
            team_shares = []
            for team_data in resource_teams:
                team_shares.append({
                    'team_id': team_data['id'],  # get_resource_teams returns 'id' not 'team_id'
                    'team_name': team_data.get('name', 'Unknown Team'),
                    'user_permissions': team_data.get('user_permissions', {})
                })
            dataset["team_shares"] = team_shares
        else:
            dataset["team_shares"] = None

        # Add chunking configuration fields if not present
        if "chunking_strategy" not in dataset:
            dataset["chunking_strategy"] = "hybrid"
        if "chunk_size" not in dataset:
            dataset["chunk_size"] = 512
        if "chunk_overlap" not in dataset:
            dataset["chunk_overlap"] = 50
        if "embedding_model" not in dataset:
            dataset["embedding_model"] = "BAAI/bge-m3"

        # Apply security filtering
        can_view = True  # User can access dataset if they got this far
        filtered_dataset = ResponseFilter.filter_dataset_response(
            dataset,
            is_owner=is_owner,
            can_view=can_view
        )

        return filtered_dataset
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.get("/{dataset_id}/summary")
async def get_dataset_summary(
    dataset_id: str,
    force_regenerate: bool = Query(False, description="Force regeneration of summary"),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get AI-generated summary for a dataset"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email

        # Check access
        if not await service.can_user_access_dataset(user_id, dataset_id):
            raise HTTPException(403, "Access denied")

        # Initialize summarizer
        summarizer = DatasetSummarizer()

        # Generate or retrieve summary
        summary_result = await summarizer.generate_dataset_summary(
            dataset_id=dataset_id,
            tenant_domain=tenant_domain,
            user_id=user_id,
            force_regenerate=force_regenerate
        )

        # Map the DatasetSummarizer response to the expected frontend structure
        if isinstance(summary_result, dict):
            # Extract the relevant fields from the summary result
            formatted_response = {
                "summary": summary_result.get("overview", "No summary available"),
                "key_topics": [],
                "common_themes": [],
                "search_optimization_tips": []
            }

            # Extract topics from the topics analysis
            if "topics" in summary_result and isinstance(summary_result["topics"], dict):
                formatted_response["key_topics"] = summary_result["topics"].get("main_topics", [])[:10]

            # Extract recommendations as search optimization tips
            if "recommendations" in summary_result and isinstance(summary_result["recommendations"], list):
                formatted_response["search_optimization_tips"] = summary_result["recommendations"]

            # Include statistics if available
            if "statistics" in summary_result:
                formatted_response["statistics"] = summary_result["statistics"]

            # Include metadata
            if "metadata" in summary_result:
                formatted_response["metadata"] = summary_result["metadata"]

            # codeql[py/stack-trace-exposure] returns formatted summary dict, not error details
            return formatted_response
        else:
            # codeql[py/stack-trace-exposure] returns summary result dict, not error details
            return summary_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dataset summary generation failed for {dataset_id}: {e}", exc_info=True)
        # Return a fallback response
        return {
            "summary": "Dataset summary generation is currently unavailable. Please try again later.",
            "key_topics": [],
            "document_types": {},
            "total_documents": 0,
            "total_chunks": 0,
            "common_themes": [],
            "search_optimization_tips": [],
            "generated_at": None
        }


@router.post("/", response_model=DatasetResponse)
async def create_dataset(
    request: CreateDatasetRequest,
    current_user: Dict = Depends(get_current_user)
) -> DatasetResponse:
    """Create new dataset owned by current user"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email
        
        # Create dataset object
        dataset_data = {
            "id": str(uuid.uuid4()),
            "name": request.name,
            "description": request.description,
            "owner_id": user_id,
            "access_group": request.access_group.value,
            "team_members": request.team_members or [] if request.access_group == AccessGroup.TEAM else [],
            "tags": request.tags or [],
            "document_count": 0,
            "chunk_count": 0,
            "vector_count": 0,
            "storage_size_mb": 0.0,
            "metadata": {}
        }
        
        dataset = await service.create_dataset(dataset_data)

        # Share to teams if team_shares provided and access_group is TEAM
        team_shares = getattr(request, 'team_shares', None)
        if team_shares and request.access_group == AccessGroup.TEAM:
            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=tenant_domain,
                user_id=current_user['user_id'],
                user_email=user_email
            )

            try:
                await team_service.share_resource_to_teams(
                    resource_id=dataset['id'],
                    resource_type='dataset',
                    shared_by=current_user['user_id'],
                    team_shares=team_shares
                )
                logger.info(f"Dataset {dataset['id']} shared to {len(team_shares)} team(s)")
            except Exception as team_error:
                logger.error(f"Error sharing dataset to teams: {team_error}")
                # Don't fail dataset creation if sharing fails

        # Add access indicators
        dataset["is_owner"] = True
        dataset["can_edit"] = True
        dataset["can_delete"] = True
        dataset["can_share"] = True

        return dataset
        
    except Exception as e:
        logger.error(f"Error creating dataset: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str,
    request: UpdateDatasetRequest,
    current_user: Dict = Depends(get_current_user)
) -> DatasetResponse:
    """Update dataset (owner only)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email

        # Check ownership
        if not await service.can_user_modify_dataset(user_id, dataset_id):
            raise HTTPException(403, "Only owner can modify dataset")

        # Get current dataset to check for access_group changes
        current_dataset = await service.get_dataset(dataset_id)
        if not current_dataset:
            raise HTTPException(404, "Dataset not found")

        # Update fields
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            update_data["tags"] = request.tags

        # Handle access group and team members updates
        if request.access_group is not None:
            update_data["access_group"] = request.access_group
            # If changing to team access, include team members
            if request.access_group == "team" and request.team_members:
                update_data["team_members"] = request.team_members
            # Clear team members if not team access
            elif request.access_group != "team":
                update_data["team_members"] = []

        # Handle chunking configuration updates
        if request.chunking_strategy is not None:
            update_data["chunking_strategy"] = request.chunking_strategy
        if request.chunk_size is not None:
            # Validate chunk size
            if request.chunk_size < 100 or request.chunk_size > 2000:
                raise HTTPException(400, "Chunk size must be between 100 and 2000")
            update_data["chunk_size"] = request.chunk_size
        if request.chunk_overlap is not None:
            # Validate chunk overlap
            if request.chunk_overlap < 0 or request.chunk_overlap > 200:
                raise HTTPException(400, "Chunk overlap must be between 0 and 200")
            update_data["chunk_overlap"] = request.chunk_overlap

        # Handle embedding model update
        if request.embedding_model is not None:
            # Validate embedding model
            valid_models = [
                "BAAI/bge-m3",
                "BAAI/bge-large-en-v1.5",
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2"
            ]
            if request.embedding_model not in valid_models:
                raise HTTPException(400, f"Invalid embedding model. Must be one of: {', '.join(valid_models)}")
            update_data["embedding_model"] = request.embedding_model

        # Check if access_group is changing from 'team' to 'individual'
        current_access_group = current_dataset.get('access_group', 'individual')
        new_access_group = update_data.get('access_group', current_access_group)

        if current_access_group == 'team' and new_access_group == 'individual':
            # Changing from team to individual - remove all team shares
            from app.services.team_service import TeamService
            from app.api.auth import get_tenant_user_uuid_by_email

            tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
            team_service = TeamService(
                tenant_domain=tenant_domain,
                user_id=tenant_user_uuid,
                user_email=user_email
            )

            try:
                # Get all team shares for this dataset
                resource_teams = await team_service.get_resource_teams('dataset', dataset_id)
                # Remove from each team
                for team in resource_teams:
                    await team_service.unshare_resource_from_team(
                        resource_id=dataset_id,
                        resource_type='dataset',
                        team_id=team['id']  # Use 'id' not 'team_id'
                    )
                logger.info(f"Removed dataset {dataset_id} from {len(resource_teams)} team(s) due to access_group change")
            except Exception as unshare_error:
                logger.error(f"Error removing team shares: {unshare_error}")
                # Continue with update even if unsharing fails

        # Handle team sharing if provided AND access_group is 'team'
        if request.team_shares is not None:
            # Auto-update access_group to 'team' when team_shares provided
            if request.team_shares and len(request.team_shares) > 0:
                update_data["access_group"] = "team"

        # Update dataset with all changes
        updated_dataset = await service.update_dataset(dataset_id, update_data)

        # Process team shares only when access_group is 'team'
        if request.team_shares is not None:
            final_access_group = update_data.get('access_group', current_access_group)

            # Only process team shares when access_group is actually 'team'
            if final_access_group == 'team':
                from app.services.team_service import TeamService
                from app.api.auth import get_tenant_user_uuid_by_email

                tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
                team_service = TeamService(
                    tenant_domain=tenant_domain,
                    user_id=tenant_user_uuid,
                    user_email=user_email
                )

                # Update team shares: this replaces existing shares
                await team_service.share_resource_to_teams(
                    resource_id=dataset_id,
                    resource_type='dataset',
                    shared_by=tenant_user_uuid,
                    team_shares=request.team_shares
                )

        # Add access indicators
        updated_dataset["is_owner"] = True
        updated_dataset["can_edit"] = True
        updated_dataset["can_delete"] = True
        updated_dataset["can_share"] = True

        return updated_dataset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.put("/{dataset_id}/share", response_model=DatasetResponse)
async def share_dataset(
    dataset_id: str,
    request: ShareDatasetRequest,
    current_user: Dict = Depends(get_current_user)
) -> DatasetResponse:
    """Share dataset with team or organization (owner only)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email
        
        # Check ownership
        if not await service.can_user_modify_dataset(user_id, dataset_id):
            raise HTTPException(403, "Only owner can share dataset")
        
        # Update sharing settings
        update_data = {
            "access_group": request.access_group.value,
            "team_members": request.team_members or [] if request.access_group == AccessGroup.TEAM else []
        }
        
        updated_dataset = await service.update_dataset(dataset_id, update_data)
        
        # Add access indicators
        updated_dataset["is_owner"] = True
        updated_dataset["can_edit"] = True
        updated_dataset["can_delete"] = True
        updated_dataset["can_share"] = True
        
        return updated_dataset
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sharing dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete dataset (owner only)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email
        
        # Check ownership
        if not await service.can_user_modify_dataset(user_id, dataset_id):
            raise HTTPException(403, "Only owner can delete dataset")
        
        # Delete dataset and all associated data
        success = await service.delete_dataset(dataset_id)
        
        if not success:
            raise HTTPException(404, "Dataset not found")
        
        return {"message": "Dataset deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.post("/{dataset_id}/documents")
async def add_documents_to_dataset(
    dataset_id: str,
    document_ids: List[str],
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Add documents to dataset (owner or team with write access)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email
        
        # Check access
        if not await service.can_user_modify_dataset(user_id, dataset_id):
            raise HTTPException(403, "Insufficient permissions to modify dataset")
        
        # Add documents
        result = await service.add_documents_to_dataset(dataset_id, document_ids)
        
        return {
            "message": f"Added {len(document_ids)} documents to dataset",
            "dataset_id": dataset_id,
            "added_documents": result.get("added", []),
            "failed_documents": result.get("failed", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding documents to dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.get("/{dataset_id}/stats")
async def get_dataset_stats(
    dataset_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed dataset statistics"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Missing user email in authentication context"
            )
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email

        # Check access
        if not await service.can_user_access_dataset(user_id, dataset_id):
            raise HTTPException(403, "Access denied")

        stats = await service.get_dataset_stats(dataset_id)
        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset stats {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.get("/agents/{agent_id}/accessible", response_model=List[DatasetResponse])
async def get_agent_accessible_datasets(
    agent_id: str,
    current_user: Dict = Depends(get_current_user)
) -> List[DatasetResponse]:
    """
    DEPRECATED: Get datasets accessible to a specific agent.

    This endpoint was used by the dataset selection dropdown in the chat interface,
    which has been removed. Datasets are now configured via agent settings only.
    Keeping for backward compatibility but should not be used in new code.
    """
    try:
        tenant_domain = current_user.get("tenant_domain", "test-company")
        user_id = current_user["email"]

        # Get user UUID for permission comparison
        from app.core.user_resolver import ensure_user_uuid
        user_uuid = await ensure_user_uuid(user_id, tenant_domain)

        # Initialize services
        agent_service = AgentService(tenant_domain, user_id)
        dataset_service = DatasetService(tenant_domain, user_id)

        # Get the agent and verify user has access to it
        agent = await agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found or access denied")

        # Get agent's selected dataset IDs (handle None case)
        agent_dataset_ids = agent.get('selected_dataset_ids') or []
        logger.info(f"Agent {agent_id} has access to datasets: {agent_dataset_ids}")

        # Get all user's accessible datasets (combining owned, team, and org datasets)
        all_datasets = []

        # Get owned datasets
        owned = await dataset_service.get_owned_datasets(user_id)
        all_datasets.extend(owned)

        # Get team datasets
        team_datasets = await dataset_service.get_team_datasets(user_id)
        all_datasets.extend(team_datasets)

        # Get org datasets if needed (optional - most installs won't have org datasets)
        try:
            org_datasets = await dataset_service.get_org_datasets(tenant_domain)
            all_datasets.extend(org_datasets)
        except Exception as e:
            logger.warning(f"Could not load org datasets: {e}")
            # Continue without org datasets

        # Get user role for permission checks
        from app.core.postgresql_client import get_postgresql_client
        from app.core.permissions import get_user_role, is_effective_owner

        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_id, tenant_domain)

        # Remove duplicates and add access indicators
        unique_datasets = {}
        for dataset in all_datasets:
            if dataset["id"] not in unique_datasets:
                # Add standard access indicators using effective ownership
                is_owner = is_effective_owner(dataset["owner_id"], user_uuid, user_role)
                dataset["is_owner"] = is_owner
                dataset["can_edit"] = is_owner
                dataset["can_delete"] = is_owner
                dataset["can_share"] = is_owner
                unique_datasets[dataset["id"]] = dataset

        # Filter datasets to only include datasets explicitly selected by the agent
        # This enforces proper agent dataset isolation
        accessible_datasets = []

        for dataset in unique_datasets.values():
            dataset_id = dataset.get('id')
            owner_id = dataset.get('owner_id')

            # Only include datasets that the agent is explicitly configured to access
            if dataset_id in agent_dataset_ids:
                # Add agent-specific security markers
                dataset["agent_has_access"] = True  # Always true for included datasets
                dataset["user_owns"] = is_effective_owner(owner_id, user_uuid, user_role)
                accessible_datasets.append(dataset)

        logger.info(f"Agent {agent_id} can access {len(accessible_datasets)} out of {len(unique_datasets)} datasets")

        # Log successful completion
        logger.debug(f"Successfully filtered {len(accessible_datasets)} datasets for agent {agent_id}")

        return accessible_datasets

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent accessible datasets for {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.get("/summary/complete")
async def get_complete_summary(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get complete summary statistics including all documents"""
    try:
        # Validate user email is present
        user_email = current_user.get("email", "").strip()
        if not user_email:
            logger.error(f"Empty or missing email in current_user: {current_user}")
            raise HTTPException(401, "User email not found in authentication context")

        tenant_domain = current_user.get("tenant_domain", "test-company")
        service = DatasetService(tenant_domain, user_email)
        user_id = user_email

        # Get complete statistics including orphaned documents
        summary = await service.get_complete_user_summary(user_id)

        return summary

    except Exception as e:
        logger.error(f"Error getting complete summary: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")