"""
GT 2.0 Tenant Backend Models

Database models for tenant-specific data with perfect isolation.
Each tenant has their own SQLite database with these models.
"""

from .agent import Agent  # Complete migration - only Agent class
from .conversation import Conversation
from .message import Message
from .document import Document, RAGDataset, DatasetDocument, DocumentChunk
from .user_session import UserSession
from .workflow import (
    Workflow, 
    WorkflowExecution, 
    WorkflowTrigger, 
    WorkflowSession, 
    WorkflowMessage,
    WorkflowStatus,
    TriggerType,
    InteractionMode
)

__all__ = [
    "Agent",
    "Conversation",
    "Message", 
    "Document",
    "RAGDataset",
    "DatasetDocument",
    "DocumentChunk",
    "UserSession",
    "Workflow",
    "WorkflowExecution", 
    "WorkflowTrigger", 
    "WorkflowSession", 
    "WorkflowMessage",
    "WorkflowStatus",
    "TriggerType",
    "InteractionMode",
]