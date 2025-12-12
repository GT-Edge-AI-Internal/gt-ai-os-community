"""
Chat API endpoints for GT 2.0 Tenant Backend

OpenAI-compatible chat completions endpoint that integrates with:
- Admin-configured models via Resource Cluster
- Agent configurations and personalities
- Conversation persistence in PostgreSQL
- Real-time AI responses from Groq/other providers
"""

import logging
import json
import asyncio
import httpx
import uuid
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.security import get_current_user
from app.core.config import get_settings
from app.core.response_filter import ResponseFilter
from app.services.conversation_service import ConversationService
from app.services.agent_service import AgentService
from app.services.rag_orchestrator import get_rag_orchestrator, RAGSearchParams
from app.services.task_classifier import get_task_classifier, TaskComplexity
from app.services.agent_orchestrator_client import get_subagent_orchestrator
from app.websocket.manager import (
    websocket_manager,
    emit_agentic_phase, emit_tool_update, emit_subagent_update, emit_source_update,
    emit_agentic_phase_socketio, emit_tool_update_socketio, emit_subagent_update_socketio, emit_source_update_socketio
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])




def detect_tool_intent(
    message: str,
    knowledge_search_enabled: bool = True
) -> List[str]:
    """
    Analyze user message and detect if it should trigger automatic tool usage.
    Returns list of tool names that should be used based on message intent.
    """
    if not message:
        return []

    message_lower = message.lower()
    tools_needed = []

    # Document/dataset search patterns - EXPANDED
    doc_patterns = [
        'document', 'documents', 'file', 'files', 'uploaded', 'upload',
        'pdf', 'dataset', 'datasets', 'content', 'material', 'reference',
        'sources', 'information about', 'what do we have', 'show me',
        'find', 'search for', 'do you have', 'any documents', 'any files',
        # New patterns from refinements:
        'what\'s in the dataset', 'what is in the dataset',
        'search our data', 'check if we have', 'look through files',
        'check documentation', 'reference data', 'look up',
        'find information', 'what\'s in', 'search files',
        'check the files', 'in our documents', 'compliance documentation',
        'check our', 'look in our', 'search in'
    ]

    if any(pattern in message_lower for pattern in doc_patterns) and knowledge_search_enabled:
        tools_needed.append('search_datasets')

    return tools_needed


def parse_function_format_to_tool_calls(content: str) -> List[Dict[str, Any]]:
    """
    Parse non-standard function format like <function=tool_name>{"param": "value"}
    into OpenAI tool_calls format
    """
    tool_calls = []

    # Pattern to match <function=tool_name>{json}
    pattern = r'<function=([^>]+)>\s*(\{[^}]*\})'
    matches = re.findall(pattern, content)

    for match in matches:
        tool_name, args_str = match
        try:
            # Parse the JSON arguments
            arguments = json.loads(args_str)

            # Create proper tool call structure
            tool_call = {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments)
                }
            }
            tool_calls.append(tool_call)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse function arguments: {args_str}, error: {e}")
            continue

    return tool_calls


# Streaming removed for reliability - using non-streaming only


# OpenAI-Compatible Request/Response Models
class ChatMessage(BaseModel):
    role: str  # "user", "agent", "system"
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = 0.0
    presence_penalty: Optional[float] = 0.0
    stop: Optional[Union[str, List[str]]] = None
    stream: Optional[bool] = False

    # GT 2.0 Extensions
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None
    knowledge_search_enabled: Optional[bool] = True

    # RAG Extensions
    use_rag: Optional[bool] = True
    # dataset_ids removed - datasets now configured via agent settings only
    rag_max_chunks: Optional[int] = 12
    rag_similarity_threshold: Optional[float] = 0.7


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageBreakdown(BaseModel):
    """Per-model token usage for Compound models (for accurate billing)"""
    models: List[Dict[str, Any]] = []


class CostBreakdown(BaseModel):
    """Detailed cost breakdown for Compound models"""
    models: List[Dict[str, Any]] = []
    tools: List[Dict[str, Any]] = []
    total_cost_dollars: float = 0.0
    total_cost_cents: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Usage

    # GT 2.0 Extensions
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None

    # RAG Extensions
    rag_context: Optional[Dict[str, Any]] = None

    # Compound model billing extensions (pass-through from Resource Cluster)
    usage_breakdown: Optional[UsageBreakdown] = None
    executed_tools: Optional[List[str]] = None
    cost_breakdown: Optional[CostBreakdown] = None


# Streaming model classes removed - using non-streaming only


@router.post("/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    http_request: Request = None
):
    """
    OpenAI-compatible chat completions endpoint with GT 2.0 enhancements
    
    Features:
    - Admin-configured model access control
    - Agent personality integration
    - Conversation persistence
    - Real AI responses via Resource Cluster
    """
    try:

        # Resolve user email to UUID for internal services
        from app.core.user_resolver import resolve_user_uuid
        tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)

        # Initialize services
        conversation_service = ConversationService(tenant_domain, user_id)
        agent_service = AgentService(tenant_domain, user_id, user_email)

        # Handle agent-based conversations
        agent_id = request.agent_id
        conversation_id = request.conversation_id

        logger.info(f"🎯 Chat API received - agent_id: {agent_id}, conversation_id: {conversation_id}, model: {request.model}")

        # Get model configuration early for token allocation
        available_models = await conversation_service.get_available_models(tenant_domain)
        logger.info(f"🔧 Available models: {[m.get('model_id', 'NO_ID') for m in available_models]}")

        # Safely match model configuration
        model_config = None
        if request.model:
            model_config = next((m for m in available_models if m.get('model_id') == request.model), None)
            if not model_config:
                logger.warning(f"⚠️ Model '{request.model}' not found in available models, using defaults")

        model_max_tokens = model_config.get('performance', {}).get('max_tokens', 4096) if model_config else 4096
        logger.info(f"🔧 Using model_max_tokens: {model_max_tokens}")

        # If agent_id provided, get agent configuration
        agent_instance = None
        agent_data = None
        if agent_id:
            agent_data = await agent_service.get_agent(agent_id)
            if not agent_data:
                raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

            # Create agent instance for RAG
            from app.models.agent import Agent, AgentVisibility, AgentStatus

            # Extract model provider and name from model string
            model_string = agent_data.get('model', 'llama-3.1-8b-instant')
            if '/' in model_string and model_string.startswith('groq/'):
                model_provider = 'groq'
                model_name = model_string.replace('groq/', '')
            else:
                model_provider = 'groq'  # Default
                model_name = model_string

            agent_instance = Agent(
                id=agent_data['id'],
                name=agent_data['name'],
                description=agent_data.get('description', ''),
                instructions=agent_data.get('prompt_template', ''),
                model_provider=model_provider,
                model_name=model_name,
                model_settings=agent_data.get('config', {}).get('model_settings', {}),
                capabilities=agent_data.get('capabilities', []),
                tools=[],
                mcp_servers=[],
                rag_enabled=True,  # Enable RAG for agents with datasets
                owner_id=str(agent_data.get('user_id', current_user.get('id', current_user.get('sub', '')))),
                access_group=agent_data.get('access_group', 'individual'),
                visibility=AgentVisibility(agent_data.get('visibility', 'individual')),
                status=AgentStatus.ACTIVE if agent_data.get('is_active', True) else AgentStatus.INACTIVE,
                featured=False,
                tags=agent_data.get('tags', []),
                category=None,
                conversation_count=agent_data.get('conversation_count', 0),
                last_used_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # Use agent's preferred model if not specified or if not provided
            if agent_data.get('model') and not request.model:
                request.model = agent_data['model']
            elif not request.model:
                request.model = 'llama-3.1-8b-instant'  # Default model

            # Get all available datasets (agent + conversation) for tool provisioning
            agent_dataset_ids = agent_data.get('selected_dataset_ids', []) if agent_data else []
            conversation_dataset_ids = []

            # Get conversation datasets if conversation exists
            if conversation_id:
                try:
                    conversation_dataset_ids = await conversation_service.get_conversation_datasets(
                        conversation_id=conversation_id,
                        user_identifier=user_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to get conversation datasets: {e}")
                    conversation_dataset_ids = []

            # Combine all available datasets
            all_available_datasets = list(set(agent_dataset_ids + conversation_dataset_ids))
            agent_has_datasets = len(all_available_datasets) > 0

            logger.info(f"🔧 Dataset availability: agent={len(agent_dataset_ids)}, conversation={len(conversation_dataset_ids)}, total={len(all_available_datasets)}")

            # Add agent's system prompt with tool awareness
            system_prompt = agent_data.get('prompt_template') or agent_data.get('system_prompt')
            if system_prompt:
                # Build dynamic tool awareness instructions based on enabled features
                tool_sections = []

                if request.knowledge_search_enabled and agent_has_datasets:
                    tool_sections.append("""• search_datasets: Searches your datasets (uploaded files, documents, PDFs).
  Examples of when to use:
  - "What's in our compliance documentation?" → search_datasets
  - "Check if we have any security policies" → search_datasets
  - "Find information about authentication" → search_datasets
  - "Look through our uploaded files for X" → search_datasets""")

                # Only add tool instructions if any tools are enabled
                if tool_sections:
                    tool_aware_prompt = f"""{system_prompt}

TOOL USAGE INSTRUCTIONS:
You have access to powerful search tools that help you find information:

{chr(10).join(tool_sections)}

CRITICAL: Analyze user intent and use tools proactively. Don't wait to be asked explicitly. If the user asks about content that might be in datasets or previous conversations, use the appropriate tool immediately."""
                else:
                    # No tools enabled, don't mention any tool capabilities
                    tool_aware_prompt = system_prompt

                logger.info(f"🎯 Dynamic system prompt: {len(tool_sections)} tool sections included (datasets: {request.knowledge_search_enabled and agent_has_datasets})")

                system_message = ChatMessage(role="system", content=tool_aware_prompt)
                request.messages.insert(0, system_message)

        # Add dataset context for agent awareness (Day 4 enhancement) - SECURITY FIXED
        if agent_instance:
            try:
                from app.services.summarization_service import SummarizationService
                summarization_service = SummarizationService(
                    tenant_domain,
                    current_user.get("id", user_id)
                )

                # SECURITY FIX: Only get summaries for datasets the agent should access
                # Use combined agent + conversation datasets (user selection removed)
                # This prevents information disclosure by restricting dataset access to:
                # 1. Datasets explicitly configured in agent settings
                # 2. Datasets from conversation-attached files only
                # Any other datasets (including other users' datasets) are completely hidden
                allowed_dataset_ids = all_available_datasets

                logger.info(f"Dataset access control: agent_datasets={len(agent_dataset_ids)}, conversation_datasets={len(conversation_dataset_ids)}, total_allowed={len(allowed_dataset_ids)}")

                # Only get summaries for explicitly allowed datasets
                datasets_with_summaries = []
                if allowed_dataset_ids:
                    raw_datasets = await summarization_service.get_filtered_datasets_with_summaries(
                        user_id,  # Pass the resolved UUID
                        allowed_dataset_ids
                    )

                    # Apply additional security filtering to dataset summaries
                    # Remove sensitive internal fields before adding to context
                    for dataset in raw_datasets:
                        sanitized = ResponseFilter.sanitize_dataset_summary(
                            dataset,
                            user_can_access=True  # Already filtered by allowed_dataset_ids
                        )
                        if sanitized:
                            datasets_with_summaries.append(sanitized)

                # Get conversation files for context
                conversation_files = []
                if conversation_id:
                    try:
                        from app.services.conversation_file_service import get_conversation_file_service
                        file_service = get_conversation_file_service(tenant_domain, current_user.get("id", user_id))
                        conversation_files = await file_service.list_files(conversation_id)
                        conversation_files = [f for f in conversation_files if f.get('processing_status') == 'completed']
                    except Exception as e:
                        logger.warning(f"Could not retrieve conversation files: {e}")

                # Build context string with datasets and conversation files
                if datasets_with_summaries or conversation_files:
                    context_parts = []

                    # Add dataset context (token-optimized)
                    if datasets_with_summaries:
                        num_datasets = len(datasets_with_summaries)
                        compact_mode = num_datasets > 2

                        dataset_context = "📂 PERMANENT DATASETS (Persistent Knowledge):\n"

                        if compact_mode:
                            dataset_context += f"{num_datasets} datasets available:\n"
                            for ds in datasets_with_summaries[:3]:
                                dataset_context += f"• {ds['name']} ({ds['document_count']} docs)\n"
                            if num_datasets > 3:
                                dataset_context += f"• ...and {num_datasets - 3} more\n"
                            dataset_context += "\nAuto-searched when relevant (similarity > 0.7)\n"
                        else:
                            for dataset in datasets_with_summaries:
                                dataset_context += f"\n• **{dataset['name']}** ({str(dataset['id'])[:8]}...)\n"
                                dataset_context += f"  Summary: {dataset.get('summary', 'No summary')}\n"
                                dataset_context += f"  Scope: {dataset['document_count']} documents, {dataset['chunk_count']:,} chunks\n"
                                dataset_context += f"  Access: Automatic RAG search (similarity > 0.7)\n"
                                dataset_context += f"  Type: Permanent - all conversations\n"

                        context_parts.append(dataset_context)

                    # Add conversation files context (token-optimized)
                    if conversation_files:
                        num_files = len(conversation_files)
                        compact_mode = num_files > 2

                        files_context = "📎 CONVERSATION FILES (This Chat Only):\n"

                        if compact_mode:
                            files_context += f"{num_files} files attached:\n"
                            for file_info in conversation_files[:3]:
                                filename = file_info.get('original_filename', 'Unknown')
                                status = '✅' if file_info.get('processing_status') == 'completed' else '⏳'
                                files_context += f"{status} {filename}\n"
                            if num_files > 3:
                                files_context += f"...and {num_files - 3} more files\n"
                            files_context += "\nThese files are automatically searched when relevant to user questions (similarity > 0.7).\n"
                        else:
                            for file_info in conversation_files:
                                filename = file_info.get('original_filename', 'Unknown')
                                file_id = file_info.get('id', 'unknown')

                                file_size = file_info.get('file_size_bytes', 0)
                                size_str = f"{file_size/(1024*1024):.1f}MB" if file_size > 1024*1024 else f"{file_size/1024:.1f}KB"

                                uploaded_at = file_info.get('uploaded_at', '')
                                if uploaded_at:
                                    try:
                                        dt = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))
                                        timestamp = dt.strftime('%Y-%m-%d %H:%M UTC')
                                    except:
                                        timestamp = 'Unknown'
                                else:
                                    timestamp = 'Unknown'

                                status_map = {
                                    'completed': '✅ Processed & searchable',
                                    'processing': '⚙️ Processing',
                                    'pending': '⏳ Pending',
                                    'failed': '❌ Failed'
                                }
                                status = status_map.get(file_info.get('processing_status'), '❓ Unknown')

                                files_context += f"\n• **{filename}**\n"
                                files_context += f"  Size: {size_str} | Uploaded: {timestamp}\n"
                                files_context += f"  Status: {status}\n"
                                files_context += f"  File ID: `{file_id}`\n"
                                files_context += f"  Access: Automatically searched when relevant (similarity > 0.7)\n"

                            files_context += "\n**Note:** Files only available in THIS conversation, auto-deleted when chat ends.\n"

                        context_parts.append(files_context)

                    # Combine context parts
                    full_context = "\n\n".join(context_parts)

                    # Add context awareness message
                    context_awareness_message = ChatMessage(
                        role="system",
                        content=full_context
                    )
                    request.messages.insert(-1 if len(request.messages) > 1 else 0, context_awareness_message)

                    logger.info(f"Added filtered dataset context: {len(datasets_with_summaries)} accessible datasets")
                else:
                    logger.info(f"No datasets accessible for agent - no context added")

            except Exception as e:
                logger.error(f"Error adding dataset context: {e}")
                # Continue without dataset context if it fails

        # Create or get conversation
        conversation_created = False
        if not conversation_id and agent_id:
            # Create new conversation if none specified
            conversation_data = await conversation_service.create_conversation(
                agent_id=agent_id,
                title=None,  # Let the conversation service generate the title consistently
                user_identifier=user_id
            )
            conversation_id = conversation_data["id"]
            conversation_created = True

        # Emit initial thinking phase for agentic UI
        if conversation_id:
            try:
                # Emit to both native WebSocket and Socket.IO
                await emit_agentic_phase(conversation_id, "thinking", {
                    "agent_id": agent_id,
                    "task_complexity": "simple"  # Will be updated after classification
                })
                await emit_agentic_phase_socketio(conversation_id, "thinking", {
                    "agent_id": agent_id,
                    "task_complexity": "simple"
                })
            except Exception as e:
                logger.warning(f"Failed to emit agentic phase: {e}")
                # Don't fail the request if WebSocket emission fails

            # Copy agent's default datasets to new conversation
            if agent_id:
                await conversation_service.copy_agent_datasets_to_conversation(
                    conversation_id=conversation_id,
                    user_identifier=user_id,
                    agent_id=agent_id
                )

        # Dataset selection via request removed - datasets configured via agent settings only

        # Conversation File Context - Budget-aware full file retrieval
        conversation_file_context = None
        if agent_instance and len(request.messages) > 0 and conversation_id:
            try:
                from app.services.conversation_file_service import get_conversation_file_service
                from app.utils.token_counter import (
                    estimate_tokens,
                    estimate_messages_tokens,
                    calculate_file_context_budget,
                    fit_chunks_to_budget
                )
                from collections import defaultdict

                file_service = get_conversation_file_service(tenant_domain, current_user.get("id", user_id))

                # Step 1: Get model configuration for context window (model_max_tokens already fetched at function start)
                context_window = model_config.get('performance', {}).get('context_window', 8192) if model_config else 8192

                # Step 2: Calculate conversation history tokens
                history_tokens = estimate_messages_tokens([msg.dict() if hasattr(msg, 'dict') else msg for msg in request.messages])

                # Step 3: Calculate HARD BUDGET for file context (ZERO OVERFLOW GUARANTEE)
                file_context_token_budget = calculate_file_context_budget(
                    context_window=context_window,
                    conversation_history_tokens=history_tokens,
                    model_max_tokens=model_max_tokens,
                    system_overhead_tokens=500
                )

                # Step 4: Check if there are conversation files
                conversation_files = await file_service.list_files(conversation_id)
                completed_files = [f for f in conversation_files if f.get('processing_status') == 'completed']

                if completed_files and file_context_token_budget > 0:
                    # Get ALL chunks from attached files (full file mode)
                    all_chunks = await file_service.get_all_chunks_for_conversation(
                        conversation_id=conversation_id
                    )

                    # Step 5: Fit chunks to EXACT budget (guarantees no overflow)
                    fitted_chunks = fit_chunks_to_budget(
                        chunks=all_chunks,
                        token_budget=file_context_token_budget,
                        preserve_file_boundaries=True
                    )

                    # Step 6: Build formatted context (already guaranteed to fit)
                    if fitted_chunks:
                        chunks_by_file = defaultdict(list)
                        for chunk in fitted_chunks:
                            chunks_by_file[chunk['document_id']].append(chunk)

                        file_context_parts = []
                        file_context_parts.append("#" * 80)
                        file_context_parts.append(f"📎 ATTACHED FILES ({len(chunks_by_file)} files, {len(fitted_chunks)} chunks)")
                        file_context_parts.append("#" * 80)
                        file_context_parts.append("⚠️  CONTEXT TYPE: FULL FILE CONTENT (NOT EXCERPTS)")
                        file_context_parts.append("These are COMPLETE files attached by the user to THIS conversation.")
                        file_context_parts.append("")
                        file_context_parts.append("Full content from attached files:\n")

                        for file_num, (file_id, chunks) in enumerate(chunks_by_file.items(), 1):
                            first_chunk = chunks[0]
                            filename = first_chunk['original_filename']
                            total_file_chunks = first_chunk['total_chunks']

                            file_context_parts.append(f"{'─' * 80}")
                            file_context_parts.append(f"📄 FILE {file_num}/{len(chunks_by_file)}: {filename}")
                            file_context_parts.append(f"   Showing {len(chunks)}/{total_file_chunks} chunks")
                            file_context_parts.append(f"{'─' * 80}\n")

                            for chunk in chunks:
                                file_context_parts.append(f"Chunk {chunk['chunk_index'] + 1}/{total_file_chunks}:")
                                file_context_parts.append(chunk['content'])  # Full chunk, no truncation
                                file_context_parts.append("")

                        file_context_parts.append(f"\n{'#' * 80}")
                        file_context_parts.append("⚠️  CRITICAL INSTRUCTIONS:")
                        file_context_parts.append("1. The content above is FROM THE USER'S ATTACHED FILE(S)")
                        file_context_parts.append("2. This is NOT from your knowledge base or training data")
                        file_context_parts.append("3. Always reference these files when answering questions about them")
                        file_context_parts.append("4. Say 'In your attached file [filename]...' when citing this content")
                        file_context_parts.append("#" * 80)

                        conversation_file_context = "\n".join(file_context_parts)

                        # Add conversation file context to messages (GUARANTEED TO FIT)
                        file_context_message = ChatMessage(
                            role="system",
                            content=conversation_file_context
                        )
                        request.messages.insert(-1, file_context_message)

                        logger.info(
                            f"📎 Added file context: {len(chunks_by_file)} files, "
                            f"{len(fitted_chunks)}/{len(all_chunks)} chunks, "
                            f"budget: {file_context_token_budget} tokens "
                            f"(model: {request.model}, context: {context_window})"
                        )

                        if len(fitted_chunks) < len(all_chunks):
                            logger.info(f"Excluded {len(all_chunks) - len(fitted_chunks)} chunks due to token budget")

                elif completed_files and file_context_token_budget <= 0:
                    # Budget exhausted by conversation history
                    logger.warning(
                        f"Cannot include attached files - context budget exhausted "
                        f"(history: {history_tokens} tokens, context: {context_window})"
                    )

            except Exception as e:
                logger.error(f"Conversation file retrieval failed: {e}")
                # Continue without file context

        # Dataset RAG Context Retrieval (gated by use_rag flag)
        rag_context = None
        if request.use_rag and agent_instance and len(request.messages) > 0 and conversation_id:
            try:
                # Get the user's latest message for RAG query
                user_messages = [msg for msg in request.messages if msg.role == "user"]
                if user_messages:
                    latest_user_message = user_messages[-1].content

                    # Get RAG orchestrator
                    rag_orchestrator = get_rag_orchestrator(
                        tenant_domain=tenant_domain,
                        user_id=current_user.get("id", user_id)
                    )

                    # Get datasets for this conversation (now populated)
                    conversation_dataset_ids = await conversation_service.get_conversation_datasets(
                        conversation_id=conversation_id,
                        user_identifier=user_id
                    )

                    # Simplified dataset logic: agent config + conversation files only
                    search_dataset_ids = None
                    dataset_source = "none"

                    if agent_data and agent_data.get('selected_dataset_ids'):
                        search_dataset_ids = agent_data.get('selected_dataset_ids')
                        dataset_source = "agent_config"
                        logger.info(f"🔍 RAG DATASETS: Using agent configured dataset_ids: {search_dataset_ids}")
                    elif conversation_dataset_ids:
                        search_dataset_ids = conversation_dataset_ids
                        dataset_source = "conversation_files"
                        logger.info(f"🔍 RAG DATASETS: Using conversation file dataset_ids: {search_dataset_ids}")
                    else:
                        logger.warning(f"🔍 RAG DATASETS: No dataset_ids found from agent ({agent_data.get('selected_dataset_ids') if agent_data else None}) or conversation files ({conversation_dataset_ids})")
                        dataset_source = "none_available"

                    # Create RAG search parameters
                    rag_params = RAGSearchParams(
                        query=latest_user_message,
                        dataset_ids=search_dataset_ids,
                        max_chunks=request.rag_max_chunks or 5,
                        similarity_threshold=request.rag_similarity_threshold or 0.7,
                        search_method="hybrid"
                    )

                    # Get RAG context
                    rag_context = await rag_orchestrator.get_rag_context(
                        agent=agent_instance,
                        user_message=latest_user_message,
                        conversation_id=conversation_id,
                        params=rag_params
                    )

                    # If we got relevant context, add it to the messages
                    if rag_context.chunks:
                        total_sources = len(rag_context.sources)
                        use_compact = total_sources > 2

                        context_text = rag_orchestrator.format_context_for_agent(
                            rag_context,
                            compact_mode=use_compact
                        )

                        context_message = ChatMessage(
                            role="system",
                            content=context_text
                        )
                        request.messages.insert(-1, context_message)

                        logger.info(
                            f"RAG context added: {len(rag_context.chunks)} chunks from {len(rag_context.sources)} sources "
                            f"(compact={'yes' if use_compact else 'no'})"
                        )

            except Exception as e:
                logger.error(f"RAG context retrieval failed: {e}")
                # Continue without RAG if it fails
                rag_context = None

        # Only enable knowledge search if agent has datasets AND user requested it
        effective_knowledge_search = request.knowledge_search_enabled and agent_has_datasets
        if not agent_has_datasets and request.knowledge_search_enabled:
            logger.info(f"🚫 Disabling knowledge search for agent without datasets")
        elif agent_has_datasets:
            logger.info(f"🔧 Agent dataset check: {len(agent_data.get('selected_dataset_ids', []))} datasets configured")

        # Get available MCP tools for this agent
        available_tools = await _get_mcp_tools_for_agent(
            agent_instance,
            tenant_domain,
            user_id,
            knowledge_search_enabled=effective_knowledge_search
        )

        # Detect tool usage intent from user message and add instruction if needed
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if user_messages and available_tools:
            latest_user_message = user_messages[-1].content
            detected_tools = detect_tool_intent(
                latest_user_message,
                knowledge_search_enabled=effective_knowledge_search
            )

            if detected_tools:
                # Add instruction message to guide the agent to use detected tools
                # Build tool descriptions dynamically based on what's actually available
                tool_descriptions = []

                if 'search_datasets' in detected_tools and effective_knowledge_search:
                    tool_descriptions.append("For search_datasets: Use when the user asks about documents, files, datasets, uploaded content, or needs to check documentation.")

                tool_instruction = f"""Based on the user's question, you should proactively use these tools: {', '.join(detected_tools)}.

{chr(10).join(tool_descriptions)}

Use the tools first, then provide your answer based on the results."""

                tool_message = ChatMessage(role="system", content=tool_instruction)
                request.messages.insert(-1, tool_message)  # Insert before last user message

                logger.info(f"🎯 Intent detected: {detected_tools} - Added tool usage instruction")
                logger.info(f"🎯 System instruction generated: {len(tool_descriptions)} tool descriptions included")
                logger.info(f"🎯 Tool descriptions: {[desc.split(':')[0] for desc in tool_descriptions]}")

        # User message is already saved by frontend via saveMessageToConversation
        # We only need to save the AI response here

        # Always use non-streaming for reliability (streaming removed)
        # Call Resource Cluster for AI response (non-streaming)
        try:
            # Task Classification for Agentic Behavior
            task_classifier = get_task_classifier()
            user_messages = [msg for msg in request.messages if msg.role == "user"]
            latest_user_message = user_messages[-1].content if user_messages else ""

            # Classify the task complexity
            task_classification = await task_classifier.classify_task(
                query=latest_user_message,
                conversation_context=request.messages,
                available_tools=[tool["function"]["name"] for tool in available_tools] if available_tools else []
            )

            logger.info(f"🧠 Task Classification: {task_classification.complexity} - {task_classification.reasoning}")

            # DISABLED: Subagent orchestration temporarily disabled to resolve 500 errors
            # See SUBAGENT-ORCHESTRATION-STREAMLINING.md for full analysis
            # Re-enable when system has 5+ MCP tools and genuine multi-step workflows are needed
            # To re-enable: change "if False and" to "if True and" or remove the False condition entirely
            # Check if we need subagent orchestration
            if False and task_classification.complexity in [TaskComplexity.COMPLEX, TaskComplexity.RESEARCH, TaskComplexity.IMPLEMENTATION]:
                # Use subagent orchestration for complex tasks
                logger.info(f"🚀 Launching subagent orchestration for {task_classification.complexity} task")

                orchestrator = get_subagent_orchestrator(tenant_domain, user_id)
                orchestration_result = await orchestrator.execute_task_plan(
                    task_classification=task_classification,
                    parent_agent=agent_instance,
                    conversation_id=conversation_id,
                    user_message=latest_user_message,
                    available_tools=available_tools or []
                )

                # Create AI response from orchestration
                ai_response = {
                    "id": f"chatcmpl-{conversation_id[:8]}",
                    "created": int(datetime.now().timestamp()),
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "agent",
                            "content": orchestration_result["final_response"]
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": 100,  # Estimate
                        "completion_tokens": len(orchestration_result["final_response"]) // 4,
                        "total_tokens": 100 + len(orchestration_result["final_response"]) // 4
                    }
                }

                # Note: Message persistence handled by frontend to avoid duplication
                # Metadata can be added via separate endpoint if needed

            else:
                # Standard single-agent execution with tool support
                ai_response = await _execute_with_tools(
                    conversation_service=conversation_service,
                    model=request.model,
                    messages=[{
                        "role": msg.role,
                        "content": msg.content,
                        **({"tool_calls": msg.tool_calls} if msg.tool_calls else {}),
                        **({"tool_call_id": getattr(msg, "tool_call_id", None)} if hasattr(msg, "tool_call_id") and getattr(msg, "tool_call_id", None) else {})
                    } for msg in request.messages],
                tenant_id=tenant_domain,
                user_id=user_id,
                temperature=request.temperature,
                max_tokens=model_max_tokens,
                top_p=request.top_p,
                tools=available_tools,
                conversation_id=conversation_id,
                rag_context=rag_context,
                agent_data=agent_data
            )
            
            # Add AI response to conversation history
            if conversation_id:
                # Prepare metadata with RAG context if available
                message_metadata = {}
                if rag_context and rag_context.sources:
                    message_metadata["context_sources"] = [source["document_name"] for source in rag_context.sources]
                    message_metadata["rag_context"] = {
                        "chunks_used": len(rag_context.chunks),
                        "datasets_searched": rag_context.datasets_used,
                        "retrieval_time_ms": rag_context.retrieval_time_ms
                    }

                # Handle tool calls or regular content
                message = ai_response["choices"][0]["message"]
                content = message.get("content") or ""

                # If there are tool calls, format them in content
                if message.get("tool_calls") and not content:
                    tool_calls_summary = []
                    for tool_call in message["tool_calls"]:
                        if tool_call.get("function"):
                            tool_name = tool_call["function"].get("name", "unknown_tool")
                            tool_calls_summary.append(f"Called {tool_name}")
                    content = f"[Tool calls: {', '.join(tool_calls_summary)}]"

                # Note: Message persistence handled by frontend to avoid duplication
                # Tool call metadata can be added via separate endpoint if needed
                
                # Auto-generate conversation title after first exchange
                if conversation_created:
                    # Generate title for new conversation after first agent response
                    logger.info(f"🎯 New conversation created, generating title after first exchange")
                    try:
                        await conversation_service.auto_generate_conversation_title(
                            conversation_id=conversation_id,
                            user_identifier=user_id
                        )
                        logger.info(f"✅ Title generation initiated for conversation {conversation_id}")
                    except Exception as e:
                        logger.warning(f"Failed to generate title for conversation {conversation_id}: {e}")
                        # Don't fail the request if title generation fails
                else:
                    # Check if existing conversation needs title generation
                    if conversation_id:
                        conversation = await conversation_service.get_conversation(conversation_id, user_email)
                        if conversation:
                            title = conversation.get("title", "")

                            # Check if title is generic or missing
                            if not title or title.startswith("New Conversation") or \
                               title.startswith("Title Generation") or \
                               title.startswith("Conversation with"):
                                # Check if we have enough messages for title generation
                                messages = await conversation_service.get_messages(conversation_id, user_email)
                                if len(messages) >= 2:  # At least user + agent message
                                    logger.info(f"🎯 Generating title for conversation {conversation_id} with generic title")
                                    try:
                                        await conversation_service.auto_generate_conversation_title(
                                            conversation_id=conversation_id,
                                            user_identifier=user_email
                                        )
                                        logger.info(f"✅ Title generated for conversation {conversation_id}")
                                    except Exception as e:
                                        logger.warning(f"Failed to generate title: {e}")
            
            # Prepare RAG context for response
            rag_response_context = None
            if rag_context and rag_context.chunks:
                rag_response_context = {
                    "chunks_used": len(rag_context.chunks),
                    "sources": rag_context.sources,
                    "datasets_searched": rag_context.datasets_used,
                    "retrieval_time_ms": rag_context.retrieval_time_ms,
                    "search_queries": rag_context.search_queries
                }

            # Build response with optional Compound billing fields
            response_kwargs = {
                "id": ai_response["id"],
                "created": ai_response["created"],
                "model": ai_response["model"],
                "choices": [
                    ChatChoice(
                        index=choice["index"],
                        message=ChatMessage(
                            role=choice["message"]["role"],
                            content=choice["message"].get("content") or "",
                            tool_calls=choice["message"].get("tool_calls")
                        ),
                        finish_reason=choice.get("finish_reason")
                    )
                    for choice in ai_response["choices"]
                ],
                "usage": Usage(
                    prompt_tokens=ai_response["usage"]["prompt_tokens"],
                    completion_tokens=ai_response["usage"]["completion_tokens"],
                    total_tokens=ai_response["usage"]["total_tokens"]
                ),
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "rag_context": rag_response_context
            }

            # Pass through Compound model billing data if present
            if ai_response.get("usage_breakdown"):
                usage_breakdown = ai_response["usage_breakdown"]
                # Handle both dict and object formats
                if isinstance(usage_breakdown, dict):
                    models = usage_breakdown.get("models", [])
                else:
                    models = getattr(usage_breakdown, "models", [])
                response_kwargs["usage_breakdown"] = UsageBreakdown(models=models)
            if ai_response.get("executed_tools"):
                response_kwargs["executed_tools"] = ai_response["executed_tools"]
            if ai_response.get("cost_breakdown"):
                cost_breakdown = ai_response["cost_breakdown"]
                # Handle both dict and object formats
                if isinstance(cost_breakdown, dict):
                    response_kwargs["cost_breakdown"] = CostBreakdown(
                        models=cost_breakdown.get("models", []),
                        tools=cost_breakdown.get("tools", []),
                        total_cost_dollars=cost_breakdown.get("total_cost_dollars", 0.0),
                        total_cost_cents=cost_breakdown.get("total_cost_cents", 0)
                    )
                else:
                    response_kwargs["cost_breakdown"] = CostBreakdown(
                        models=getattr(cost_breakdown, "models", []),
                        tools=getattr(cost_breakdown, "tools", []),
                        total_cost_dollars=getattr(cost_breakdown, "total_cost_dollars", 0.0),
                        total_cost_cents=getattr(cost_breakdown, "total_cost_cents", 0)
                    )

            return ChatCompletionResponse(**response_kwargs)
            
        except Exception as e:
            logger.error(f"Resource Cluster request failed: {e}")
            raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_available_models(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List models available to the current tenant

    Returns admin-configured models that the tenant has access to
    """
    try:
        from app.core.user_resolver import resolve_user_uuid
        tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)

        conversation_service = ConversationService(tenant_domain, user_id)
        
        # Get available models from Resource Cluster via admin configuration
        models = await conversation_service.get_available_models(tenant_id=tenant_domain)
        
        # Format as OpenAI models response
        return {
            "object": "list",
            "data": [
                {
                    "id": model["model_id"],
                    "object": "model",
                    "created": 1677610602,
                    "owned_by": model.get("provider", "gt2"),
                    "permission": [],
                    "root": model["model_id"],
                    "parent": None,
                    # GT 2.0 extensions
                    "provider": model.get("provider"),
                    "model_type": model.get("model_type"),
                    "capabilities": model.get("capabilities", {}),
                    "context_window": model.get("context_window"),
                    "max_tokens": model.get("max_tokens")
                }
                for model in models
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_with_tools(
    conversation_service,
    model: str,
    messages: List[Dict[str, Any]],
    tenant_id: str,
    user_id: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    top_p: float = 1.0,
    tools: Optional[List[Dict[str, Any]]] = None,
    conversation_id: Optional[str] = None,
    rag_context: Optional[Any] = None,
    max_iterations: int = 10,
    agent_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute chat completion with recursive tool execution support.

    Handles tool calls from the LLM, executes them via MCP,
    and feeds results back to the LLM for final response.
    """
    iteration = 0
    conversation_messages = messages.copy()

    while iteration < max_iterations:
        try:
            # Convert messages to format expected by conversation service
            # Need to handle tool messages specially
            api_messages = []
            for msg in conversation_messages:
                if msg.get("role") == "tool":
                    # Tool messages need special handling - ensure tool_call_id is present
                    tool_call_id = msg.get("tool_call_id")
                    if not tool_call_id:
                        logger.error(f"Tool message missing tool_call_id: {msg}")
                        continue
                    api_messages.append({
                        "role": "tool",
                        "content": msg.get("content", ""),
                        "tool_call_id": tool_call_id
                    })
                elif msg.get("tool_calls"):
                    # Assistant message with tool calls
                    api_messages.append({
                        "role": "agent",
                        "content": msg.get("content") or "",
                        "tool_calls": msg["tool_calls"]
                    })
                else:
                    # Regular message
                    api_messages.append({
                        "role": msg["role"],
                        "content": msg.get("content", "")
                    })

            # Get AI response with tools
            ai_response = await conversation_service.get_ai_response(
                model=model,
                messages=api_messages,
                tenant_id=tenant_id,
                user_id=user_id,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools if tools else None
            )

            # Check if the response contains tool calls
            message = ai_response["choices"][0]["message"]

            # Check for non-standard function format and convert to tool_calls
            if not message.get("tool_calls") and "<function=" in message.get("content", ""):
                logger.info("🔧 Parsing non-standard function format in AI response")
                parsed_tool_calls = parse_function_format_to_tool_calls(message.get("content", ""))
                if parsed_tool_calls:
                    message["tool_calls"] = parsed_tool_calls
                    # Clear the content since it contained the function call
                    message["content"] = ""
                    logger.info(f"🔧 Converted {len(parsed_tool_calls)} function calls to tool_calls format")

            if not message.get("tool_calls"):
                # No tool calls, return final response
                # Note: Message persistence handled by frontend to avoid duplication
                # Metadata can be added via separate endpoint if needed

                return ai_response

            # Execute tool calls
            logger.info(f"🔧 Executing {len(message['tool_calls'])} tool calls")

            # Add agent's message with tool calls to conversation
            conversation_messages.append({
                "role": "agent",  # Use agent for GT 2.0 compliance
                "content": message.get("content") or "",
                "tool_calls": message["tool_calls"]
            })

            # Execute each tool call
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_arguments = json.loads(tool_call["function"].get("arguments", "{}"))

                logger.info(f"🔨 Executing tool: {tool_name} with args: {tool_arguments}")

                try:
                    # Execute tool via MCP
                    tool_result = await _execute_mcp_tool(
                        tool_name=tool_name,
                        arguments=tool_arguments,
                        tenant_domain=tenant_id,
                        user_id=user_id,
                        agent_data=agent_data
                    )

                    conversation_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result)
                    })

                except Exception as e:
                    logger.error(f"Tool execution failed for {tool_name}: {e}")
                    # Add error result
                    conversation_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps({"error": str(e)})
                    })

            iteration += 1
            # Continue loop to get next response with tool results

        except Exception as e:
            logger.error(f"Tool execution loop failed: {e}")
            raise

    # Max iterations reached without final response
    logger.warning(f"Max tool execution iterations ({max_iterations}) reached")
    return {
        "id": f"chatcmpl-max-iterations",
        "created": int(datetime.now().timestamp()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "agent",
                "content": "I've executed multiple tools but couldn't complete the task within the iteration limit."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }


async def _execute_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tenant_domain: str,
    user_id: str,
    agent_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute an MCP tool via the Resource Cluster (simplified without capability tokens)"""
    import time
    start_time = time.time()

    logger.info(f"🚀 Starting MCP tool execution: {tool_name} for user {user_id} in tenant {tenant_domain}")
    logger.debug(f"📝 Tool arguments: {arguments}")

    try:
        settings = get_settings()
        mcp_base_url = settings.mcp_service_url
        logger.info(f"🔗 MCP base URL: {mcp_base_url}")

        # Map tool names to servers
        if tool_name == "search_datasets":
            server_name = "rag_server"
            actual_tool_name = "search_datasets"
        elif tool_name.startswith("rag_server_"):
            server_name = "rag_server"
            actual_tool_name = tool_name[len("rag_server_"):]
        else:
            server_name = "rag_server"
            actual_tool_name = tool_name

        logger.info(f"🎯 Mapped tool '{tool_name}' → server '{server_name}', actual_tool '{actual_tool_name}'")

        # Build request payload with agent context
        request_payload = {
            "server_id": server_name,
            "tool_name": actual_tool_name,
            "parameters": arguments,
            "tenant_domain": tenant_domain,
            "user_id": user_id,
            "agent_context": {
                "agent_id": agent_data.get('id') if agent_data else None,
                "agent_name": agent_data.get('name') if agent_data else None,
                "selected_dataset_ids": agent_data.get('selected_dataset_ids', []) if agent_data else []
            }
        }
        logger.debug(f"📤 Request payload: {request_payload}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"🌐 Making HTTP request to: {mcp_base_url}/api/v1/mcp/execute")

            response = await client.post(
                f"{mcp_base_url}/api/v1/mcp/execute",
                json=request_payload
            )

            execution_time_ms = (time.time() - start_time) * 1000
            logger.info(f"📊 HTTP response: {response.status_code} ({execution_time_ms:.1f}ms)")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ MCP Tool executed successfully: {tool_name} ({execution_time_ms:.1f}ms)")

                logger.debug(f"📥 Tool result structure: {json.dumps(result, indent=2)[:500]}")

                return result
            else:
                error_text = response.text
                error_msg = f"MCP tool execution failed: {response.status_code} - {error_text}"
                logger.error(f"❌ {error_msg}")
                logger.debug(f"📥 Error response body: {error_text}")
                return {"error": f"Tool execution failed: {response.status_code}"}

    except httpx.TimeoutException as e:
        execution_time_ms = (time.time() - start_time) * 1000
        error_msg = f"MCP tool execution timeout for {tool_name}: {e} ({execution_time_ms:.1f}ms)"
        logger.error(f"⏰ {error_msg}")
        return {"error": "Tool execution timed out"}
    except httpx.RequestError as e:
        error_msg = f"MCP tool execution network error for {tool_name}: {e}"
        logger.error(error_msg)
        return {"error": "Network error during tool execution"}
    except Exception as e:
        error_msg = f"MCP tool execution error for {tool_name}: {e}"
        logger.error(error_msg, exc_info=True)
        return {"error": str(e)}


async def _get_mcp_tools_for_agent(
    agent,
    tenant_domain: str,
    user_id: str,
    knowledge_search_enabled: bool = True
) -> List[Dict[str, Any]]:
    """Get available MCP tools formatted as OpenAI-compatible tools for the agent"""
    logger.info(f"🔧 Getting MCP tools - knowledge_search_enabled: {knowledge_search_enabled}")
    try:
        settings = get_settings()
        mcp_base_url = settings.mcp_service_url

        # Get available MCP servers from Resource Cluster
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{mcp_base_url}/api/v1/mcp/servers",
                params={
                    "knowledge_search_enabled": knowledge_search_enabled
                }
            )

            if response.status_code != 200:
                logger.error(f"Failed to get MCP servers from {mcp_base_url}: {response.status_code} - {response.text}")
                return []

            server_data = response.json()
            servers = server_data.get("servers", [])

            # Format MCP tools as OpenAI-compatible tools
            openai_tools = []

            for server in servers:
                if server.get("status") != "healthy":
                    continue

                server_name = server.get("server_name", "")

                # Get detailed tool schemas from the specific MCP server
                try:
                    tools_response = await client.get(
                        f"{mcp_base_url}/api/v1/mcp/tools",
                        params={
                            "server_name": server_name,
                            "knowledge_search_enabled": knowledge_search_enabled
                        }
                    )

                    if tools_response.status_code == 200:
                        tools_data = tools_response.json()
                        tools = tools_data.get("tools", [])

                        for tool in tools:
                            # Tool name mapping for consistency
                            tool_name_map = {
                                "rag_server_search_datasets": "search_datasets"
                            }

                            original_name = f"{server_name}_{tool.get('name', 'unknown')}"
                            simple_name = tool_name_map.get(original_name, original_name)

                            logger.info(f"✅ ADDING tool from resource cluster: {simple_name}")

                            # Enhanced descriptions
                            enhanced_descriptions = {
                                "search_datasets": "Search through datasets containing uploaded documents, PDFs, and files. Use when users ask about documentation, reference materials, checking files, looking up information, or need data from uploaded content."
                            }

                            # Use the actual tool schema from MCP
                            tool_def = {
                                "type": "function",
                                "function": {
                                    "name": simple_name,
                                    "description": enhanced_descriptions.get(simple_name, tool.get('description', f"{tool.get('name', 'unknown')} from {server_name} server")),
                                    "parameters": tool.get('inputSchema', {
                                        "type": "object",
                                        "properties": {
                                            "query": {
                                                "type": "string",
                                                "description": "The query or input for the tool"
                                            }
                                        },
                                        "required": ["query"]
                                    })
                                }
                            }
                            openai_tools.append(tool_def)

                    else:
                        logger.error(f"Failed to get tools for server {server_name}: {tools_response.status_code} - {tools_response.text}")
                        logger.info(f"🔄 Using fallback tool list for server {server_name}")

                        # Fallback to basic tool listing for this server
                        available_tools = server.get("available_tools", [])
                        for tool_name in available_tools:
                            # Tool name mapping for consistency
                            tool_name_map = {
                                "rag_server_search_datasets": "search_datasets"
                            }

                            original_name = f"{server_name}_{tool_name}"
                            simple_name = tool_name_map.get(original_name, original_name)

                            logger.info(f"✅ FALLBACK: Adding tool from resource cluster: {simple_name}")

                            tool_def = {
                                "type": "function",
                                "function": {
                                    "name": simple_name,  # Use simple_name like main path
                                    "description": f"{tool_name} from {server_name} server",
                                    "parameters": {
                                        "type": "object",
                                        "properties": {
                                            "query": {
                                                "type": "string",
                                                "description": "The query or input for the tool"
                                            }
                                        },
                                        "required": ["query"]
                                    }
                                }
                            }
                            openai_tools.append(tool_def)

                except Exception as tool_error:
                    logger.error(f"Error fetching tools for server {server_name}: {tool_error}", exc_info=True)
                    continue

            agent_name = agent.name if agent else "default"

            # Log summary of available tools
            tool_names = [tool.get("function", {}).get("name", "unknown") for tool in openai_tools]
            has_dataset_search = any("search_datasets" in name for name in tool_names)

            logger.info(f"🔧 MCP Tools Summary: Providing {len(openai_tools)} tools to agent {agent_name}")
            logger.info(f"🔧 Available search tools - Datasets: {has_dataset_search}")

            return openai_tools

    except Exception as e:
        logger.error(f"Failed to get MCP tools from {mcp_base_url if 'mcp_base_url' in locals() else 'unknown URL'}: {e}", exc_info=True)
        return []


@router.post("/conversations")
async def create_conversation(
    agent_id: str,
    title: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new conversation with an agent"""
    try:
        from app.core.user_resolver import resolve_user_uuid
        tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)

        conversation_service = ConversationService(tenant_domain, user_id)
        
        conversation = await conversation_service.create_conversation(
            agent_id=agent_id,
            title=title,
            user_identifier=user_id
        )
        
        return conversation
        
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    agent_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List user's conversations"""
    try:
        from app.core.user_resolver import resolve_user_uuid
        tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)

        conversation_service = ConversationService(tenant_domain, user_id)
        
        result = await conversation_service.list_conversations(
            user_identifier=user_id,
            agent_id=agent_id,
            limit=limit,
            offset=offset
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get conversation details with message history"""
    try:
        from app.core.user_resolver import resolve_user_uuid
        tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)

        conversation_service = ConversationService(tenant_domain, user_id)
        
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            user_identifier=user_email
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        messages = await conversation_service.get_messages(
            conversation_id=conversation_id,
            user_identifier=user_email
        )
        
        conversation["messages"] = messages
        return conversation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/mark-read")
async def mark_conversation_read(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Mark all messages in a conversation as read by updating last_read_at timestamp."""
    try:
        from app.core.user_resolver import resolve_user_uuid
        tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)

        conversation_service = ConversationService(tenant_domain, user_id)

        # Update last_read_at for this user's participation in the conversation
        success = await conversation_service.mark_conversation_read(
            conversation_id=conversation_id,
            user_identifier=user_email
        )

        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")

        # Broadcast to user's other devices for multi-device sync
        try:
            from app.websocket.manager import broadcast_to_user
            await broadcast_to_user(
                user_id=str(user_id),
                tenant_id=tenant_domain,
                event='conversation:read',
                data={'conversation_id': conversation_id}
            )
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast conversation:read via WebSocket: {ws_error}")
            # Don't fail the request if WebSocket broadcast fails

        return {
            "success": True,
            "conversation_id": conversation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark conversation as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))