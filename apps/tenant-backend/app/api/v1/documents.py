"""
GT 2.0 Documents API - Wrapper for Files API

Provides document-centric interface that wraps the underlying files API.
This maintains the document abstraction for the frontend while leveraging
the existing file storage infrastructure.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from typing import Dict, Any, List, Optional

from app.core.security import get_current_user
from app.api.v1.files import (
    get_file_info,
    download_file,
    delete_file,
    list_files,
    get_document_summary as get_file_summary,
    upload_file
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=201)
@router.post("/", status_code=201)  # Support both with and without trailing slash
async def upload_document(
    file: UploadFile = File(...),
    dataset_id: Optional[str] = Form(None, description="Associate with dataset"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload document (proxy to files API) - accepts dataset_id from FormData"""
    try:
        logger.info(f"Document upload requested - file: {file.filename}, dataset_id: {dataset_id}")
        # Proxy to files upload endpoint with "documents" category
        return await upload_file(file, dataset_id, "documents", current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get document details (proxy to files API)"""
    try:
        # Proxy to files API - documents are stored as files
        return await get_file_info(document_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@router.get("/{document_id}/summary")
async def get_document_summary(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get AI-generated summary for a document (proxy to files API)"""
    try:
        # Proxy to files summary endpoint
        return await get_file_summary(document_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document summary generation failed for {document_id}: {e}")
        # Return a fallback response
        return {
            "summary": "Summary generation is currently unavailable. Please try again later.",
            "key_topics": [],
            "document_type": "unknown",
            "language": "en",
            "metadata": {}
        }


@router.get("")
async def list_documents(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List documents with optional filtering (proxy to files API)"""
    try:
        # Map documents request to files API
        # Documents are files in the "documents" category
        result = await list_files(
            dataset_id=dataset_id,
            category="documents",
            limit=limit,
            offset=offset,
            current_user=current_user
        )

        # Extract just the files array from the response object
        # The list_files endpoint returns {files: [...], total: N, limit: N, offset: N}
        # But frontend expects just the array
        if isinstance(result, dict) and 'files' in result:
            return result['files']
        elif isinstance(result, list):
            return result
        else:
            logger.warning(f"Unexpected response format from list_files: {type(result)}")
            return []

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete document and its metadata (proxy to files API)"""
    try:
        # Proxy to files delete endpoint
        return await delete_file(document_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Download document file (proxy to files API)"""
    try:
        # Proxy to files download endpoint
        return await download_file(document_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download document: {str(e)}")


@router.post("/{document_id}/process")
async def process_document(
    document_id: str,
    chunking_strategy: Optional[str] = Query("hybrid", description="Chunking strategy"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Trigger document processing (chunking and embedding generation)"""
    try:
        from app.services.document_processor import get_document_processor
        from app.core.user_resolver import resolve_user_uuid

        logger.info(f"Manual processing requested for document {document_id}")

        # Get user info
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get document processor
        processor = await get_document_processor(tenant_domain=tenant_domain)

        # Get document info to verify it exists and get metadata
        from app.services.postgresql_file_service import PostgreSQLFileService
        file_service = PostgreSQLFileService(tenant_domain=tenant_domain, user_id=user_uuid)

        try:
            doc_info = await file_service.get_file_info(document_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")

        # Trigger processing using the file service's processing method
        await file_service._process_document_from_database(
            processor=processor,
            document_id=document_id,
            dataset_id=doc_info.get("dataset_id"),
            user_uuid=user_uuid,
            filename=doc_info["original_filename"]
        )

        return {
            "status": "success",
            "message": "Document processing started",
            "document_id": document_id,
            "chunking_strategy": chunking_strategy
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.post("/processing-status")
async def get_processing_status(
    request: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get processing status for multiple documents"""
    try:
        from app.services.document_processor import get_document_processor
        from app.core.user_resolver import resolve_user_uuid

        # Get user info
        tenant_domain, user_email, user_uuid = await resolve_user_uuid(current_user)

        # Get document IDs from request
        document_ids = request.get("document_ids", [])
        if not document_ids:
            raise HTTPException(status_code=400, detail="document_ids required")

        # Get processor instance
        processor = await get_document_processor(tenant_domain=tenant_domain)

        # Get status for each document
        status_results = {}
        for doc_id in document_ids:
            try:
                status_info = await processor.get_processing_status(doc_id)
                status_results[doc_id] = {
                    "status": status_info["status"],
                    "error_message": status_info["error_message"],
                    "progress": status_info["processing_progress"],
                    "stage": status_info["processing_stage"],
                    "chunks_processed": status_info["chunks_processed"],
                    "total_chunks_expected": status_info["total_chunks_expected"]
                }
            except Exception as e:
                status_results[doc_id] = {
                    "status": "error",
                    "error_message": f"Failed to get status: {str(e)}",
                    "progress": 0,
                    "stage": "unknown"
                }

        return status_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get processing status: {str(e)}")