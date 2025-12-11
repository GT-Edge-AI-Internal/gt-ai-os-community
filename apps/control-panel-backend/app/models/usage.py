"""
Usage tracking database model
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UsageRecord(Base):
    """Usage tracking for billing and monitoring"""
    
    __tablename__ = "usage_records"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("ai_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    request_type = Column(String(50), nullable=False, index=True)  # chat, embedding, image_generation, etc.
    tokens_used = Column(Integer, nullable=False, default=0)
    cost_cents = Column(Integer, nullable=False, default=0)
    request_metadata = Column(JSON, nullable=False, default=dict)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="usage_records")
    ai_resource = relationship("AIResource", back_populates="usage_records")
    
    def __repr__(self):
        return f"<UsageRecord(id={self.id}, tenant_id={self.tenant_id}, tokens={self.tokens_used})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert usage record to dictionary"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "user_email": self.user_email,
            "request_type": self.request_type,
            "tokens_used": self.tokens_used,
            "cost_cents": self.cost_cents,
            "request_metadata": self.request_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def cost_dollars(self) -> float:
        """Get cost in dollars"""
        return self.cost_cents / 100.0
    
    @classmethod
    def calculate_cost(cls, tokens_used: int, resource_type: str, provider: str) -> int:
        """Calculate cost in cents based on usage"""
        # Cost calculation logic (example rates)
        if provider == "groq":
            if resource_type == "llm":
                # Groq LLM pricing: ~$0.0001 per 1K tokens
                return max(1, int((tokens_used / 1000) * 0.01 * 100))  # Convert to cents
            elif resource_type == "embedding":
                # Embedding pricing: ~$0.00002 per 1K tokens
                return max(1, int((tokens_used / 1000) * 0.002 * 100))  # Convert to cents
        
        # Default fallback cost
        return max(1, int((tokens_used / 1000) * 0.001 * 100))  # 0.1 cents per 1K tokens