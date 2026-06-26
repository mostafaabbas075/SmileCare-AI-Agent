"""
Document upload router.

Provides an endpoint for uploading knowledge base documents that will
be processed, chunked, and embedded into Qdrant for RAG retrieval.

The actual embedding pipeline is not implemented yet — this stub
validates the upload and stores document metadata.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.schemas.chat import DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["Knowledge Base"])
logger = structlog.get_logger(__name__)

ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a knowledge base document",
    description=(
        "Upload a file (Markdown, PDF, TXT, DOCX) to the clinic knowledge base. "
        "The document will be chunked, embedded, and indexed into Qdrant for RAG retrieval. "
        "Accepted MIME types: text/plain, text/markdown, application/pdf, DOCX."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload."),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Accept a document upload and queue it for RAG indexing.

    This is a stub — the embedding pipeline will be connected in a
    future development phase.
    """
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{content_type}'. "
                f"Allowed: {sorted(ALLOWED_CONTENT_TYPES)}"
            ),
        )

    filename = file.filename or "unknown"
    logger.info("document_upload_received", filename=filename, content_type=content_type)

    # TODO: Persist KnowledgeDocument metadata and enqueue embedding job
    # document = await knowledge_service.ingest_document(db, file)

    return DocumentUploadResponse(
        filename=filename,
        status="pending",
        message=(
            f"Document '{filename}' received and queued for indexing. "
            "It will be available in the knowledge base shortly."
        ),
    )
