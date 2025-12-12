"""
Webhook Receiver API

Handles incoming webhooks for automation triggers with security validation
and rate limiting.
"""

import logging
import hmac
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends, Header
from pydantic import BaseModel

from app.services.event_bus import TenantEventBus, TriggerType
from app.services.automation_executor import AutomationChainExecutor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookRegistration(BaseModel):
    """Webhook registration model"""
    name: str
    description: Optional[str] = None
    secret: Optional[str] = None
    rate_limit: int = 60  # Requests per minute
    allowed_ips: Optional[list[str]] = None
    events_to_trigger: list[str] = []


class WebhookPayload(BaseModel):
    """Generic webhook payload"""
    event: Optional[str] = None
    data: Dict[str, Any] = {}
    timestamp: Optional[str] = None


# In-memory webhook registry (in production, use database)
webhook_registry: Dict[str, Dict[str, Any]] = {}

# Rate limiting tracker (in production, use Redis)
rate_limiter: Dict[str, list[datetime]] = {}


def validate_webhook_registration(tenant_domain: str, webhook_id: str) -> Dict[str, Any]:
    """Validate webhook is registered"""
    key = f"{tenant_domain}:{webhook_id}"
    
    if key not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return webhook_registry[key]


def check_rate_limit(key: str, limit: int) -> bool:
    """Check if request is within rate limit"""
    now = datetime.utcnow()
    
    # Get request history
    if key not in rate_limiter:
        rate_limiter[key] = []
    
    # Remove old requests (older than 1 minute)
    rate_limiter[key] = [
        ts for ts in rate_limiter[key]
        if (now - ts).total_seconds() < 60
    ]
    
    # Check limit
    if len(rate_limiter[key]) >= limit:
        return False
    
    # Add current request
    rate_limiter[key].append(now)
    return True


def validate_hmac_signature(
    signature: str,
    body: bytes,
    secret: str
) -> bool:
    """Validate HMAC signature"""
    if not signature or not secret:
        return False
    
    # Calculate expected signature
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(signature, expected)


def sanitize_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize webhook payload to prevent injection attacks"""
    # Remove potentially dangerous keys
    dangerous_keys = ["__proto__", "constructor", "prototype"]
    
    def clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        for key, value in d.items():
            if key not in dangerous_keys:
                if isinstance(value, dict):
                    cleaned[key] = clean_dict(value)
                elif isinstance(value, list):
                    cleaned[key] = [
                        clean_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    # Limit string length
                    if isinstance(value, str) and len(value) > 10000:
                        cleaned[key] = value[:10000]
                    else:
                        cleaned[key] = value
        return cleaned
    
    return clean_dict(payload)


@router.post("/{tenant_domain}/{webhook_id}")
async def receive_webhook(
    tenant_domain: str,
    webhook_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_signature: Optional[str] = Header(None)
):
    """
    Receive webhook and trigger automations.
    
    Note: In production, webhooks terminate at NGINX in DMZ, not directly here.
    Traffic flow: Internet → NGINX (DMZ) → OAuth2 Proxy → This endpoint
    """
    try:
        # Validate webhook registration
        webhook = validate_webhook_registration(tenant_domain, webhook_id)
        
        # Check rate limiting
        rate_key = f"webhook:{tenant_domain}:{webhook_id}"
        if not check_rate_limit(rate_key, webhook.get("rate_limit", 60)):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Get request body
        body = await request.body()
        
        # Validate signature if configured
        if webhook.get("secret"):
            if not validate_hmac_signature(x_webhook_signature, body, webhook["secret"]):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Check IP whitelist if configured
        client_ip = request.client.host
        allowed_ips = webhook.get("allowed_ips")
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning(f"Webhook request from unauthorized IP: {client_ip}")
            raise HTTPException(status_code=403, detail="IP not authorized")
        
        # Parse and sanitize payload
        try:
            payload = await request.json()
            payload = sanitize_webhook_payload(payload)
        except Exception as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload format")
        
        # Queue for processing
        background_tasks.add_task(
            process_webhook_automation,
            tenant_domain=tenant_domain,
            webhook_id=webhook_id,
            payload=payload,
            webhook_config=webhook
        )
        
        return {
            "status": "accepted",
            "webhook_id": webhook_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_webhook_automation(
    tenant_domain: str,
    webhook_id: str,
    payload: Dict[str, Any],
    webhook_config: Dict[str, Any]
):
    """Process webhook and trigger associated automations"""
    try:
        # Initialize event bus
        event_bus = TenantEventBus(tenant_domain)
        
        # Create webhook event
        event_type = payload.get("event", "webhook.received")
        
        # Emit event to trigger automations
        await event_bus.emit_event(
            event_type=event_type,
            user_id=webhook_config.get("owner_id", "system"),
            data={
                "webhook_id": webhook_id,
                "payload": payload,
                "source": webhook_config.get("name", "Unknown")
            },
            metadata={
                "trigger_type": TriggerType.WEBHOOK.value,
                "webhook_config": webhook_config
            }
        )
        
        logger.info(f"Webhook processed: {webhook_id} → {event_type}")
        
    except Exception as e:
        logger.error(f"Error processing webhook automation: {e}")
        
        # Emit failure event
        try:
            event_bus = TenantEventBus(tenant_domain)
            await event_bus.emit_event(
                event_type="webhook.failed",
                user_id="system",
                data={
                    "webhook_id": webhook_id,
                    "error": str(e)
                }
            )
        except:
            pass


@router.post("/{tenant_domain}/register")
async def register_webhook(
    tenant_domain: str,
    registration: WebhookRegistration,
    user_email: str = "admin@example.com"  # In production, get from auth
):
    """Register a new webhook endpoint"""
    import secrets
    
    # Generate webhook ID
    webhook_id = secrets.token_urlsafe(16)
    
    # Store registration
    key = f"{tenant_domain}:{webhook_id}"
    webhook_registry[key] = {
        "id": webhook_id,
        "name": registration.name,
        "description": registration.description,
        "secret": registration.secret or secrets.token_urlsafe(32),
        "rate_limit": registration.rate_limit,
        "allowed_ips": registration.allowed_ips,
        "events_to_trigger": registration.events_to_trigger,
        "owner_id": user_email,
        "created_at": datetime.utcnow().isoformat(),
        "url": f"/webhooks/{tenant_domain}/{webhook_id}"
    }
    
    return {
        "webhook_id": webhook_id,
        "url": f"/webhooks/{tenant_domain}/{webhook_id}",
        "secret": webhook_registry[key]["secret"],
        "created_at": webhook_registry[key]["created_at"]
    }


@router.get("/{tenant_domain}/list")
async def list_webhooks(
    tenant_domain: str,
    user_email: str = "admin@example.com"  # In production, get from auth
):
    """List registered webhooks for tenant"""
    webhooks = []
    
    for key, webhook in webhook_registry.items():
        if key.startswith(f"{tenant_domain}:"):
            # Only show webhooks owned by user
            if webhook.get("owner_id") == user_email:
                webhooks.append({
                    "id": webhook["id"],
                    "name": webhook["name"],
                    "description": webhook.get("description"),
                    "url": webhook["url"],
                    "rate_limit": webhook["rate_limit"],
                    "created_at": webhook["created_at"]
                })
    
    return {
        "webhooks": webhooks,
        "total": len(webhooks)
    }


@router.delete("/{tenant_domain}/{webhook_id}")
async def delete_webhook(
    tenant_domain: str,
    webhook_id: str,
    user_email: str = "admin@example.com"  # In production, get from auth
):
    """Delete a webhook registration"""
    key = f"{tenant_domain}:{webhook_id}"
    
    if key not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    webhook = webhook_registry[key]
    
    # Check ownership
    if webhook.get("owner_id") != user_email:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Delete webhook
    del webhook_registry[key]
    
    return {
        "status": "deleted",
        "webhook_id": webhook_id
    }


@router.get("/{tenant_domain}/{webhook_id}/test")
async def test_webhook(
    tenant_domain: str,
    webhook_id: str,
    background_tasks: BackgroundTasks,
    user_email: str = "admin@example.com"  # In production, get from auth
):
    """Send a test payload to webhook"""
    key = f"{tenant_domain}:{webhook_id}"
    
    if key not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    webhook = webhook_registry[key]
    
    # Check ownership
    if webhook.get("owner_id") != user_email:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Create test payload
    test_payload = {
        "event": "webhook.test",
        "data": {
            "message": "This is a test webhook",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    # Process webhook
    background_tasks.add_task(
        process_webhook_automation,
        tenant_domain=tenant_domain,
        webhook_id=webhook_id,
        payload=test_payload,
        webhook_config=webhook
    )
    
    return {
        "status": "test_sent",
        "webhook_id": webhook_id,
        "payload": test_payload
    }