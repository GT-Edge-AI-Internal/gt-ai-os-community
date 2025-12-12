import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client
from app.core.permissions import get_user_role, validate_visibility_permission, can_edit_resource, can_delete_resource, is_effective_owner
from app.services.category_service import CategoryService
import logging

logger = logging.getLogger(__name__)

class AgentService:
    """GT 2.0 PostgreSQL+PGVector Agent Service with Perfect Tenant Isolation"""
    
    def __init__(self, tenant_domain: str, user_id: str, user_email: str = None):
        """Initialize with tenant and user isolation using PostgreSQL+PGVector storage"""
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.user_email = user_email or user_id  # Fallback to user_id if no email provided
        self.settings = get_settings()
        self._resolved_user_uuid = None  # Cache for resolved user UUID (performance optimization)

        logger.info(f"Agent service initialized with PostgreSQL+PGVector for {tenant_domain}/{user_id} (email: {self.user_email})")

    async def _get_resolved_user_uuid(self, user_identifier: Optional[str] = None) -> str:
        """
        Resolve user identifier to UUID with caching for performance.

        This optimization reduces repeated database lookups by caching the resolved UUID.
        Performance impact: ~50% reduction in query time for operations with multiple queries.
        Pattern matches conversation_service.py for consistency.
        """
        identifier = user_identifier or self.user_email or self.user_id

        # Return cached UUID if already resolved for this instance
        if self._resolved_user_uuid and str(identifier) in [str(self.user_email), str(self.user_id)]:
            return self._resolved_user_uuid

        # Check if already a UUID
        if "@" not in str(identifier):
            try:
                # Validate it's a proper UUID format
                uuid.UUID(str(identifier))
                if str(identifier) == str(self.user_id):
                    self._resolved_user_uuid = str(identifier)
                return str(identifier)
            except (ValueError, AttributeError):
                pass  # Not a valid UUID, treat as email/username

        # Resolve email to UUID
        pg_client = await get_postgresql_client()
        query = """
            SELECT id FROM users
            WHERE (email = $1 OR username = $1)
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            LIMIT 1
        """
        result = await pg_client.fetch_one(query, str(identifier), self.tenant_domain)

        if not result:
            raise ValueError(f"User not found: {identifier}")

        user_uuid = str(result["id"])

        # Cache if this is the service's primary user
        if str(identifier) in [str(self.user_email), str(self.user_id)]:
            self._resolved_user_uuid = user_uuid

        return user_uuid

    async def create_agent(
        self, 
        name: str, 
        agent_type: str = "conversational",
        prompt_template: str = "",
        description: str = "",
        capabilities: Optional[List[str]] = None,
        access_group: str = "INDIVIDUAL",
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new agent using PostgreSQL+PGVector storage following GT 2.0 principles"""
        
        try:
            # Get PostgreSQL client
            pg_client = await get_postgresql_client()
            
            # Generate agent ID
            agent_id = str(uuid.uuid4())

            # Resolve user UUID with caching (performance optimization)
            user_id = await self._get_resolved_user_uuid()

            logger.info(f"Found user ID: {user_id} for email/id: {self.user_email}/{self.user_id}")

            # Create agent in PostgreSQL
            query = """
                INSERT INTO agents (
                    id, name, description, system_prompt,
                    tenant_id, created_by, model, temperature, max_tokens,
                    visibility, configuration, is_active, access_group, agent_type
                ) VALUES (
                    $1, $2, $3, $4,
                    (SELECT id FROM tenants WHERE domain = $5 LIMIT 1),
                    $6,
                    $7, $8, $9, $10, $11, true, $12, $13
                )
                RETURNING id, name, description, system_prompt, model, temperature, max_tokens,
                          visibility, configuration, access_group, agent_type, created_at, updated_at
            """
            
            # Prepare configuration with additional kwargs
            # Ensure list fields are always lists, never None
            configuration = {
                "agent_type": agent_type,
                "capabilities": capabilities or [],
                "personality_config": kwargs.get("personality_config", {}),
                "resource_preferences": kwargs.get("resource_preferences", {}),
                "model_config": kwargs.get("model_config", {}),
                "tags": kwargs.get("tags") or [],
                "easy_prompts": kwargs.get("easy_prompts") or [],
                "selected_dataset_ids": kwargs.get("selected_dataset_ids") or [],
                **{k: v for k, v in kwargs.items() if k not in ["tags", "easy_prompts", "selected_dataset_ids"]}
            }
            
            # Extract model configuration
            model = kwargs.get("model")
            if not model:
                raise ValueError("Model is required for agent creation")
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 8000)  # Increased to match Groq Llama 3.1 capabilities

            # Use access_group as visibility directly (individual, organization only)
            visibility = access_group.lower()

            # Validate visibility permission based on user role
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            validate_visibility_permission(visibility, user_role)
            logger.info(f"User {self.user_email} (role: {user_role}) creating agent with visibility: {visibility}")

            # Auto-create category if specified (Issue #215)
            # This ensures imported agents with unknown categories create those categories
            # Category is stored in agent_type column
            category = kwargs.get("category")
            if category and isinstance(category, str) and category.strip():
                category_slug = category.strip().lower()
                try:
                    category_service = CategoryService(self.tenant_domain, user_id, self.user_email)
                    # Pass category_description from CSV import if provided
                    category_description = kwargs.get("category_description")
                    await category_service.get_or_create_category(category_slug, description=category_description)
                    logger.info(f"Ensured category exists: {category}")
                except Exception as cat_err:
                    logger.warning(f"Failed to ensure category '{category}' exists: {cat_err}")
                    # Continue with agent creation even if category creation fails
                # Use category as agent_type (they map to the same column)
                agent_type = category_slug

            agent_data = await pg_client.fetch_one(
                query,
                agent_id, name, description, prompt_template,
                self.tenant_domain, user_id,
                model, temperature, max_tokens, visibility,
                json.dumps(configuration), access_group, agent_type
            )
            
            if not agent_data:
                raise RuntimeError("Failed to create agent - no data returned")
            
            # Convert to dict with proper types
            # Parse configuration JSON if it's a string
            config = agent_data["configuration"]
            if isinstance(config, str):
                config = json.loads(config)
            elif config is None:
                config = {}
                
            result = {
                "id": str(agent_data["id"]),
                "name": agent_data["name"],
                "agent_type": config.get("agent_type", "conversational"),
                "prompt_template": agent_data["system_prompt"],
                "description": agent_data["description"],
                "capabilities": config.get("capabilities", []),
                "access_group": agent_data["access_group"],
                "config": config,
                "model": agent_data["model"],
                "temperature": float(agent_data["temperature"]) if agent_data["temperature"] is not None else None,
                "max_tokens": agent_data["max_tokens"],
                "top_p": config.get("top_p"),
                "frequency_penalty": config.get("frequency_penalty"),
                "presence_penalty": config.get("presence_penalty"),
                "visibility": agent_data["visibility"],
                "dataset_connection": config.get("dataset_connection"),
                "selected_dataset_ids": config.get("selected_dataset_ids", []),
                "max_chunks_per_query": config.get("max_chunks_per_query"),
                "history_context": config.get("history_context"),
                "personality_config": config.get("personality_config", {}),
                "resource_preferences": config.get("resource_preferences", {}),
                "tags": config.get("tags", []),
                "is_favorite": config.get("is_favorite", False),
                "conversation_count": 0,
                "total_cost_cents": 0,
                "created_at": agent_data["created_at"].isoformat(),
                "updated_at": agent_data["updated_at"].isoformat(),
                "user_id": self.user_id,
                "tenant_domain": self.tenant_domain
            }
            
            logger.info(f"Created agent {agent_id} in PostgreSQL for user {self.user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise

    async def get_user_agents(
        self,
        active_only: bool = True,
        sort_by: Optional[str] = None,
        filter_usage: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all agents for the current user using PostgreSQL storage"""
        try:
            # Get PostgreSQL client
            pg_client = await get_postgresql_client()

            # Resolve user UUID with caching (performance optimization)
            try:
                user_id = await self._get_resolved_user_uuid()
            except ValueError as e:
                logger.warning(f"User not found for agents list: {self.user_email} (or {self.user_id}) in tenant {self.tenant_domain}: {e}")
                return []

            # Get user role to determine access level
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Query agents from PostgreSQL with conversation counts
            # Admins see ALL agents, others see only their own or organization-level agents
            if is_admin:
                where_clause = "WHERE a.tenant_id = (SELECT id FROM tenants WHERE domain = $1)"
                params = [self.tenant_domain]
            else:
                where_clause = "WHERE (a.created_by = $1 OR a.visibility = 'organization') AND a.tenant_id = (SELECT id FROM tenants WHERE domain = $2)"
                params = [user_id, self.tenant_domain]

            # Prepare user_id parameter for per-user usage tracking
            # Need to add user_id as an additional parameter for usage calculations
            user_id_param_index = len(params) + 1
            params.append(user_id)

            # Per-user usage tracking: Count only conversations for this user
            query = f"""
                SELECT
                    a.id, a.name, a.description, a.system_prompt, a.model, a.temperature, a.max_tokens,
                    a.visibility, a.configuration, a.access_group, a.created_at, a.updated_at,
                    a.is_active, a.created_by, a.agent_type,
                    u.full_name as created_by_name,
                    COUNT(CASE WHEN c.user_id = ${user_id_param_index}::uuid THEN c.id END) as user_conversation_count,
                    MAX(CASE WHEN c.user_id = ${user_id_param_index}::uuid THEN c.created_at END) as user_last_used_at
                FROM agents a
                LEFT JOIN conversations c ON a.id = c.agent_id
                LEFT JOIN users u ON a.created_by = u.id
                {where_clause}
            """

            if active_only:
                query += " AND a.is_active = true"

            # Time-based usage filters (per-user)
            if filter_usage == "used_last_7_days":
                query += f" AND EXISTS (SELECT 1 FROM conversations c2 WHERE c2.agent_id = a.id AND c2.user_id = ${user_id_param_index}::uuid AND c2.created_at >= NOW() - INTERVAL '7 days')"
            elif filter_usage == "used_last_30_days":
                query += f" AND EXISTS (SELECT 1 FROM conversations c2 WHERE c2.agent_id = a.id AND c2.user_id = ${user_id_param_index}::uuid AND c2.created_at >= NOW() - INTERVAL '30 days')"

            query += " GROUP BY a.id, a.name, a.description, a.system_prompt, a.model, a.temperature, a.max_tokens, a.visibility, a.configuration, a.access_group, a.created_at, a.updated_at, a.is_active, a.created_by, a.agent_type, u.full_name"

            # User-specific sorting
            if sort_by == "recent_usage":
                query += " ORDER BY user_last_used_at DESC NULLS LAST, a.updated_at DESC"
            elif sort_by == "my_most_used":
                query += " ORDER BY user_conversation_count DESC, a.updated_at DESC"
            else:
                query += " ORDER BY a.updated_at DESC"
            
            agents_data = await pg_client.execute_query(query, *params)
            
            # Convert to proper format
            agents = []
            for agent in agents_data:
                # Debug logging for creator name
                logger.info(f"🔍 Agent '{agent['name']}': created_by={agent.get('created_by')}, created_by_name={agent.get('created_by_name')}")

                # Parse configuration JSON if it's a string
                config = agent["configuration"]
                if isinstance(config, str):
                    config = json.loads(config)
                elif config is None:
                    config = {}
                    
                disclaimer_val = config.get("disclaimer")
                easy_prompts_val = config.get("easy_prompts", [])
                logger.info(f"get_user_agents - Agent {agent['name']}: disclaimer={disclaimer_val}, easy_prompts={easy_prompts_val}")

                # Determine if user can edit this agent
                # User can edit if they created it OR if they're admin/developer
                # Use cached user_role from line 190 (no need to re-query for each agent)
                is_owner = is_effective_owner(str(agent["created_by"]), str(user_id), user_role)
                can_edit = can_edit_resource(str(agent["created_by"]), str(user_id), user_role, agent["visibility"])
                can_delete = can_delete_resource(str(agent["created_by"]), str(user_id), user_role)

                logger.info(f"Agent {agent['name']}: created_by={agent['created_by']}, user_id={user_id}, user_role={user_role}, is_owner={is_owner}, can_edit={can_edit}, can_delete={can_delete}")

                agents.append({
                    "id": str(agent["id"]),
                    "name": agent["name"],
                    "agent_type": agent["agent_type"] or "conversational",
                    "prompt_template": agent["system_prompt"],
                    "description": agent["description"],
                    "capabilities": config.get("capabilities", []),
                    "access_group": agent["access_group"],
                    "config": config,
                    "model": agent["model"],
                    "temperature": float(agent["temperature"]) if agent["temperature"] is not None else None,
                    "max_tokens": agent["max_tokens"],
                    "visibility": agent["visibility"],
                    "dataset_connection": config.get("dataset_connection"),
                    "selected_dataset_ids": config.get("selected_dataset_ids", []),
                    "personality_config": config.get("personality_config", {}),
                    "resource_preferences": config.get("resource_preferences", {}),
                    "tags": config.get("tags", []),
                    "is_favorite": config.get("is_favorite", False),
                    "disclaimer": disclaimer_val,
                    "easy_prompts": easy_prompts_val,
                    "conversation_count": int(agent["user_conversation_count"]) if agent.get("user_conversation_count") is not None else 0,
                    "last_used_at": agent["user_last_used_at"].isoformat() if agent.get("user_last_used_at") else None,
                    "total_cost_cents": 0,
                    "created_at": agent["created_at"].isoformat() if agent["created_at"] else None,
                    "updated_at": agent["updated_at"].isoformat() if agent["updated_at"] else None,
                    "is_active": agent["is_active"],
                    "user_id": agent["created_by"],
                    "created_by_name": agent.get("created_by_name", "Unknown"),
                    "tenant_domain": self.tenant_domain,
                    "can_edit": can_edit,
                    "can_delete": can_delete,
                    "is_owner": is_owner
                })
            
            # Fetch team-shared agents and merge with owned agents
            team_shared = await self.get_team_shared_agents(user_id)

            # Merge and deduplicate (owned agents take precedence)
            agent_ids_seen = {agent["id"] for agent in agents}
            for team_agent in team_shared:
                if team_agent["id"] not in agent_ids_seen:
                    agents.append(team_agent)
                    agent_ids_seen.add(team_agent["id"])

            logger.info(f"Retrieved {len(agents)} total agents ({len(agents) - len(team_shared)} owned + {len(team_shared)} team-shared) from PostgreSQL for user {self.user_id}")
            return agents

        except Exception as e:
            logger.error(f"Error reading agents for user {self.user_id}: {e}")
            return []

    async def get_team_shared_agents(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get agents shared to teams where user is a member (via junction table).

        Uses the user_accessible_resources view for efficient lookups.

        Returns agents with permission flags:
        - can_edit: True if user has 'edit' permission for this agent
        - can_delete: False (only owner can delete)
        - is_owner: False (team-shared agents)
        - shared_via_team: True (indicates team sharing)
        - shared_in_teams: Number of teams this agent is shared with
        """
        try:
            pg_client = await get_postgresql_client()

            # Query agents using the efficient user_accessible_resources view
            # This view joins team_memberships -> team_resource_shares -> agents
            # Include per-user usage statistics
            query = """
                SELECT DISTINCT
                    a.id, a.name, a.description, a.system_prompt, a.model, a.temperature, a.max_tokens,
                    a.visibility, a.configuration, a.access_group, a.created_at, a.updated_at,
                    a.is_active, a.created_by, a.agent_type,
                    u.full_name as created_by_name,
                    COUNT(DISTINCT CASE WHEN c.user_id = $1::uuid THEN c.id END) as user_conversation_count,
                    MAX(CASE WHEN c.user_id = $1::uuid THEN c.created_at END) as user_last_used_at,
                    uar.best_permission as user_permission,
                    uar.shared_in_teams,
                    uar.team_ids
                FROM user_accessible_resources uar
                INNER JOIN agents a ON a.id = uar.resource_id
                LEFT JOIN users u ON a.created_by = u.id
                LEFT JOIN conversations c ON a.id = c.agent_id
                WHERE uar.user_id = $1::uuid
                  AND uar.resource_type = 'agent'
                  AND a.tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                  AND a.is_active = true
                GROUP BY a.id, a.name, a.description, a.system_prompt, a.model, a.temperature,
                         a.max_tokens, a.visibility, a.configuration, a.access_group, a.created_at,
                         a.updated_at, a.is_active, a.created_by, a.agent_type, u.full_name,
                         uar.best_permission, uar.shared_in_teams, uar.team_ids
                ORDER BY a.updated_at DESC
            """

            agents_data = await pg_client.execute_query(query, user_id, self.tenant_domain)

            # Format agents with team sharing metadata
            agents = []
            for agent in agents_data:
                # Parse configuration JSON
                config = agent["configuration"]
                if isinstance(config, str):
                    config = json.loads(config)
                elif config is None:
                    config = {}

                # Get permission from view (will be "read" or "edit")
                user_permission = agent.get("user_permission")
                can_edit = user_permission == "edit"

                # Get team sharing metadata
                shared_in_teams = agent.get("shared_in_teams", 0)
                team_ids = agent.get("team_ids", [])

                agents.append({
                    "id": str(agent["id"]),
                    "name": agent["name"],
                    "agent_type": agent["agent_type"] or "conversational",
                    "prompt_template": agent["system_prompt"],
                    "description": agent["description"],
                    "capabilities": config.get("capabilities", []),
                    "access_group": agent["access_group"],
                    "config": config,
                    "model": agent["model"],
                    "temperature": float(agent["temperature"]) if agent["temperature"] is not None else None,
                    "max_tokens": agent["max_tokens"],
                    "visibility": agent["visibility"],
                    "dataset_connection": config.get("dataset_connection"),
                    "selected_dataset_ids": config.get("selected_dataset_ids", []),
                    "personality_config": config.get("personality_config", {}),
                    "resource_preferences": config.get("resource_preferences", {}),
                    "tags": config.get("tags", []),
                    "is_favorite": config.get("is_favorite", False),
                    "disclaimer": config.get("disclaimer"),
                    "easy_prompts": config.get("easy_prompts", []),
                    "conversation_count": int(agent["user_conversation_count"]) if agent.get("user_conversation_count") else 0,
                    "last_used_at": agent["user_last_used_at"].isoformat() if agent.get("user_last_used_at") else None,
                    "total_cost_cents": 0,
                    "created_at": agent["created_at"].isoformat() if agent["created_at"] else None,
                    "updated_at": agent["updated_at"].isoformat() if agent["updated_at"] else None,
                    "is_active": agent["is_active"],
                    "user_id": agent["created_by"],
                    "created_by_name": agent.get("created_by_name", "Unknown"),
                    "tenant_domain": self.tenant_domain,
                    "can_edit": can_edit,
                    "can_delete": False,  # Only owner can delete
                    "is_owner": False,  # Team-shared agents
                    "shared_via_team": True,
                    "shared_in_teams": shared_in_teams,
                    "team_ids": [str(tid) for tid in team_ids] if team_ids else [],
                    "team_permission": user_permission
                })

            logger.info(f"Retrieved {len(agents)} team-shared agents for user {user_id}")
            return agents

        except Exception as e:
            logger.error(f"Error fetching team-shared agents for user {user_id}: {e}")
            return []

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent by ID using PostgreSQL"""
        try:
            # Get PostgreSQL client
            pg_client = await get_postgresql_client()

            # Resolve user UUID with caching (performance optimization)
            try:
                user_id = await self._get_resolved_user_uuid()
            except ValueError as e:
                logger.warning(f"User not found: {self.user_email} (or {self.user_id}) in tenant {self.tenant_domain}: {e}")
                return None

            # Check if user is admin - admins can see all agents
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Query the agent first
            query = """
                SELECT
                    a.id, a.name, a.description, a.system_prompt, a.model, a.temperature, a.max_tokens,
                    a.visibility, a.configuration, a.access_group, a.created_at, a.updated_at,
                    a.is_active, a.created_by, a.agent_type,
                    COUNT(c.id) as conversation_count
                FROM agents a
                LEFT JOIN conversations c ON a.id = c.agent_id
                WHERE a.id = $1 AND a.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                GROUP BY a.id, a.name, a.description, a.system_prompt, a.model, a.temperature, a.max_tokens,
                         a.visibility, a.configuration, a.access_group, a.created_at, a.updated_at,
                         a.is_active, a.created_by, a.agent_type
                LIMIT 1
            """

            agent_data = await pg_client.fetch_one(query, agent_id, self.tenant_domain)
            logger.info(f"Agent query result: {agent_data is not None}")

            # If agent doesn't exist, return None
            if not agent_data:
                return None

            # Check access: admin, owner, organization, or team-based
            if not is_admin:
                is_owner = str(agent_data["created_by"]) == str(user_id)
                is_org_wide = agent_data["visibility"] == "organization"

                # Check team-based access if not owner or org-wide
                if not is_owner and not is_org_wide:
                    # Import TeamService here to avoid circular dependency
                    from app.services.team_service import TeamService
                    team_service = TeamService(self.tenant_domain, str(user_id), self.user_email)

                    has_team_access = await team_service.check_user_resource_permission(
                        user_id=str(user_id),
                        resource_type="agent",
                        resource_id=agent_id,
                        required_permission="read"
                    )

                    if not has_team_access:
                        logger.warning(f"User {user_id} denied access to agent {agent_id}")
                        return None

                    logger.info(f"User {user_id} has team-based access to agent {agent_id}")
            
            if agent_data:
                # Parse configuration JSON if it's a string
                config = agent_data["configuration"]
                if isinstance(config, str):
                    config = json.loads(config)
                elif config is None:
                    config = {}
                
                # Convert to proper format
                logger.info(f"Config disclaimer: {config.get('disclaimer')}, easy_prompts: {config.get('easy_prompts')}")

                # Compute is_owner for export permission checks
                is_owner = str(agent_data["created_by"]) == str(user_id)

                result = {
                    "id": str(agent_data["id"]),
                    "name": agent_data["name"],
                    "agent_type": agent_data["agent_type"] or "conversational",
                    "prompt_template": agent_data["system_prompt"],
                    "description": agent_data["description"],
                    "capabilities": config.get("capabilities", []),
                    "access_group": agent_data["access_group"],
                    "config": config,
                    "model": agent_data["model"],
                    "temperature": float(agent_data["temperature"]) if agent_data["temperature"] is not None else None,
                    "max_tokens": agent_data["max_tokens"],
                    "visibility": agent_data["visibility"],
                    "dataset_connection": config.get("dataset_connection"),
                    "selected_dataset_ids": config.get("selected_dataset_ids", []),
                    "personality_config": config.get("personality_config", {}),
                    "resource_preferences": config.get("resource_preferences", {}),
                    "tags": config.get("tags", []),
                    "is_favorite": config.get("is_favorite", False),
                    "disclaimer": config.get("disclaimer"),
                    "easy_prompts": config.get("easy_prompts", []),
                    "conversation_count": int(agent_data["conversation_count"]) if agent_data.get("conversation_count") is not None else 0,
                    "total_cost_cents": 0,
                    "created_at": agent_data["created_at"].isoformat() if agent_data["created_at"] else None,
                    "updated_at": agent_data["updated_at"].isoformat() if agent_data["updated_at"] else None,
                    "is_active": agent_data["is_active"],
                    "created_by": agent_data["created_by"],  # Keep DB field
                    "user_id": agent_data["created_by"],  # Alias for compatibility
                    "is_owner": is_owner,  # Computed ownership for export/edit permissions
                    "tenant_domain": self.tenant_domain
                }
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error reading agent {agent_id}: {e}")
            return None

    async def update_agent(
        self,
        agent_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an agent's configuration using PostgreSQL with permission checks"""
        try:
            logger.info(f"Processing updates for agent {agent_id}: {updates}")

            # Log which fields will be processed
            logger.info(f"Update fields being processed: {list(updates.keys())}")
            # Get PostgreSQL client
            pg_client = await get_postgresql_client()

            # Get user role for permission checks
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)

            # If updating visibility, validate permission
            if "visibility" in updates:
                validate_visibility_permission(updates["visibility"], user_role)
                logger.info(f"User {self.user_email} (role: {user_role}) updating agent visibility to: {updates['visibility']}")
            
            # Build dynamic UPDATE query based on provided updates
            set_clauses = []
            params = []
            param_idx = 1
            
            # Collect all configuration updates in a single object
            config_updates = {}
            
            # Handle each update field mapping to correct column names
            for field, value in updates.items():
                if field in ["name", "description", "access_group"]:
                    set_clauses.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field == "prompt_template":
                    set_clauses.append(f"system_prompt = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field in ["model", "temperature", "max_tokens", "visibility", "agent_type"]:
                    set_clauses.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field == "is_active":
                    set_clauses.append(f"is_active = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif field in ["config", "configuration", "personality_config", "resource_preferences", "tags", "is_favorite",
                              "dataset_connection", "selected_dataset_ids", "disclaimer", "easy_prompts"]:
                    # Collect configuration updates
                    if field in ["config", "configuration"]:
                        config_updates.update(value if isinstance(value, dict) else {})
                    else:
                        config_updates[field] = value
            
            # Apply configuration updates as a single operation
            if config_updates:
                set_clauses.append(f"configuration = configuration || ${param_idx}::jsonb")
                params.append(json.dumps(config_updates))
                param_idx += 1
            
            if not set_clauses:
                logger.warning(f"No valid update fields provided for agent {agent_id}")
                return await self.get_agent(agent_id)
            
            # Add updated_at timestamp
            set_clauses.append(f"updated_at = NOW()")

            # Resolve user UUID with caching (performance optimization)
            try:
                user_id = await self._get_resolved_user_uuid()
            except ValueError as e:
                logger.warning(f"User not found for update: {self.user_email} (or {self.user_id}) in tenant {self.tenant_domain}: {e}")
                return None

            # Check if user is admin - admins can update any agent
            is_admin = user_role in ["admin", "developer"]

            # Build final query - admins can update any agent in tenant, others only their own
            if is_admin:
                query = f"""
                    UPDATE agents
                    SET {', '.join(set_clauses)}
                    WHERE id = ${param_idx}
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = ${param_idx + 1})
                    RETURNING id
                """
                params.extend([agent_id, self.tenant_domain])
            else:
                query = f"""
                    UPDATE agents
                    SET {', '.join(set_clauses)}
                    WHERE id = ${param_idx}
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = ${param_idx + 1})
                      AND created_by = ${param_idx + 2}
                    RETURNING id
                """
                params.extend([agent_id, self.tenant_domain, user_id])
            
            # Execute update
            logger.info(f"Executing update query: {query}")
            logger.info(f"Query parameters: {params}")
            updated_id = await pg_client.fetch_scalar(query, *params)
            logger.info(f"Update result: {updated_id}")
            
            if updated_id:
                # Get updated agent data
                updated_agent = await self.get_agent(agent_id)
                
                logger.info(f"Updated agent {agent_id} in PostgreSQL")
                return updated_agent
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating agent {agent_id}: {e}")
            return None

    async def delete_agent(self, agent_id: str) -> bool:
        """Soft delete an agent using PostgreSQL"""
        try:
            # Get PostgreSQL client
            pg_client = await get_postgresql_client()

            # Get user role to check if admin
            user_role = await get_user_role(pg_client, self.user_email, self.tenant_domain)
            is_admin = user_role in ["admin", "developer"]

            # Soft delete in PostgreSQL - admins can delete any agent, others only their own
            if is_admin:
                query = """
                    UPDATE agents
                    SET is_active = false, updated_at = NOW()
                    WHERE id = $1
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                    RETURNING id
                """
                deleted_id = await pg_client.fetch_scalar(query, agent_id, self.tenant_domain)
            else:
                query = """
                    UPDATE agents
                    SET is_active = false, updated_at = NOW()
                    WHERE id = $1
                      AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                      AND created_by = (SELECT id FROM users WHERE email = $3)
                    RETURNING id
                """
                deleted_id = await pg_client.fetch_scalar(query, agent_id, self.tenant_domain, self.user_email or self.user_id)
            
            if deleted_id:
                logger.info(f"Deleted agent {agent_id} from PostgreSQL")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting agent {agent_id}: {e}")
            return False
    
    async def check_access_permission(self, agent_id: str, requesting_user_id: str, access_type: str = "read") -> bool:
        """
        Check if user has access to agent (via ownership, organization, or team).

        Args:
            agent_id: UUID of the agent
            requesting_user_id: UUID of the user requesting access
            access_type: 'read' or 'edit' (default: 'read')

        Returns:
            True if user has required access
        """
        try:
            pg_client = await get_postgresql_client()

            # Check if admin/developer
            user_role = await get_user_role(pg_client, requesting_user_id, self.tenant_domain)
            if user_role in ["admin", "developer"]:
                return True

            # Get agent to check ownership and visibility
            query = """
                SELECT created_by, visibility
                FROM agents
                WHERE id = $1 AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
            """
            agent_data = await pg_client.fetch_one(query, agent_id, self.tenant_domain)

            if not agent_data:
                return False

            owner_id = str(agent_data["created_by"])
            visibility = agent_data["visibility"]

            # Owner has full access
            if requesting_user_id == owner_id:
                return True

            # Organization-wide resources are accessible to all in tenant
            if visibility == "organization":
                return True

            # Check team-based access
            from app.services.team_service import TeamService
            team_service = TeamService(self.tenant_domain, requesting_user_id, requesting_user_id)

            return await team_service.check_user_resource_permission(
                user_id=requesting_user_id,
                resource_type="agent",
                resource_id=agent_id,
                required_permission=access_type
            )

        except Exception as e:
            logger.error(f"Error checking access permission for agent {agent_id}: {e}")
            return False
    
    async def _check_team_membership(self, user_id: str, team_members: List[str]) -> bool:
        """Check if user is in the team members list"""
        return user_id in team_members
    
    async def _check_same_tenant(self, user_id: str) -> bool:
        """Check if requesting user is in the same tenant through PostgreSQL"""
        try:
            pg_client = await get_postgresql_client()
            
            # Check if user exists in same tenant
            query = """
                SELECT COUNT(*) as count
                FROM users
                WHERE id = $1 AND tenant_id = (SELECT id FROM tenants WHERE domain = $2)
            """
            
            result = await pg_client.fetch_one(query, user_id, self.tenant_domain)
            return result and result["count"] > 0
            
        except Exception as e:
            logger.error(f"Failed to check tenant membership for user {user_id}: {e}")
            return False
    
    def get_agent_conversation_history(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for an agent (file-based)"""
        conversations_path = Path(f"/data/{self.tenant_domain}/users/{self.user_id}/conversations")
        conversations_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        conversations = []
        try:
            for conv_file in conversations_path.glob("*.json"):
                with open(conv_file, 'r') as f:
                    conv_data = json.load(f)
                    if conv_data.get("agent_id") == agent_id:
                        conversations.append(conv_data)
        except Exception as e:
            logger.error(f"Error reading conversations for agent {agent_id}: {e}")
            
        conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return conversations