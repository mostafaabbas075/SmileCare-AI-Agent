"""
Multi-Tenant Dental Agent (Virtual Receptionist).

Handles patient interactions, intent routing, dynamic clinic context retrieval,
and appointment booking strictly isolated per clinic:
- Real-Time Live Sync with Clinic Dashboard (Settings, Working Hours, Capacity).
- Dynamic Live Services & Pricing Context from PostgreSQL.
- Dynamic Active Offers & Discounts synced live with Clinic Dashboard Settings.
- Anti-Hallucination Guardrails for Dates, Times, Prices, and Offers.
- Tenant Isolation & In-Memory Conversation Management.
"""

from __future__ import annotations

import uuid
from datetime import date as date_cls, datetime, time as time_cls
from typing import Any, Dict, List

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.rag.qdrant_retriever import ClinicRetriever
from app.rag.sentence_embedder import SentenceTransformerEmbedder
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import appointment_service
from app.services.intent_router import intent_router
from app.services.patient_service import patient_service
from app.services.security_service import security_service

logger = structlog.get_logger(__name__)

# الحد الأقصى للرسائل داخل الجلسة الواحدة
MAX_SESSION_MESSAGES = 50

# 🧠 ذاكرة المحادثات معزولة لكل عيادة وكل جلسة
chat_memory_store: Dict[str, List[BaseMessage]] = {}

DEFAULT_FALLBACK_SETTINGS: dict[str, Any] = {
    "working_days": [5, 6, 0, 1, 2],
    "daily_capacity": 10,
    "opening_time": "16:00",
    "closing_time": "22:00",
    "timezone": "Africa/Cairo",
    "offers": [],
}

ARABIC_DAY_NAMES = {
    0: "الإثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}


class DentalAgent:
    def __init__(
        self,
        db_session: AsyncSession,
        clinic_id: uuid.UUID | str | None = None,
        clinic_slug: str | None = None,
    ):
        self.db = db_session
        self.clinic_id: uuid.UUID | None = (
            uuid.UUID(str(clinic_id)) if clinic_id else None
        )
        self.clinic_slug: str | None = clinic_slug.strip().lower() if clinic_slug else None

        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0.1,
            google_api_key=settings.GOOGLE_API_KEY,
        )

        # ربط أداة الحجز بالوكيل الذكي
        self.llm_with_tools = self.llm.bind_tools(
            [self.book_dental_appointment]
        )

        self.embedder = SentenceTransformerEmbedder()
        self.retriever = ClinicRetriever(embedder=self.embedder)

    async def _resolve_clinic(self) -> Clinic | None:
        """جلب بيانات العيادة الحالية وإعادة تحميل أحدث إعداداتها وعروضها من قاعدة البيانات مباشرة."""
        # 1. البحث بالـ ID إن وُجد
        if self.clinic_id:
            stmt = select(Clinic).where(Clinic.id == self.clinic_id)
            res = await self.db.execute(stmt)
            clinic = res.scalar_one_or_none()
            if clinic:
                self.clinic_slug = clinic.slug
                return clinic

        # 2. البحث بالـ Slug إن وُجد (القادم من الرابط ?clinic=slug)
        if self.clinic_slug:
            stmt = select(Clinic).where(Clinic.slug == self.clinic_slug)
            res = await self.db.execute(stmt)
            clinic = res.scalar_one_or_none()
            if clinic:
                self.clinic_id = clinic.id
                return clinic

        # 3. خطة بديلة (Fallback): أول عيادة نشطة
        stmt = select(Clinic).where(Clinic.is_active == True).limit(1)
        res = await self.db.execute(stmt)
        clinic = res.scalar_one_or_none()
        if clinic:
            self.clinic_id = clinic.id
            self.clinic_slug = clinic.slug
        return clinic

    def _format_arabic_time(self, time_str: str) -> str:
        """تحويل الوقت من 24-ساعة (16:00) إلى 12-ساعة بالعربي (4:00 عصراً)."""
        try:
            t = datetime.strptime(time_str, "%H:%M")
            hour12 = t.strftime("%I:%M").lstrip("0")
            if t.hour < 12:
                period = "صباحاً"
            elif t.hour == 12:
                period = "ظهراً"
            elif t.hour < 18:
                period = "عصراً"
            else:
                period = "مساءً"
            return f"{hour12} {period}"
        except Exception:
            return time_str

    def _get_live_clinic_config_context(self, clinic: Clinic | None) -> str:
        """تحويل إعدادات العيادة الحية (أيام وساعات العمل، السعة) إلى سياق صارم للـ AI."""
        cfg = (clinic.settings if clinic and clinic.settings else DEFAULT_FALLBACK_SETTINGS)

        working_indices = cfg.get("working_days", [5, 6, 0, 1, 2])
        working_days_list = [ARABIC_DAY_NAMES[i] for i in working_indices if i in ARABIC_DAY_NAMES]
        working_days_str = "، ".join(working_days_list) if working_days_list else "كل أيام الأسبوع"

        capacity = cfg.get("daily_capacity", 10)
        open_time_raw = cfg.get("opening_time", "16:00")
        close_time_raw = cfg.get("closing_time", "22:00")
        open_time_ar = self._format_arabic_time(open_time_raw)
        close_time_ar = self._format_arabic_time(close_time_raw)

        return (
            f"📅 أيام وساعات العمل المعتمدة بالداشبورد:\n"
            f"- أيام العمل المتاحة للحجز: **({working_days_str})**.\n"
            f"- مواعيد وساعات الاستقبال: من الساعة **{open_time_ar}** حتى الساعة **{close_time_ar}**.\n"
            f"- الحد الأقصى لسعة الحجوزات اليومية: {capacity} مريض.\n"
            f"- قاعدة الحضور: الحجز لليوم، والدخول بأسبقية الحضور خلال الساعات المحددة أعلاه.\n"
            f"⛔ تنبيه حاسم: يمنع منعاً باتاً اقتراح أو قبول أي يوم غير مذكور في قائمة الأيام أعلاه ({working_days_str})."
        )

    async def _get_live_services_context(self) -> str:
        """سحب قائمة الخدمات والأسعار الحية من قاعدة البيانات الخاصة بالعيادة الحالية."""
        try:
            stmt = select(Service).where(
                Service.is_active == True,
                or_(Service.is_deleted == False, Service.is_deleted.is_(None)),
            )
            if self.clinic_id:
                stmt = stmt.where(Service.clinic_id == self.clinic_id)

            result = await self.db.execute(stmt)
            services = result.scalars().all()

            if not services:
                return "قائمة الخدمات والأسعار: الكشف الطبي العام متاح حالياً بالعيادة."

            context_lines = [
                "📋 قائمة الخدمات والأسعار الرسمية المسجلة بالداشبورد حالياً (التزم بها بدقة):"
            ]
            for s in services:
                desc = s.description or "بدون وصف"
                context_lines.append(
                    f"- الخدمة: {s.name} | الوصف: {desc} | السعر: {s.price} ج.م | المدة: {s.duration} دقيقة."
                )

            return "\n".join(context_lines)
        except Exception as e:
            await self.db.rollback()
            logger.error("live_services_fetch_failed", error=str(e), clinic_id=str(self.clinic_id))
            return "الأسعار الحالية متوفرة ومحدثة لدى لوحة التحكم والاستقبال."

    def _get_live_offers_context(self, clinic: Clinic | None) -> str:
        """قراءة العروض والخصومات المضافة من الداشبورد فورياً بمرونة ودقة كاملة."""
        if not clinic or not clinic.settings:
            return (
                "🎁 حالة العروض بالعيادة: لا توجد عروض أو خصومات نشطة حالياً.\n"
                "⚠️ تنبيه: اذكر عدم وجود عروض فقط إذا سأل المريض عنها صراحةً."
            )

        all_offers = clinic.settings.get("offers", [])
        
        # استخراج العروض المفعلة (تتعامل مع مختلف طرق كتابة الداشبورد للقيم)
        active_offers = [
            o for o in all_offers
            if o.get("is_active") is True or o.get("is_active") == "true" or str(o.get("is_active", "")).lower() == "true" or "is_active" not in o
        ]

        if not active_offers:
            return (
                "🎁 حالة العروض بالعيادة: لا توجد عروض أو خصومات نشطة حالياً في لوحة التحكم.\n"
                "⚠️ تنبيه: اذكر عدم وجود عروض فقط إذا سأل المريض عنها صراحةً."
            )

        lines = [
            "🎁 قائمة العروض والخصومات الخاصة النشطة في لوحة التحكم (الداشبورد) حالياً:",
            "⚠️ تعليمات حاسمة: عندما يسأل المريض عن العروض أو الخصومات، قدم له هذه العروض بدقة واذكر السعر قبل وبعد الخصم:"
        ]
        
        for idx, o in enumerate(active_offers, 1):
            title = o.get("title") or o.get("name") or o.get("offer_title") or f"عرض خاص {idx}"
            service = o.get("service_name") or o.get("service") or o.get("related_service") or "خدمات الأسنان"
            orig_price = o.get("original_price") or o.get("originalPrice") or o.get("price")
            new_price = (
                o.get("discounted_price") 
                or o.get("discount_price") 
                or o.get("offer_price") 
                or o.get("offerPrice") 
                or o.get("new_price")
            )
            desc = o.get("description") or o.get("details") or ""

            price_str = ""
            if orig_price and new_price:
                price_str = f"بسعر {new_price} ج.م بدلاً من {orig_price} ج.م"
            elif new_price:
                price_str = f"بسعر {new_price} ج.م"

            detail_str = f" (التفاصيل: {desc})" if desc else ""
            lines.append(f"{idx}. عرض **{title}** على خدمة ({service}): {price_str}{detail_str}.")

        return "\n".join(lines)

    async def book_dental_appointment(
        self,
        patient_name: str,
        patient_age: int,
        phone_number: str,
        service_name: str = "كشف أسنان",
        date: str = "",
        time: str = "16:00",
    ) -> str:
        """إنشاء حجز حقيقي في قاعدة بيانات العيادة مع احتساب الخصم تلقائياً إن وُجد."""
        try:
            clinic = await self._resolve_clinic()
            if not clinic:
                return "تعذر إتمام الحجز: لم يتم التعرف على العيادة المطلوبة."

            try:
                appointment_date = date_cls.fromisoformat(date)
            except ValueError:
                return "تعذر فهم تاريخ الموعد. يجب أن يكون بصيغة YYYY-MM-DD."

            try:
                appointment_time = time_cls.fromisoformat(time)
            except ValueError:
                appointment_time = time_cls(16, 0)

            phone_number = phone_number.strip()
            name_parts = patient_name.strip().split()
            first_name = name_parts[0] if name_parts else "مريض"
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "جديد"

            # 1. المريض ضمن نطاق العيادة
            stmt_patient = select(Patient).where(
                Patient.phone == phone_number,
                Patient.clinic_id == clinic.id,
            )
            res_p = await self.db.execute(stmt_patient)
            patient = res_p.scalar_one_or_none()

            if not patient:
                patient = Patient(
                    clinic_id=clinic.id,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone_number,
                )
                self.db.add(patient)
                await self.db.flush()

            # 2. الطبيب الخاص بالعيادة
            stmt_doc = select(Doctor).where(Doctor.clinic_id == clinic.id).limit(1)
            res_d = await self.db.execute(stmt_doc)
            doctor = res_d.scalar_one_or_none()

            if not doctor:
                doctor = Doctor(
                    clinic_id=clinic.id,
                    name=f"طبيب {clinic.name}",
                    specialty="طب وجراحة الفم والأسنان",
                    experience_years=5,
                )
                self.db.add(doctor)
                await self.db.flush()

            # 3. الخدمة الخاصة بالعيادة
            stmt_serv = select(Service).where(
                Service.clinic_id == clinic.id,
                Service.name.ilike(f"%{service_name.strip()}%"),
                Service.is_active == True,
                or_(Service.is_deleted == False, Service.is_deleted.is_(None)),
            )
            res_s = await self.db.execute(stmt_serv)
            service = res_s.scalar_one_or_none()

            if not service:
                stmt_fallback = select(Service).where(
                    Service.clinic_id == clinic.id,
                    Service.is_active == True,
                    or_(Service.is_deleted == False, Service.is_deleted.is_(None)),
                ).limit(1)
                res_fallback = await self.db.execute(stmt_fallback)
                service = res_fallback.scalar_one_or_none()

            if not service:
                service = Service(
                    clinic_id=clinic.id,
                    name=service_name.strip() or "كشف أسنان عام",
                    price=250.0,
                    duration=30,
                    is_active=True,
                )
                self.db.add(service)
                await self.db.flush()

            # 4. فحص العروض الخاصة بالعيادة لاحتساب السعر بعد الخصم
            all_offers = (clinic.settings or {}).get("offers", [])
            active_offers = [
                o for o in all_offers
                if o.get("is_active") is True or o.get("is_active") == "true" or "is_active" not in o
            ]
            
            applied_offer = next(
                (o for o in active_offers if (o.get("service_name") or o.get("title", "")).strip().lower() in service.name.lower()),
                None
            )

            if applied_offer:
                discount_price = (
                    applied_offer.get("discounted_price") 
                    or applied_offer.get("discount_price") 
                    or applied_offer.get("offer_price")
                    or applied_offer.get("offerPrice")
                )
                final_price = discount_price if discount_price else service.price
                offer_title = applied_offer.get("title") or applied_offer.get("name") or "عرض خاص"
                booking_note = f"السن: {patient_age} | السعر: {final_price} ج.م (تطبيق عرض: {offer_title})"
                price_message = f"{final_price} ج.م (شامل الخصم والعرض)"
            else:
                final_price = service.price
                booking_note = f"السن: {patient_age} | السعر: {final_price} ج.م"
                price_message = f"{final_price} ج.م"

            appointment_data = AppointmentCreate(
                patient_id=patient.id,
                doctor_id=doctor.id,
                service_id=service.id,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                notes=booking_note,
            )

            appointment = await appointment_service.book_appointment(
                self.db,
                appointment_data,
                clinic_id=clinic.id,
            )

            return (
                "تم تسجيل طلب الحجز بنجاح. 🎉\n"
                f"العيادة: {clinic.name}\n"
                f"اسم المريض: {patient.first_name} {patient.last_name}\n"
                f"رقم الهاتف: {patient.phone}\n"
                f"الخدمة: {service.name}\n"
                f"السعر المطلوب: {price_message}\n"
                f"الطبيب: {doctor.name}\n"
                f"التاريخ: {appointment_date}\n"
                f"رقم الحجز: #{str(appointment.id)[:8].upper()}\n"
                "الحالة: مؤكد (الدخول بأسبقية الحضور خلال ساعات العمل الرسمية)."
            )

        except ConflictError as exc:
            await self.db.rollback()
            return f"عذراً، تعذر الحجز: {exc.message}"

        except ValidationError as exc:
            await self.db.rollback()
            return f"تنويه: {exc.message}"

        except NotFoundError as exc:
            await self.db.rollback()
            return "تعذر تسجيل الحجز بسبب عدم العثور على بيانات العيادة أو الطبيب أو الخدمة."

        except Exception as exc:
            await self.db.rollback()
            logger.exception("appointment_booking_failed", error=str(exc), clinic_id=str(self.clinic_id))
            return "حدث خطأ غير متوقع أثناء الحجز. يرجى المحاولة مرة أخرى."

    async def run(
        self,
        message: str,
        session_id: str,
        clinic_id: uuid.UUID | str | None = None,
        clinic_slug: str | None = None,
    ) -> str:
        """تشغيل محادثة البوت وربطها الفوري بأحدث بيانات الداشبورد للعيادة المستهدفة."""
        if clinic_id:
            self.clinic_id = uuid.UUID(str(clinic_id))
        if clinic_slug:
            self.clinic_slug = clinic_slug.strip().lower()

        # مزامنة بيانات العيادة الحية فورياً
        clinic = await self._resolve_clinic()
        clinic_name = clinic.name if clinic else "العيادة التخصصية للأسنان"
        clinic_address = clinic.address if clinic and clinic.address else "مقر العيادة الرئيسي"
        clinic_phone = clinic.phone if clinic and clinic.phone else "استقبال العيادة"

        # مفتاح عزل الذاكرة حسب العيادة وجلسة المستخدم
        tenant_identifier = str(self.clinic_id) if self.clinic_id else (self.clinic_slug or "default")
        tenant_session_key = f"{tenant_identifier}:{session_id}"

        if tenant_session_key not in chat_memory_store:
            chat_memory_store[tenant_session_key] = []

        history = chat_memory_store[tenant_session_key]

        if len(history) >= MAX_SESSION_MESSAGES:
            return (
                "وصلت هذه المحادثة للحد الأقصى المسموح به (50 رسالة). "
                f"يرجى بدء محادثة جديدة أو التواصل مع {clinic_name} هاتفياً على ({clinic_phone})."
            )

        # فحص الحماية والأمان
        sec_res = security_service.inspect_message(
            message,
            conversation_history_count=len(history),
        )

        if not sec_res.is_safe:
            logger.warning("prompt_injection_blocked", session_id=session_id, clinic_id=str(self.clinic_id))
            return sec_res.refusal_message

        if sec_res.is_escalated and "تواصل" not in message:
            return (
                "يبدو أن لديك استفسارات تخصصية دقيقة. "
                f"حرصاً على تقديم أفضل رعاية طبية لك، يرجى التواصل مع استقبال {clinic_name} مباشرة على ({clinic_phone}). 📞"
            )

        # فحص النوايا الثابتة
        router_res = intent_router.route_message(message)
        if router_res.handled_by_backend and router_res.response_text:
            history.append(HumanMessage(content=message))
            history.append(AIMessage(content=router_res.response_text))
            chat_memory_store[tenant_session_key] = history
            return router_res.response_text

        # استرجاع المعرفة عبر RAG (مع Tenant Filter)
        try:
            context = await self.retriever.search(message, clinic_id=self.clinic_id)
        except Exception as exc:
            logger.error("qdrant_retrieval_failed", error=str(exc), clinic_id=str(self.clinic_id))
            context = "لا توجد معلومات إضافية."

        # بناء السياق الحي المتصل بالداشبورد
        live_services_context = await self._get_live_services_context()
        live_clinic_config = self._get_live_clinic_config_context(clinic)
        live_offers_context = self._get_live_offers_context(clinic)

        today = date_cls.today().isoformat()

        system_prompt = f"""
أنت موظف استقبال افتراضي ذكي (AI Agent) لعيادة ({clinic_name})، وهي عيادة واقعية ومعتمدة (العنوان: {clinic_address} | هاتف: {clinic_phone}).

{live_clinic_config}

{live_offers_context}

{live_services_context}

سياسات العيادة المحدثة:
1. المعرف الرئيسي للمريض هو (رقم الهاتف).
2. لا يُسمح بأكثر من حجز نشط (Active) لنفس رقم الهاتف في العيادة.
3. إذا سأل المريض عن العروض أو الخصومات، قدم له العروض المذكورة أعلاه في "قائمة العروض والخصومات" بحماس ودقة وبالأسعار المحددة.
4. إذا لم يسأل عن العروض، لا تنفِ العروض من تلقاء نفسك بل أجب على سؤاله مباشرة.

البيانات المطلوب جمعها للحجز بأسلوب طبيعي ولبق:
- الاسم الكامل
- السن
- رقم الهاتف
- الخدمة المطلوب حجزها
- اليوم المفضل للحجز (تذكير المريض بأيام وساعات العمل المعتمدة للعيادة أعلاه فقط).

🚨 قواعد حاسمة لاستدعاء أداة الحجز (book_dental_appointment):
1. ⛔ يمنع منعاً باتاً استدعاء أداة الحجز إذا كان هناك أي بيان ناقص من البيانات الخمسة (خصوصاً رقم الهاتف والسن). إذا نقص أي بيان، اطلبه بلطف أولاً ولا تنفذ الحجز.
2. 📅 تحويل التاريخ إلى صيغة ISO رقمية:
   - التاريخ الحالي اليوم هو: ({today}).
   - عند استدعاء الأداة، يجب عليك حساب التاريخ الفعلي لليوم الذي اختاره المريض وتحويله إلى صيغة (YYYY-MM-DD) مثل (2026-08-30).
   - ⛔ يمنع منعاً باتاً تمرير أسماء أيام كنص في خانة التاريخ مثل "يوم الأحد" أو "غداً".
3. **الالتزام المطلق بمواعيد وأيام الداشبورد:** اذكر دائماً أيام وساعات العمل المحددة لك أعلاه حرفياً، ولا تقبل أي يوم عطلة.
4. **الالتزام بأسعار وعروض الداشبورد:** يمنع منعاً باتاً اختراع أي سعر أو عرض غير مسجل في القوائم أعلاه.
5. **أسبقية الحضور:** وضح للمريض بلطف أن الدخول يكون بـ (أسبقية الحضور) خلال ساعات العمل الرسمية.

معلومات إضافية:
{{context}}
"""

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{user_message}"),
            ]
        )

        try:
            logger.info("generating_ai_response", session=session_id, clinic_id=str(self.clinic_id), slug=self.clinic_slug)

            messages = prompt_template.format_messages(
                context=(context if context else "لا توجد معلومات إضافية."),
                chat_history=history,
                user_message=message,
            )

            response = await self.llm_with_tools.ainvoke(messages)

            tool_result = None
            if response.tool_calls:
                tool_call = response.tool_calls[0]
                if tool_call["name"] == "book_dental_appointment":
                    args = tool_call["args"]
                    tool_result = await self.book_dental_appointment(**args)

                    messages.append(response)
                    messages.append(
                        ToolMessage(
                            content=tool_result,
                            tool_call_id=tool_call["id"],
                        )
                    )

                    try:
                        final_response = await self.llm_with_tools.ainvoke(messages)
                        raw_content = final_response.content
                    except Exception:
                        raw_content = None

                    if not raw_content or (isinstance(raw_content, str) and not raw_content.strip()):
                        raw_content = tool_result
                else:
                    raw_content = response.content
            else:
                raw_content = response.content

            # معالجة وتنسيق الرد النهائي
            if isinstance(raw_content, list):
                text_parts = [
                    part if isinstance(part, str) else part.get("text", "")
                    for part in raw_content
                    if isinstance(part, (str, dict))
                ]
                final_text = " ".join(text_parts)
            elif not raw_content or not str(raw_content).strip():
                final_text = tool_result if tool_result else "تم تنفيذ طلبك بنجاح."
            else:
                final_text = str(raw_content)

            final_text = final_text.strip()

            # حفظ سجل المحادثة
            history.append(HumanMessage(content=message))
            history.append(AIMessage(content=final_text))

            if len(history) > 10:
                history = history[-10:]
            chat_memory_store[tenant_session_key] = history

            return final_text

        except Exception as exc:
            await self.db.rollback()
            logger.error("agent_execution_failed", error=str(exc), session=session_id, clinic_id=str(self.clinic_id))
            return (
                "حدث خطأ مؤقت في نظام الذكاء الاصطناعي. "
                f"يمكنك إكمال الحجز عن طريق الاتصال بـ {clinic_name} مباشرة على ({clinic_phone}) أو المحاولة لاحقاً."
            )