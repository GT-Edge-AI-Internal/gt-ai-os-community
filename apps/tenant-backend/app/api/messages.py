"""
Message API endpoints for GT 2.0 Tenant Backend

Handles message management within conversations.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any
from pydantic import BaseModel, Field
import json
import logging

from app.services.conversation_service import ConversationService
from app.core.security import get_current_user
from app.core.user_resolver import resolve_user_uuid

router = APIRouter(tags=["messages"])


class SendMessageRequest(BaseModel):
    """Request model for sending a message"""
    content: str = Field(..., description="Message content")
    stream: bool = Field(default=False, description="Stream the response")


logger = logging.getLogger(__name__)


async def get_conversation_service(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ConversationService:
    """Get properly initialized conversation service"""
    tenant_domain, user_email, user_id = await resolve_user_uuid(current_user)
    return ConversationService(tenant_domain=tenant_domain, user_id=user_id)


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> JSONResponse:
    """List messages in conversation"""
    try:
        # Get properly initialized service
        service = await get_conversation_service(current_user)

        # Get conversation with messages
        result = await service.get_conversation(
            conversation_id=conversation_id,
            user_identifier=service.user_id,
            include_messages=True
        )
        return JSONResponse(
            status_code=200,
            content={"messages": result.get("messages", [])}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    role: str,
    content: str,
    stream: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> JSONResponse:
    """Send a message and get AI response"""
    try:
        # Get properly initialized service
        service = await get_conversation_service(current_user)

        # Send message
        result = await service.send_message(
            conversation_id=conversation_id,
            content=content,
            stream=stream
        )

        # Generate title after first message
        if result.get("is_first_message", False):
            try:
                await service.auto_generate_conversation_title(
                    conversation_id=conversation_id,
                    user_identifier=service.user_id
                )
                logger.info(f"✅ Title generated for conversation {conversation_id}")
            except Exception as e:
                logger.warning(f"Failed to generate title: {e}")
                # Don't fail the request if title generation fails

        return JSONResponse(status_code=201, content=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: int,
    content: str,
    service: ConversationService = Depends(get_conversation_service),
    current_user: str = Depends(get_current_user)
):
    """Stream AI response for a message"""
    
    async def generate():
        """Generate SSE stream"""
        try:
            async for chunk in service.stream_message_response(
                conversation_id=conversation_id,
                message_content=content,
                user_identifier=current_user
            ):
                # Format as Server-Sent Event
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Send completion signal
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Message streaming failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'An internal error occurred. Please try again.'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )