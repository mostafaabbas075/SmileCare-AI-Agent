from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.constants import MessageRole

# استدعاء الـ Agent (الذي سنقوم بإنشائه في الخطوة التالية)
from app.agents.dental_agent import DentalAgent 

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the AI receptionist",
    description=(
        "Submit a patient message to the AI agent. The agent will respond "
        "based on the conversation history and the clinic knowledge base."
    ),
)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Process a patient message and return the AI agent's reply."""
    
    # تهيئة الـ Agent مع تمرير جلسة قاعدة البيانات
    agent = DentalAgent(db_session=db)
    
    # تشغيل الـ Agent للحصول على الرد
    response_text = await agent.run(
        message=body.message,
        session_id=body.session_id,
    )

    return ChatResponse(
        session_id=body.session_id,
        message=response_text,
        role=MessageRole.ASSISTANT,
        timestamp=datetime.now(UTC),
    )