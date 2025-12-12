"""
GT 2.0 Files API - PostgreSQL File Storage

Provides file upload, download, and management using PostgreSQL unified storage.
Replaces MinIO integration with PostgreSQL 3-tier storage strategy.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Query, Form
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, List, Optional

from app.core.security import get_current_user
from app.core.user_resolver import resolve_user_uuid
from app.core.response_filter import ResponseFilter
from app.core.permissions import get_user_role, is_effective_owner
from app.core.postgresql_client import get_postgresql_client
from app.services.postgresql_file_service import PostgreSQLFileService
from app.services.document_summarizer import DocumentSummarizer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    dataset_id: Optional[str] = Form(None, description="Associate with dataset"),
    category: str = Form("documents", description="File category"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload file using PostgreSQL storage"""
    try:
        logger.info(f"File upload started: {file.filename}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
        logger.info(f"Current user: {current_user}")
        logger.info(f"Dataset ID: {dataset_id}, Category: {category}")

        if not file.filename:
            logger.error("No filename provided in upload request")
            raise HTTPException(status_code=400, detail="No filename provided")

        # Get file service with proper UUID resolution
        tenant_domain = current_user.get('tenant_domain', 'test-company')
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)
        logger.info(f"Creating file service for tenant: {tenant_domain}, user: {user_email} (UUID: {user_uuid})")

        # Get user role for permission checks
        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid,
            user_role=user_role
        )

        # Store file
        logger.info(f"Storing file: {file.filename}")
        result = await file_service.store_file(
            file=file,
            dataset_id=dataset_id,
            category=category
        )

        logger.info(f"File uploaded successfully: {file.filename} -> {result['id']}")
        return result

    except Exception as e:
        logger.error(f"File upload failed for {file.filename if file and file.filename else 'unknown'}: {e}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Current user context: {current_user}")
        raise HTTPException(status_code=500, detail="Failed to upload file")


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Download file by ID with streaming support"""
    try:
        # Get file service with proper UUID resolution
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get user role for permission checks
        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid,
            user_role=user_role
        )
        
        # Get file info first
        file_info = await file_service.get_file_info(file_id)
        
        # Stream file content
        file_stream = file_service.get_file(file_id)
        
        return StreamingResponse(
            file_stream,
            media_type=file_info['content_type'],
            headers={
                "Content-Disposition": f"attachment; filename=\"{file_info['original_filename']}\"",
                "Content-Length": str(file_info['file_size'])
            }
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"File download failed for {file_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{file_id}/info")
async def get_file_info(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get file metadata"""
    try:
        # Get file service with proper UUID resolution
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get user role for permission checks
        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid,
            user_role=user_role
        )
        
        file_info = await file_service.get_file_info(file_id)

        # Apply security filtering using effective ownership
        from app.core.postgresql_client import get_postgresql_client
        from app.core.permissions import get_user_role, is_effective_owner

        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)
        is_owner = is_effective_owner(file_info.get("user_id"), user_uuid, user_role)

        filtered_info = ResponseFilter.filter_file_response(
            file_info,
            is_owner=is_owner
        )

        return filtered_info
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Get file info failed for {file_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_files(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    category: str = Query("documents", description="Filter by category"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List user files with filtering"""
    try:
        # Get file service with proper UUID resolution
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get user role for permission checks
        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid,
            user_role=user_role
        )
        
        files = await file_service.list_files(
            dataset_id=dataset_id,
            category=category,
            limit=limit,
            offset=offset
        )

        # Apply security filtering to file list using effective ownership
        filtered_files = []
        for file_info in files:
            is_owner = is_effective_owner(file_info.get("user_id"), user_uuid, user_role)
            filtered_file = ResponseFilter.filter_file_response(
                file_info,
                is_owner=is_owner
            )
            filtered_files.append(filtered_file)

        return {
            "files": filtered_files,
            "total": len(filtered_files),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"List files failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete file and its metadata"""
    try:
        # Get file service with proper UUID resolution
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get user role for permission checks
        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid,
            user_role=user_role
        )
        
        success = await file_service.delete_file(file_id)
        
        if success:
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="File not found or delete failed")
        
    except Exception as e:
        logger.error(f"Delete file failed for {file_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cleanup")
async def cleanup_orphaned_files(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Clean up orphaned files (admin operation)"""
    try:
        # Only allow admin users to run cleanup
        user_roles = current_user.get('roles', [])
        if 'admin' not in user_roles:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get file service with proper UUID resolution
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get user role for permission checks
        pg_client = await get_postgresql_client()
        user_role = await get_user_role(pg_client, user_email, tenant_domain)

        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid,
            user_role=user_role
        )
        
        cleanup_count = await file_service.cleanup_orphaned_files()
        
        return {
            "message": f"Cleaned up {cleanup_count} orphaned files",
            "count": cleanup_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{file_id}/summary")
async def get_document_summary(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get AI-generated summary for a document"""
    try:
        # Get file service with proper UUID resolution
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get file service to retrieve document content
        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=user_uuid
        )

        # Get file info
        file_info = await file_service.get_file_info(file_id)

        # Initialize summarizer
        summarizer = DocumentSummarizer()

        # Get file content (for text files)
        # Note: This assumes text content is available
        # In production, you'd need to extract text from PDFs, etc.
        file_stream = file_service.get_file(file_id)
        content = ""
        async for chunk in file_stream:
            content += chunk.decode('utf-8', errors='ignore')

        # Generate summary
        summary_result = await summarizer.generate_document_summary(
            document_id=file_id,
            content=content[:summarizer.max_content_length],  # Truncate if too long
            filename=file_info['original_filename'],
            tenant_domain=tenant_domain,
            user_id=user_id
        )

        # codeql[py/stack-trace-exposure] returns document summary dict, not error details
        return {
            "summary": summary_result.get("summary", "No summary available"),
            "key_topics": summary_result.get("key_topics", []),
            "document_type": summary_result.get("document_type"),
            "language": summary_result.get("language", "en"),
            "metadata": summary_result.get("metadata", {})
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Document summary generation failed for {file_id}: {e}", exc_info=True)
        # Return a fallback response instead of failing completely
        return {
            "summary": "Summary generation is currently unavailable. Please try again later.",
            "key_topics": [],
            "document_type": "unknown",
            "language": "en",
            "metadata": {}
        }