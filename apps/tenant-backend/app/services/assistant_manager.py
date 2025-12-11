"""
AssistantManager Service for GT 2.0 Tenant Backend

File-based agent lifecycle management with perfect tenant isolation.
Implements the core Agent System specification from CLAUDE.md.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
import logging

from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.message import Message
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AssistantManager:
    """File-based agent lifecycle management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def create_from_template(self, template_id: str, config: Dict[str, Any], user_identifier: str) -> str:
        """Create agent from template or custom config"""
        try:
            # Get template configuration
            template_config = await self._load_template_config(template_id)
            
            # Merge template config with user overrides
            merged_config = {**template_config, **config}
            
            # Create agent record
            agent = Agent(
                name=merged_config.get("name", f"Agent from {template_id}"),
                description=merged_config.get("description", f"Created from template: {template_id}"),
                template_id=template_id,
                created_by=user_identifier,
                user_name=merged_config.get("user_name"),
                personality_config=merged_config.get("personality_config", {}),
                resource_preferences=merged_config.get("resource_preferences", {}),
                memory_settings=merged_config.get("memory_settings", {}),
                tags=merged_config.get("tags", []),
            )
            
            # Initialize with placeholder paths first
            agent.config_file_path = "placeholder"
            agent.prompt_file_path = "placeholder"
            agent.capabilities_file_path = "placeholder"
            
            # Save to database first to get ID and UUID
            self.db.add(agent)
            await self.db.flush()  # Flush to get the generated UUID without committing
            
            # Now we can initialize proper file paths with the UUID
            agent.initialize_file_paths()
            
            # Create file system structure
            await self._setup_assistant_files(agent, merged_config)
            
            # Commit all changes
            await self.db.commit()
            await self.db.refresh(agent)
            
            logger.info(
                f"Created agent from template",
                extra={
                    "agent_id": agent.id,
                    "assistant_uuid": agent.uuid,
                    "template_id": template_id,
                    "created_by": user_identifier,
                }
            )
            
            return str(agent.uuid)
            
        except Exception as e:
            logger.error(f"Failed to create agent from template: {e}", exc_info=True)
            await self.db.rollback()
            raise
    
    async def create_custom_assistant(self, config: Dict[str, Any], user_identifier: str) -> str:
        """Create custom agent without template"""
        try:
            # Validate required fields
            if not config.get("name"):
                raise ValueError("Agent name is required")
            
            # Create agent record
            agent = Agent(
                name=config["name"],
                description=config.get("description", "Custom AI agent"),
                template_id=None,  # No template used
                created_by=user_identifier,
                user_name=config.get("user_name"),
                personality_config=config.get("personality_config", {}),
                resource_preferences=config.get("resource_preferences", {}),
                memory_settings=config.get("memory_settings", {}),
                tags=config.get("tags", []),
            )
            
            # Initialize with placeholder paths first
            agent.config_file_path = "placeholder"
            agent.prompt_file_path = "placeholder"
            agent.capabilities_file_path = "placeholder"
            
            # Save to database first to get ID and UUID
            self.db.add(agent)
            await self.db.flush()  # Flush to get the generated UUID without committing
            
            # Now we can initialize proper file paths with the UUID
            agent.initialize_file_paths()
            
            # Create file system structure
            await self._setup_assistant_files(agent, config)
            
            # Commit all changes
            await self.db.commit()
            await self.db.refresh(agent)
            
            logger.info(
                f"Created custom agent",
                extra={
                    "agent_id": agent.id,
                    "assistant_uuid": agent.uuid,
                    "created_by": user_identifier,
                }
            )
            
            return str(agent.uuid)
            
        except Exception as e:
            logger.error(f"Failed to create custom agent: {e}", exc_info=True)
            await self.db.rollback()
            raise
    
    async def get_assistant_config(self, assistant_uuid: str, user_identifier: str) -> Dict[str, Any]:
        """Get complete agent configuration including file-based data"""
        try:
            # Get agent from database
            result = await self.db.execute(
                select(Agent).where(
                    and_(
                        Agent.uuid == assistant_uuid,
                        Agent.created_by == user_identifier,
                        Agent.is_active == True
                    )
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent not found: {assistant_uuid}")
            
            # Load complete configuration
            return agent.get_full_configuration()
            
        except Exception as e:
            logger.error(f"Failed to get agent config: {e}", exc_info=True)
            raise
    
    async def list_user_assistants(
        self, 
        user_identifier: str, 
        include_archived: bool = False,
        template_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List user's agents with filtering options"""
        try:
            # Build base query
            query = select(Agent).where(Agent.created_by == user_identifier)
            
            # Apply filters
            if not include_archived:
                query = query.where(Agent.is_active == True)
            
            if template_id:
                query = query.where(Agent.template_id == template_id)
            
            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        Agent.name.ilike(search_term),
                        Agent.description.ilike(search_term)
                    )
                )
            
            # Apply ordering and pagination
            query = query.order_by(desc(Agent.last_used_at), desc(Agent.created_at))
            query = query.limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            agents = result.scalars().all()
            
            return [agent.to_dict() for agent in agents]
            
        except Exception as e:
            logger.error(f"Failed to list user agents: {e}", exc_info=True)
            raise
    
    async def count_user_assistants(
        self,
        user_identifier: str,
        include_archived: bool = False,
        template_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
        """Count user's agents matching criteria"""
        try:
            # Build base query
            query = select(func.count(Agent.id)).where(Agent.created_by == user_identifier)
            
            # Apply filters
            if not include_archived:
                query = query.where(Agent.is_active == True)
            
            if template_id:
                query = query.where(Agent.template_id == template_id)
            
            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        Agent.name.ilike(search_term),
                        Agent.description.ilike(search_term)
                    )
                )
            
            result = await self.db.execute(query)
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Failed to count user agents: {e}", exc_info=True)
            raise
    
    async def update_assistant(self, agent_id: str, updates: Dict[str, Any], user_identifier: str) -> bool:
        """Update agent configuration (renamed from update_configuration)"""
        return await self.update_configuration(agent_id, updates, user_identifier)
    
    async def update_configuration(self, assistant_uuid: str, updates: Dict[str, Any], user_identifier: str) -> bool:
        """Update agent configuration"""
        try:
            # Get agent
            result = await self.db.execute(
                select(Agent).where(
                    and_(
                        Agent.uuid == assistant_uuid,
                        Agent.created_by == user_identifier,
                        Agent.is_active == True
                    )
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent not found: {assistant_uuid}")
            
            # Update database fields
            if "name" in updates:
                agent.name = updates["name"]
            if "description" in updates:
                agent.description = updates["description"]
            if "personality_config" in updates:
                agent.personality_config = updates["personality_config"]
            if "resource_preferences" in updates:
                agent.resource_preferences = updates["resource_preferences"]
            if "memory_settings" in updates:
                agent.memory_settings = updates["memory_settings"]
            if "tags" in updates:
                agent.tags = updates["tags"]
            
            # Update file-based configurations
            if "config" in updates:
                agent.save_config_to_file(updates["config"])
            if "prompt" in updates:
                agent.save_prompt_to_file(updates["prompt"])
            if "capabilities" in updates:
                agent.save_capabilities_to_file(updates["capabilities"])
            
            agent.updated_at = datetime.utcnow()
            await self.db.commit()
            
            logger.info(
                f"Updated agent configuration",
                extra={
                    "assistant_uuid": assistant_uuid,
                    "updated_fields": list(updates.keys()),
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update agent configuration: {e}", exc_info=True)
            await self.db.rollback()
            raise
    
    async def clone_assistant(self, source_uuid: str, new_name: str, user_identifier: str, modifications: Dict[str, Any] = None) -> str:
        """Clone existing agent with modifications"""
        try:
            # Get source agent
            result = await self.db.execute(
                select(Agent).where(
                    and_(
                        Agent.uuid == source_uuid,
                        Agent.created_by == user_identifier,
                        Agent.is_active == True
                    )
                )
            )
            source_assistant = result.scalar_one_or_none()
            
            if not source_assistant:
                raise ValueError(f"Source agent not found: {source_uuid}")
            
            # Clone agent
            cloned_assistant = source_assistant.clone(new_name, user_identifier, modifications or {})
            
            # Initialize with placeholder paths first
            cloned_assistant.config_file_path = "placeholder"
            cloned_assistant.prompt_file_path = "placeholder"
            cloned_assistant.capabilities_file_path = "placeholder"
            
            # Save to database first to get UUID
            self.db.add(cloned_assistant)
            await self.db.flush()  # Flush to get the generated UUID
            
            # Initialize proper file paths with UUID
            cloned_assistant.initialize_file_paths()
            
            # Copy and modify files
            await self._clone_assistant_files(source_assistant, cloned_assistant, modifications or {})
            
            # Commit all changes
            await self.db.commit()
            await self.db.refresh(cloned_assistant)
            
            logger.info(
                f"Cloned agent",
                extra={
                    "source_uuid": source_uuid,
                    "new_uuid": cloned_assistant.uuid,
                    "new_name": new_name,
                }
            )
            
            return str(cloned_assistant.uuid)
            
        except Exception as e:
            logger.error(f"Failed to clone agent: {e}", exc_info=True)
            await self.db.rollback()
            raise
    
    async def archive_assistant(self, assistant_uuid: str, user_identifier: str) -> bool:
        """Archive agent (soft delete)"""
        try:
            result = await self.db.execute(
                select(Agent).where(
                    and_(
                        Agent.uuid == assistant_uuid,
                        Agent.created_by == user_identifier
                    )
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent not found: {assistant_uuid}")
            
            agent.archive()
            await self.db.commit()
            
            logger.info(
                f"Archived agent",
                extra={"assistant_uuid": assistant_uuid}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive agent: {e}", exc_info=True)
            await self.db.rollback()
            raise
    
    async def get_assistant_statistics(self, assistant_uuid: str, user_identifier: str) -> Dict[str, Any]:
        """Get usage statistics for agent"""
        try:
            result = await self.db.execute(
                select(Agent).where(
                    and_(
                        Agent.uuid == assistant_uuid,
                        Agent.created_by == user_identifier,
                        Agent.is_active == True
                    )
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent not found: {assistant_uuid}")
            
            # Get conversation statistics
            conv_result = await self.db.execute(
                select(func.count(Conversation.id))
                .where(Conversation.agent_id == agent.id)
            )
            conversation_count = conv_result.scalar() or 0
            
            # Get message statistics
            msg_result = await self.db.execute(
                select(
                    func.count(Message.id),
                    func.sum(Message.tokens_used),
                    func.sum(Message.cost_cents)
                )
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(Conversation.agent_id == agent.id)
            )
            message_stats = msg_result.first()
            
            return {
                "agent_id": assistant_uuid,  # Use agent_id to match schema
                "name": agent.name,
                "created_at": agent.created_at,  # Return datetime object, not ISO string
                "last_used_at": agent.last_used_at,  # Return datetime object, not ISO string
                "conversation_count": conversation_count,
                "total_messages": message_stats[0] or 0,
                "total_tokens_used": message_stats[1] or 0,
                "total_cost_cents": message_stats[2] or 0,
                "total_cost_dollars": (message_stats[2] or 0) / 100.0,
                "average_tokens_per_message": (
                    (message_stats[1] or 0) / max(1, message_stats[0] or 1)
                ),
                "is_favorite": agent.is_favorite,
                "tags": agent.tags,
            }
            
        except Exception as e:
            logger.error(f"Failed to get agent statistics: {e}", exc_info=True)
            raise
    
    # Private helper methods
    
    async def _load_template_config(self, template_id: str) -> Dict[str, Any]:
        """Load template configuration from Resource Cluster or built-in templates"""
        # Built-in templates (as specified in CLAUDE.md)
        builtin_templates = {
            "research_assistant": {
                "name": "Research & Analysis Agent",
                "description": "Specialized in information synthesis and analysis",
                "prompt": """You are a research agent specialized in information synthesis and analysis.
Focus on providing well-sourced, analytical responses with clear reasoning.""",
                "personality_config": {
                    "tone": "balanced",
                    "explanation_depth": "expert",
                    "interaction_style": "collaborative"
                },
                "resource_preferences": {
                    "primary_llm": "groq:llama3-70b-8192",
                    "temperature": 0.7,
                    "max_tokens": 4000
                },
                "capabilities": [
                    {"resource": "llm:groq", "actions": ["inference"], "limits": {"max_tokens_per_request": 4000}},
                    {"resource": "rag:semantic_search", "actions": ["search"], "limits": {}},
                    {"resource": "tools:web_search", "actions": ["search"], "limits": {"requests_per_hour": 50}},
                    {"resource": "export:citations", "actions": ["create"], "limits": {}}
                ]
            },
            "coding_assistant": {
                "name": "Software Development Agent",
                "description": "Focused on code quality and best practices",
                "prompt": """You are a software development agent focused on code quality and best practices.
Provide clear explanations, suggest improvements, and help debug issues.""",
                "personality_config": {
                    "tone": "direct",
                    "explanation_depth": "intermediate",
                    "interaction_style": "teaching"
                },
                "resource_preferences": {
                    "primary_llm": "groq:llama3-70b-8192",
                    "temperature": 0.3,
                    "max_tokens": 4000
                },
                "capabilities": [
                    {"resource": "llm:groq", "actions": ["inference"], "limits": {"max_tokens_per_request": 4000}},
                    {"resource": "tools:github_integration", "actions": ["read"], "limits": {}},
                    {"resource": "resources:documentation", "actions": ["search"], "limits": {}},
                    {"resource": "export:code_snippets", "actions": ["create"], "limits": {}}
                ]
            },
            "cyber_analyst": {
                "name": "Cybersecurity Analysis Agent",
                "description": "For threat detection and response analysis",
                "prompt": """You are a cybersecurity analyst agent for threat detection and response.
Prioritize security best practices and provide actionable recommendations.""",
                "personality_config": {
                    "tone": "formal",
                    "explanation_depth": "expert",
                    "interaction_style": "direct"
                },
                "resource_preferences": {
                    "primary_llm": "groq:llama3-70b-8192",
                    "temperature": 0.2,
                    "max_tokens": 4000
                },
                "capabilities": [
                    {"resource": "llm:groq", "actions": ["inference"], "limits": {"max_tokens_per_request": 4000}},
                    {"resource": "tools:security_scanning", "actions": ["analyze"], "limits": {}},
                    {"resource": "resources:threat_intelligence", "actions": ["search"], "limits": {}},
                    {"resource": "export:security_reports", "actions": ["create"], "limits": {}}
                ]
            },
            "educational_tutor": {
                "name": "AI Literacy Educational Agent",
                "description": "Develops critical thinking and AI literacy",
                "prompt": """You are an educational agent focused on developing critical thinking and AI literacy.
Use socratic questioning and encourage deep analysis of problems.""",
                "personality_config": {
                    "tone": "casual",
                    "explanation_depth": "beginner",
                    "interaction_style": "teaching"
                },
                "resource_preferences": {
                    "primary_llm": "groq:llama3-70b-8192",
                    "temperature": 0.8,
                    "max_tokens": 3000
                },
                "capabilities": [
                    {"resource": "llm:groq", "actions": ["inference"], "limits": {"max_tokens_per_request": 3000}},
                    {"resource": "games:strategic_thinking", "actions": ["play"], "limits": {}},
                    {"resource": "puzzles:logic_reasoning", "actions": ["present"], "limits": {}},
                    {"resource": "analytics:learning_progress", "actions": ["track"], "limits": {}}
                ]
            }
        }
        
        if template_id in builtin_templates:
            return builtin_templates[template_id]
        
        # TODO: In the future, load from Resource Cluster Agent Library
        # For now, return empty config for unknown templates
        logger.warning(f"Unknown template ID: {template_id}")
        return {
            "name": f"Agent ({template_id})",
            "description": "Custom agent",
            "prompt": "You are a helpful AI agent.",
            "capabilities": []
        }
    
    async def _setup_assistant_files(self, agent: Agent, config: Dict[str, Any]) -> None:
        """Create file system structure for agent"""
        # Ensure directory exists
        agent.ensure_directory_exists()
        
        # Save configuration files
        agent.save_config_to_file(config)
        agent.save_prompt_to_file(config.get("prompt", "You are a helpful AI agent."))
        agent.save_capabilities_to_file(config.get("capabilities", []))
        
        logger.info(f"Created agent files for {agent.uuid}")
    
    async def _clone_assistant_files(self, source: Agent, target: Agent, modifications: Dict[str, Any]) -> None:
        """Clone agent files with modifications"""
        # Load source configurations
        source_config = source.load_config_from_file()
        source_prompt = source.load_prompt_from_file()
        source_capabilities = source.load_capabilities_from_file()
        
        # Apply modifications
        target_config = {**source_config, **modifications.get("config", {})}
        target_prompt = modifications.get("prompt", source_prompt)
        target_capabilities = modifications.get("capabilities", source_capabilities)
        
        # Create target files
        target.ensure_directory_exists()
        target.save_config_to_file(target_config)
        target.save_prompt_to_file(target_prompt)
        target.save_capabilities_to_file(target_capabilities)
        
        logger.info(f"Cloned agent files from {source.uuid} to {target.uuid}")


async def get_assistant_manager(db: AsyncSession) -> AssistantManager:
    """Get AssistantManager instance"""
    return AssistantManager(db)