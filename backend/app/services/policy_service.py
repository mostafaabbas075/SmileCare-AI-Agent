from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.core.constants import AppointmentStatus
from app.core.exceptions import ValidationError, ConflictError

class PolicyService:

    @staticmethod
    async def reset_daily_counters_if_needed(patient: Patient, db: AsyncSession):
        today = date.today()
        if patient.last_action_date != today:
            patient.daily_edits_count = 0
            patient.daily_cancels_count = 0
            patient.daily_attempts_count = 0
            patient.last_action_date = today
            await db.commit()

    @staticmethod
    async def validate_patient_status(patient: Patient):
        # 1. فحص البلاك ليست الدائم
        if patient.is_blacklisted:
            raise ValidationError("تم حظر حسابك من الحجز الإلكتروني. يرجى التواصل مع استقبال العيادة مباشرة.")

        # 2. فحص الحظر المؤقت (7 أيام أو 30 يوم)
        if patient.banned_until and patient.banned_until > datetime.utcnow():
            remaining_days = (patient.banned_until - datetime.utcnow()).days + 1
            raise ValidationError(f"حسابك معلق مؤقتاً لمدة {remaining_days} يوم بسبب عدم الحضور المسبق.")

    @staticmethod
    async def validate_new_booking(patient: Patient, db: AsyncSession):
        await PolicyService.reset_daily_counters_if_needed(patient, db)
        await PolicyService.validate_patient_status(patient)

        # 1. فحص الحد الأقصى لمحاولات الحجز اليومية (3 محاولات)
        if patient.daily_attempts_count >= 3:
            raise ConflictError("استنفذت الحد الأقصى لمحاولات الحجز اليومية (3 محاولات). حاول غداً.")

        # 2. فحص الـ Cooldown بعد الإلغاء (10 دقائق)
        if patient.last_cancelled_at:
            cooldown_end = patient.last_cancelled_at + timedelta(minutes=10)
            if datetime.utcnow() < cooldown_end:
                remaining_sec = int((cooldown_end - datetime.utcnow()).total_seconds() // 60) + 1
                raise ValidationError(f"يرجى الانتظار {remaining_sec} دقائق قبل إنشاء حجز جديد بعد الإلغاء.")

        # 3. فحص وجود حجز نشط (Active Booking: PENDING or CONFIRMED)
        stmt = select(Appointment).where(
            Appointment.patient_id == patient.id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        )
        res = await db.execute(stmt)
        active_booking = res.scalar_one_or_none()

        if active_booking:
            # إرجاع تفاصيل الحجز الحالي لمنع إنشاء حجز جديد
            return {
                "has_active_booking": True,
                "appointment": active_booking
            }

        return {"has_active_booking": False}

    @staticmethod
    async def validate_update_booking(patient: Patient, db: AsyncSession):
        await PolicyService.reset_daily_counters_if_needed(patient, db)
        if patient.daily_edits_count >= 2:
            raise ConflictError("وصلت للحد الأقصى لتعديل المواعيد اليوم (تعديلان فقط يومياً).")

    @staticmethod
    async def validate_cancel_booking(patient: Patient, db: AsyncSession):
        await PolicyService.reset_daily_counters_if_needed(patient, db)
        if patient.daily_cancels_count >= 1:
            raise ConflictError("وصلت للحد الأقصى للإلغاء اليوم (إلغاء واحد فقط يومياً).")