from __future__ import annotations

import re
import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select

from app.agents.dental_agent import DentalAgent
from app.database.base import AsyncSessionFactory
from app.models.clinic import Clinic
from app.models.conversation_history import ConversationHistory

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

WHATSAPP_VERIFY_TOKEN = "smilecare_whatsapp_secret_token_2026"


# ── Schemas ──────────────────────────────────────────────────────────────────


class ManualMessageRequest(BaseModel):
    phone_number: str
    message: str
    clinic_slug: str = "white"


class ToggleAIRequest(BaseModel):
    phone_number: str
    is_paused: bool
    clinic_slug: str = "white"


# ── Helper: Format Text for WhatsApp ─────────────────────────────────────────


def format_text_for_whatsapp(text: str) -> str:
    """تحويل علامات Markdown العامة إلى صيغة واتساب المقروءة:

    - استبدال **نص عريض** بـ *نص عريض*
    - إزالة علامات العناوين ###
    """
    if not text:
        return ""
    # تحويل النجوم المزدوجة إلى نجمة واحدة للخط العريض في واتساب
    formatted = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    # تحويل الخط المائل المزدوج إن وجد
    formatted = re.sub(r"__(.*?)__", r"_\1_", formatted)
    # إزالة علامات العناوين Markdown من بداية الأسطر
    formatted = re.sub(r"^#{1,6}\s*", "", formatted, flags=re.MULTILINE)
    return formatted.strip()


# ── Webhook Verification & Receiving ─────────────────────────────────────────


@router.get("/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """التحقق الأولي من ملكية الـ Webhook مع Meta."""
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("whatsapp_webhook_verified")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=403)


@router.post("/webhook")
async def receive_whatsapp_message(request: Request):
    """استقبال رسائل المرضى، حفظها، والرد بالذكاء الاصطناعي إذا لم يتم إيقافه."""
    payload = await request.json()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            val = change.get("value", {})
            metadata = val.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")

            messages = val.get("messages", [])
            if not messages:
                continue

            msg = messages[0]
            if msg.get("type") != "text":
                continue

            sender_phone = str(msg.get("from"))
            user_text = msg.get("text", {}).get("body", "").strip()

            if not user_text or not phone_number_id:
                continue

            async with AsyncSessionFactory() as db:
                # 1. مطابقة العيادة بالرقم أو اختيار عيادة white
                stmt = (
                    select(Clinic)
                    .where(
                        Clinic.is_active.is_(True),
                        or_(
                            Clinic.settings["whatsapp_phone_number_id"].astext
                            == str(phone_number_id),
                            Clinic.slug == "white",
                        ),
                    )
                    .order_by(
                        (
                            Clinic.settings["whatsapp_phone_number_id"].astext
                            == str(phone_number_id)
                        ).desc()
                    )
                    .limit(1)
                )

                res = await db.execute(stmt)
                clinic = res.scalar_one_or_none()

                if not clinic:
                    logger.warning(
                        "clinic_not_found", phone_number_id=phone_number_id
                    )
                    continue

                clinic_settings = clinic.settings or {}
                access_token = clinic_settings.get("whatsapp_access_token")
                session_key = f"wa_{sender_phone}"

                # 2. تسجيل رسالة المريض الواردة في السجل
                user_msg_entry = ConversationHistory(
                    session_id=session_key,
                    role="user",
                    content=user_text,
                )
                db.add(user_msg_entry)
                await db.commit()

                # 3. التحقق هل الـ AI متوقف يدوياً لهذه المحادثة
                paused_numbers = clinic_settings.get("paused_ai_numbers", [])
                if sender_phone in paused_numbers:
                    logger.info(
                        "ai_reply_skipped_manual_mode", phone=sender_phone
                    )
                    continue

                if not access_token:
                    logger.warning(
                        "missing_whatsapp_access_token", clinic_slug=clinic.slug
                    )
                    continue

                # 4. تشغيل الـ AI Agent
                agent = DentalAgent(db_session=db, clinic_id=clinic.id)
                ai_reply = await agent.run(
                    message=user_text,
                    session_id=session_key,
                    clinic_id=clinic.id,
                )

                # 5. حفظ رد الـ AI في السجل
                ai_msg_entry = ConversationHistory(
                    session_id=session_key,
                    role="assistant",
                    content=ai_reply,
                )
                db.add(ai_msg_entry)
                await db.commit()

                # 6. إرسال الرد للمريض على واتساب بتنسيق نظيف
                await send_whatsapp_message(
                    phone_number_id=str(phone_number_id),
                    recipient_phone=sender_phone,
                    message_text=ai_reply,
                    access_token=access_token,
                )

    return {"status": "success"}


# ── Dashboard Chat Management Endpoints ─────────────────────────────────────


@router.get("/chats/recent")
async def get_recent_conversations(clinic_slug: str = "white"):
    """جلب قائمة بآخر المحادثات المفتوحة مع المرضى وحالة الـ AI."""
    async with AsyncSessionFactory() as db:
        stmt = select(Clinic).where(Clinic.slug == clinic_slug).limit(1)
        res = await db.execute(stmt)
        clinic = res.scalar_one_or_none()
        if not clinic:
            return {"conversations": []}

        paused_numbers = (clinic.settings or {}).get("paused_ai_numbers", [])

        query = (
            select(
                ConversationHistory.session_id,
                func.max(ConversationHistory.created_at).label("last_activity"),
            )
            .where(ConversationHistory.session_id.like("wa_%"))
            .group_by(ConversationHistory.session_id)
            .order_by(desc("last_activity"))
            .limit(50)
        )

        chats = (await db.execute(query)).all()
        result = []
        for chat in chats:
            phone = chat.session_id.replace("wa_", "")
            result.append(
                {
                    "session_id": chat.session_id,
                    "phone_number": phone,
                    "last_activity": (
                        chat.last_activity.isoformat()
                        if chat.last_activity
                        else None
                    ),
                    "is_ai_paused": phone in paused_numbers,
                }
            )

        return {"conversations": result}


@router.get("/chats/{phone_number}/messages")
async def get_chat_history(phone_number: str):
    """جلب سجل الرسائل بالكامل لمحادثة معينة."""
    session_id = (
        f"wa_{phone_number}"
        if not phone_number.startswith("wa_")
        else phone_number
    )

    async with AsyncSessionFactory() as db:
        stmt = (
            select(ConversationHistory)
            .where(ConversationHistory.session_id == session_id)
            .order_by(ConversationHistory.created_at.asc())
        )
        res = await db.execute(stmt)
        messages = res.scalars().all()

        return {
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "created_at": (
                        m.created_at.isoformat() if m.created_at else None
                    ),
                }
                for m in messages
            ]
        }


@router.post("/chats/send-manual")
async def send_manual_message(req: ManualMessageRequest):
    """إرسال رسالة يدوية من موظف العيادة مباشرة إلى واتساب وتخزينها في السجل."""
    async with AsyncSessionFactory() as db:
        stmt = (
            select(Clinic)
            .where(
                Clinic.is_active.is_(True),
                or_(
                    Clinic.slug == req.clinic_slug,
                    Clinic.slug == "white",
                ),
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        clinic = res.scalar_one_or_none()

        if not clinic:
            raise HTTPException(status_code=404, detail="Clinic not found")

        clinic_settings = clinic.settings or {}
        access_token = clinic_settings.get("whatsapp_access_token")
        phone_id = clinic_settings.get("whatsapp_phone_number_id")

        if not access_token or not phone_id:
            raise HTTPException(
                status_code=400, detail="Missing WhatsApp credentials"
            )

        # 1. إرسال الرسالة للمريض على واتساب
        await send_whatsapp_message(
            phone_number_id=str(phone_id),
            recipient_phone=req.phone_number,
            message_text=req.message,
            access_token=access_token,
        )

        # 2. تسجيل رسالة الموظف في قاعدة البيانات
        session_id = f"wa_{req.phone_number}"
        staff_entry = ConversationHistory(
            session_id=session_id,
            role="staff",
            content=req.message,
        )
        db.add(staff_entry)
        await db.commit()

        return {"status": "success", "message": "Sent successfully"}


@router.post("/chats/toggle-ai")
async def toggle_ai_mode(req: ToggleAIRequest):
    """إيقاف أو تفعيل الرد التلقائي للـ AI لمحادثة معينة."""
    async with AsyncSessionFactory() as db:
        stmt = (
            select(Clinic)
            .where(
                Clinic.is_active.is_(True),
                or_(
                    Clinic.slug == req.clinic_slug,
                    Clinic.slug == "white",
                ),
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        clinic = res.scalar_one_or_none()

        if not clinic:
            raise HTTPException(status_code=404, detail="Clinic not found")

        settings_dict = dict(clinic.settings or {})
        paused_list = set(settings_dict.get("paused_ai_numbers", []))

        if req.is_paused:
            paused_list.add(req.phone_number)
        else:
            paused_list.discard(req.phone_number)

        settings_dict["paused_ai_numbers"] = list(paused_list)
        clinic.settings = settings_dict
        await db.commit()

        return {"status": "success", "is_paused": req.is_paused}


# ── Meta API Helper ──────────────────────────────────────────────────────────


async def send_whatsapp_message(
    phone_number_id: str,
    recipient_phone: str,
    message_text: str,
    access_token: str,
):
    """إرسال الرسالة مع ضبط التنسيق ليتوافق مع واتساب."""
    clean_text = format_text_for_whatsapp(message_text)

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": clean_text},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                logger.info(
                    "whatsapp_message_sent",
                    to=recipient_phone,
                    phone_number_id=phone_number_id,
                )
            else:
                logger.error(
                    "whatsapp_send_failed",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
    except Exception as exc:
        logger.exception("whatsapp_api_request_exception", error=str(exc))