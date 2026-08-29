"""
Appointment service.

Orchestrates appointment booking, cancellation, rescheduling, and retrieval.
Enforces Policy V1 & Business Rules directly in Backend:
- Strict Backend Business Hours (Sat, Mon, Tue | 16:00 - 22:00).
- Active Service validation (is_active check).
- Admin Override capability to bypass policy restrictions.
- Progressive No-Show penalty escalation.
- Atomic Booking & Race Condition protection using Pessimistic Row Locking.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AppointmentStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.repositories.appointment import AppointmentRepository, appointment_repository
from app.repositories.doctor import DoctorRepository, doctor_repository
from app.repositories.patient import PatientRepository, patient_repository
from app.repositories.service import ServiceRepository, service_repository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate

logger = structlog.get_logger(__name__)

# الحدود الصارمة لسياسة العيادة V1
MAX_DAILY_PATIENTS: int = 5
MAX_DAILY_ATTEMPTS: int = 3
MAX_DAILY_EDITS: int = 2
MAX_DAILY_CANCELS: int = 1
CANCEL_COOLDOWN_MINUTES: int = 10

# مواعيد وأيام العمل المعتمدة
ALLOWED_WEEKDAYS: set[int] = {0, 1, 5}  # Mon (0), Tue (1), Sat (5)
WORK_START_TIME: time = time(16, 0)
WORK_END_TIME: time = time(22, 0)

_ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.PENDING: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.EXPIRED,
    },
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
    AppointmentStatus.EXPIRED: set(),
}


class AppointmentService:
    """Business logic for appointment lifecycle management."""

    def __init__(
        self,
        repo: AppointmentRepository = appointment_repository,
        patient_repo: PatientRepository = patient_repository,
        doctor_repo: DoctorRepository = doctor_repository,
        service_repo: ServiceRepository = service_repository,
    ) -> None:
        self._repo = repo
        self._patient_repo = patient_repo
        self._doctor_repo = doctor_repo
        self._service_repo = service_repo

    async def _reset_daily_counters_if_needed(self, patient: Patient, db: AsyncSession) -> None:
        """تصفير العدادات اليومية إذا كان التاريخ قد تغير."""
        today = date.today()
        last_action = getattr(patient, "last_action_date", None)
        if last_action != today:
            if hasattr(patient, "daily_edits_count"):
                patient.daily_edits_count = 0
            if hasattr(patient, "daily_cancels_count"):
                patient.daily_cancels_count = 0
            if hasattr(patient, "daily_attempts_count"):
                patient.daily_attempts_count = 0
            if hasattr(patient, "last_action_date"):
                patient.last_action_date = today

    async def get_appointment(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        appointment = await self._repo.get_by_id(db, appointment_id)
        if appointment is None:
            raise NotFoundError("Appointment", appointment_id)
        return appointment

    async def get_appointment_detail(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        appointment = await self._repo.get_with_details(db, appointment_id)
        if appointment is None:
            raise NotFoundError("Appointment", appointment_id)
        return appointment

    async def list_appointments(
        self,
        db: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
        patient_id: uuid.UUID | None = None,
    ) -> tuple[list[Appointment], int]:
        if patient_id is not None:
            appointments = await self._repo.get_by_patient(
                db, patient_id, offset=offset, limit=limit
            )
            total = len(appointments)
            return appointments, total

        appointments = await self._repo.get_all(db, offset=offset, limit=limit)
        total = await self._repo.count(db)
        return appointments, total

    async def book_appointment(
        self,
        db: AsyncSession,
        data: AppointmentCreate,
        admin_override: bool = False,
    ) -> Appointment:
        """
        Book a new appointment with Backend Business Hours, Active Services enforcement,
        and Atomic Pessimistic Row Locking to prevent Race Conditions / Overbooking.
        """
        # 1. Lock Patient record (Pessimistic Lock)
        patient_stmt = (
            select(Patient)
            .where(Patient.id == data.patient_id)
            .with_for_update()
        )
        patient_res = await db.execute(patient_stmt)
        patient = patient_res.scalar_one_or_none()

        if not patient:
            raise NotFoundError("Patient", data.patient_id)

        # 2. Lock Doctor record (Pessimistic Lock)
        doctor_stmt = (
            select(Doctor)
            .where(Doctor.id == data.doctor_id)
            .with_for_update()
        )
        doctor_res = await db.execute(doctor_stmt)
        doctor = doctor_res.scalar_one_or_none()

        if not doctor:
            raise NotFoundError("Doctor", data.doctor_id)

        service = await self._service_repo.get_by_id(db, data.service_id)
        if not service:
            raise NotFoundError("Service", data.service_id)

        if not getattr(service, "is_active", True) and not admin_override:
            raise ValidationError(f"الخدمة '{service.name}' غير متاحة للحجز حالياً.")

        if not admin_override:
            if data.appointment_date.weekday() not in ALLOWED_WEEKDAYS:
                raise ValidationError("العيادة مغلقة في اليوم المحدد. أيام العمل الرسمية هي: (السبت، الإثنين، الثلاثاء) فقط.")

            if data.appointment_time < WORK_START_TIME or data.appointment_time >= WORK_END_TIME:
                raise ValidationError(f"الوقت المحدد خارج ساعات الاستقبال الرسمية ({WORK_START_TIME.strftime('%H:%M')} - {WORK_END_TIME.strftime('%H:%M')}).")

        await self._reset_daily_counters_if_needed(patient, db)

        is_blacklisted = getattr(patient, "is_blacklisted", False)
        banned_until = getattr(patient, "banned_until", None)
        daily_attempts = getattr(patient, "daily_attempts_count", 0)
        last_cancelled_at = getattr(patient, "last_cancelled_at", None)

        if not admin_override:
            if is_blacklisted:
                raise ValidationError("حسابك محظور من الحجز الإلكتروني. يرجى التواصل مع العيادة.")

            if banned_until and banned_until > datetime.utcnow():
                days_left = (banned_until - datetime.utcnow()).days + 1
                raise ValidationError(f"حسابك معلق مؤقتاً لمدة {days_left} أيام بسبب عدم الحضور المسبق.")

            if daily_attempts >= MAX_DAILY_ATTEMPTS:
                raise ConflictError("استنفذت الحد الأقصى لمحاولات الحجز اليومية (3 محاولات يومياً).")

            if last_cancelled_at:
                cooldown_until = last_cancelled_at + timedelta(minutes=CANCEL_COOLDOWN_MINUTES)
                if datetime.utcnow() < cooldown_until:
                    remaining = int((cooldown_until - datetime.utcnow()).total_seconds() // 60) + 1
                    raise ValidationError(f"يرجى الانتظار {remaining} دقائق قبل إجراء حجز جديد بعد الإلغاء.")

            active_stmt = select(Appointment).where(
                Appointment.patient_id == patient.id,
                Appointment.status.in_([
                    AppointmentStatus.PENDING,
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                ]),
            )
            active_res = await db.execute(active_stmt)
            active_booking = active_res.scalars().first()

            if active_booking:
                raise ConflictError(
                    f"لديك حجز نشط بالفعل بتاريخ {active_booking.appointment_date}. "
                    f"يمكنك تعديله أو إلغاؤه بدلاً من إنشاء حجز جديد."
                )

            # Capacity check under atomic Doctor lock
            count_stmt = (
                select(func.count(Appointment.id))
                .where(
                    Appointment.doctor_id == data.doctor_id,
                    Appointment.appointment_date == data.appointment_date,
                    Appointment.status.notin_([
                        AppointmentStatus.CANCELLED,
                        AppointmentStatus.NO_SHOW,
                        AppointmentStatus.EXPIRED,
                    ]),
                )
            )
            res = await db.execute(count_stmt)
            daily_count = res.scalar() or 0

            if daily_count >= MAX_DAILY_PATIENTS:
                raise ConflictError(
                    f"عذراً، اكتمل الحد الأقصى للحجوزات ليوم {data.appointment_date} "
                    f"({MAX_DAILY_PATIENTS} مرضى). يرجى اختيار يوم آخر."
                )

        if hasattr(patient, "daily_attempts_count"):
            patient.daily_attempts_count = daily_attempts + 1

        appointment = await self._repo.create(db, data.model_dump())
        await db.commit()
        await db.refresh(appointment)

        logger.info(
            "appointment_booked",
            appointment_id=str(appointment.id),
            patient_id=str(data.patient_id),
            date=str(data.appointment_date),
            admin_override=admin_override,
        )
        return appointment

    async def update_appointment(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
        data: AppointmentUpdate,
        admin_override: bool = False,
    ) -> Appointment:
        """Update appointment with Policy enforcement or Admin Override."""
        appointment = await self.get_appointment(db, appointment_id)
        patient = await self._patient_repo.get_by_id(db, appointment.patient_id)

        if patient and not admin_override:
            await self._reset_daily_counters_if_needed(patient, db)
            if data.appointment_date is not None or data.appointment_time is not None:
                daily_edits = getattr(patient, "daily_edits_count", 0)
                if daily_edits >= MAX_DAILY_EDITS:
                    raise ConflictError("وصلت للحد الأقصى لتعديل المواعيد اليوم (تعديلان فقط يومياً).")
                if hasattr(patient, "daily_edits_count"):
                    patient.daily_edits_count = daily_edits + 1

        if data.status is not None and data.status != appointment.status and not admin_override:
            allowed = _ALLOWED_TRANSITIONS.get(appointment.status, set())
            if data.status not in allowed:
                raise ValidationError(
                    f"Cannot transition from '{appointment.status}' to '{data.status}'."
                )

        updated = await self._repo.update(
            db, appointment, data.model_dump(exclude_none=True)
        )
        await db.commit()
        await db.refresh(updated)
        logger.info("appointment_updated", appointment_id=str(appointment_id), admin_override=admin_override)
        return updated

    async def cancel_appointment(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
        admin_override: bool = False,
    ) -> Appointment:
        """Cancel appointment with Policy check or Admin Override."""
        appointment = await self.get_appointment(db, appointment_id)
        patient = await self._patient_repo.get_by_id(db, appointment.patient_id)

        if patient and not admin_override:
            await self._reset_daily_counters_if_needed(patient, db)
            daily_cancels = getattr(patient, "daily_cancels_count", 0)
            if daily_cancels >= MAX_DAILY_CANCELS:
                raise ConflictError("وصلت للحد الأقصى للإلغاء اليوم (إلغاء واحد فقط يومياً).")

            if hasattr(patient, "daily_cancels_count"):
                patient.daily_cancels_count = daily_cancels + 1
            if hasattr(patient, "last_cancelled_at"):
                patient.last_cancelled_at = datetime.utcnow()

        return await self.update_appointment(
            db,
            appointment_id,
            AppointmentUpdate(status=AppointmentStatus.CANCELLED),
            admin_override=admin_override,
        )

    async def mark_no_show(
        self,
        db: AsyncSession,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        """Mark appointment as NO_SHOW and apply penalty escalation."""
        appointment = await self.get_appointment(db, appointment_id)
        patient = await self._patient_repo.get_by_id(db, appointment.patient_id)

        if patient:
            no_show_cnt = getattr(patient, "no_show_count", 0) + 1
            if hasattr(patient, "no_show_count"):
                patient.no_show_count = no_show_cnt

            if no_show_cnt == 2:
                if hasattr(patient, "banned_until"):
                    patient.banned_until = datetime.utcnow() + timedelta(days=7)
                logger.warning("patient_banned_7_days", patient_id=str(patient.id))
            elif no_show_cnt == 3:
                if hasattr(patient, "banned_until"):
                    patient.banned_until = datetime.utcnow() + timedelta(days=30)
                logger.warning("patient_banned_30_days", patient_id=str(patient.id))
            elif no_show_cnt > 3:
                if hasattr(patient, "is_blacklisted"):
                    patient.is_blacklisted = True
                logger.warning("patient_blacklisted", patient_id=str(patient.id))

        return await self.update_appointment(
            db,
            appointment_id,
            AppointmentUpdate(status=AppointmentStatus.NO_SHOW),
            admin_override=True,
        )


appointment_service = AppointmentService()