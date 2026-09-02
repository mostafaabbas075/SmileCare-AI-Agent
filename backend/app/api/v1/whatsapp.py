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


# ── Helpers ──────────────────────────────────────────────────────────────────


def format_text_for_whatsapp(text: str) -> str:
    """تحويل علامات Markdown العامة إلى صيغة واتساب المقروءة."""
    if not text:
        return ""
    formatted = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    formatted = re.sub(r"__(.*?)__", r"_\1_", formatted)
    formatted = re.sub(r"^#{1,6}\s*", "", formatted, flags=re.MULTILINE)
    return formatted.strip()


def clean_phone_number(phone: str) -> str:
    """تنظيف رقم الهاتف من أي إضافات مثل wa_ أو علامة + أو مسافات."""
    return re.sub(r"\D", "", phone.replace("wa_", "").strip())


async def send_typing_and_read_indicator(
    phone_number_id: str,
    message_id: str,
    access_token: str,
):
    """إرسال علامة القراءة الزرقاء ومؤشر الثلاث نقاط المتحركة (يكتب الآن... / Typing Indicator)."""
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        },
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                logger.info("typing_indicator_and_read_sent", msg_id=message_id)
            else:
                # محاولة بديلة في حالة الـ fallback
                fallback = {
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id,
                }
                await client.post(url, headers=headers, json=fallback)
    except Exception as exc:
        logger.debug("typing_indicator_exception", error=str(exc))


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
    """استقبال رسائل المرضى، تشغيل علامة الصح ومؤشر الكتابة فوراً، والرد بالـ AI."""
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

            msg_id = msg.get("id")
            raw_phone = str(msg.get("from"))
            sender_phone = clean_phone_number(raw_phone)
            user_text = msg.get("text", {}).get("body", "").strip()

            if not user_text or not phone_number_id:
                continue

            async with AsyncSessionFactory() as db:
                # 1. مطابقة العيادة
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
                    logger.warning("clinic_not_found", phone_number_id=phone_number_id)
                    continue

                clinic_settings = clinic.settings or {}
                access_token = clinic_settings.get("whatsapp_access_token")
                session_key = f"wa_{sender_phone}"

                # 2. إرسال علامة القراءة وتشغيل حركة الـ Typing (الثلاث نقاط) فوراً للمريض
                if msg_id and access_token:
                    await send_typing_and_read_indicator(str(phone_number_id), msg_id, access_token)

                # 3. تسجيل رسالة المريض في السجل
                user_msg_entry = ConversationHistory(
                    session_id=session_key,
                    role="user",
                    content=user_text,
                )
                db.add(user_msg_entry)
                await db.commit()

                # 4. التحقق هل الـ AI متوقف يدوياً لهذه المحادثة
                paused_numbers = clinic_settings.get("paused_ai_numbers", [])
                if sender_phone in paused_numbers or raw_phone in paused_numbers:
                    logger.info("ai_reply_skipped_manual_mode", phone=sender_phone)
                    continue

                if not access_token:
                    logger.warning("missing_whatsapp_access_token", clinic_slug=clinic.slug)
                    continue

                # 5. تشغيل الـ AI Agent
                agent = DentalAgent(db_session=db, clinic_id=clinic.id)
                ai_reply = await agent.run(
                    message=user_text,
                    session_id=session_key,
                    clinic_id=clinic.id,
                    patient_phone=sender_phone,
                )

                # 6. حفظ رد الـ AI في السجل
                ai_msg_entry = ConversationHistory(
                    session_id=session_key,
                    role="assistant",
                    content=ai_reply,
                )
                db.add(ai_msg_entry)
                await db.commit()

                # 7. إرسال الرد للمريض على واتساب
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
        stmt = (
            select(Clinic)
            .where(
                Clinic.is_active.is_(True),
                or_(Clinic.slug == clinic_slug, Clinic.slug == "white"),
            )
            .order_by((Clinic.slug == clinic_slug).desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        clinic = res.scalar_one_or_none()

        paused_numbers = (
            (clinic.settings or {}).get("paused_ai_numbers", [])
            if clinic
            else []
        )

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
            phone = clean_phone_number(chat.session_id)
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
    """جلب سجل الرسائل بالكامل وتحديد رسائل الموظف تلقائياً."""
    clean_phone = clean_phone_number(phone_number)
    session_id = f"wa_{clean_phone}"

    async with AsyncSessionFactory() as db:
        stmt = (
            select(ConversationHistory)
            .where(
                or_(
                    ConversationHistory.session_id == session_id,
                    ConversationHistory.session_id == f"wa_{phone_number}",
                    ConversationHistory.session_id == phone_number,
                )
            )
            .order_by(ConversationHistory.created_at.asc())
        )
        res = await db.execute(stmt)
        messages = res.scalars().all()

        formatted_messages = []
        for m in messages:
            role = m.role
            content = m.content or ""

            if role == "assistant" and content.startswith("[موظف العيادة]:"):
                role = "staff"
                content = content.replace("[موظف العيادة]:", "").strip()

            formatted_messages.append(
                {
                    "id": str(m.id),
                    "role": role,
                    "content": content,
                    "created_at": (
                        m.created_at.isoformat() if m.created_at else None
                    ),
                }
            )

        return {"messages": formatted_messages}


@router.post("/chats/send-manual")
async def send_manual_message(req: ManualMessageRequest):
    """إرسال رسالة يدوية من موظف العيادة وتخزينها بأمان كـ assistant مع الوسم."""
    clean_phone = clean_phone_number(req.phone_number)
    if not clean_phone or not req.message.strip():
        raise HTTPException(status_code=400, detail="Invalid phone or message")

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
            .order_by(
                (Clinic.slug == req.clinic_slug).desc(),
                (
                    Clinic.settings["whatsapp_access_token"].is_not(None)
                ).desc(),
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

        # 1. إرسال الرسالة إلى واتساب المريض
        is_sent = await send_whatsapp_message(
            phone_number_id=str(phone_id),
            recipient_phone=clean_phone,
            message_text=req.message,
            access_token=access_token,
        )

        if not is_sent:
            raise HTTPException(
                status_code=502, detail="Failed to send message via WhatsApp"
            )

        # 2. الحفظ المباشر في قاعدة البيانات
        session_id = f"wa_{clean_phone}"
        staff_entry = ConversationHistory(
            session_id=session_id,
            role="assistant",
            content=f"[موظف العيادة]: {req.message.strip()}",
        )
        db.add(staff_entry)
        await db.commit()

        return {"status": "success", "message": "Sent successfully"}


@router.post("/chats/toggle-ai")
async def toggle_ai_mode(req: ToggleAIRequest):
    """إيقاف أو تفعيل الرد التلقائي للـ AI لمحادثة معينة."""
    clean_phone = clean_phone_number(req.phone_number)

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
            .order_by((Clinic.slug == req.clinic_slug).desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        clinic = res.scalar_one_or_none()

        if not clinic:
            raise HTTPException(status_code=404, detail="Clinic not found")

        settings_dict = dict(clinic.settings or {})
        paused_list = set(settings_dict.get("paused_ai_numbers", []))

        if req.is_paused:
            paused_list.add(clean_phone)
        else:
            paused_list.discard(clean_phone)

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
) -> bool:
    """إرسال الرسالة مع ضبط التنسيق ليتوافق مع واتساب وإرجاع حالة النجاح."""
    clean_text = format_text_for_whatsapp(message_text)
    clean_recipient = clean_phone_number(recipient_phone)

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_recipient,
        "type": "text",
        "text": {"body": clean_text},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                logger.info(
                    "whatsapp_message_sent",
                    to=clean_recipient,
                    phone_number_id=phone_number_id,
                )
                return True
            else:
                logger.error(
                    "whatsapp_send_failed",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )
                return False
    except Exception as exc:
        logger.exception("whatsapp_api_request_exception", error=str(exc))
        return False