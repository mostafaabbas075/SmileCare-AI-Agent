from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import or_, select

from app.agents.dental_agent import DentalAgent
from app.database.base import AsyncSessionFactory
from app.models.clinic import Clinic

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])

# كود التحقق السري المشترك مع Meta
WHATSAPP_VERIFY_TOKEN = "smilecare_whatsapp_secret_token_2026"


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
    """استقبال رسائل المرضى القادمة من واتساب وتوجيهها ديناميكياً للعيادة المناسبة."""
    payload = await request.json()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            val = change.get("value", {})
            metadata = val.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")

            # استخراج الرسائل وتجاهل التحديثات الأخرى
            messages = val.get("messages", [])
            if not messages:
                continue

            msg = messages[0]
            if msg.get("type") != "text":
                continue

            sender_phone = msg.get("from")
            user_text = msg.get("text", {}).get("body", "").strip()

            if not user_text or not phone_number_id:
                continue

            async with AsyncSessionFactory() as db:
                # 1. البحث الديناميكي: مطابقة phone_number_id أو السقوط على عيادة white
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
                        "clinic_not_found_for_phone_id",
                        phone_number_id=phone_number_id,
                    )
                    continue

                clinic_settings = clinic.settings or {}
                access_token = clinic_settings.get("whatsapp_access_token")

                if not access_token:
                    logger.warning(
                        "missing_whatsapp_access_token",
                        clinic_slug=clinic.slug,
                        phone_number_id=phone_number_id,
                    )
                    continue

                # 2. تشغيل وكيل الذكاء الاصطناعي الخاص بالعيادة
                agent = DentalAgent(db_session=db, clinic_id=clinic.id)
                session_key = f"wa_{sender_phone}"

                ai_reply = await agent.run(
                    message=user_text,
                    session_id=session_key,
                    clinic_id=clinic.id,
                )

                # 3. إرسال الرد الفوري إلى المريض
                await send_whatsapp_message(
                    phone_number_id=str(phone_number_id),
                    recipient_phone=str(sender_phone),
                    message_text=ai_reply,
                    access_token=access_token,
                )

    return {"status": "success"}


async def send_whatsapp_message(
    phone_number_id: str,
    recipient_phone: str,
    message_text: str,
    access_token: str,
):
    """إرسال رد الذكاء الاصطناعي عبر Meta Graph API."""
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": message_text},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                logger.info(
                    "whatsapp_reply_sent_successfully",
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