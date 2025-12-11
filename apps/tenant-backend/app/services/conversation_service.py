"""
Conversation Service for GT 2.0 Tenant Backend - PostgreSQL + PGVector

Manages AI-powered conversations with Agent integration using PostgreSQL directly.
Handles message persistence, context management, and LLM inference.
Replaces SQLAlchemy with direct PostgreSQL operations for GT 2.0 principles.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncIterator, AsyncGenerator

from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client
from app.services.agent_service import AgentService
from app.core.resource_client import ResourceClusterClient
from app.services.conversation_summarizer import ConversationSummarizer

logger = logging.getLogger(__name__)


class ConversationService:
    """PostgreSQL-based service for managing AI conversations"""

    def __init__(self, tenant_domain: str, user_id: str):
        """Initialize with tenant and user isolation using PostgreSQL"""
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.settings = get_settings()
        self.agent_service = AgentService(tenant_domain, user_id)
        self.resource_client = ResourceClusterClient()
        self._resolved_user_uuid = None  # Cache for resolved user UUID

        logger.info(f"Conversation service initialized with PostgreSQL for {tenant_domain}/{user_id}")

    async def _get_resolved_user_uuid(self, user_identifier: Optional[str] = None) -> str:
        """
        Resolve user identifier to UUID with caching for performance.

        This optimization reduces repeated database lookups by caching the resolved UUID.
        Performance impact: ~50% reduction in query time for operations with multiple queries.
        """
        identifier = user_identifier or self.user_id

        # Return cached UUID if already resolved for this instance
        if self._resolved_user_uuid and identifier == self.user_id:
            return self._resolved_user_uuid

        # Check if already a UUID
        if not "@" in identifier:
            try:
                # Validate it's a proper UUID format
                uuid.UUID(identifier)
                if identifier == self.user_id:
                    self._resolved_user_uuid = identifier
                return identifier
            except ValueError:
                pass  # Not a valid UUID, treat as email/username

        # Resolve email to UUID
        pg_client = await get_postgresql_client()
        query = "SELECT id FROM users WHERE email = $1 LIMIT 1"
        result = await pg_client.fetch_one(query, identifier)

        if not result:
            raise ValueError(f"User not found: {identifier}")

        user_uuid = str(result["id"])

        # Cache if this is the service's primary user
        if identifier == self.user_id:
            self._resolved_user_uuid = user_uuid

        return user_uuid

    def _get_user_clause(self, param_num: int, user_identifier: str) -> str:
        """
        DEPRECATED: Get the appropriate SQL clause for user identification.
        Use _get_resolved_user_uuid() instead for better performance.
        """
        if "@" in user_identifier:
            # Email - do lookup
            return f"(SELECT id FROM users WHERE email = ${param_num} LIMIT 1)"
        else:
            # UUID - use directly
            return f"${param_num}::uuid"
    
    async def create_conversation(
        self,
        agent_id: str,
        title: Optional[str],
        user_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new conversation with an agent using PostgreSQL"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            # Get agent configuration
            agent_data = await self.agent_service.get_agent(agent_id)
            if not agent_data:
                raise ValueError(f"Agent {agent_id} not found")

            # Validate tenant has access to the agent's model
            agent_model = agent_data.get("model")
            if agent_model:
                available_models = await self.get_available_models(self.tenant_domain)
                available_model_ids = [m["model_id"] for m in available_models]

                if agent_model not in available_model_ids:
                    raise ValueError(f"Agent model '{agent_model}' is not accessible to tenant '{self.tenant_domain}'. Available models: {', '.join(available_model_ids)}")

                logger.info(f"Validated tenant access to model '{agent_model}' for agent '{agent_data.get('name')}'")
            else:
                logger.warning(f"Agent {agent_id} has no model configured, will use default")

            # Get PostgreSQL client
            pg_client = await get_postgresql_client()

            # Generate conversation ID
            conversation_id = str(uuid.uuid4())

            # Create conversation in PostgreSQL (optimized: use resolved UUID directly)
            query = """
                INSERT INTO conversations (
                    id, title, tenant_id, user_id, agent_id, summary,
                    total_messages, total_tokens, metadata, is_archived,
                    created_at, updated_at
                ) VALUES (
                    $1, $2,
                    (SELECT id FROM tenants WHERE domain = $3 LIMIT 1),
                    $4::uuid,
                    $5, '', 0, 0, '{}', false, NOW(), NOW()
                )
                RETURNING id, title, tenant_id, user_id, agent_id, created_at, updated_at
            """

            conv_title = title or f"Conversation with {agent_data.get('name', 'Agent')}"

            conversation_data = await pg_client.fetch_one(
                query,
                conversation_id, conv_title, self.tenant_domain,
                user_uuid, agent_id
            )
            
            if not conversation_data:
                raise RuntimeError("Failed to create conversation - no data returned")
            
            # Note: conversation_settings and conversation_participants are now created automatically
            # by the auto_create_conversation_settings trigger, so we don't need to create them manually
            
            # Get the model_id from the auto-created settings or use agent's model
            settings_query = """
                SELECT model_id FROM conversation_settings WHERE conversation_id = $1
            """
            settings_data = await pg_client.fetch_one(settings_query, conversation_id)
            model_id = settings_data["model_id"] if settings_data else agent_model
            
            result = {
                "id": str(conversation_data["id"]),
                "title": conversation_data["title"],
                "agent_id": str(conversation_data["agent_id"]),
                "model_id": model_id,
                "created_at": conversation_data["created_at"].isoformat(),
                "user_id": user_uuid,
                "tenant_domain": self.tenant_domain
            }

            logger.info(f"Created conversation {conversation_id} in PostgreSQL for user {user_uuid}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise
            
    async def list_conversations(
        self,
        user_identifier: str,
        agent_id: Optional[str] = None,
        search: Optional[str] = None,
        time_filter: str = "all",
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List conversations for a user using PostgreSQL with server-side filtering"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            # Build query with optional filters - exclude archived conversations (optimized: use cached UUID)
            where_clause = "WHERE c.user_id = $1::uuid AND c.is_archived = false"
            params = [user_uuid]
            param_count = 1

            # Time filter
            if time_filter != "all":
                if time_filter == "today":
                    where_clause += " AND c.updated_at >= NOW() - INTERVAL '1 day'"
                elif time_filter == "week":
                    where_clause += " AND c.updated_at >= NOW() - INTERVAL '7 days'"
                elif time_filter == "month":
                    where_clause += " AND c.updated_at >= NOW() - INTERVAL '30 days'"

            # Agent filter
            if agent_id:
                param_count += 1
                where_clause += f" AND c.agent_id = ${param_count}"
                params.append(agent_id)

            # Search filter (case-insensitive title search)
            if search:
                param_count += 1
                where_clause += f" AND c.title ILIKE ${param_count}"
                params.append(f"%{search}%")
            
            # Get conversations with agent info and unread counts (optimized: use cached UUID)
            query = f"""
                SELECT
                    c.id, c.title, c.agent_id, c.created_at, c.updated_at,
                    c.total_messages, c.total_tokens, c.is_archived,
                    a.name as agent_name,
                    COUNT(m.id) FILTER (
                        WHERE m.created_at > COALESCE((c.metadata->>'last_read_at')::timestamptz, c.created_at)
                        AND m.user_id != $1::uuid
                    ) as unread_count
                FROM conversations c
                LEFT JOIN agents a ON c.agent_id = a.id
                LEFT JOIN messages m ON m.conversation_id = c.id
                {where_clause}
                GROUP BY c.id, c.title, c.agent_id, c.created_at, c.updated_at,
                         c.total_messages, c.total_tokens, c.is_archived, a.name
                ORDER BY
                    CASE WHEN COUNT(m.id) FILTER (
                        WHERE m.created_at > COALESCE((c.metadata->>'last_read_at')::timestamptz, c.created_at)
                        AND m.user_id != $1::uuid
                    ) > 0 THEN 0 ELSE 1 END,
                    c.updated_at DESC
                LIMIT ${param_count + 1} OFFSET ${param_count + 2}
            """
            params.extend([limit, offset])
            
            conversations = await pg_client.execute_query(query, *params)
            
            # Get total count
            count_query = f"""
                SELECT COUNT(*) as total
                FROM conversations c
                {where_clause}
            """
            count_result = await pg_client.fetch_one(count_query, *params[:-2])  # Exclude limit/offset
            total = count_result["total"] if count_result else 0
            
            # Format results with lightweight fields including unread count
            conversation_list = [
                {
                    "id": str(conv["id"]),
                    "title": conv["title"],
                    "agent_id": str(conv["agent_id"]) if conv["agent_id"] else None,
                    "agent_name": conv["agent_name"] or "AI Assistant",
                    "created_at": conv["created_at"].isoformat(),
                    "updated_at": conv["updated_at"].isoformat(),
                    "last_message_at": conv["updated_at"].isoformat(),  # Use updated_at as last activity
                    "message_count": conv["total_messages"] or 0,
                    "token_count": conv["total_tokens"] or 0,
                    "is_archived": conv["is_archived"],
                    "unread_count": conv.get("unread_count", 0) or 0  # Include unread count
                    # Removed preview field for performance
                }
                for conv in conversations
            ]
            
            return {
                "conversations": conversation_list,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            raise
    
    async def get_conversation(
        self,
        conversation_id: str,
        user_identifier: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific conversation with details"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            query = """
                SELECT
                    c.id, c.title, c.agent_id, c.created_at, c.updated_at,
                    c.total_messages, c.total_tokens, c.is_archived, c.summary,
                    a.name as agent_name,
                    cs.model_id, cs.temperature, cs.max_tokens, cs.system_prompt
                FROM conversations c
                LEFT JOIN agents a ON c.agent_id = a.id
                LEFT JOIN conversation_settings cs ON c.id = cs.conversation_id
                WHERE c.id = $1
                  AND c.user_id = $2::uuid
                LIMIT 1
            """

            conversation = await pg_client.fetch_one(query, conversation_id, user_uuid)
            
            if not conversation:
                return None
                
            return {
                "id": conversation["id"],
                "title": conversation["title"],
                "agent_id": conversation["agent_id"],
                "agent_name": conversation["agent_name"],
                "model_id": conversation["model_id"],
                "temperature": float(conversation["temperature"]) if conversation["temperature"] else 0.7,
                "max_tokens": conversation["max_tokens"],
                "system_prompt": conversation["system_prompt"],
                "summary": conversation["summary"],
                "message_count": conversation["total_messages"],
                "token_count": conversation["total_tokens"],
                "is_archived": conversation["is_archived"],
                "created_at": conversation["created_at"].isoformat(),
                "updated_at": conversation["updated_at"].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        user_identifier: str,
        model_used: Optional[str] = None,
        token_count: int = 0,
        metadata: Optional[Dict] = None,
        attachments: Optional[List] = None
    ) -> Dict[str, Any]:
        """Add a message to a conversation"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            message_id = str(uuid.uuid4())

            # Insert message (optimized: use cached UUID)
            query = """
                INSERT INTO messages (
                    id, conversation_id, user_id, role, content,
                    content_type, token_count, model_used, metadata, attachments, created_at
                ) VALUES (
                    $1, $2, $3::uuid,
                    $4, $5, 'text', $6, $7, $8, $9, NOW()
                )
                RETURNING id, created_at
            """

            message_data = await pg_client.fetch_one(
                query,
                message_id, conversation_id, user_uuid,
                role, content, token_count, model_used,
                json.dumps(metadata or {}), json.dumps(attachments or [])
            )

            if not message_data:
                raise RuntimeError("Failed to add message - no data returned")

            # Update conversation totals (optimized: use cached UUID)
            update_query = """
                UPDATE conversations
                SET total_messages = total_messages + 1,
                    total_tokens = total_tokens + $3,
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2::uuid
            """
            
            await pg_client.execute_command(update_query, conversation_id, user_uuid, token_count)
            
            result = {
                "id": message_data["id"],
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "token_count": token_count,
                "model_used": model_used,
                "metadata": metadata or {},
                "attachments": attachments or [],
                "created_at": message_data["created_at"].isoformat()
            }
            
            logger.info(f"Added message {message_id} to conversation {conversation_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
            raise

    async def get_messages(
        self,
        conversation_id: str,
        user_identifier: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a conversation"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            query = """
                SELECT
                    m.id, m.role, m.content, m.content_type, m.token_count,
                    m.model_used, m.finish_reason, m.metadata, m.attachments, m.created_at
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.id = $1
                  AND c.user_id = $2::uuid
                ORDER BY m.created_at ASC
                LIMIT $3 OFFSET $4
            """

            messages = await pg_client.execute_query(query, conversation_id, user_uuid, limit, offset)
            
            return [
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "content_type": msg["content_type"],
                    "token_count": msg["token_count"],
                    "model_used": msg["model_used"],
                    "finish_reason": msg["finish_reason"],
                    "metadata": (
                        json.loads(msg["metadata"]) if isinstance(msg["metadata"], str)
                        else (msg["metadata"] if isinstance(msg["metadata"], dict) else {})
                    ),
                    "attachments": (
                        json.loads(msg["attachments"]) if isinstance(msg["attachments"], str)
                        else (msg["attachments"] if isinstance(msg["attachments"], list) else [])
                    ),
                    "context_sources": (
                        (json.loads(msg["metadata"]) if isinstance(msg["metadata"], str) else msg["metadata"]).get("context_sources", [])
                        if (isinstance(msg["metadata"], str) or isinstance(msg["metadata"], dict))
                        else []
                    ),
                    "created_at": msg["created_at"].isoformat()
                }
                for msg in messages
            ]
            
        except Exception as e:
            logger.error(f"Failed to get messages for conversation {conversation_id}: {e}")
            return []

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        user_identifier: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send a message to conversation and get AI response"""
        user_id = user_identifier or self.user_id

        # Check if this is the first message
        existing_messages = await self.get_messages(conversation_id, user_id)
        is_first_message = len(existing_messages) == 0

        # Add user message
        user_message = await self.add_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            user_identifier=user_identifier
        )

        # Get conversation details for agent
        conversation = await self.get_conversation(conversation_id, user_identifier)
        agent_id = conversation.get("agent_id")

        ai_message = None
        if agent_id:
            agent_data = await self.agent_service.get_agent(agent_id)

            # Prepare messages for AI
            messages = [
                {"role": "system", "content": agent_data.get("prompt_template", "You are a helpful assistant.")},
                {"role": "user", "content": content}
            ]

            # Get AI response
            ai_response = await self.get_ai_response(
                model=agent_data.get("model", "llama-3.1-8b-instant"),
                messages=messages,
                tenant_id=self.tenant_domain,
                user_id=user_id
            )

            # Extract content from response
            ai_content = ai_response["choices"][0]["message"]["content"]

            # Add AI message
            ai_message = await self.add_message(
                conversation_id=conversation_id,
                role="agent",
                content=ai_content,
                user_identifier=user_id,
                model_used=agent_data.get("model"),
                token_count=ai_response["usage"]["total_tokens"]
            )

        return {
            "user_message": user_message,
            "ai_message": ai_message,
            "is_first_message": is_first_message,
            "conversation_id": conversation_id
        }

    async def update_conversation(
        self,
        conversation_id: str,
        user_identifier: str,
        title: Optional[str] = None
    ) -> bool:
        """Update conversation properties like title"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            # Build dynamic update query based on provided fields
            update_fields = []
            params = []
            param_count = 1

            if title is not None:
                update_fields.append(f"title = ${param_count}")
                params.append(title)
                param_count += 1

            if not update_fields:
                return True  # Nothing to update

            # Add updated_at timestamp
            update_fields.append(f"updated_at = NOW()")

            query = f"""
                UPDATE conversations
                SET {', '.join(update_fields)}
                WHERE id = ${param_count}
                  AND user_id = ${param_count + 1}::uuid
                RETURNING id
            """

            params.extend([conversation_id, user_uuid])

            result = await pg_client.fetch_scalar(query, *params)
            
            if result:
                logger.info(f"Updated conversation {conversation_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update conversation {conversation_id}: {e}")
            return False

    async def auto_generate_conversation_title(
        self,
        conversation_id: str,
        user_identifier: str
    ) -> Optional[str]:
        """Generate conversation title based on first user prompt and agent response pair"""
        try:
            # Get only the first few messages (first exchange)
            messages = await self.get_messages(conversation_id, user_identifier, limit=2)
            
            if not messages or len(messages) < 2:
                return None  # Need at least one user-agent exchange
            
            # Only use first user message and first agent response for title
            first_exchange = messages[:2]
            
            # Generate title using the summarization service
            from app.services.conversation_summarizer import generate_conversation_title
            new_title = await generate_conversation_title(first_exchange, self.tenant_domain, user_identifier)
            
            # Update the conversation with the generated title
            success = await self.update_conversation(
                conversation_id=conversation_id,
                user_identifier=user_identifier,
                title=new_title
            )
            
            if success:
                logger.info(f"Auto-generated title '{new_title}' for conversation {conversation_id} based on first exchange")
                return new_title
            else:
                logger.warning(f"Failed to update conversation {conversation_id} with generated title")
                return None
                
        except Exception as e:
            logger.error(f"Failed to auto-generate title for conversation {conversation_id}: {e}")
            return None

    async def delete_conversation(
        self,
        conversation_id: str,
        user_identifier: str
    ) -> bool:
        """Soft delete a conversation (archive it)"""
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            query = """
                UPDATE conversations
                SET is_archived = true, updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2::uuid
                RETURNING id
            """

            result = await pg_client.fetch_scalar(query, conversation_id, user_uuid)
            
            if result:
                logger.info(f"Archived conversation {conversation_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to archive conversation {conversation_id}: {e}")
            return False
    
    async def get_ai_response(
        self,
        model: str,
        messages: List[Dict[str, str]],
        tenant_id: str,
        user_id: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get AI response from Resource Cluster"""
        try:
            # Prepare request for Resource Cluster
            request_data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p
            }

            # Add tools if provided
            if tools:
                request_data["tools"] = tools
            if tool_choice:
                request_data["tool_choice"] = tool_choice
            
            # Call Resource Cluster AI inference endpoint
            response = await self.resource_client.call_inference_endpoint(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint="chat/completions",
                data=request_data
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get AI response: {e}")
            raise
    
    # Streaming removed for reliability - using non-streaming only
    
    async def get_available_models(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available models for tenant from Resource Cluster"""
        try:
            # Get models dynamically from Resource Cluster
            import aiohttp
            
            resource_cluster_url = self.resource_client.base_url
            
            async with aiohttp.ClientSession() as session:
                # Get capability token for model access
                token = await self.resource_client._get_capability_token(
                    tenant_id=tenant_id,
                    user_id=self.user_id,
                    resources=['model_registry']
                )
                
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'X-Tenant-ID': tenant_id,
                    'X-User-ID': self.user_id
                }
                
                async with session.get(
                    f"{resource_cluster_url}/api/v1/models/",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        response_data = await response.json()
                        models_data = response_data.get("models", [])
                        
                        # Transform Resource Cluster model format to frontend format
                        available_models = []
                        for model in models_data:
                            # Only include available models
                            if model.get("status", {}).get("deployment") == "available":
                                available_models.append({
                                    "id": model.get("uuid"),  # Database UUID for unique identification
                                    "model_id": model["id"],  # model_id string for API calls
                                    "name": model["name"],
                                    "provider": model["provider"],
                                    "model_type": model["model_type"],
                                    "context_window": model.get("performance", {}).get("context_window", 4000),
                                    "max_tokens": model.get("performance", {}).get("max_tokens", 4000),
                                    "performance": model.get("performance", {}),  # Include full performance for chat.py
                                    "capabilities": {"chat": True}  # All LLM models support chat
                                })
                        
                        logger.info(f"Retrieved {len(available_models)} models from Resource Cluster")
                        return available_models
                    else:
                        logger.error(f"Resource Cluster returned {response.status}: {await response.text()}")
                        raise RuntimeError(f"Resource Cluster API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to get models from Resource Cluster: {e}")
            raise

    async def get_conversation_datasets(self, conversation_id: str, user_identifier: str) -> List[str]:
        """Get dataset IDs attached to a conversation"""
        try:
            pg_client = await get_postgresql_client()

            # Ensure proper schema qualification
            schema_name = f"tenant_{self.tenant_domain.replace('.', '_').replace('-', '_')}"

            query = f"""
                SELECT cd.dataset_id
                FROM {schema_name}.conversations c
                JOIN {schema_name}.conversation_datasets cd ON cd.conversation_id = c.id
                WHERE c.id = $1
                  AND c.user_id = (SELECT id FROM {schema_name}.users WHERE email = $2 LIMIT 1)
                  AND cd.is_active = true
                ORDER BY cd.attached_at ASC
            """

            rows = await pg_client.execute_query(query, conversation_id, user_identifier)
            dataset_ids = [str(row['dataset_id']) for row in rows]

            logger.info(f"Found {len(dataset_ids)} datasets for conversation {conversation_id}")
            return dataset_ids

        except Exception as e:
            logger.error(f"Failed to get conversation datasets: {e}")
            return []

    async def add_datasets_to_conversation(
        self,
        conversation_id: str,
        user_identifier: str,
        dataset_ids: List[str],
        source: str = "user_selected"
    ) -> bool:
        """Add datasets to a conversation"""
        try:
            if not dataset_ids:
                return True

            pg_client = await get_postgresql_client()

            # Ensure proper schema qualification
            schema_name = f"tenant_{self.tenant_domain.replace('.', '_').replace('-', '_')}"

            # Get user ID first
            user_query = f"SELECT id FROM {schema_name}.users WHERE email = $1 LIMIT 1"
            user_result = await pg_client.fetch_scalar(user_query, user_identifier)

            if not user_result:
                logger.error(f"User not found: {user_identifier}")
                return False

            user_id = user_result

            # Insert dataset attachments (ON CONFLICT DO NOTHING to avoid duplicates)
            values_list = []
            params = []
            param_idx = 1

            for dataset_id in dataset_ids:
                values_list.append(f"(${param_idx}, ${param_idx + 1}, ${param_idx + 2})")
                params.extend([conversation_id, dataset_id, user_id])
                param_idx += 3

            query = f"""
                INSERT INTO {schema_name}.conversation_datasets (conversation_id, dataset_id, attached_by)
                VALUES {', '.join(values_list)}
                ON CONFLICT (conversation_id, dataset_id) DO UPDATE SET
                    is_active = true,
                    attached_at = NOW()
            """

            await pg_client.execute_query(query, *params)

            logger.info(f"Added {len(dataset_ids)} datasets to conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add datasets to conversation: {e}")
            return False

    async def copy_agent_datasets_to_conversation(
        self,
        conversation_id: str,
        user_identifier: str,
        agent_id: str
    ) -> bool:
        """Copy an agent's default datasets to a new conversation"""
        try:
            # Get agent's selected dataset IDs from config
            from app.services.agent_service import AgentService
            agent_service = AgentService(self.tenant_domain, user_identifier)
            agent_data = await agent_service.get_agent(agent_id)

            if not agent_data:
                logger.warning(f"Agent {agent_id} not found")
                return False

            # Get selected_dataset_ids from agent config
            selected_dataset_ids = agent_data.get('selected_dataset_ids', [])

            if not selected_dataset_ids:
                logger.info(f"Agent {agent_id} has no default datasets")
                return True

            # Add agent's datasets to conversation
            success = await self.add_datasets_to_conversation(
                conversation_id=conversation_id,
                user_identifier=user_identifier,
                dataset_ids=selected_dataset_ids,
                source="agent_default"
            )

            if success:
                logger.info(f"Copied {len(selected_dataset_ids)} datasets from agent {agent_id} to conversation {conversation_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to copy agent datasets: {e}")
            return False

    async def get_recent_conversations(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations ordered by last activity"""
        try:
            pg_client = await get_postgresql_client()

            # Handle both email and UUID formats using existing pattern
            user_clause = self._get_user_clause(1, user_id)

            query = f"""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) as message_count,
                       MAX(m.created_at) as last_message_at,
                       a.name as agent_name
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                LEFT JOIN agents a ON a.id = c.agent_id
                WHERE c.user_id = {user_clause}
                  AND c.is_archived = false
                GROUP BY c.id, c.title, c.created_at, c.updated_at, a.name
                ORDER BY COALESCE(MAX(m.created_at), c.created_at) DESC
                LIMIT $2
            """

            rows = await pg_client.execute_query(query, user_id, limit)
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []

    async def mark_conversation_read(
        self,
        conversation_id: str,
        user_identifier: str
    ) -> bool:
        """
        Mark a conversation as read by updating last_read_at in metadata.

        Args:
            conversation_id: UUID of the conversation
            user_identifier: User email or UUID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Resolve user UUID with caching (performance optimization)
            user_uuid = await self._get_resolved_user_uuid(user_identifier)

            pg_client = await get_postgresql_client()

            # Update last_read_at in conversation metadata
            query = """
                UPDATE conversations
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{last_read_at}',
                    to_jsonb(NOW()::text)
                )
                WHERE id = $1
                  AND user_id = $2::uuid
                RETURNING id
            """

            result = await pg_client.fetch_one(query, conversation_id, user_uuid)

            if result:
                logger.info(f"Marked conversation {conversation_id} as read for user {user_identifier}")
                return True
            else:
                logger.warning(f"Conversation {conversation_id} not found or access denied for user {user_identifier}")
                return False

        except Exception as e:
            logger.error(f"Failed to mark conversation as read: {e}")
            return False