"""
KnowledgeDocument ORM model.

Tracks files uploaded to the RAG knowledge base. The actual vector
embeddings are stored in Qdrant; this table stores metadata and
processing status so the system can display indexing progress and
support re-indexing on demand.
"""

from __future__ import annotations

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import DocumentStatus
from app.database.base_model import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metadata record for a knowledge base document."""

    __tablename__ = "knowledge_documents"

    # ------------------------------------------------------------------
    # File identity
    # ------------------------------------------------------------------
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Original filename as uploaded.",
    )
    file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Path on disk relative to the knowledge_base/ directory.",
    )
    content_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="MIME type (e.g. text/markdown, application/pdf).",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Raw file size in bytes.",
    )

    # ------------------------------------------------------------------
    # Processing state
    # ------------------------------------------------------------------
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum"),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
    )
    chunk_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Number of text chunks generated from this document.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Populated when status=failed.",
    )

    # ------------------------------------------------------------------
    # Qdrant reference
    # ------------------------------------------------------------------
    qdrant_collection: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Qdrant collection name where vectors are stored.",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument id={self.id} filename='{self.filename}' status={self.status}>"
