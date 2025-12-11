"""
Conversation API endpoints for GT 2.0 Tenant Backend - PostgreSQL Migration

Basic conversation endpoints during PostgreSQL migration.
Full functionality will be restored as migration completes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging

from app.core.security import get_current_user
from app.services.conversation_service import ConversationService
from app.websocket.manager import websocket_manager

# TEMPORARY: Basic response schemas during migration
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List
from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse

class ConversationResponse(BaseModel):
    id: str
    title: str
    agent_id: Optional[str]
    agent_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    token_count: int = 0
    is_archived: bool = False
    unread_count: int = 0

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int

# Message creation model
class MessageCreate(BaseModel):
    """Request body for creating a message in a conversation"""
    role: str = Field(..., description="Message role: user, assistant, agent, or system")
    content: str = Field(..., description="Message content (supports any length)")
    model_used: Optional[str] = Field(None, description="Model used to generate the message")
    token_count: int = Field(0, ge=0, description="Token count for the message")
    metadata: Optional[Dict] = Field(None, description="Additional message metadata")
    attachments: Optional[List] = Field(None, description="Message attachments")

    model_config = {"protected_namespaces": ()}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    current_user: Dict[str, Any] = Depends(get_current_user),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    search: Optional[str] = Query(None, description="Search in conversation titles"),
    time_filter: str = Query("all", description="Filter by time: 'today', 'week', 'month', 'all'"),
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0)
) -> ConversationListResponse:
    """List user's conversations using PostgreSQL with server-side filtering"""
    try:
        # Extract tenant domain from user context
        tenant_domain = current_user.get("tenant_domain", "test")

        service = ConversationService(tenant_domain, current_user["email"])

        # Get conversations from PostgreSQL with filters
        result = await service.list_conversations(
            user_identifier=current_user["email"],
            agent_id=agent_id,
            search=search,
            time_filter=time_filter,
            limit=limit,
            offset=offset
        )

        # Convert to response format
        conversations = [
            ConversationResponse(
                id=conv["id"],
                title=conv["title"],
                agent_id=conv["agent_id"],
                agent_name=conv.get("agent_name"),
                created_at=conv["created_at"],
                updated_at=conv.get("updated_at"),
                last_message_at=conv.get("last_message_at"),
                message_count=conv.get("message_count", 0),
                token_count=conv.get("token_count", 0),
                is_archived=conv.get("is_archived", False),
                unread_count=conv.get("unread_count", 0)
            )
            for conv in result["conversations"]
        ]

        return ConversationListResponse(
            conversations=conversations,
            total=result["total"]
        )
        
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Dict[str, Any])
async def create_conversation(
    agent_id: str,
    title: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new conversation with an agent"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])
        
        result = await service.create_conversation(
            agent_id=agent_id,
            title=title,
            user_identifier=current_user["email"]
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific conversation with details"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])
        
        result = await service.get_conversation(
            conversation_id=conversation_id,
            user_identifier=current_user["email"]
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/messages", response_model=List[Dict[str, Any]])
async def get_conversation_messages(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> List[Dict[str, Any]]:
    """Get messages for a conversation"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])
        
        messages = await service.get_messages(
            conversation_id=conversation_id,
            user_identifier=current_user["email"],
            limit=limit,
            offset=offset
        )
        
        return messages
        
    except Exception as e:
        logger.error(f"Failed to get messages for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/messages", response_model=Dict[str, Any])
async def add_message(
    conversation_id: str,
    message: MessageCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Add a message to a conversation (supports messages of any length)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])

        result = await service.add_message(
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
            user_identifier=current_user["email"],
            model_used=message.model_used,
            token_count=message.token_count,
            metadata=message.metadata,
            attachments=message.attachments
        )

        # Broadcast message creation via WebSocket for unread tracking and sidebar updates
        try:
            # Get updated conversation details (message count, timestamp)
            conv_details = await service.get_conversation(
                conversation_id=conversation_id,
                user_identifier=current_user["email"]
            )

            # Import the Socket.IO broadcast function
            from app.websocket.manager import broadcast_conversation_update

            await broadcast_conversation_update(
                conversation_id=conversation_id,
                event='conversation:message_added',
                data={
                    'conversation_id': conversation_id,
                    'message_id': result.get('id'),
                    'sender_id': current_user.get('id'),
                    'role': message.role,
                    'content': message.content[:100],  # First 100 chars for preview
                    'message_count': conv_details.get('message_count', conv_details.get('total_messages', 0)),
                    'last_message_at': result.get('created_at'),
                    'title': conv_details.get('title', 'New Conversation')
                }
            )
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast message via WebSocket: {ws_error}")
            # Don't fail the request if WebSocket broadcast fails

        # Check if we should generate a title after this message
        if message.role == "agent" or message.role == "assistant":
            # This is an AI response - check if it's after the first user message
            try:
                # Get all messages in conversation
                messages = await service.get_messages(
                    conversation_id=conversation_id,
                    user_identifier=current_user["email"]
                )

                # Count user and agent messages
                user_messages = [m for m in messages if m["role"] == "user"]
                agent_messages = [m for m in messages if m["role"] in ["agent", "assistant"]]

                # Generate title if this is the first exchange (1 user + 1 agent message)
                if len(user_messages) == 1 and len(agent_messages) == 1:
                    logger.info(f"🎯 First exchange complete, generating title for conversation {conversation_id}")
                    try:
                        await service.auto_generate_conversation_title(
                            conversation_id=conversation_id,
                            user_identifier=current_user["email"]
                        )
                        logger.info(f"✅ Title generated for conversation {conversation_id}")
                    except Exception as e:
                        logger.warning(f"Failed to generate title for conversation {conversation_id}: {e}")
                        # Don't fail the request if title generation fails

            except Exception as e:
                logger.error(f"Error checking for title generation: {e}")
                # Don't fail the request if title check fails

        return result
        
    except Exception as e:
        logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    title: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update a conversation (e.g., rename title)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])
        
        success = await service.update_conversation(
            conversation_id=conversation_id,
            user_identifier=current_user["email"],
            title=title
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
            
        return {"message": "Conversation updated successfully", "conversation_id": conversation_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete a conversation (soft delete)"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])

        success = await service.delete_conversation(
            conversation_id=conversation_id,
            user_identifier=current_user["email"]
        )

        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent", response_model=ConversationListResponse)
async def get_recent_conversations(
    current_user: Dict[str, Any] = Depends(get_current_user),
    days_back: int = Query(7, ge=1, le=30, description="Number of days back"),
    max_conversations: int = Query(10, ge=1, le=25, description="Maximum conversations"),
    include_archived: bool = Query(False, description="Include deleted conversations")
):
    """
    Get recent conversation summaries.

    Used by MCP conversation server for recent activity context.
    """
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])

        # Get recent conversations
        result = await service.list_conversations(
            user_identifier=current_user["email"],
            limit=max_conversations,
            offset=0,
            order_by="updated_at",
            order_direction="desc"
        )

        # Convert to response format
        conversations = [
            ConversationResponse(
                id=conv["id"],
                title=conv["title"],
                agent_id=conv["agent_id"],
                created_at=conv["created_at"]
            )
            for conv in result["conversations"]
        ]

        return ConversationListResponse(
            conversations=conversations,
            total=len(conversations)
        )

    except Exception as e:
        logger.error(f"Failed to get recent conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Dataset management models
class AddDatasetsRequest(BaseModel):
    """Request to add datasets to a conversation"""
    dataset_ids: List[str] = Field(..., min_items=1, description="Dataset IDs to add to conversation")

class DatasetOperationResponse(BaseModel):
    """Response for dataset operations"""
    success: bool
    message: str
    conversation_id: str
    dataset_count: int

# Conversation file models
class ConversationFileResponse(BaseModel):
    """Response for conversation file operations"""
    id: str
    filename: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    processing_status: str
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

class ConversationFileListResponse(BaseModel):
    """Response for listing conversation files"""
    conversation_id: str
    files: List[ConversationFileResponse]
    total_files: int


@router.post("/{conversation_id}/datasets", response_model=DatasetOperationResponse)
async def add_datasets_to_conversation(
    conversation_id: str,
    request: AddDatasetsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> DatasetOperationResponse:
    """Add datasets to a conversation for context awareness"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])

        # Add datasets to conversation
        success = await service.add_datasets_to_conversation(
            conversation_id=conversation_id,
            dataset_ids=request.dataset_ids,
            user_identifier=current_user["email"]
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to add datasets to conversation. Check conversation exists and you have access."
            )

        logger.info(f"Added {len(request.dataset_ids)} datasets to conversation {conversation_id}")

        return DatasetOperationResponse(
            success=True,
            message=f"Successfully added {len(request.dataset_ids)} dataset(s) to conversation",
            conversation_id=conversation_id,
            dataset_count=len(request.dataset_ids)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add datasets to conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/datasets")
async def get_conversation_datasets(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get datasets associated with a conversation"""
    try:
        tenant_domain = current_user.get("tenant_domain", "test")
        service = ConversationService(tenant_domain, current_user["email"])

        dataset_ids = await service.get_conversation_datasets(
            conversation_id=conversation_id,
            user_identifier=current_user["email"]
        )

        return {
            "conversation_id": conversation_id,
            "dataset_ids": dataset_ids,
            "dataset_count": len(dataset_ids)
        }

    except Exception as e:
        logger.error(f"Failed to get datasets for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Conversation File Management Endpoints

@router.post("/{conversation_id}/files", response_model=List[ConversationFileResponse])
async def upload_conversation_files(
    conversation_id: str,
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[ConversationFileResponse]:
    """Upload files directly to conversation (replaces dataset-based uploads)"""
    try:
        from app.services.conversation_file_service import get_conversation_file_service

        tenant_domain = current_user.get("tenant_domain", "test")
        service = get_conversation_file_service(tenant_domain, current_user["email"])

        # Upload files to conversation
        uploaded_files = await service.upload_files(
            conversation_id=conversation_id,
            files=files,
            user_id=current_user["email"]
        )

        # Convert to response format
        file_responses = []
        for file_data in uploaded_files:
            file_responses.append(ConversationFileResponse(
                id=file_data["id"],
                filename=file_data["filename"],
                original_filename=file_data["original_filename"],
                content_type=file_data["content_type"],
                file_size_bytes=file_data["file_size_bytes"],
                processing_status=file_data["processing_status"],
                uploaded_at=file_data["uploaded_at"],
                processed_at=file_data.get("processed_at")
            ))

        logger.info(f"Uploaded {len(uploaded_files)} files to conversation {conversation_id}")
        return file_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload files to conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/files", response_model=ConversationFileListResponse)
async def list_conversation_files(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ConversationFileListResponse:
    """List files attached to conversation"""
    try:
        from app.services.conversation_file_service import get_conversation_file_service

        tenant_domain = current_user.get("tenant_domain", "test")
        service = get_conversation_file_service(tenant_domain, current_user["email"])

        files = await service.list_files(conversation_id)

        # Convert to response format
        file_responses = []
        for file_data in files:
            file_responses.append(ConversationFileResponse(
                id=str(file_data["id"]),  # Convert UUID to string
                filename=file_data["filename"],
                original_filename=file_data["original_filename"],
                content_type=file_data["content_type"],
                file_size_bytes=file_data["file_size_bytes"],
                processing_status=file_data["processing_status"],
                uploaded_at=file_data["uploaded_at"],
                processed_at=file_data.get("processed_at")
            ))

        return ConversationFileListResponse(
            conversation_id=conversation_id,
            files=file_responses,
            total_files=len(file_responses)
        )

    except Exception as e:
        logger.error(f"Failed to list files for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}/files/{file_id}")
async def delete_conversation_file(
    conversation_id: str,
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete specific file from conversation"""
    try:
        from app.services.conversation_file_service import get_conversation_file_service

        tenant_domain = current_user.get("tenant_domain", "test")
        service = get_conversation_file_service(tenant_domain, current_user["email"])

        success = await service.delete_file(
            conversation_id=conversation_id,
            file_id=file_id,
            user_id=current_user["email"]
        )

        if not success:
            raise HTTPException(status_code=404, detail="File not found or access denied")

        return {"message": "File deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file {file_id} from conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/files/{file_id}/download")
async def download_conversation_file(
    conversation_id: str,
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Download specific conversation file"""
    try:
        from app.services.conversation_file_service import get_conversation_file_service

        tenant_domain = current_user.get("tenant_domain", "test")
        service = get_conversation_file_service(tenant_domain, current_user["email"])

        # Get file record for metadata
        file_record = await service._get_file_record(file_id)
        if not file_record or file_record['conversation_id'] != conversation_id:
            raise HTTPException(status_code=404, detail="File not found")

        # Get file content
        content = await service.get_file_content(file_id, current_user["email"])
        if not content:
            raise HTTPException(status_code=404, detail="File content not found")

        # Return file as streaming response
        def iter_content():
            yield content

        return StreamingResponse(
            iter_content(),
            media_type=file_record['content_type'],
            headers={
                "Content-Disposition": f"attachment; filename=\"{file_record['original_filename']}\"",
                "Content-Length": str(file_record['file_size_bytes'])
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))