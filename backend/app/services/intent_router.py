"""
Intent Router Service.

Intercepts incoming messages to bypass LLM calls for simple/predictable intents,
saving AI API quota and providing sub-second fast responses.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class RouterResult(NamedTuple):
    handled_by_backend: bool
    response_text: str | None
    action_type: str | None


class IntentRouter:
    """Fast pattern-based Intent Router to conserve LLM quota."""

    # أنماط التحيات
    GREETINGS_PATTERN = r"^(أهلا|أهلاً|اهل|اهلاً|مرحبا|مرحباً|سلام|السلام عليكم|صباح الخير|مساء الخير|أهلا وسهلا|مرحبتين|hi|hello|hey)$"
    
    # تم إزالة "ماشي"، "تمام"، "ok" من هنا حتى لا تقطع تسلسل الحجز إذا قالها المريض كاستجابة
    THANKS_PATTERN = r"^(شكرا|شكراً|تسلم|يعطيك العافية|شكرا جزيلا|شكراً جزيلاً|الف شكر|ألف شكر|ربنا يخليك|الله يسلمك|thanks|thank you)$"
    
    # خيارات التحكم المباشرة بالتعليمات
    VIEW_BOOKING_PATTERN = r"^(1|عرض|عرض الحجز|معرفة الحجز|حجوزاتي|مواعيدي)$"
    EDIT_BOOKING_PATTERN = r"^(2|تعديل|تعديل الحجز|تغيير الموعد|تأجيل الحجز)$"
    CANCEL_BOOKING_PATTERN = r"^(3|إلغاء|الغاء|إلغاء الحجز|الغاء الحجز|حذف الحجز)$"

    @classmethod
    def route_message(cls, message: str) -> RouterResult:
        msg = message.strip().lower()

        # 1. التحيات المباشرة
        if re.search(cls.GREETINGS_PATTERN, msg):
            return RouterResult(
                handled_by_backend=True,
                response_text="أهلاً بك في عيادة SmileCare! 🦷 كيف يمكنني مساعدتك اليوم؟ (يمكنك حجز موعد، استعراض حجوزاتك، أو الاستفسار عن خدماتنا).",
                action_type="GREETING"
            )

        # 2. الشكر المباشر
        if re.search(cls.THANKS_PATTERN, msg):
            return RouterResult(
                handled_by_backend=True,
                response_text="العفو، في خدمتك دائماً! إذا كان لديك أي استفسار طبي آخر أنا هنا للمساعدة. 😊",
                action_type="THANKS"
            )

        # 3. خيارات التحكم بالحجز
        if re.search(cls.VIEW_BOOKING_PATTERN, msg):
            return RouterResult(
                handled_by_backend=False,
                response_text=None,
                action_type="VIEW_BOOKING"
            )

        if re.search(cls.EDIT_BOOKING_PATTERN, msg):
            return RouterResult(
                handled_by_backend=False,
                response_text=None,
                action_type="EDIT_BOOKING"
            )

        if re.search(cls.CANCEL_BOOKING_PATTERN, msg):
            return RouterResult(
                handled_by_backend=False,
                response_text=None,
                action_type="CANCEL_BOOKING"
            )

        # تحويل للـ LLM للاستفسارات المعقدة أو عمليات الحجز
        return RouterResult(
            handled_by_backend=False,
            response_text=None,
            action_type="FORWARD_TO_LLM"
        )


intent_router = IntentRouter()