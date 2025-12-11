"""
Tenant Template Model
Stores reusable tenant configuration templates
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class TenantTemplate(Base):
    """Tenant template model for storing reusable configurations"""

    __tablename__ = "tenant_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    template_data = Column(JSONB, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<TenantTemplate(id={self.id}, name='{self.name}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template_data": self.template_data,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get template summary with resource counts"""
        model_count = len(self.template_data.get("model_configs", []))
        agent_count = len(self.template_data.get("agents", []))
        dataset_count = len(self.template_data.get("datasets", []))

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "resource_counts": {
                "models": model_count,
                "agents": agent_count,
                "datasets": dataset_count
            },
            "created_at": self.created_at.isoformat() if self.created_at else None
        }