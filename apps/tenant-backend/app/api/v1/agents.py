"""
Agent API endpoints for GT 2.0 Tenant Backend

Provides comprehensive agent management with template support,
capability configuration, and file-based storage.
This is the primary API - agents.py provides backward compatibility.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import io
import httpx

from app.core.security import get_current_user
from app.core.response_filter import ResponseFilter
from app.core.permissions import is_effective_owner, get_user_role, ADMIN_ROLES
from app.core.cache import get_cache
from app.services.agent_service import AgentService
from app.api.auth import get_tenant_user_uuid_by_email
from app.services.resource_service import ResourceService
from app.utils.csv_helper import AgentCSVHelper
# TEMPORARY: Disabled during PostgreSQL migration
# from app.services.team_access_service import TeamAccessService
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentTemplate,
    AgentTemplateListResponse,
    AgentCapabilities,
    AgentStatistics
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])
cache = get_cache()


async def get_agent_service_for_user(current_user: Dict[str, Any]) -> AgentService:
    """Helper function to create AgentService with proper tenant UUID mapping"""
    user_email = current_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="User email not found in token")

    tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
    if not tenant_user_uuid:
        raise HTTPException(status_code=404, detail=f"User {user_email} not found in tenant system")

    return AgentService(
        tenant_domain=current_user.get('tenant_domain', 'test'),
        user_id=tenant_user_uuid,
        user_email=user_email
    )

async def get_dynamic_agent_templates(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Get agent templates with dynamically available models and capabilities"""
    resource_service = ResourceService()
    available_models = await resource_service.get_available_models(user_id)
    
    # Get first available model as default (or None if no models available)
    default_model = available_models[0]["model_id"] if available_models else None
    
    if not default_model:
        logger.warning("No models available for user - templates will require manual model selection")
    
    return {
    "research_agent": {
        "user_id": "research_agent",
        "name": "Research & Analysis Agent",
        "description": "Specialized in information synthesis, analysis, and research support",
        "icon": "🔍",
        "category": "research",
        "prompt": """You are a research agent specialized in information synthesis and analysis.
Focus on provuser_iding well-sourced, analytical responses with clear reasoning.
Always cite sources when available and maintain academic rigor in your analysis.""",
        "default_capabilities": [cap for cap in [
            f"llm:{default_model}" if default_model else None,
            "rag:semantic_search",
            "tools:web_search",
            "export:citations"
        ] if cap is not None],
        "personality_config": {
            "tone": "formal",
            "explanation_depth": "detailed",
            "interaction_style": "analytical"
        },
        "resource_preferences": {
            "primary_llm": default_model,
            "temperature": 0.7
        }
    },
    "coding_agent": {
        "user_id": "coding_agent",
        "name": "Software Development Agent",
        "description": "Expert in code quality, debugging, and development best practices",
        "icon": "💻",
        "category": "development",
        "prompt": """You are a software development agent focused on code quality and best practices.
Provuser_ide clear explanations, suggest improvements, and help debug issues.
Always consuser_ider security, performance, and maintainability in your suggestions.""",
        "default_capabilities": [cap for cap in [
            f"llm:{default_model}" if default_model else None,
            "tools:github_integration",
            "resources:documentation",
            "export:code_snippets"
        ] if cap is not None],
        "personality_config": {
            "tone": "technical",
            "explanation_depth": "code-focused",
            "interaction_style": "collaborative"
        },
        "resource_preferences": {
            "primary_llm": default_model,
            "temperature": 0.3
        }
    },
    "cyber_analyst": {
        "user_id": "cyber_analyst",
        "name": "Cybersecurity Analysis Agent",
        "description": "Threat detection, security analysis, and incuser_ident response support",
        "icon": "🛡️",
        "category": "cybersecurity",
        "prompt": """You are a cybersecurity analyst agent for threat detection and response.
Prioritize security best practices and provuser_ide actionable recommendations.
Always consuser_ider the threat landscape and maintain a security-first mindset.""",
        "default_capabilities": [cap for cap in [
            f"llm:{default_model}" if default_model else None,
            "tools:security_scanning",
            "resources:threat_intelligence",
            "export:security_reports"
        ] if cap is not None],
        "personality_config": {
            "tone": "professional",
            "explanation_depth": "technical",
            "interaction_style": "advisory"
        },
        "resource_preferences": {
            "primary_llm": default_model,
            "temperature": 0.2
        }
    },
    "educational_tutor": {
        "user_id": "educational_tutor",
        "name": "AI Literacy Educational Agent",
        "description": "Develops critical thinking and AI literacy through Socratic questioning",
        "icon": "🎓",
        "category": "education",
        "prompt": """You are an educational agent focused on developing critical thinking and AI literacy.
Use socratic questioning and encourage deep analysis of problems.
Guuser_ide learners to discover answers rather than provuser_iding them directly.""",
        "default_capabilities": [cap for cap in [
            f"llm:{default_model}" if default_model else None,
            "games:strategic_thinking",
            "puzzles:logic_reasoning",
            "analytics:learning_progress"
        ] if cap is not None],
        "personality_config": {
            "tone": "encouraging",
            "explanation_depth": "adaptive",
            "interaction_style": "teaching"
        },
        "resource_preferences": {
            "primary_llm": default_model,
            "temperature": 0.8
        }
    }
}

# Agent Templates
@router.get("/templates", response_model=AgentTemplateListResponse)
async def list_agent_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    current_user: str = Depends(get_current_user)
):
    """Get available agent templates for creating new agents"""
    logger.info("Fetching agent templates")
    
    # Get dynamic templates with user's available models
    agent_templates = await get_dynamic_agent_templates(current_user)
    
    filtered_templates = []
    for template_user_id, template in agent_templates.items():
        # Apply category filter
        if category and template.get("category") != category:
            continue
            
        # Apply search filter
        if search:
            search_lower = search.lower()
            if (search_lower not in template["name"].lower() and 
                search_lower not in template["description"].lower()):
                continue
        
        # Convert to response format
        template_response = AgentTemplate(
            user_id=template["user_id"],
            name=template["name"],
            description=template["description"],
            icon=template["icon"],
            category=template["category"],
            prompt=template["prompt"],
            default_capabilities=template["default_capabilities"],
            personality_config=template["personality_config"],
            resource_preferences=template["resource_preferences"]
        )
        filtered_templates.append(template_response)
    
    return AgentTemplateListResponse(
        templates=filtered_templates,
        total=len(filtered_templates)
    )

# Lightweight Endpoints for Performance
@router.get("/minimal")
async def list_agents_minimal(
    response: Response,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Lightweight endpoint returning only id and name - for dropdowns and filters

    Performance optimization: Returns minimal data for UI components that only need
    basic agent identification (sidebar filters, dropdown selectors, etc.)
    """
    user_id = current_user.get('sub')
    logger.info(f"Listing minimal agents for user {user_id}")

    # Check cache first (60-second TTL)
    cache_key = f"agents_minimal_{user_id}"
    cached_data = cache.get(cache_key, ttl=60)
    if cached_data:
        logger.debug(f"Returning cached minimal agent list for user {user_id}")
        response.headers["Cache-Control"] = "public, max-age=60"
        response.headers["X-Cache-Hit"] = "true"
        return cached_data

    # Set cache headers for better performance
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["X-Cache-Hit"] = "false"

    service = await get_agent_service_for_user(current_user)
    agents = await service.get_user_agents(active_only=True)

    # Return only id and name for minimal payload
    minimal_agents = [
        {"id": agent.get('id'), "name": agent.get('name')}
        for agent in agents
    ]

    # Cache for 60 seconds
    cache.set(cache_key, minimal_agents)
    logger.debug(f"Cached minimal agent list for user {user_id}")

    return minimal_agents


@router.get("/summary")
async def list_agents_summary(
    response: Response,
    current_user: Dict[str, Any] = Depends(get_current_user),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=100, description="Maximum agents to return"),
    offset: int = Query(0, ge=0, description="Number of agents to skip")
):
    """
    Summary endpoint excluding heavy fields - for gallery/list views

    Performance optimization: Returns agent data WITHOUT system_prompt, model_parameters,
    and tool_configurations which can be very large. Perfect for gallery views where
    only display metadata is needed.
    """
    user_id = current_user.get('sub')
    logger.info(f"Listing summary agents for user {user_id}")

    # Check cache first (30-second TTL) - only if no filters applied
    # Cache key includes filters to ensure correct data
    cache_key = f"agents_summary_{user_id}_{category or 'all'}_{search or 'none'}_{limit}_{offset}"
    if not category and not search and offset == 0:
        # Simple case - cache the default view
        cache_key = f"agents_summary_{user_id}"
        cached_data = cache.get(cache_key, ttl=30)
        if cached_data:
            logger.debug(f"Returning cached summary agent list for user {user_id}")
            response.headers["Cache-Control"] = "public, max-age=30"
            response.headers["X-Cache-Hit"] = "true"
            return cached_data

    # Set cache headers for better performance
    response.headers["Cache-Control"] = "public, max-age=30"
    response.headers["X-Cache-Hit"] = "false"

    service = await get_agent_service_for_user(current_user)
    agents = await service.get_user_agents(active_only=True)

    # Apply filters
    if category:
        agents = [a for a in agents if a.get('agent_type') == category]
    if search:
        search_lower = search.lower()
        agents = [a for a in agents if (
            search_lower in a.get('name', '').lower() or
            search_lower in a.get('description', '').lower()
        )]

    # Build summary responses (exclude heavy fields)
    summary_agents = []
    for agent in agents[offset:offset+limit]:
        is_owner = agent.get('is_owner', False)

        summary_data = {
            'id': agent.get('id', ''),
            'name': agent.get('name', ''),
            'description': agent.get('description', ''),
            'category': agent.get('agent_type'),
            'tags': agent.get('config', {}).get('tags', []) if isinstance(agent.get('config'), dict) else [],
            'visibility': agent.get('visibility', 'individual'),
            'disclaimer': agent.get('disclaimer'),
            'easy_prompts': agent.get('easy_prompts', []),
            'usage_count': agent.get('conversation_count', 0),
            'created_at': agent.get('created_at'),
            'updated_at': agent.get('updated_at'),
            'created_by_name': agent.get('created_by_name'),
            'can_edit': agent.get('can_edit', False),
            'can_delete': agent.get('can_delete', False),
            'is_owner': is_owner,
            # Excluded fields for performance:
            # - prompt_template (can be thousands of characters)
            # - model_parameters (complex nested object)
            # - tool_configurations (large config objects)
            # - personality_config (not needed for gallery view)
        }

        summary_agents.append(summary_data)

    result = {
        "data": summary_agents,
        "total": len(agents),
        "limit": limit,
        "offset": offset
    }

    # Cache default view (no filters) for 30 seconds
    if not category and not search and offset == 0:
        cache.set(cache_key, result)
        logger.debug(f"Cached summary agent list for user {user_id}")

    return result


# Agent Management
@router.get("", response_model=AgentListResponse)
async def list_agents(
    response: Response,
    current_user: Dict[str, Any] = Depends(get_current_user),
    active_only: bool = Query(True, description="Show only active agents (hide archived)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    template_user_id: Optional[str] = Query(None, description="Filter by template"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    sort: Optional[str] = Query(None, description="Sort by: recent_usage (user's last use), my_most_used (user's usage count)"),
    filter: Optional[str] = Query(None, description="Filter by: used_last_7_days, used_last_30_days"),
    limit: int = Query(50, ge=1, le=100, description="Maximum agents to return"),
    offset: int = Query(0, ge=0, description="Number of agents to skip")
):
    """List all agents for the current user using GT 2.0 file-based storage with caching"""
    user_id = current_user.get('sub')
    logger.info(f"Listing agents for user {user_id}")

    # Get database client for user role lookup (needed for cache key)
    from app.core.postgresql_client import get_postgresql_client
    pg_client = await get_postgresql_client()

    # Get user role for cache key (critical for permission correctness)
    user_email = current_user.get('email')
    tenant_domain = current_user.get('tenant_domain')
    user_role = await get_user_role(pg_client, user_email, tenant_domain)

    # Check cache first (45-second TTL) - cache full unfiltered list
    cache_key = f"agents_full_{user_id}_{user_role}_{active_only}"
    cached_data = cache.get(cache_key, ttl=45)

    if cached_data is not None:
        logger.debug(f"Cache hit for agents list: {cache_key}")
        response.headers["X-Cache-Hit"] = "true"

        # Unpack cached data
        agents = cached_data['agents']

        # Apply in-memory filters (cheap operations)
        filtered_agents = agents
        if category:
            filtered_agents = [a for a in filtered_agents if a.get('agent_type') == category]
        if search:
            search_lower = search.lower()
            filtered_agents = [a for a in filtered_agents if (
                search_lower in a.get('name', '').lower() or
                search_lower in a.get('description', '').lower()
            )]
        if tag:
            filtered_agents = [a for a in filtered_agents if tag in a.get('tags', [])]

        # Apply pagination
        paginated_agents = filtered_agents[offset:offset+limit]

        # Use cached agent_responses (already built)
        agent_responses = [AgentResponse(**agent_data) for agent_data in paginated_agents]

        return AgentListResponse(
            data=agent_responses,
            total=len(filtered_agents),
            limit=limit,
            offset=offset
        )

    # Cache miss - execute full query
    logger.debug(f"Cache miss for agents list: {cache_key}")
    response.headers["X-Cache-Hit"] = "false"

    # GT 2.0: File-based agent service with tenant isolation
    service = await get_agent_service_for_user(current_user)

    # Get agents from PostgreSQL + PGVector with user-specific usage tracking
    agents = await service.get_user_agents(
        active_only=active_only,
        sort_by=sort,
        filter_usage=filter
    )
    
    # Note: Database query already filters to active agents only
    # Apply filters
    if category:
        agents = [a for a in agents if a.get('agent_type') == category]
    if search:
        search_lower = search.lower()
        agents = [a for a in agents if (
            search_lower in a.get('name', '').lower() or 
            search_lower in a.get('description', '').lower()
        )]
    if tag:
        agents = [a for a in agents if tag in a.get('tags', [])]
    
    # Convert to response format with security filtering
    # Build full agent data for ALL agents (for caching)

    # OPTIMIZATION: Batch fetch team shares for all owned agents (fixes N+1 query)
    # Collect agent IDs where user is owner
    owned_agent_ids = [agent.get('id', '') for agent in agents if agent.get('is_owner', False)]
    team_shares_map = {}
    if owned_agent_ids:
        user_email = current_user.get('email')
        tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)

        from app.services.team_service import TeamService
        team_service = TeamService(
            tenant_domain=current_user.get('tenant_domain', 'test'),
            user_id=tenant_user_uuid,
            user_email=user_email
        )
        # Single batch query instead of N queries
        raw_team_shares = await team_service.get_resource_teams_batch('agent', owned_agent_ids)

        # Convert to frontend format
        for agent_id, teams in raw_team_shares.items():
            team_shares_map[agent_id] = [
                {
                    'team_id': team_data['id'],
                    'team_name': team_data.get('name', 'Unknown Team'),
                    'user_permissions': team_data.get('user_permissions', {})
                }
                for team_data in teams
            ]

    full_agent_data_list = []
    for agent in agents:
        logger.info(f"Agent {agent.get('name')}: disclaimer={agent.get('disclaimer')}, easy_prompts={agent.get('easy_prompts')}")

        # Determine access level for filtering
        is_owner = agent.get('is_owner', False)
        shared_via_team = agent.get('shared_via_team', False)
        can_view = agent.get('can_edit', False) or is_owner or shared_via_team  # Owners, editors, and team members can view details

        # Get team shares from batch lookup (instead of per-agent query)
        team_shares = team_shares_map.get(agent.get('id', '')) if is_owner else None

        # Build full agent data
        agent_data = {
            'id': agent.get('id', ''),
            'name': agent.get('name', ''),
            'description': agent.get('description', ''),
            'template_id': agent.get('template_id'),
            'category': agent.get('agent_type'),
            'prompt_template': agent.get('prompt_template', ''),
            'model': agent.get('model', ''),
            'temperature': agent.get('temperature', 0.7),
            # max_tokens removed - now determined by model configuration
            'visibility': agent.get('visibility', 'individual'),
            'dataset_connection': agent.get('dataset_connection'),
            'selected_dataset_ids': agent.get('selected_dataset_ids', []),
            'personality_config': agent.get('config', {}).get('personality_config', {}) if isinstance(agent.get('config'), dict) else {},
            'resource_preferences': agent.get('config', {}).get('resource_preferences', {}) if isinstance(agent.get('config'), dict) else {},
            'tags': agent.get('config', {}).get('tags', []) if isinstance(agent.get('config'), dict) else [],
            'is_favorite': agent.get('config', {}).get('is_favorite', False) if isinstance(agent.get('config'), dict) else False,
            'disclaimer': agent.get('disclaimer'),
            'easy_prompts': agent.get('easy_prompts', []),
            'conversation_count': agent.get('conversation_count', 0),
            'usage_count': agent.get('conversation_count', 0),  # Frontend expects usage_count
            'total_cost_cents': agent.get('total_cost_cents', 0),
            'created_at': agent.get('created_at'),
            'updated_at': agent.get('updated_at'),
            'created_by_name': agent.get('created_by_name'),
            'can_edit': agent.get('can_edit', False),
            'can_delete': agent.get('can_delete', False),
            'is_owner': is_owner,
            'team_shares': team_shares
        }

        # Apply security filtering based on ownership
        filtered_data = ResponseFilter.filter_agent_response(
            agent_data,
            is_owner=is_owner,
            can_view=can_view
        )

        full_agent_data_list.append(filtered_data)

    # Cache the full unfiltered agent list (as serializable dicts)
    cache_data = {
        'agents': full_agent_data_list,
    }
    cache.set(cache_key, cache_data)
    logger.info(f"Cached agents list for {cache_key} (TTL: 45s, count: {len(full_agent_data_list)})")

    # Apply pagination for response
    paginated_agent_data = full_agent_data_list[offset:offset+limit]
    agent_responses = [AgentResponse(**agent_data) for agent_data in paginated_agent_data]

    return AgentListResponse(
        data=agent_responses,
        total=len(full_agent_data_list),
        limit=limit,
        offset=offset
    )

@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    agent_data: AgentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new agent using GT 2.0 file-based storage"""
    logger.info("="*50)
    logger.info("🚀 CREATE AGENT ENDPOINT HIT!")
    logger.info("="*50)
    logger.info(f"Creating agent for user {current_user['sub']}")
    logger.info(f"Agent request data: {agent_data}")
    logger.info(f"Current user data: {current_user}")
    
    try:
        # GT 2.0: PostgreSQL-based agent service with tenant isolation
        service = await get_agent_service_for_user(current_user)
        
        # Extract template configuration if template_id provided
        template_config = {}
        if agent_data.template_id and agent_data.template_id in AGENT_TEMPLATES:
            template = AGENT_TEMPLATES[agent_data.template_id]
            template_config = {
                'agent_type': template['category'],
                'prompt_template': template['prompt'],
                'personality_config': template.get('personality_config', {}),
                'resource_preferences': template.get('resource_preferences', {}),
            }
        
        # Create agent with PostgreSQL storage
        agent = await service.create_agent(
            name=agent_data.name,
            agent_type=template_config.get('agent_type', 'conversational'),
            description=agent_data.description or '',
            prompt_template=getattr(agent_data, 'prompt_template', '') or template_config.get('prompt_template', ''),
            capabilities=template_config.get('capabilities', []),  # Use template capabilities
            access_group='individual',  # Default for now
            personality_config=agent_data.personality_config or template_config.get('personality_config', {}),
            resource_preferences=agent_data.resource_preferences or template_config.get('resource_preferences', {}),
            tags=agent_data.tags or [],
            template_id=agent_data.template_id,
            # Category for agent classification - auto-creates if not exists (Issue #215)
            category=agent_data.category or 'general',
            # MVP fields - Use model_id first (what frontend sends), fall back to model
            model=getattr(agent_data, 'model_id', None) or getattr(agent_data, 'model', None),
            temperature=getattr(agent_data, 'temperature', None),
            # max_tokens removed - now determined by model configuration
            dataset_connection=getattr(agent_data, 'dataset_connection', None),
            selected_dataset_ids=getattr(agent_data, 'selected_dataset_ids', None),
            # Additional fields for agent configuration
            visibility=getattr(agent_data, 'visibility', None),
            disclaimer=getattr(agent_data, 'disclaimer', None),
            easy_prompts=getattr(agent_data, 'easy_prompts', None)
        )

        # Validate team selection when visibility is 'team'
        team_shares = getattr(agent_data, 'team_shares', None)
        if agent.get('visibility') == 'team' and (not team_shares or len(team_shares) == 0):
            raise HTTPException(
                status_code=400,
                detail="Must select at least one team when visibility is 'team'"
            )

        # Share to teams if team_shares provided and visibility is 'team'
        if team_shares and agent.get('visibility') == 'team':
            # Get tenant UUID for TeamService (same pattern as other endpoints)
            user_email = current_user.get('email')
            tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)

            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=current_user['tenant_domain'],
                user_id=tenant_user_uuid,
                user_email=user_email
            )

            try:
                await team_service.share_resource_to_teams(
                    resource_id=agent['id'],
                    resource_type='agent',
                    shared_by=tenant_user_uuid,
                    team_shares=team_shares
                )
                logger.info(f"Agent {agent['id']} shared to {len(team_shares)} team(s)")
            except Exception as team_error:
                logger.error(f"Error sharing agent to teams: {team_error}")
                # Don't fail agent creation if sharing fails

        # Invalidate cache after successful agent creation
        user_id = current_user.get('sub')
        cache.delete(f"agents_minimal_{user_id}")
        cache.delete(f"agents_summary_{user_id}")
        cache.delete(f"agents_full_{user_id}")  # Invalidate full agent list cache (all role variants)
        logger.info(f"Invalidated agent cache for user {user_id} after agent creation")

        # Convert to response format (extract agent_type from model_config)
        model_config = agent.get('model_config', {})
        if isinstance(model_config, str):
            import json
            model_config = json.loads(model_config)

        return AgentResponse(
            id=agent['id'],
            name=agent['name'],
            description=agent['description'],
            template_id=agent.get('config', {}).get('template_id'),
            category=agent.get('agent_type', 'conversational'),
            prompt_template=agent.get('prompt_template'),
            model=agent.get('model'),
            temperature=agent.get('temperature'),
            # max_tokens removed - now determined by model configuration
            visibility=agent.get('visibility'),
            dataset_connection=agent.get('dataset_connection'),
            selected_dataset_ids=agent.get('selected_dataset_ids', []),
            personality_config=agent.get('personality_config', {}),
            resource_preferences=agent.get('resource_preferences', {}),
            tags=agent.get('tags', []),
            is_favorite=agent.get('is_favorite', False),
            disclaimer=agent.get('disclaimer'),
            easy_prompts=agent.get('easy_prompts', []),
            conversation_count=agent.get('conversation_count', 0),
            usage_count=agent.get('conversation_count', 0),
            total_cost_cents=agent.get('total_cost_cents', 0),
            created_at=agent.get('created_at', datetime.utcnow().isoformat()),
            updated_at=agent.get('updated_at', datetime.utcnow().isoformat())
        )
        
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")

@router.get("/{agent_user_id}", response_model=AgentResponse)
async def get_agent(
    agent_user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific agent by ID using GT 2.0 file-based storage"""
    logger.info(f"Getting agent {agent_user_id} for user {current_user['sub']}")
    
    # GT 2.0: File-based agent service with tenant isolation
    service = AgentService(
        tenant_domain=current_user['tenant_domain'], 
        user_id=str(current_user.get('sub', '')),
        user_email=current_user.get('email', 'gtadmin@test.com')
    )
    agent = await service.get_agent(agent_user_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentResponse(
        id=agent['id'],
        user_id=agent['user_id'],
        name=agent['name'],
        description=agent['description'],
        template_user_id=agent.get('config', {}).get('template_id'),
        category=agent['agent_type'],
        personality_config=agent.get('config', {}).get('personality_config', {}),
        resource_preferences=agent.get('config', {}).get('resource_preferences', {}),
        tags=agent.get('config', {}).get('tags', []),
        is_favorite=agent.get('config', {}).get('is_favorite', False),
        conversation_count=0,  # TODO: implement conversation history
        total_cost_cents=0,
        created_at=agent['created_at'],
        updated_at=agent['updated_at']
    )

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific agent by ID"""
    logger.info(f"Getting agent {agent_id} for user {current_user['sub']}")
    
    try:
        # GT 2.0: PostgreSQL Agent Service with Perfect Tenant Isolation
        service = AgentService(
            tenant_domain=current_user.get('tenant_domain', 'test'), 
            user_id=str(current_user.get('sub', '')),
            user_email=current_user.get('email', 'gtadmin@test.com')
        )
        
        # Get agent using AgentService
        agent = await service.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        logger.info(f"Agent data from service: disclaimer={agent.get('disclaimer')}, easy_prompts={agent.get('easy_prompts')}")

        # Determine access level for filtering
        is_owner = agent.get('is_owner', False)
        shared_via_team = agent.get('shared_via_team', False)
        can_view = agent.get('can_edit', False) or is_owner or shared_via_team

        # Get team shares if owner (for edit mode)
        team_shares = None
        if is_owner:
            # Get tenant UUID for TeamService
            user_email = current_user.get('email')
            tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)

            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=current_user.get('tenant_domain', 'test'),
                user_id=tenant_user_uuid,
                user_email=user_email
            )
            resource_teams = await team_service.get_resource_teams('agent', agent_id)

            # Convert to frontend format
            team_shares = []
            for team_data in resource_teams:
                team_shares.append({
                    'team_id': team_data['id'],  # get_resource_teams returns 'id' not 'team_id'
                    'team_name': team_data.get('name', 'Unknown Team'),
                    'user_permissions': team_data.get('user_permissions', {})
                })

        # Build full agent data
        agent_data = {
            'id': agent['id'],
            'name': agent['name'],
            'description': agent['description'],
            'template_id': None,  # Not stored in this version
            'category': agent.get('agent_type', 'conversational'),
            'prompt_template': agent.get('prompt_template', ''),
            'model': agent.get('model', ''),
            'temperature': agent.get('temperature', 0.7),
            # max_tokens removed - now determined by model configuration
            'visibility': agent.get('visibility', 'individual'),
            'dataset_connection': agent.get('dataset_connection'),
            'selected_dataset_ids': agent.get('selected_dataset_ids', []),
            'personality_config': agent.get('config', {}).get('personality_config', {}),
            'resource_preferences': agent.get('config', {}).get('resource_preferences', {}),
            'tags': agent.get('config', {}).get('tags', []),
            'is_favorite': agent.get('config', {}).get('is_favorite', False),
            'disclaimer': agent.get('disclaimer'),
            'easy_prompts': agent.get('easy_prompts', []),
            'conversation_count': 0,
            'total_cost_cents': 0,
            'created_at': agent.get('created_at', datetime.utcnow().isoformat()),
            'updated_at': agent.get('updated_at', datetime.utcnow().isoformat()),
            'is_owner': is_owner,
            'can_edit': agent.get('can_edit', False),
            'can_delete': agent.get('can_delete', False),
            'team_shares': team_shares
        }

        # Apply security filtering
        filtered_data = ResponseFilter.filter_agent_response(
            agent_data,
            is_owner=is_owner,
            can_view=can_view
        )

        return AgentResponse(**filtered_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    update_data: AgentUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update an agent"""
    logger.info(f"Updating agent {agent_id} for user {current_user['sub']}")
    logger.info(f"Update data received: {update_data.dict()}")
    
    try:
        # GT 2.0: PostgreSQL Agent Service with Perfect Tenant Isolation
        service = AgentService(
            tenant_domain=current_user.get('tenant_domain', 'test'),
            user_id=str(current_user.get('sub', '')),
            user_email=current_user.get('email', 'gtadmin@test.com')
        )

        # Get current agent to check for visibility changes
        current_agent = await service.get_agent(agent_id)
        if not current_agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Convert update data to dict
        updates = {}
        if update_data.name is not None:
            updates['name'] = update_data.name
        if update_data.description is not None:
            updates['description'] = update_data.description
        if update_data.category is not None:
            updates['agent_type'] = update_data.category
        if update_data.prompt_template is not None:
            updates['prompt_template'] = update_data.prompt_template
        if update_data.model is not None:
            updates['model'] = update_data.model
        if update_data.temperature is not None:
            updates['temperature'] = update_data.temperature
        # max_tokens removed - now determined by model configuration
        if update_data.visibility is not None:
            updates['visibility'] = update_data.visibility
        if update_data.dataset_connection is not None:
            updates['dataset_connection'] = update_data.dataset_connection
        if update_data.selected_dataset_ids is not None:
            updates['selected_dataset_ids'] = update_data.selected_dataset_ids
        if update_data.personality_config is not None:
            updates['personality_config'] = update_data.personality_config
        if update_data.resource_preferences is not None:
            updates['resource_preferences'] = update_data.resource_preferences
        if update_data.tags is not None:
            updates['tags'] = update_data.tags
        if update_data.is_favorite is not None:
            updates['is_favorite'] = update_data.is_favorite
        if update_data.disclaimer is not None:
            updates['disclaimer'] = update_data.disclaimer
        if update_data.easy_prompts is not None:
            updates['easy_prompts'] = update_data.easy_prompts

        # Check if visibility is changing from 'team' to 'individual'
        current_visibility = current_agent.get('visibility', 'individual')
        new_visibility = updates.get('visibility', current_visibility)

        if current_visibility == 'team' and new_visibility == 'individual':
            # User is changing from team to individual - remove all team shares
            # Get tenant UUID for TeamService
            user_email = current_user.get('email')
            tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)

            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=current_user.get('tenant_domain', 'test'),
                user_id=tenant_user_uuid,
                user_email=user_email
            )

            try:
                # Get all team shares for this agent
                resource_teams = await team_service.get_resource_teams('agent', agent_id)
                # Remove from each team
                for team in resource_teams:
                    await team_service.unshare_resource_from_team(
                        resource_id=agent_id,
                        resource_type='agent',
                        team_id=team['id']  # get_resource_teams returns 'id' not 'team_id'
                    )
                logger.info(f"Removed agent {agent_id} from {len(resource_teams)} team(s) due to visibility change")
            except Exception as unshare_error:
                logger.error(f"Error removing team shares: {unshare_error}")
                # Continue with update even if unsharing fails

        # Validate team selection when changing to 'team' visibility
        if new_visibility == 'team':
            team_shares = getattr(update_data, 'team_shares', None)
            # Only validate if team_shares is explicitly provided (not None)
            # If None, we're not changing team shares, so existing shares are preserved
            if team_shares is not None and (isinstance(team_shares, list) and len(team_shares) == 0):
                # User is explicitly trying to set team visibility with no teams selected
                # Check if agent already has shares that would be preserved
                # Get tenant UUID for TeamService
                user_email = current_user.get('email')
                tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)

                from app.services.team_service import TeamService
                team_service = TeamService(
                    tenant_domain=current_user.get('tenant_domain', 'test'),
                    user_id=tenant_user_uuid,
                    user_email=user_email
                )
                existing_shares = await team_service.get_resource_teams('agent', agent_id)
                if not existing_shares or len(existing_shares) == 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Must select at least one team when visibility is 'team'"
                    )

        # Update agent using AgentService
        updated_agent = await service.update_agent(agent_id, updates)

        # Handle team sharing if provided AND visibility is 'team'
        team_shares = getattr(update_data, 'team_shares', None)
        new_visibility = updates.get('visibility', current_agent.get('visibility', 'individual'))

        # Only process team shares when visibility is actually 'team'
        if team_shares is not None and new_visibility == 'team':
            # Get tenant UUID for TeamService
            user_email = current_user.get('email')
            tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)

            from app.services.team_service import TeamService
            team_service = TeamService(
                tenant_domain=current_user.get('tenant_domain', 'test'),
                user_id=tenant_user_uuid,
                user_email=user_email
            )

            # Update team shares: this replaces existing shares
            await team_service.share_resource_to_teams(
                resource_id=agent_id,
                resource_type='agent',
                shared_by=tenant_user_uuid,
                team_shares=team_shares
            )
        
        if not updated_agent:
            raise HTTPException(status_code=404, detail="Agent not found or update failed")

        # Invalidate cache after successful agent update
        user_id = current_user.get('sub')
        cache.delete(f"agents_minimal_{user_id}")
        cache.delete(f"agents_summary_{user_id}")
        cache.delete(f"agents_full_{user_id}")  # Invalidate full agent list cache (all role variants)
        logger.info(f"Invalidated agent cache for user {user_id} after agent update")

        # Parse model_config for response
        model_config = updated_agent.get('model_config', {})
        if isinstance(model_config, str):
            import json
            model_config = json.loads(model_config)

        return AgentResponse(
            id=updated_agent['id'],
            name=updated_agent['name'],
            description=updated_agent['description'],
            template_id=None,  # Not stored in this version
            category=updated_agent.get('agent_type', 'conversational'),
            prompt_template=updated_agent.get('prompt_template', ''),
            model=updated_agent.get('model', ''),
            temperature=updated_agent.get('temperature', 0.7),
            # max_tokens removed - now determined by model configuration
            visibility=updated_agent.get('visibility', 'individual'),
            dataset_connection=updated_agent.get('dataset_connection'),
            selected_dataset_ids=updated_agent.get('selected_dataset_ids', []),
            personality_config=updated_agent.get('config', {}).get('personality_config', {}),
            resource_preferences=updated_agent.get('config', {}).get('resource_preferences', {}),
            tags=updated_agent.get('config', {}).get('tags', []),
            is_favorite=updated_agent.get('config', {}).get('is_favorite', False),
            disclaimer=updated_agent.get('disclaimer'),
            easy_prompts=updated_agent.get('easy_prompts', []),
            conversation_count=0,
            total_cost_cents=0,
            created_at=updated_agent.get('created_at', datetime.utcnow().isoformat()),
            updated_at=updated_agent.get('updated_at', datetime.utcnow().isoformat())
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like validation errors) without modification
        raise
    except Exception as e:
        logger.error(f"Error updating agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Archive an agent (soft delete for audit trail compliance)"""
    logger.info(f"Archiving agent {agent_id} for user {current_user['sub']}")
    
    try:
        # GT 2.0: PostgreSQL Agent Service with Perfect Tenant Isolation
        service = AgentService(
            tenant_domain=current_user.get('tenant_domain', 'test'), 
            user_id=str(current_user.get('sub', '')),
            user_email=current_user.get('email', 'gtadmin@test.com')
        )
        
        # Soft delete agent using AgentService (preserves for audit trail)
        success = await service.delete_agent(agent_id)

        if not success:
            raise HTTPException(status_code=404, detail="Agent not found or archive failed")

        # Invalidate cache after successful agent deletion
        user_id = current_user.get('sub')
        cache.delete(f"agents_minimal_{user_id}")
        cache.delete(f"agents_summary_{user_id}")
        cache.delete(f"agents_full_{user_id}")  # Invalidate full agent list cache (all role variants)
        logger.info(f"Invalidated agent cache for user {user_id} after agent deletion")

        return {"message": "Agent archived successfully - preserved for audit trail"}
        
    except Exception as e:
        logger.error(f"Error archiving agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to archive agent: {str(e)}")

@router.get("/{agent_user_id}/capabilities", response_model=AgentCapabilities)
async def get_agent_capabilities(
    agent_user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get agent capabilities and configuration"""
    logger.info(f"Getting capabilities for agent {agent_user_id}")
    
    # GT 2.0: PostgreSQL + PGVector Agent Service with Perfect Tenant Isolation
    service = AgentService(
        tenant_domain=current_user.get('tenant_domain', 'test'), 
        user_id=str(current_user.get('sub', '')),
        user_email=current_user.get('email', 'gtadmin@test.com')
    )
    agent = await service.get_agent(agent_user_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentCapabilities(
        agent_user_id=str(agent.get('id', agent_user_id)),
        capabilities=agent.get('capabilities', []),
        resource_preferences=agent.get('resource_preferences', {}),
        allowed_tools=agent.get('allowed_tools', []),
        total=len(agent.get('capabilities', []))
    )

@router.post("/{agent_user_id}/clone")
async def clone_agent(
    agent_user_id: str,
    new_name: str = Body(..., description="Name for the cloned agent"),
    modifications: Optional[Dict[str, Any]] = Body(None, description="Modifications to apply"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Clone an agent with optional modifications"""
    logger.info(f"Cloning agent {agent_user_id} to {new_name}")
    
    # GT 2.0: PostgreSQL + PGVector Agent Service with Perfect Tenant Isolation
    service = AgentService(
        tenant_domain=current_user.get('tenant_domain', 'test'), 
        user_id=str(current_user.get('sub', '')),
        user_email=current_user.get('email', 'gtadmin@test.com')
    )
    
    # Get original agent
    original_agent = service.get_agent(agent_user_id)
    if not original_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Create new agent with cloned data
    cloned_agent = await service.create_agent(
        name=new_name,
        agent_type=original_agent.get('agent_type', 'conversational'),
        description=f"Cloned from {original_agent.get('name', 'Unknown')}",
        prompt_template=original_agent.get('prompt_template', ''),
        capabilities=original_agent.get('capabilities', []),
        access_group='individual',
        personality_config=original_agent.get('personality_config', {}),
        resource_preferences=original_agent.get('resource_preferences', {}),
        tags=original_agent.get('tags', [])
    )
    
    # Invalidate cache after successful agent cloning
    user_id = current_user.get('sub')
    cache.delete(f"agents_minimal_{user_id}")
    cache.delete(f"agents_summary_{user_id}")
    cache.delete(f"agents_full_{user_id}")
    logger.info(f"Invalidated agent cache for user {user_id} after agent cloning")

    # Parse model_config for response
    model_config = cloned_agent.get('model_config', {})
    if isinstance(model_config, str):
        import json
        model_config = json.loads(model_config)

    return AgentResponse(
        id=cloned_agent['id'],
        user_id=cloned_agent['owner_id'],
        name=cloned_agent['name'],
        description=cloned_agent['description'],
        template_user_id=None,
        category=model_config.get('agent_type', 'conversational'),
        personality_config=model_config.get('personality_config', {}),
        resource_preferences=model_config.get('resource_preferences', {}),
        tags=[],
        is_favorite=False,
        conversation_count=0,
        total_cost_cents=0,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )

@router.get("/{agent_user_id}/statistics", response_model=AgentStatistics)
async def get_agent_statistics(
    agent_user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get usage statistics for an agent"""
    logger.info(f"Getting statistics for agent {agent_user_id}")
    
    # GT 2.0: PostgreSQL + PGVector Agent Service with Perfect Tenant Isolation
    service = AgentService(
        tenant_domain=current_user.get('tenant_domain', 'test'), 
        user_id=str(current_user.get('sub', '')),
        user_email=current_user.get('email', 'gtadmin@test.com')
    )
    agent = await service.get_agent(agent_user_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentStatistics(
        agent_user_id=str(agent.get('id', agent_user_id)),
        name=agent.get('name', 'Unknown'),
        created_at=agent.get('created_at', datetime.utcnow().isoformat()),
        last_used_at=agent.get('last_used_at'),
        conversation_count=agent.get('usage_count', 0),
        total_messages=agent.get('total_messages', 0),
        total_tokens_used=agent.get('total_tokens', 0),
        total_cost_cents=agent.get('total_cost_cents', 0),
        total_cost_dollars=agent.get('total_cost_cents', 0) / 100.0,
        average_tokens_per_message=agent.get('avg_tokens_per_message', 0.0),
        is_favorite=agent.get('is_favorite', False),
        tags=agent.get('tags', [])
    )


@router.post("/bulk-import")
async def bulk_import_agents(
    csv_file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Body(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Bulk import agents from CSV (file upload or pasted text).

    CSV Format (RFC 4180):
    - Comma delimiter, quoted fields for embedded commas/newlines
    - Header row required with column names
    - Arrays: pipe-separated (easy_prompts, selected_dataset_ids)
    - Tags: comma-separated
    - Objects: JSON strings (personality_config, resource_preferences)

    Duplicate Handling:
    - Auto-rename with suffix: "Agent Name" → "Agent Name (1)"

    Returns:
    - success_count: Number of successfully imported agents
    - error_count: Number of failed rows
    - errors: List of validation errors with row numbers
    - created_agents: List of created agent IDs
    """
    logger.info(f"Bulk import agents for user {current_user['sub']}")

    try:
        # Get CSV content from either file or text
        csv_content = None
        if csv_file:
            content_bytes = await csv_file.read()
            csv_content = content_bytes.decode('utf-8')
        elif csv_text:
            csv_content = csv_text
        else:
            raise HTTPException(status_code=400, detail="Either csv_file or csv_text must be provided")

        # Validate CSV size (1MB limit)
        if not AgentCSVHelper.validate_csv_size(csv_content, max_size_mb=1.0):
            raise HTTPException(status_code=413, detail="CSV file too large (max 1MB)")

        # Parse and validate CSV
        valid_agents, errors = AgentCSVHelper.parse_csv(csv_content)

        logger.info(f"CSV parsed: {len(valid_agents)} valid, {len(errors)} errors")

        # Get existing agent names for duplicate detection
        service = await get_agent_service_for_user(current_user)
        existing_agents = await service.get_user_agents(active_only=True)
        existing_names = [agent.get('name', '') for agent in existing_agents]

        # Fetch available models for validation
        available_models = []
        try:
            import os
            if os.path.exists('/.dockerenv'):
                resource_cluster_url = "http://resource-cluster:8000"
            else:
                from app.core.config import get_settings
                settings = get_settings()
                resource_cluster_url = settings.resource_cluster_url

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{resource_cluster_url}/api/v1/models/",
                    headers={"X-Tenant-Domain": current_user.get("tenant_domain", "default")},
                    timeout=10.0
                )
                if response.status_code == 200:
                    models_data = response.json()
                    available_models = [
                        model["id"] for model in models_data.get("models", [])
                        if model["status"]["deployment"] == "available"
                    ]
                    logger.info(f"Fetched {len(available_models)} available models for validation")
        except Exception as e:
            logger.warning(f"Could not fetch models for validation: {e}")

        # Fetch available datasets for validation
        available_datasets = []
        try:
            from app.core.postgresql_client import get_postgresql_client
            pg_client = await get_postgresql_client()
            datasets_query = """
                SELECT id FROM datasets
                WHERE tenant_id = (SELECT id FROM tenants WHERE domain = $1 LIMIT 1)
                AND is_deleted = false
            """
            dataset_rows = await pg_client.fetch_all(datasets_query, current_user.get("tenant_domain"))
            available_datasets = [str(row["id"]) for row in dataset_rows]
            logger.info(f"Fetched {len(available_datasets)} available datasets for validation")
        except Exception as e:
            logger.warning(f"Could not fetch datasets for validation: {e}")

        # Create agents with duplicate name handling
        created_agents = []
        creation_errors = []

        for idx, agent_data in enumerate(valid_agents, start=1):
            try:
                # Generate unique name if duplicate
                original_name = agent_data['name']
                unique_name = AgentCSVHelper.generate_unique_name(original_name, existing_names)

                if unique_name != original_name:
                    logger.info(f"Renamed duplicate: '{original_name}' → '{unique_name}'")
                    agent_data['name'] = unique_name

                # Validate and correct model
                model = agent_data['model']
                if available_models and model not in available_models:
                    # Model doesn't exist - use first available model
                    if available_models:
                        fallback_model = available_models[0]
                        logger.warning(f"Row {idx}: Model '{model}' not found, using '{fallback_model}'")
                        agent_data['model'] = fallback_model
                    else:
                        raise ValueError(f"Model '{model}' not available and no fallback models exist")

                # Validate and filter datasets
                selected_dataset_ids = agent_data.get('selected_dataset_ids', [])
                if selected_dataset_ids and available_datasets:
                    # Filter out non-existent datasets
                    valid_dataset_ids = [
                        ds_id for ds_id in selected_dataset_ids
                        if ds_id in available_datasets
                    ]
                    invalid_count = len(selected_dataset_ids) - len(valid_dataset_ids)
                    if invalid_count > 0:
                        logger.warning(f"Row {idx}: {invalid_count} dataset(s) not found, removed from selection")
                        agent_data['selected_dataset_ids'] = valid_dataset_ids if valid_dataset_ids else None
                        # If all datasets were invalid and connection is 'selected', change to 'none'
                        if not valid_dataset_ids and agent_data.get('dataset_connection') == 'selected':
                            agent_data['dataset_connection'] = 'none'
                            logger.warning(f"Row {idx}: No valid datasets, changed dataset_connection to 'none'")

                # Create agent using service
                created_agent = await service.create_agent(
                    name=agent_data['name'],
                    agent_type='conversational',  # Default agent type
                    description=agent_data.get('description', ''),
                    prompt_template=agent_data.get('prompt_template', ''),
                    model=agent_data['model'],
                    temperature=agent_data.get('temperature'),
                    # max_tokens removed - now determined by model configuration
                    category=agent_data.get('category', 'general'),  # Category auto-creates if not exists (Issue #215)
                    category_description=agent_data.get('category_description'),  # For auto-created categories
                    dataset_connection=agent_data.get('dataset_connection'),
                    selected_dataset_ids=agent_data.get('selected_dataset_ids'),
                    visibility=agent_data.get('visibility'),
                    disclaimer=agent_data.get('disclaimer'),
                    easy_prompts=agent_data.get('easy_prompts'),
                    tags=agent_data.get('tags', []),
                    access_group='individual'
                )

                created_agents.append({
                    'id': created_agent['id'],
                    'name': created_agent['name'],
                    'original_name': original_name if unique_name != original_name else None
                })

                # Add to existing names to check for duplicates in subsequent rows
                existing_names.append(unique_name)

            except Exception as e:
                logger.error(f"Failed to create agent from row {idx}: {e}")
                creation_errors.append({
                    'row_number': idx + 1,  # +1 for header
                    'field': 'creation',
                    'message': f"Agent creation failed: {str(e)}"
                })

        # Combine parsing and creation errors
        all_errors = errors + creation_errors

        # Invalidate agent list cache so imported agents appear immediately
        if created_agents:
            user_id = current_user.get('sub')
            cache.delete(f"agents_minimal_{user_id}")
            cache.delete(f"agents_summary_{user_id}")
            cache.delete(f"agents_full_{user_id}")  # Invalidate full agent list cache (all role variants)
            logger.info(f"Invalidated agent cache for user {user_id} after bulk import")

        # codeql[py/stack-trace-exposure] returns import results dict, not error details
        return {
            'success_count': len(created_agents),
            'error_count': len(all_errors),
            'total_rows': len(valid_agents) + len(errors),
            'created_agents': created_agents,
            'errors': all_errors
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: str,
    format: str = Query('download', description="Export format: 'download' or 'clipboard'"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Export a single agent configuration as CSV.

    Permission Requirements:
    - User must be agent owner OR sysadmin

    Query Parameters:
    - format: 'download' (returns file download) or 'clipboard' (returns CSV text)

    Returns:
    - CSV file download or CSV text response
    """
    logger.info(f"Export agent {agent_id} for user {current_user['sub']}")

    try:
        # Get agent service
        service = await get_agent_service_for_user(current_user)
        agent = await service.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Check permissions
        from app.core.postgresql_client import get_postgresql_client
        pg_client = await get_postgresql_client()

        # Get user role
        user_role = await get_user_role(pg_client, current_user.get('email'), current_user.get('tenant_domain'))

        # Get current user UUID
        user_email = current_user.get('email')
        tenant_domain = current_user.get('tenant_domain')

        user_lookup_query = """
            SELECT id FROM users
            WHERE (email = $1 OR username = $1)
              AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
            LIMIT 1
        """
        current_user_uuid = await pg_client.fetch_scalar(user_lookup_query, user_email, tenant_domain)

        if not current_user_uuid:
            raise HTTPException(status_code=404, detail=f"User not found: {user_email}")

        # Use the is_owner field already computed by agent service
        # This avoids field name mismatches and duplicate ownership logic
        is_owner = agent.get('is_owner', False)

        # Only owners and administrators can export
        if not is_owner and user_role not in ADMIN_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Only agent owners and administrators can export agents"
            )

        # Fetch category description from categories table (Issue #215)
        agent_category = agent.get('agent_type') or agent.get('category')
        if agent_category:
            category_desc_query = """
                SELECT description FROM categories
                WHERE slug = $1
                  AND tenant_id = (SELECT id FROM tenants WHERE domain = $2 LIMIT 1)
                  AND is_deleted = FALSE
                LIMIT 1
            """
            category_description = await pg_client.fetch_scalar(
                category_desc_query, agent_category.lower(), tenant_domain
            )
            if category_description:
                agent['category_description'] = category_description

        # Serialize agent to CSV
        csv_content = AgentCSVHelper.serialize_agent_to_csv(agent)

        # Return based on format
        if format == 'download':
            # Return as file download
            filename = f"agent_{agent.get('name', 'export').replace(' ', '_')}.csv"
            return StreamingResponse(
                io.BytesIO(csv_content.encode('utf-8')),
                media_type='text/csv',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
        else:  # clipboard
            # Return as plain text
            return Response(content=csv_content, media_type='text/plain')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")