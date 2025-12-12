"""
Authentication utilities for API endpoints
"""

from fastapi import HTTPException, Header
from app.core.security import capability_validator, CapabilityToken


async def verify_capability(authorization: str = Header(None)) -> CapabilityToken:
    """Verify capability token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token_str = authorization.replace("Bearer ", "")
    token = capability_validator.verify_capability_token(token_str)
    
    if not token:
        raise HTTPException(status_code=401, detail="Invalid capability token")
    
    return token