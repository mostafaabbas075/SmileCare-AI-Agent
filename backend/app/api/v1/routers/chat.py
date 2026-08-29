"""
Multi-Tenant Chat Router for Virtual Receptionist AI Agent (Strict Production Mode).

Handles incoming patient messages, strictly isolates clinic context,
enforces zero-token quota leaks for non-existent/deleted clinics,
and logs token usage and audit analytics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.dental_agent import DentalAgent
from app.core.constants import MessageRole
from app.dependencies.database import get_db
from app.models.ai_usage import AIUsageLog
from app.models.clinic import Clinic
from app.schemas.chat import ChatRequest, ChatResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


async def resolve_active_clinic(
    request: Request,
    body: ChatRequest,
    db: AsyncSession,
    clinic_param: str | None = None,
    clinic_slug_param: str | None = None,
    clinic_id_param: str | None = None,
) -> Clinic | None:
    """
    استنتاج والتحقق من وجود العيادة ونشاطها (is_active == True) بالترتيب:
    1. فحص معرف UUID المباشر (Header أو Query Param أو Body).
    2. فحص معرف الرابط Slug (Header أو Query Param أو Body).
    """
    # 1. فحص UUID المباشر
    raw_id = (
        request.headers.get("x-clinic-id")
        or clinic_id_param
        or request.query_params.get("clinic_id")
        or getattr(body, "clinic_id", None)
    )
    if raw_id:
        try:
            parsed_id = uuid.UUID(str(raw_id).strip())
            stmt = select(Clinic).where(Clinic.id == parsed_id, Clinic.is_active == True)
            res = await db.execute(stmt)
            clinic = res.scalar_one_or_none()
            if clinic:
                return clinic
        except (ValueError, TypeError):
            pass

    # 2. فحص Slug العيادة
    slug = (
        request.headers.get("x-clinic-slug")
        or clinic_param
        or clinic_slug_param
        or request.query_params.get("clinic")
        or request.query_params.get("clinic_slug")
        or getattr(body, "clinic_slug", None)
    )

    if slug:
        stmt = select(Clinic).where(
            Clinic.slug == slug.strip().lower(),
            Clinic.is_active == True,
        )
        res = await db.execute(stmt)
        clinic = res.scalar_one_or_none()
        if clinic:
            return clinic

    return None


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the Multi-Tenant AI receptionist",
    description=(
        "Submit a patient message to the AI agent. The agent will respond "
        "based on the specific clinic's pricing, schedule, offers, and knowledge base."
    ),
)
async def chat(
    request: Request,
    body: ChatRequest,
    clinic: str | None = Query(None, description="Clinic unique slug (?clinic=al-nour)"),
    clinic_slug: str | None = Query(None, description="Clinic unique slug alias (?clinic_slug=al-nour)"),
    clinic_id: str | None = Query(None, description="Clinic UUID identifier"),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Process a patient message with Strict Tenant Isolation, Cost Guards, and Audit Logging."""

    # 1. جلب بيانات العيادة والتأكد من أنها نشطة
    target_clinic = await resolve_active_clinic(
        request=request,
        body=body,
        db=db,
        clinic_param=clinic,
        clinic_slug_param=clinic_slug,
        clinic_id_param=clinic_id,
    )

    # 2. ⛔ حماية التوكنز: رفض الطلب فوراً بـ 404 إذا كانت العيادة محذوفة أو غير موجودة
    if not target_clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="العيادة المطلوبة غير مسجلة بالنظام أو تم إيقاف الخدمة لها.",
        )

    # حفظ القيم الأساسية كمتغيرات ثابتة لتجنب مشاكل انتهاء صلاحية الكائن بعد الـ commit
    current_clinic_id = target_clinic.id
    current_clinic_slug = target_clinic.slug

    # 3. تسجيل طلب الشات في الـ Audit Trail
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    logger.info(
        "audit_chat_request",
        clinic_id=str(current_clinic_id),
        clinic_slug=current_clinic_slug,
        session_id=body.session_id,
        ip_address=client_ip,
        user_agent=user_agent,
        action="CHAT_INPUT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    # 4. تهيئة وتشغيل الـ Agent مع ربطه الحصري بالعيادة
    agent = DentalAgent(
        db_session=db,
        clinic_id=current_clinic_id,
        clinic_slug=current_clinic_slug,
    )

    response_text = await agent.run(
        message=body.message,
        session_id=body.session_id,
        clinic_id=current_clinic_id,
        clinic_slug=current_clinic_slug,
    )

    # 5. تسجيل استجابة النظام في الـ Audit Trail بأمان
    logger.info(
        "audit_chat_response",
        clinic_id=str(current_clinic_id),
        clinic_slug=current_clinic_slug,
        session_id=body.session_id,
        ip_address=client_ip,
        user_agent=user_agent,
        action="CHAT_OUTPUT",
        timestamp=datetime.now(UTC).isoformat(),
    )

    # 6. تسجيل استهلاك التوكنز والتكلفة لحساب العيادة
    try:
        approx_tokens = int((len(body.message) + len(response_text)) * 0.7)
        approx_cost = (approx_tokens / 1000) * 0.000075

        usage_record = AIUsageLog(
            clinic_id=current_clinic_id,
            session_id=body.session_id,
            message_length=len(body.message),
            response_length=len(response_text),
            estimated_tokens=approx_tokens,
            cost_usd=round(approx_cost, 6),
        )
        db.add(usage_record)
        await db.commit()
    except Exception as e:
        logger.warning(
            "ai_usage_logging_failed",
            error=str(e),
            clinic_id=str(current_clinic_id),
        )

    return ChatResponse(
        session_id=body.session_id,
        message=response_text,
        role=MessageRole.ASSISTANT,
        clinic_slug=current_clinic_slug,
        timestamp=datetime.now(UTC),
    )