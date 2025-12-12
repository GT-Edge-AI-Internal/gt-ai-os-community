"""
RabbitMQ Message Bus Service for cross-cluster communication

Implements secure message passing between Admin, Tenant, and Resource clusters
with cryptographic signing and air-gap communication protocol.
"""
import asyncio
import json
import logging
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
import aio_pika
from aio_pika import Message, ExchangeType, DeliveryMode
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AdminCommand:
    """Base class for admin commands sent via message bus"""
    command_id: str
    command_type: str
    target_cluster: str  # 'tenant' or 'resource'
    target_namespace: Optional[str]  # For tenant-specific commands
    payload: Dict[str, Any]
    timestamp: str
    signature: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary for JSON serialization"""
        return asdict(self)
    
    def sign(self, secret_key: str) -> None:
        """Sign the command with HMAC-SHA256"""
        # Create message to sign (exclude signature field)
        message = json.dumps({
            'command_id': self.command_id,
            'command_type': self.command_type,
            'target_cluster': self.target_cluster,
            'target_namespace': self.target_namespace,
            'payload': self.payload,
            'timestamp': self.timestamp
        }, sort_keys=True)
        
        # Generate signature
        self.signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @classmethod
    def verify_signature(cls, data: Dict[str, Any], secret_key: str) -> bool:
        """Verify command signature"""
        signature = data.get('signature', '')
        
        # Create message to verify (exclude signature field)
        message = json.dumps({
            'command_id': data.get('command_id'),
            'command_type': data.get('command_type'),
            'target_cluster': data.get('target_cluster'),
            'target_namespace': data.get('target_namespace'),
            'payload': data.get('payload'),
            'timestamp': data.get('timestamp')
        }, sort_keys=True)
        
        # Verify signature
        expected_signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


class MessageBusService:
    """RabbitMQ message bus service for cross-cluster communication"""
    
    def __init__(self):
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractRobustChannel] = None
        self.command_callbacks: Dict[str, List[Callable]] = {}
        self.response_futures: Dict[str, asyncio.Future] = {}
        self.secret_key = settings.MESSAGE_BUS_SECRET_KEY or "PRODUCTION_MESSAGE_BUS_SECRET_REQUIRED"
        
    async def connect(self) -> None:
        """Establish connection to RabbitMQ"""
        try:
            # Get connection URL from settings
            rabbitmq_url = settings.RABBITMQ_URL or "amqp://admin:dev_rabbitmq_password@localhost:5672/gt2"
            
            # Create robust connection (auto-reconnect on failure)
            self.connection = await aio_pika.connect_robust(
                rabbitmq_url,
                client_properties={
                    'connection_name': 'gt2-control-panel'
                }
            )
            
            # Create channel
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            
            # Declare exchanges
            await self._declare_exchanges()
            
            # Set up queues for receiving responses
            await self._setup_response_queue()
            
            logger.info("Connected to RabbitMQ message bus")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close RabbitMQ connection"""
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("Disconnected from RabbitMQ message bus")
    
    async def _declare_exchanges(self) -> None:
        """Declare message exchanges for cross-cluster communication"""
        # Admin commands exchange (fanout to all clusters)
        await self.channel.declare_exchange(
            name='gt2.admin.commands',
            type=ExchangeType.TOPIC,
            durable=True
        )
        
        # Tenant cluster exchange
        await self.channel.declare_exchange(
            name='gt2.tenant.commands',
            type=ExchangeType.DIRECT,
            durable=True
        )
        
        # Resource cluster exchange
        await self.channel.declare_exchange(
            name='gt2.resource.commands',
            type=ExchangeType.DIRECT,
            durable=True
        )
        
        # Response exchange (for command responses)
        await self.channel.declare_exchange(
            name='gt2.responses',
            type=ExchangeType.DIRECT,
            durable=True
        )
        
        # System alerts exchange
        await self.channel.declare_exchange(
            name='gt2.alerts',
            type=ExchangeType.FANOUT,
            durable=True
        )
    
    async def _setup_response_queue(self) -> None:
        """Set up queue for receiving command responses"""
        # Declare response queue for this control panel instance
        queue_name = f"gt2.admin.responses.{uuid.uuid4().hex[:8]}"
        
        queue = await self.channel.declare_queue(
            name=queue_name,
            exclusive=True,  # Exclusive to this connection
            auto_delete=True  # Delete when connection closes
        )
        
        # Bind to response exchange
        await queue.bind(
            exchange='gt2.responses',
            routing_key=queue_name
        )
        
        # Start consuming responses
        await queue.consume(self._handle_response)
        
        self.response_queue_name = queue_name
    
    async def send_tenant_command(
        self,
        command_type: str,
        tenant_namespace: str,
        payload: Dict[str, Any],
        wait_for_response: bool = False,
        timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Send command to tenant cluster
        
        Args:
            command_type: Type of command (e.g., 'provision', 'deploy', 'suspend')
            tenant_namespace: Target tenant namespace
            payload: Command payload
            wait_for_response: Whether to wait for response
            timeout: Response timeout in seconds
        
        Returns:
            Response data if wait_for_response is True, else None
        """
        command = AdminCommand(
            command_id=str(uuid.uuid4()),
            command_type=command_type,
            target_cluster='tenant',
            target_namespace=tenant_namespace,
            payload=payload,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Sign the command
        command.sign(self.secret_key)
        
        # Create response future if needed
        if wait_for_response:
            future = asyncio.Future()
            self.response_futures[command.command_id] = future
        
        # Send command
        await self._publish_command(command)
        
        # Wait for response if requested
        if wait_for_response:
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return response
            except asyncio.TimeoutError:
                logger.error(f"Command {command.command_id} timed out after {timeout}s")
                del self.response_futures[command.command_id]
                return None
            finally:
                # Clean up future
                if command.command_id in self.response_futures:
                    del self.response_futures[command.command_id]
        
        return None
    
    async def send_resource_command(
        self,
        command_type: str,
        payload: Dict[str, Any],
        wait_for_response: bool = False,
        timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Send command to resource cluster
        
        Args:
            command_type: Type of command (e.g., 'health_check', 'update_config')
            payload: Command payload
            wait_for_response: Whether to wait for response
            timeout: Response timeout in seconds
        
        Returns:
            Response data if wait_for_response is True, else None
        """
        command = AdminCommand(
            command_id=str(uuid.uuid4()),
            command_type=command_type,
            target_cluster='resource',
            target_namespace=None,
            payload=payload,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Sign the command
        command.sign(self.secret_key)
        
        # Create response future if needed
        if wait_for_response:
            future = asyncio.Future()
            self.response_futures[command.command_id] = future
        
        # Send command
        await self._publish_command(command)
        
        # Wait for response if requested
        if wait_for_response:
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return response
            except asyncio.TimeoutError:
                logger.error(f"Command {command.command_id} timed out after {timeout}s")
                del self.response_futures[command.command_id]
                return None
            finally:
                # Clean up future
                if command.command_id in self.response_futures:
                    del self.response_futures[command.command_id]
        
        return None
    
    async def _publish_command(self, command: AdminCommand) -> None:
        """Publish command to appropriate exchange"""
        # Determine exchange and routing key
        if command.target_cluster == 'tenant':
            exchange_name = 'gt2.tenant.commands'
            routing_key = command.target_namespace or 'all'
        elif command.target_cluster == 'resource':
            exchange_name = 'gt2.resource.commands'
            routing_key = 'all'
        else:
            exchange_name = 'gt2.admin.commands'
            routing_key = f"{command.target_cluster}.{command.command_type}"
        
        # Create message
        message = Message(
            body=json.dumps(command.to_dict()).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            headers={
                'command_id': command.command_id,
                'command_type': command.command_type,
                'timestamp': command.timestamp,
                'reply_to': self.response_queue_name if hasattr(self, 'response_queue_name') else None
            }
        )
        
        # Get exchange
        exchange = await self.channel.get_exchange(exchange_name)
        
        # Publish message
        await exchange.publish(
            message=message,
            routing_key=routing_key
        )
        
        logger.info(f"Published command {command.command_id} to {exchange_name}/{routing_key}")
    
    async def _handle_response(self, message: aio_pika.IncomingMessage) -> None:
        """Handle response messages"""
        async with message.process():
            try:
                # Parse response
                data = json.loads(message.body.decode())
                
                # Verify signature
                if not AdminCommand.verify_signature(data, self.secret_key):
                    logger.error(f"Invalid signature for response: {data.get('command_id')}")
                    return
                
                command_id = data.get('command_id')
                
                # Check if we're waiting for this response
                if command_id in self.response_futures:
                    future = self.response_futures[command_id]
                    if not future.done():
                        future.set_result(data.get('payload'))
                
                # Log response
                logger.info(f"Received response for command {command_id}")
                
            except Exception as e:
                logger.error(f"Error handling response: {e}")
    
    async def publish_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Publish system alert to all clusters
        
        Args:
            alert_type: Type of alert (e.g., 'security', 'health', 'deployment')
            severity: Alert severity ('info', 'warning', 'error', 'critical')
            message: Alert message
            details: Additional alert details
        """
        alert_data = {
            'alert_id': str(uuid.uuid4()),
            'alert_type': alert_type,
            'severity': severity,
            'message': message,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'admin_cluster'
        }
        
        # Sign the alert
        alert_json = json.dumps(alert_data, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            alert_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        alert_data['signature'] = signature
        
        # Create message
        message = Message(
            body=json.dumps(alert_data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            headers={
                'alert_type': alert_type,
                'severity': severity,
                'timestamp': alert_data['timestamp']
            }
        )
        
        # Get alerts exchange
        exchange = await self.channel.get_exchange('gt2.alerts')
        
        # Publish alert
        await exchange.publish(
            message=message,
            routing_key=''  # Fanout exchange, routing key ignored
        )
        
        logger.info(f"Published {severity} alert: {message}")


# Global message bus instance
message_bus = MessageBusService()


async def initialize_message_bus():
    """Initialize the message bus connection"""
    await message_bus.connect()


async def shutdown_message_bus():
    """Shutdown the message bus connection"""
    await message_bus.disconnect()