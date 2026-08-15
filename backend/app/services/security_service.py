"""
Security & Guardrails Service.

1. Prompt Injection & Leak Protection.
2. Conversation Loop & Escalation Detection.
"""

import re
from typing import NamedTuple


class SecurityCheckResult(NamedTuple):
    is_safe: bool
    refusal_message: str | None
    is_escalated: bool


class SecurityService:
    # أنماط حقن الأوامر وسرقة الـ API Keys أو الـ System Prompt
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all)\s+instructions",
        r"forget\s+(all\s+rules|your\s+role)",
        r"(give|show|tell|print|reveal)\s+me\s+the\s+api\s*key",
        r"(show|reveal|display)\s+(system\s+prompt|instructions)",
        r"you\s+are\s+now\s+a",
        r"اعطني\s+الـ?\s*api\s*key",
        r"اعطني\s+مفتاح\s+الـ?\s*api",
        r"تجاهل\s+(جميع\s+التعليمات|الأوامر\s+السبقة|التعليمات\s+القبلية)",
        r"احذف\s+التعليمات",
        r"كشف\s+الـ?\s*prompt",
        r"اطبع\s+الـ?\s*system\s*prompt",
    ]

    @classmethod
    def inspect_message(cls, message: str, conversation_history_count: int = 0) -> SecurityCheckResult:
        msg = message.strip().lower()

        # 1. فحص محاولات الـ Prompt Injection وسرقة الـ Key
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                return SecurityCheckResult(
                    is_safe=False,
                    refusal_message="عذراً، لا يمكنني الاستجابة لهذا الأسلوب من الطلبات. أنا مخصص فقط لمساعدتك في عيادة الأسنان.",
                    is_escalated=False,
                )

        # 2. فحص الـ Contact Escalation (إذا كان المستخدم يدور في حلقة مفرغة أو الرسائل تجاوزت حد التشتت)
        # إذا كانت المحادثة طويلة جداً دون حجز أو المستخدم كرر أسئلة مبهمة
        if conversation_history_count >= 16:  # تم تبادل 8 ردود بدون الوصول لنتيجة
            return SecurityCheckResult(
                is_safe=True,
                refusal_message=None,
                is_escalated=True,
            )

        return SecurityCheckResult(is_safe=True, refusal_message=None, is_escalated=False)


security_service = SecurityService()