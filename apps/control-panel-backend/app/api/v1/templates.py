"""
GT 2.0 Tenant Templates API
Manage and apply tenant configuration templates
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models.tenant_template import TenantTemplate
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    tenant_id: int
    name: str
    description: str = ""


class ApplyTemplateRequest(BaseModel):
    template_id: int
    tenant_id: int


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    is_default: bool
    resource_counts: dict
    created_at: str


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db)
):
    """List all tenant templates"""
    result = await db.execute(select(TenantTemplate).order_by(TenantTemplate.name))
    templates = result.scalars().all()

    return [TemplateResponse(**template.get_summary()) for template in templates]


@router.get("/{template_id}")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get template details including full configuration"""
    template = await db.get(TenantTemplate, template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template.to_dict()


@router.post("/export")
async def export_template(
    request: CreateTemplateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Export existing tenant configuration as a new template"""
    try:
        service = TemplateService()
        template = await service.export_tenant_as_template(
            tenant_id=request.tenant_id,
            template_name=request.name,
            template_description=request.description,
            control_panel_db=db
        )

        return {
            "success": True,
            "message": f"Template '{request.name}' created successfully",
            "template": template.get_summary()
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export template: {str(e)}")


@router.post("/apply")
async def apply_template(
    request: ApplyTemplateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Apply a template to an existing tenant"""
    try:
        service = TemplateService()
        results = await service.apply_template(
            template_id=request.template_id,
            tenant_id=request.tenant_id,
            control_panel_db=db
        )

        return {
            "success": True,
            "message": "Template applied successfully",
            "results": results
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply template: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a template"""
    template = await db.get(TenantTemplate, template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.delete(template)
    await db.commit()

    return {
        "success": True,
        "message": f"Template '{template.name}' deleted successfully"
    }