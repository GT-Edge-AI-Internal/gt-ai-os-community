"""
Agent template library API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.core.security import capability_validator, CapabilityToken
from app.api.auth import verify_capability

router = APIRouter()
logger = logging.getLogger(__name__)


class TemplateResponse(BaseModel):
    """Agent template response"""
    template_id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: str = Field(..., description="Template category")
    configuration: Dict[str, Any] = Field(..., description="Template configuration")


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    token: CapabilityToken = Depends(verify_capability)
) -> List[TemplateResponse]:
    """List available agent templates"""
    
    # Template library with predefined agent configurations
    templates = [
        TemplateResponse(
            template_id="research_assistant",
            name="Research & Analysis Agent",
            description="Specialized in information synthesis and analysis",
            category="research",
            configuration={
                "model": "llama-3.1-70b-versatile",
                "temperature": 0.7,
                "capabilities": ["llm:groq", "rag:semantic_search", "tools:web_search"]
            }
        ),
        TemplateResponse(
            template_id="coding_assistant",
            name="Software Development Agent",
            description="Focused on code quality and best practices",
            category="development",
            configuration={
                "model": "llama-3.1-70b-versatile",
                "temperature": 0.3,
                "capabilities": ["llm:groq", "tools:github_integration", "resources:documentation"]
            }
        )
    ]
    
    return templates


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    token: CapabilityToken = Depends(verify_capability)
) -> TemplateResponse:
    """Get specific agent template"""
    
    try:
        # Template library - in production this would be stored in database/filesystem
        templates = {
            "research_assistant": TemplateResponse(
                template_id="research_assistant",
                name="Research & Analysis Agent",
                description="Specialized in information synthesis and analysis",
                category="research",
                configuration={
                    "model": "llama-3.1-70b-versatile",
                    "temperature": 0.7,
                    "capabilities": ["llm:groq", "rag:semantic_search", "tools:web_search"],
                    "system_prompt": "You are a research agent focused on thorough analysis and information synthesis.",
                    "max_tokens": 4000,
                    "tools": ["web_search", "document_analysis", "citation_formatter"]
                }
            ),
            "coding_assistant": TemplateResponse(
                template_id="coding_assistant",
                name="Software Development Agent",
                description="Focused on code quality and best practices",
                category="development",
                configuration={
                    "model": "llama-3.1-70b-versatile",
                    "temperature": 0.3,
                    "capabilities": ["llm:groq", "tools:github_integration", "resources:documentation"],
                    "system_prompt": "You are a senior software engineer focused on code quality, best practices, and clean architecture.",
                    "max_tokens": 4000,
                    "tools": ["code_analysis", "github_integration", "documentation_generator"]
                }
            ),
            "creative_writing": TemplateResponse(
                template_id="creative_writing",
                name="Creative Writing Agent",
                description="Specialized in creative content generation",
                category="creative",
                configuration={
                    "model": "llama-3.1-70b-versatile",
                    "temperature": 0.9,
                    "capabilities": ["llm:groq", "tools:style_guide"],
                    "system_prompt": "You are a creative writing agent focused on engaging, original content.",
                    "max_tokens": 4000,
                    "tools": ["style_analyzer", "plot_generator", "character_development"]
                }
            )
        }
        
        template = templates.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Template retrieval failed: {str(e)}")