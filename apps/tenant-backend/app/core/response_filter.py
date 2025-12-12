"""
Response Filtering Utilities for GT 2.0

Provides field-level authorization and data filtering for API responses.
Implements principle of least privilege - users only see data they're authorized to access.

Security principles:
1. Owner-only fields: resource_preferences, advanced RAG configs (max_chunks_per_query, history_context)
2. Viewer fields: Public + usage stats + prompt_template + personality_config + dataset connections
   (Team members with read access need these fields to effectively use shared agents)
3. Public fields: id, name, description, category, basic metadata
4. No internal UUIDs, implementation details, or system configuration exposure
"""

from typing import Dict, Any, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class ResponseFilter:
    """Filter API responses based on user permissions and access level"""

    # Define field access levels for agents
    # REQUIRED fields that must always be present for AgentResponse schema
    AGENT_REQUIRED_FIELDS = {
        'id', 'name', 'description', 'created_at', 'updated_at'
    }

    AGENT_PUBLIC_FIELDS = AGENT_REQUIRED_FIELDS | {
        'category', 'conversation_count', 'usage_count', 'is_favorite', 'tags',
        'created_by_name', 'can_edit', 'can_delete', 'is_owner',
        # Include these for display purposes
        'model', 'visibility', 'disclaimer', 'easy_prompts',
        # Dataset connections for showing dataset count on agent tiles
        'dataset_connection', 'selected_dataset_ids'
    }

    AGENT_VIEWER_FIELDS = AGENT_PUBLIC_FIELDS | {
        'temperature', 'max_tokens', 'total_cost_cents', 'template_id',
        # Essential fields for using shared agents (team collaboration)
        'prompt_template', 'personality_config',
        'dataset_connection', 'selected_dataset_ids'
    }

    AGENT_OWNER_FIELDS = AGENT_VIEWER_FIELDS | {
        # Advanced configuration fields (owner-only)
        'resource_preferences', 'max_chunks_per_query', 'history_context',
        # Team sharing configuration (owner-only for editing)
        'team_shares'
    }

    # Define field access levels for datasets
    # Fields for all users (public/shared datasets) - stats are informational, not sensitive
    DATASET_PUBLIC_FIELDS = {
        'id', 'name', 'description', 'created_by_name', 'owner_name',
        'document_count', 'chunk_count', 'vector_count', 'storage_size_mb',
        'tags', 'created_at', 'updated_at', 'access_group',
        # Permission flags for UI controls
        'is_owner', 'can_edit', 'can_delete', 'can_share',
        # Team sharing flag for proper visibility indicators
        'shared_via_team'
    }

    DATASET_VIEWER_FIELDS = DATASET_PUBLIC_FIELDS | {
        'summary'  # Viewers can see dataset summary
    }

    DATASET_OWNER_FIELDS = DATASET_VIEWER_FIELDS | {
        # Only owners see internal configuration
        'owner_id', 'team_members', 'chunking_strategy', 'chunk_size',
        'chunk_overlap', 'embedding_model', 'summary_generated_at',
        # Team sharing configuration (owner-only for editing)
        'team_shares'
    }

    # Define field access levels for files
    # Public fields include processing info since it's informational metadata, not sensitive
    FILE_PUBLIC_FIELDS = {
        'id', 'original_filename', 'content_type', 'file_type', 'file_size', 'file_size_bytes',
        'created_at', 'updated_at', 'category',
        # Processing fields - informational, not sensitive
        'processing_status', 'chunk_count', 'processing_progress', 'processing_stage',
        # Permission flags for UI controls
        'can_delete'
    }

    FILE_OWNER_FIELDS = FILE_PUBLIC_FIELDS | {
        'user_id', 'dataset_id', 'storage_path', 'metadata'
    }

    @staticmethod
    def filter_agent_response(
        agent_data: Dict[str, Any],
        is_owner: bool = False,
        can_view: bool = True
    ) -> Dict[str, Any]:
        """
        Filter agent response fields based on user permissions

        Args:
            agent_data: Full agent data dictionary
            is_owner: Whether user owns this agent
            can_view: Whether user can view detailed information

        Returns:
            Filtered dictionary with only authorized fields
        """
        if is_owner:
            allowed_fields = ResponseFilter.AGENT_OWNER_FIELDS
            logger.info(f"🔓 Agent '{agent_data.get('name', 'Unknown')}': Using OWNER fields (is_owner=True, can_view={can_view})")
        elif can_view:
            allowed_fields = ResponseFilter.AGENT_VIEWER_FIELDS
            logger.info(f"👁️ Agent '{agent_data.get('name', 'Unknown')}': Using VIEWER fields (is_owner=False, can_view=True)")
        else:
            allowed_fields = ResponseFilter.AGENT_PUBLIC_FIELDS
            logger.info(f"🌍 Agent '{agent_data.get('name', 'Unknown')}': Using PUBLIC fields (is_owner=False, can_view=False)")

        filtered = {
            key: value for key, value in agent_data.items()
            if key in allowed_fields
        }

        # Ensure defaults for optional fields that were filtered out
        # This prevents AgentResponse schema validation errors
        default_values = {
            'personality_config': {},
            'resource_preferences': {},
            'tags': [],
            'easy_prompts': [],
            'conversation_count': 0,
            'usage_count': 0,
            'total_cost_cents': 0,
            'is_favorite': False,
            'can_edit': False,
            'can_delete': False,
            'is_owner': is_owner
        }

        for key, default_value in default_values.items():
            if key not in filtered:
                filtered[key] = default_value

        # Log field filtering for security audit
        removed_fields = set(agent_data.keys()) - set(filtered.keys())
        if removed_fields:
            logger.info(
                f"🔒 Filtered agent '{agent_data.get('name', 'Unknown')}' - removed fields: {removed_fields} "
                f"(is_owner={is_owner}, can_view={can_view})"
            )

        # Special logging for prompt_template field
        if 'prompt_template' in agent_data:
            if 'prompt_template' in filtered:
                logger.info(f"✅ Agent '{agent_data.get('name', 'Unknown')}': prompt_template INCLUDED in response")
            else:
                logger.warning(f"❌ Agent '{agent_data.get('name', 'Unknown')}': prompt_template FILTERED OUT (is_owner={is_owner}, can_view={can_view})")

        return filtered

    @staticmethod
    def filter_dataset_response(
        dataset_data: Dict[str, Any],
        is_owner: bool = False,
        can_view: bool = True
    ) -> Dict[str, Any]:
        """
        Filter dataset response fields based on user permissions

        Args:
            dataset_data: Full dataset data dictionary
            is_owner: Whether user owns this dataset
            can_view: Whether user can view the dataset

        Returns:
            Filtered dictionary with only authorized fields
        """
        if is_owner:
            allowed_fields = ResponseFilter.DATASET_OWNER_FIELDS
        elif can_view:
            allowed_fields = ResponseFilter.DATASET_VIEWER_FIELDS
        else:
            allowed_fields = ResponseFilter.DATASET_PUBLIC_FIELDS

        filtered = {
            key: value for key, value in dataset_data.items()
            if key in allowed_fields
        }

        # Security: Never expose owner_id UUID to non-owners
        if not is_owner and 'owner_id' in filtered:
            del filtered['owner_id']

        # Ensure defaults for optional fields to prevent schema validation errors
        default_values = {
            'tags': [],
            'is_owner': is_owner,
            'can_edit': False,
            'can_delete': False,
            'can_share': False,
            # Always set these to None for non-owners (security)
            'team_members': None if not is_owner else filtered.get('team_members', []),
            'owner_id': None if not is_owner else filtered.get('owner_id'),
            # Internal fields - null for all except detail view
            'agent_has_access': None,
            'user_owns': None,
            # Stats fields - use actual values or safe defaults for frontend compatibility
            # These are informational only, not sensitive
            'chunk_count': filtered.get('chunk_count', 0),
            'vector_count': filtered.get('vector_count', 0),
            'storage_size_mb': filtered.get('storage_size_mb', 0.0),
            'updated_at': filtered.get('updated_at'),
            'summary': None
        }

        for key, default_value in default_values.items():
            if key not in filtered:
                filtered[key] = default_value

        # Log field filtering for security audit
        removed_fields = set(dataset_data.keys()) - set(filtered.keys())
        if removed_fields:
            logger.debug(
                f"Filtered dataset response - removed fields: {removed_fields} "
                f"(is_owner={is_owner}, can_view={can_view})"
            )

        return filtered

    @staticmethod
    def filter_file_response(
        file_data: Dict[str, Any],
        is_owner: bool = False
    ) -> Dict[str, Any]:
        """
        Filter file response fields based on user permissions

        Args:
            file_data: Full file data dictionary
            is_owner: Whether user owns this file

        Returns:
            Filtered dictionary with only authorized fields
        """
        allowed_fields = (
            ResponseFilter.FILE_OWNER_FIELDS if is_owner
            else ResponseFilter.FILE_PUBLIC_FIELDS
        )

        filtered = {
            key: value for key, value in file_data.items()
            if key in allowed_fields
        }

        # Log field filtering for security audit
        removed_fields = set(file_data.keys()) - set(filtered.keys())
        if removed_fields:
            logger.debug(
                f"Filtered file response - removed fields: {removed_fields} "
                f"(is_owner={is_owner})"
            )

        return filtered

    @staticmethod
    def filter_batch_responses(
        items: List[Dict[str, Any]],
        filter_func: callable,
        ownership_map: Optional[Dict[str, bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter a batch of items using the provided filter function

        Args:
            items: List of items to filter
            filter_func: Function to apply to each item (e.g., filter_agent_response)
            ownership_map: Optional map of item_id -> is_owner boolean

        Returns:
            List of filtered items
        """
        filtered_items = []

        for item in items:
            item_id = item.get('id')
            is_owner = ownership_map.get(item_id, False) if ownership_map else False

            filtered_item = filter_func(item, is_owner=is_owner)
            filtered_items.append(filtered_item)

        return filtered_items

    @staticmethod
    def sanitize_dataset_summary(
        summary_data: Dict[str, Any],
        user_can_access: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Sanitize dataset summary for inclusion in chat context

        Args:
            summary_data: Dataset summary with metadata
            user_can_access: Whether user should have access to this dataset

        Returns:
            Sanitized summary or None if user shouldn't access
        """
        if not user_can_access:
            return None

        # Only include safe fields in summary
        safe_fields = {
            'id', 'name', 'description', 'summary',
            'document_count', 'chunk_count'
        }

        return {
            key: value for key, value in summary_data.items()
            if key in safe_fields
        }
