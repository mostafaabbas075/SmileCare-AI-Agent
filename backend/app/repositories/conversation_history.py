"""
ConversationHistory repository.

Provides session-scoped conversation retrieval used by the AI agent
to reconstruct conversation context across HTTP requests.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_history import ConversationHistory
from app.repositories.base import BaseRepository


class ConversationHistoryRepository(BaseRepository[ConversationHistory]):
    """Data access layer for the conversation_history table."""

    model = ConversationHistory

    async def get_by_session(
        self,
        db: AsyncSession,
        session_id: str,
        *,
        limit: int = 50,
    ) -> list[ConversationHistory]:
        """Return the most recent messages for a session, oldest-first.

        Args:
            session_id: The client-generated session identifier.
            limit: Maximum number of messages to retrieve.
                   Keeping this bounded prevents unbounded context windows.
        """
        stmt = (
            select(ConversationHistory)
            .where(ConversationHistory.session_id == session_id)
            .order_by(ConversationHistory.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_patient(
        self,
        db: AsyncSession,
        patient_id: uuid.UUID,
        *,
        limit: int = 100,
    ) -> list[ConversationHistory]:
        """Return conversation history for a specific patient."""
        stmt = (
            select(ConversationHistory)
            .where(ConversationHistory.patient_id == patient_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> int:
        """Delete all messages in a session. Returns number of deleted rows."""
        messages = await self.get_by_session(db, session_id, limit=10_000)
        for message in messages:
            await db.delete(message)
        await db.flush()
        return len(messages)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
conversation_repository = ConversationHistoryRepository()
