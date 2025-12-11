"""
Message DMZ Service for secure air-gap communication

Implements security controls for cross-cluster messaging including:
- Message validation and sanitization
- Command signature verification
- Audit logging
- Rate limiting
- Security policy enforcement
"""
import json
import logging
import hashlib
import hmac
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from collections import defaultdict
import asyncio

from app.core.config import settings
from app.schemas.messages import CommandType, AlertSeverity

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    """Raised when a security policy is violated"""
    pass


class MessageDMZ:
    """
    Security DMZ for message bus communication
    
    Provides defense-in-depth security controls for cross-cluster messaging
    """
    
    def __init__(self):
        # Rate limiting
        self.rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        self.rate_limit_window = timedelta(minutes=1)
        self.max_messages_per_minute = 100
        
        # Command whitelist
        self.allowed_commands = set(CommandType)
        
        # Blocked patterns (for detecting potential injection attacks)
        self.blocked_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',  # JavaScript URI
            r'on\w+\s*=',  # Event handlers
            r'DROP\s+TABLE',  # SQL injection
            r'DELETE\s+FROM',  # SQL injection
            r'INSERT\s+INTO',  # SQL injection
            r'UPDATE\s+SET',  # SQL injection
            r'--',  # SQL comment
            r'/\*.*\*/',  # SQL block comment
            r'\.\./+',  # Path traversal
            r'\\x[0-9a-fA-F]{2}',  # Hex encoding
            r'%[0-9a-fA-F]{2}',  # URL encoding suspicious patterns
        ]
        
        # Audit log
        self.audit_log: List[Dict[str, Any]] = []
        self.max_audit_entries = 10000
        
        # Security metrics
        self.metrics = {
            'messages_validated': 0,
            'messages_rejected': 0,
            'signature_failures': 0,
            'rate_limit_violations': 0,
            'injection_attempts': 0,
        }
    
    async def validate_incoming_message(
        self,
        message: Dict[str, Any],
        source: str
    ) -> Dict[str, Any]:
        """
        Validate incoming message from another cluster
        
        Args:
            message: Raw message data
            source: Source cluster identifier
        
        Returns:
            Validated and sanitized message
        
        Raises:
            SecurityViolation: If message fails validation
        """
        try:
            # Check rate limits
            if not self._check_rate_limit(source):
                self.metrics['rate_limit_violations'] += 1
                raise SecurityViolation(f"Rate limit exceeded for source: {source}")
            
            # Verify required fields
            required_fields = ['command_id', 'command_type', 'timestamp', 'signature']
            for field in required_fields:
                if field not in message:
                    raise SecurityViolation(f"Missing required field: {field}")
            
            # Verify timestamp (prevent replay attacks)
            if not self._verify_timestamp(message['timestamp']):
                raise SecurityViolation("Message timestamp is too old or invalid")
            
            # Verify command type is allowed
            if message['command_type'] not in self.allowed_commands:
                raise SecurityViolation(f"Unknown command type: {message['command_type']}")
            
            # Verify signature
            if not self._verify_signature(message):
                self.metrics['signature_failures'] += 1
                raise SecurityViolation("Invalid message signature")
            
            # Sanitize payload
            if 'payload' in message:
                message['payload'] = self._sanitize_payload(message['payload'])
            
            # Log successful validation
            self._audit_log('message_validated', source, message['command_id'])
            self.metrics['messages_validated'] += 1
            
            return message
            
        except SecurityViolation:
            self.metrics['messages_rejected'] += 1
            self._audit_log('message_rejected', source, message.get('command_id', 'unknown'))
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating message: {e}")
            self.metrics['messages_rejected'] += 1
            raise SecurityViolation(f"Message validation failed: {str(e)}")
    
    async def prepare_outgoing_message(
        self,
        command_type: str,
        payload: Dict[str, Any],
        target: str
    ) -> Dict[str, Any]:
        """
        Prepare message for sending to another cluster
        
        Args:
            command_type: Type of command
            payload: Command payload
            target: Target cluster identifier
        
        Returns:
            Prepared and signed message
        """
        # Sanitize payload
        sanitized_payload = self._sanitize_payload(payload)
        
        # Create message structure
        message = {
            'command_type': command_type,
            'payload': sanitized_payload,
            'target_cluster': target,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'admin_cluster'
        }
        
        # Sign message
        signature = self._create_signature(message)
        message['signature'] = signature
        
        # Audit log
        self._audit_log('message_prepared', target, command_type)
        
        return message
    
    def _check_rate_limit(self, source: str) -> bool:
        """Check if source has exceeded rate limits"""
        now = datetime.utcnow()
        
        # Clean old entries
        cutoff = now - self.rate_limit_window
        self.rate_limits[source] = [
            ts for ts in self.rate_limits[source]
            if ts > cutoff
        ]
        
        # Check limit
        if len(self.rate_limits[source]) >= self.max_messages_per_minute:
            return False
        
        # Add current timestamp
        self.rate_limits[source].append(now)
        return True
    
    def _verify_timestamp(self, timestamp_str: str, max_age_seconds: int = 300) -> bool:
        """Verify message timestamp is recent (prevent replay attacks)"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            age = (datetime.utcnow() - timestamp.replace(tzinfo=None)).total_seconds()
            
            # Message too old
            if age > max_age_seconds:
                return False
            
            # Message from future (clock skew tolerance of 30 seconds)
            if age < -30:
                return False
            
            return True
        except (ValueError, AttributeError):
            return False
    
    def _verify_signature(self, message: Dict[str, Any]) -> bool:
        """Verify message signature"""
        signature = message.get('signature', '')
        
        # Create message to verify (exclude signature field)
        message_copy = {k: v for k, v in message.items() if k != 'signature'}
        message_json = json.dumps(message_copy, sort_keys=True)
        
        # Verify signature
        expected_signature = hmac.new(
            settings.MESSAGE_BUS_SECRET_KEY.encode(),
            message_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def _create_signature(self, message: Dict[str, Any]) -> str:
        """Create message signature"""
        message_json = json.dumps(message, sort_keys=True)
        
        return hmac.new(
            settings.MESSAGE_BUS_SECRET_KEY.encode(),
            message_json.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _sanitize_payload(self, payload: Any) -> Any:
        """
        Sanitize payload to prevent injection attacks
        
        Recursively sanitizes strings in dictionaries and lists
        """
        if isinstance(payload, str):
            # Check for blocked patterns
            for pattern in self.blocked_patterns:
                if re.search(pattern, payload, re.IGNORECASE):
                    self.metrics['injection_attempts'] += 1
                    raise SecurityViolation(f"Potential injection attempt detected")
            
            # Basic sanitization
            # Remove control characters except standard whitespace
            sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', payload)
            
            # Limit string length
            max_length = 10000
            if len(sanitized) > max_length:
                sanitized = sanitized[:max_length]
            
            return sanitized
            
        elif isinstance(payload, dict):
            return {
                self._sanitize_payload(k): self._sanitize_payload(v)
                for k, v in payload.items()
            }
        elif isinstance(payload, list):
            return [self._sanitize_payload(item) for item in payload]
        else:
            # Numbers, booleans, None are safe
            return payload
    
    def _audit_log(
        self,
        event_type: str,
        target: str,
        details: Any
    ) -> None:
        """Add entry to audit log"""
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'target': target,
            'details': details
        }
        
        self.audit_log.append(entry)
        
        # Rotate log if too large
        if len(self.audit_log) > self.max_audit_entries:
            self.audit_log = self.audit_log[-self.max_audit_entries:]
        
        # Log to application logger
        logger.info(f"DMZ Audit: {event_type} - Target: {target} - Details: {details}")
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics"""
        return {
            **self.metrics,
            'audit_log_size': len(self.audit_log),
            'rate_limited_sources': len(self.rate_limits),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_audit_log(
        self,
        limit: int = 100,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get audit log entries"""
        logs = self.audit_log[-limit:]
        
        if event_type:
            logs = [log for log in logs if log['event_type'] == event_type]
        
        return logs
    
    async def validate_command_permissions(
        self,
        command_type: str,
        user_id: int,
        user_type: str,
        tenant_id: Optional[int] = None
    ) -> bool:
        """
        Validate user has permission to execute command
        
        Args:
            command_type: Type of command
            user_id: User ID
            user_type: User type (super_admin, tenant_admin, tenant_user)
            tenant_id: Tenant ID (for tenant-scoped commands)
        
        Returns:
            True if user has permission, False otherwise
        """
        # Super admins can execute all commands
        if user_type == 'super_admin':
            return True
        
        # Tenant admins can execute tenant-scoped commands for their tenant
        if user_type == 'tenant_admin' and tenant_id:
            tenant_commands = [
                CommandType.USER_CREATE,
                CommandType.USER_UPDATE,
                CommandType.USER_SUSPEND,
                CommandType.RESOURCE_ASSIGN,
                CommandType.RESOURCE_UNASSIGN
            ]
            return command_type in tenant_commands
        
        # Regular users cannot execute admin commands
        return False


# Global DMZ instance
message_dmz = MessageDMZ()