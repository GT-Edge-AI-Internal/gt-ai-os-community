"""
WebSocket API endpoints for GT 2.0 Tenant Backend

Provides secure WebSocket connections for real-time chat with:
- JWT authentication
- Perfect tenant isolation
- Conversation-based messaging
- Automatic cleanup on disconnect

GT 2.0 Security Features:
- Token-based authentication
- Rate limiting per user
- Connection limits per tenant
- Automatic session cleanup
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_current_user_email, get_tenant_info
from app.websocket import (
    websocket_manager,
    get_websocket_manager,
    authenticate_websocket_connection,
    WebSocketManager
)
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/chat/{conversation_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time chat in a specific conversation.
    
    Args:
        websocket: WebSocket connection
        conversation_id: Conversation ID to join
        token: JWT authentication token
    """
    connection_id = None
    
    try:
        # Authenticate connection
        try:
            user_id, tenant_id = await authenticate_websocket_connection(token)
        except ValueError as e:
            await websocket.close(code=1008, reason=f"Authentication failed: {e}")
            return
        
        # Verify conversation access
        async with get_db_session() as db:
            conversation_service = ConversationService(db)
            conversation = await conversation_service.get_conversation(conversation_id, user_id)
            
            if not conversation:
                await websocket.close(code=1008, reason="Conversation not found or access denied")
                return
        
        # Establish WebSocket connection
        manager = get_websocket_manager()
        connection_id = await manager.connect(
            websocket=websocket,
            user_id=user_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id
        )
        
        logger.info(f"WebSocket chat connection established: {connection_id} for conversation {conversation_id}")
        
        # Message handling loop
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle message
                success = await manager.handle_message(connection_id, message_data)
                
                if not success:
                    logger.warning(f"Failed to handle message from {connection_id}")
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from {connection_id}")
                await manager.send_to_connection(connection_id, {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "code": "INVALID_JSON"
                })
            except Exception as e:
                logger.error(f"Error in WebSocket message loop: {e}")
                break
    
    except Exception as e:
        logger.error(f"Error in WebSocket chat endpoint: {e}")
        try:
            await websocket.close(code=1011, reason=f"Server error: {e}")
        except:
            pass
    
    finally:
        # Cleanup connection
        if connection_id:
            await manager.disconnect(connection_id, reason="Connection closed")


@router.websocket("/general")
async def websocket_general_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token")
):
    """
    General WebSocket endpoint for notifications and system messages.
    
    Args:
        websocket: WebSocket connection
        token: JWT authentication token
    """
    connection_id = None
    
    try:
        # Authenticate connection
        try:
            user_id, tenant_id = await authenticate_websocket_connection(token)
        except ValueError as e:
            await websocket.close(code=1008, reason=f"Authentication failed: {e}")
            return
        
        # Establish WebSocket connection (no specific conversation)
        manager = get_websocket_manager()
        connection_id = await manager.connect(
            websocket=websocket,
            user_id=user_id,
            tenant_id=tenant_id,
            conversation_id=None
        )
        
        logger.info(f"General WebSocket connection established: {connection_id}")
        
        # Message handling loop
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle message
                success = await manager.handle_message(connection_id, message_data)
                
                if not success:
                    logger.warning(f"Failed to handle message from {connection_id}")
                
            except WebSocketDisconnect:
                logger.info(f"General WebSocket disconnected: {connection_id}")
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from {connection_id}")
                await manager.send_to_connection(connection_id, {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "code": "INVALID_JSON"
                })
            except Exception as e:
                logger.error(f"Error in general WebSocket message loop: {e}")
                break
    
    except Exception as e:
        logger.error(f"Error in general WebSocket endpoint: {e}")
        try:
            await websocket.close(code=1011, reason=f"Server error: {e}")
        except:
            pass
    
    finally:
        # Cleanup connection
        if connection_id:
            await manager.disconnect(connection_id, reason="Connection closed")


@router.get("/stats")
async def get_websocket_stats(
    current_user: str = Depends(get_current_user_email),
    tenant_info: dict = Depends(get_tenant_info)
):
    """Get WebSocket connection statistics for tenant"""
    try:
        manager = get_websocket_manager()
        stats = manager.get_connection_stats()
        
        # Filter stats for current tenant
        tenant_id = tenant_info["tenant_id"]
        tenant_stats = {
            "total_connections": stats["connections_by_tenant"].get(tenant_id, 0),
            "active_conversations": len([
                conv_id for conv_id, connections in manager.conversation_connections.items()
                if any(
                    manager.connections.get(conn_id, {}).tenant_id == tenant_id
                    for conn_id in connections
                )
            ]),
            "user_connections": stats["connections_by_user"].get(current_user, 0)
        }
        
        return JSONResponse(content=tenant_stats)
        
    except Exception as e:
        logger.error(f"Failed to get WebSocket stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broadcast/tenant")
async def broadcast_to_tenant(
    message: dict,
    current_user: str = Depends(get_current_user_email),
    tenant_info: dict = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Broadcast message to all connections in tenant.
    (Admin/system use only)
    """
    try:
        # Check if user has admin permissions
        # TODO: Implement proper admin role checking
        
        manager = get_websocket_manager()
        tenant_id = tenant_info["tenant_id"]
        
        broadcast_message = {
            "type": "system_broadcast",
            "message": message.get("content", ""),
            "timestamp": message.get("timestamp"),
            "sender": "system"
        }
        
        await manager.broadcast_to_tenant(tenant_id, broadcast_message)
        
        return JSONResponse(content={
            "message": "Broadcast sent successfully",
            "recipients": len(manager.tenant_connections.get(tenant_id, set()))
        })
        
    except Exception as e:
        logger.error(f"Failed to broadcast to tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/broadcast")
async def broadcast_to_conversation(
    conversation_id: str,
    message: dict,
    current_user: str = Depends(get_current_user_email),
    tenant_info: dict = Depends(get_tenant_info),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Broadcast message to all participants in a conversation.
    """
    try:
        # Verify user has access to conversation
        conversation_service = ConversationService(db)
        conversation = await conversation_service.get_conversation(conversation_id, current_user)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        manager = get_websocket_manager()
        
        broadcast_message = {
            "type": "conversation_broadcast",
            "conversation_id": conversation_id,
            "message": message.get("content", ""),
            "timestamp": message.get("timestamp"),
            "sender": current_user
        }
        
        await manager.broadcast_to_conversation(conversation_id, broadcast_message)
        
        return JSONResponse(content={
            "message": "Broadcast sent successfully",
            "conversation_id": conversation_id,
            "recipients": len(manager.conversation_connections.get(conversation_id, set()))
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to broadcast to conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/{connection_id}/send")
async def send_to_connection(
    connection_id: str,
    message: dict,
    current_user: str = Depends(get_current_user_email),
    tenant_info: dict = Depends(get_tenant_info)
):
    """
    Send message to specific connection.
    (Admin/system use only)
    """
    try:
        # Check if user has admin permissions or owns the connection
        manager = get_websocket_manager()
        connection = manager.connections.get(connection_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Verify tenant access
        if connection.tenant_id != tenant_info["tenant_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Add admin role check or connection ownership verification
        
        target_message = {
            "type": "direct_message",
            "message": message.get("content", ""),
            "timestamp": message.get("timestamp"),
            "sender": current_user
        }
        
        success = await manager.send_to_connection(connection_id, target_message)
        
        if not success:
            raise HTTPException(status_code=410, detail="Connection no longer active")
        
        return JSONResponse(content={
            "message": "Message sent successfully",
            "connection_id": connection_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send to connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/connections/{connection_id}")
async def disconnect_connection(
    connection_id: str,
    reason: str = Query("Admin disconnect", description="Disconnect reason"),
    current_user: str = Depends(get_current_user_email),
    tenant_info: dict = Depends(get_tenant_info)
):
    """
    Forcefully disconnect a WebSocket connection.
    (Admin use only)
    """
    try:
        # Check if user has admin permissions
        # TODO: Implement proper admin role checking
        
        manager = get_websocket_manager()
        connection = manager.connections.get(connection_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Verify tenant access
        if connection.tenant_id != tenant_info["tenant_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        await manager.disconnect(connection_id, code=1008, reason=reason)
        
        return JSONResponse(content={
            "message": "Connection disconnected successfully",
            "connection_id": connection_id,
            "reason": reason
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))