"""
Conversation API endpoints for GT 2.0 Tenant Backend

Handles conversation management for AI chat sessions.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.services.conversation_service import ConversationService
from app.core.database import get_db
from app.api.auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["conversations"])


class CreateConversationRequest(BaseModel):
    """Request model for creating a conversation"""
    agent_id: str = Field(..., description="Agent ID to use for conversation")
    title: Optional[str] = Field(None, description="Optional conversation title")


class MessageRequest(BaseModel):
    """Request model for sending a message"""
    content: str = Field(..., description="Message content")
    stream: bool = Field(default=False, description="Stream the response")


async def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    """Get conversation service instance"""
    return ConversationService(db)


@router.get("/conversations")
async def list_conversations(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    service: ConversationService = Depends(get_conversation_service),
    current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """List user's conversations"""
    try:
        # Extract email from user object
        user_email = current_user.get("email") if isinstance(current_user, dict) else current_user
        result = await service.list_conversations(
            user_identifier=user_email,
            agent_id=agent_id,
            limit=limit,
            offset=offset
        )
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    service: ConversationService = Depends(get_conversation_service),
    current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """Create new conversation"""
    try:
        # Extract email from user object
        user_email = current_user.get("email") if isinstance(current_user, dict) else current_user
        result = await service.create_conversation(
            agent_id=request.agent_id,
            title=request.title,
            user_identifier=user_email
        )
        return JSONResponse(status_code=201, content=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    include_messages: bool = Query(False, description="Include messages in response"),
    service: ConversationService = Depends(get_conversation_service),
    current_user: str = Depends(get_current_user)
) -> JSONResponse:
    """Get conversation details"""
    try:
        result = await service.get_conversation(
            conversation_id=conversation_id,
            user_identifier=current_user,
            include_messages=include_messages
        )
        return JSONResponse(status_code=200, content=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: dict,
    service: ConversationService = Depends(get_conversation_service),
    current_user: str = Depends(get_current_user)
) -> JSONResponse:
    """Update a conversation title"""
    try:
        title = request.get("title")
        if not title:
            raise ValueError("Title is required")
            
        await service.update_conversation(
            conversation_id=conversation_id,
            user_identifier=current_user,
            title=title
        )
        return JSONResponse(status_code=200, content={"message": "Conversation updated successfully"})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    service: ConversationService = Depends(get_conversation_service),
    current_user: str = Depends(get_current_user)
) -> JSONResponse:
    """Delete a conversation"""
    try:
        await service.delete_conversation(
            conversation_id=conversation_id,
            user_identifier=current_user
        )
        return JSONResponse(status_code=200, content={"message": "Conversation deleted successfully"})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))