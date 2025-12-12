"""
Message Bus Client for GT 2.0 Tenant Backend

Handles communication with Admin Cluster via RabbitMQ message queues.
Processes commands from admin and sends responses back.
"""

import json
import logging
import asyncio
import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from pydantic import BaseModel, Field

import aio_pika
from aio_pika import connect, Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class AdminCommand(BaseModel):
    """Command received from Admin Cluster"""
    command_id: str
    command_type: str  # TENANT_PROVISION, TENANT_SUSPEND, etc.
    target_cluster: str
    target_namespace: str
    payload: Dict[str, Any]
    timestamp: str
    signature: str

class TenantResponse(BaseModel):
    """Response sent to Admin Cluster"""
    command_id: str
    response_type: str  # SUCCESS, ERROR, PROCESSING
    target_cluster: str = "admin"
    source_cluster: str = "tenant"
    namespace: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    signature: Optional[str] = None

class MessageBusClient:
    """
    Client for RabbitMQ message bus communication with Admin Cluster.
    
    GT 2.0 Security Principles:
    - HMAC signature verification for all messages
    - Tenant-scoped command processing
    - No cross-tenant message leakage
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None
        self.admin_to_tenant_queue = None
        self.tenant_to_admin_queue = None
        
        # Message handlers
        self.command_handlers: Dict[str, Callable[[AdminCommand], Any]] = {}
        
        # RabbitMQ configuration from admin specification
        self.rabbitmq_url = getattr(
            self.settings, 
            'RABBITMQ_URL',
            'amqp://gt2_admin:dev_password_change_in_prod@rabbitmq:5672/'
        )
        
        # Security
        self.secret_key = getattr(self.settings, 'SECRET_KEY', 'production-secret-key')
        
        logger.info("Message bus client initialized")
    
    async def connect(self) -> bool:
        """Connect to RabbitMQ message bus"""
        try:
            self.connection = await connect(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            
            # Declare exchanges and queues matching admin specification
            await self.channel.declare_exchange(
                'gt2_commands', ExchangeType.DIRECT, durable=True
            )
            
            # Admin → Tenant command queue
            self.admin_to_tenant_queue = await self.channel.declare_queue(
                'admin_to_tenant', durable=True
            )
            
            # Tenant → Admin response queue  
            self.tenant_to_admin_queue = await self.channel.declare_queue(
                'tenant_to_admin', durable=True
            )
            
            # Start consuming commands
            await self.admin_to_tenant_queue.consume(self._handle_admin_command)
            
            logger.info("Connected to RabbitMQ message bus")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to message bus: {e}")
            return False
    
    def _verify_signature(self, message_data: Dict[str, Any], signature: str) -> bool:
        """Verify HMAC signature of incoming message"""
        try:
            # Create message content for signature (excluding signature field)
            content = {k: v for k, v in message_data.items() if k != 'signature'}
            content_str = json.dumps(content, sort_keys=True)
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.secret_key.encode(),
                content_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    def _sign_message(self, message_data: Dict[str, Any]) -> str:
        """Create HMAC signature for outgoing message"""
        try:
            content_str = json.dumps(message_data, sort_keys=True)
            return hmac.new(
                self.secret_key.encode(),
                content_str.encode(),
                hashlib.sha256
            ).hexdigest()
        except Exception as e:
            logger.error(f"Message signing failed: {e}")
            return ""
    
    async def _handle_admin_command(self, message: AbstractIncomingMessage) -> None:
        """Handle incoming command from Admin Cluster"""
        try:
            # Parse message
            message_data = json.loads(message.body.decode())
            command = AdminCommand(**message_data)
            
            logger.info(f"Received admin command: {command.command_type} ({command.command_id})")
            
            # Verify signature
            if not self._verify_signature(message_data, command.signature):
                logger.error(f"Invalid signature for command {command.command_id}")
                await self._send_response(command.command_id, "ERROR", {
                    "error": "Invalid signature",
                    "namespace": command.target_namespace
                })
                return
            
            # Check if we have a handler for this command type
            if command.command_type not in self.command_handlers:
                logger.warning(f"No handler for command type: {command.command_type}")
                await self._send_response(command.command_id, "ERROR", {
                    "error": f"Unknown command type: {command.command_type}",
                    "namespace": command.target_namespace
                })
                return
            
            # Execute command handler
            handler = self.command_handlers[command.command_type]
            result = await handler(command)
            
            # Send success response
            await self._send_response(command.command_id, "SUCCESS", {
                "result": result,
                "namespace": command.target_namespace
            })
            
            # Acknowledge message
            message.ack()
            
        except Exception as e:
            logger.error(f"Error handling admin command: {e}")
            try:
                if 'command' in locals():
                    await self._send_response(command.command_id, "ERROR", {
                        "error": str(e),
                        "namespace": getattr(command, 'target_namespace', 'unknown')
                    })
                message.nack(requeue=False)
            except:
                pass
    
    async def _send_response(self, command_id: str, response_type: str, payload: Dict[str, Any]) -> None:
        """Send response back to Admin Cluster"""
        try:
            response_data = {
                "command_id": command_id,
                "response_type": response_type,
                "target_cluster": "admin",
                "source_cluster": "tenant",
                "namespace": payload.get("namespace", "unknown"),
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Sign the response
            response_data["signature"] = self._sign_message(response_data)
            
            # Send message
            message = Message(
                json.dumps(response_data).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            await self.channel.default_exchange.publish(
                message, routing_key=self.tenant_to_admin_queue.name
            )
            
            logger.info(f"Sent response to admin: {response_type} for {command_id}")
            
        except Exception as e:
            logger.error(f"Failed to send response to admin: {e}")
    
    def register_handler(self, command_type: str, handler: Callable[[AdminCommand], Any]) -> None:
        """Register handler for specific command type"""
        self.command_handlers[command_type] = handler
        logger.info(f"Registered handler for command type: {command_type}")
    
    async def send_notification(self, notification_type: str, payload: Dict[str, Any]) -> None:
        """Send notification to Admin Cluster (not in response to a command)"""
        try:
            notification_data = {
                "command_id": str(uuid.uuid4()),
                "response_type": f"NOTIFICATION_{notification_type}",
                "target_cluster": "admin", 
                "source_cluster": "tenant",
                "namespace": getattr(self.settings, 'TENANT_ID', 'unknown'),
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Sign the notification
            notification_data["signature"] = self._sign_message(notification_data)
            
            # Send message
            message = Message(
                json.dumps(notification_data).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            await self.channel.default_exchange.publish(
                message, routing_key=self.tenant_to_admin_queue.name
            )
            
            logger.info(f"Sent notification to admin: {notification_type}")
            
        except Exception as e:
            logger.error(f"Failed to send notification to admin: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from message bus"""
        try:
            if self.connection:
                await self.connection.close()
                logger.info("Disconnected from message bus")
        except Exception as e:
            logger.error(f"Error disconnecting from message bus: {e}")

# Global instance
message_bus_client = MessageBusClient()

# Command handlers for different admin commands
async def handle_tenant_provision(command: AdminCommand) -> Dict[str, Any]:
    """Handle tenant provisioning command"""
    logger.info(f"Processing tenant provision for: {command.target_namespace}")
    
    # TODO: Implement tenant provisioning logic
    # - Create tenant directory structure
    # - Initialize SQLite database
    # - Set up access controls
    # - Configure resource quotas
    
    return {
        "status": "provisioned",
        "namespace": command.target_namespace,
        "resources_allocated": command.payload.get("resources", {})
    }

async def handle_tenant_suspend(command: AdminCommand) -> Dict[str, Any]:
    """Handle tenant suspension command"""
    logger.info(f"Processing tenant suspension for: {command.target_namespace}")
    
    # TODO: Implement tenant suspension logic
    # - Disable API access
    # - Pause running processes
    # - Preserve data integrity
    
    return {
        "status": "suspended",
        "namespace": command.target_namespace
    }

async def handle_tenant_activate(command: AdminCommand) -> Dict[str, Any]:
    """Handle tenant activation command"""
    logger.info(f"Processing tenant activation for: {command.target_namespace}")
    
    # TODO: Implement tenant activation logic
    # - Restore API access
    # - Resume processes
    # - Validate system state
    
    return {
        "status": "activated", 
        "namespace": command.target_namespace
    }

async def handle_resource_allocate(command: AdminCommand) -> Dict[str, Any]:
    """Handle resource allocation command"""
    logger.info(f"Processing resource allocation for: {command.target_namespace}")
    
    # TODO: Implement resource allocation logic
    # - Update resource quotas
    # - Configure rate limits
    # - Enable new capabilities
    
    return {
        "status": "allocated",
        "namespace": command.target_namespace,
        "resources": command.payload.get("resources", {})
    }

async def handle_resource_revoke(command: AdminCommand) -> Dict[str, Any]:
    """Handle resource revocation command"""
    logger.info(f"Processing resource revocation for: {command.target_namespace}")
    
    # TODO: Implement resource revocation logic
    # - Remove resource access
    # - Update quotas
    # - Gracefully handle running operations
    
    return {
        "status": "revoked",
        "namespace": command.target_namespace
    }

# Register all command handlers
async def initialize_message_bus() -> bool:
    """Initialize message bus with all command handlers"""
    try:
        # Register command handlers
        message_bus_client.register_handler("TENANT_PROVISION", handle_tenant_provision)
        message_bus_client.register_handler("TENANT_SUSPEND", handle_tenant_suspend) 
        message_bus_client.register_handler("TENANT_ACTIVATE", handle_tenant_activate)
        message_bus_client.register_handler("RESOURCE_ALLOCATE", handle_resource_allocate)
        message_bus_client.register_handler("RESOURCE_REVOKE", handle_resource_revoke)
        
        # Connect to message bus
        connected = await message_bus_client.connect()
        
        if connected:
            logger.info("Message bus client initialized successfully")
            return True
        else:
            logger.error("Failed to initialize message bus client")
            return False
            
    except Exception as e:
        logger.error(f"Error initializing message bus: {e}")
        return False