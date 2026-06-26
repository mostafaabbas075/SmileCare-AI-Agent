"""
Chat Pydantic schemas.

Defines the request and response shapes for the AI agent chat endpoint.
Designed to be provider-agnostic — no Gemini-specific fields leak here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.constants import MessageRole
from app.schemas.common import AppBaseModel


class ChatMessage(AppBaseModel):
    """A single message in a chat request (mirrors OpenAI / Gemini conventions)."""

    role: MessageRole = Field(description="Speaker role: user, assistant, or system.")
    content: str = Field(min_length=1, max_length=4096, description="Message text.")


class ChatRequest(AppBaseModel):
    """Payload for POST /api/v1/chat."""

    session_id: str = Field(
        min_length=1,
        max_length=128,
        description="Client-generated UUID identifying the conversation session.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    message: str = Field(
        min_length=1,
        max_length=4096,
        description="The user's latest message.",
    )


class ChatResponse(AppBaseModel):
    """Response from POST /api/v1/chat."""

    session_id: str = Field(description="Echoed session ID.")
    message: str = Field(description="AI assistant reply.")
    role: MessageRole = Field(default=MessageRole.ASSISTANT)
    timestamp: datetime = Field(description="Server-side timestamp of the response.")


class DocumentUploadResponse(AppBaseModel):
    """Response from POST /api/v1/upload-document."""

    filename: str
    status: str = Field(description="Processing status: pending | indexed | failed.")
    message: str
