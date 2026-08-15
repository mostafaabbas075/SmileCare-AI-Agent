"""
Multi-Tenant Admin Management Router.

Provides isolated administration for each clinic:
- Dynamic Clinic Settings (Stored in DB per Clinic)
- Dynamic Offers CRUD per Clinic
- Enhanced Daily View & Working Days Navigation
- Isolated Appointment History & Audit Trail
- Tiered No-Show & Blacklist Policy per Clinic
- Services CRUD with Soft Delete
- AI Usage & Token Tracking Analytics per Clinic
- Dynamic Clinic Knowledge Ingestion into Qdrant Vector DB
- JWT Role-Based Access Control & Tenant Guard
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.dependencies.auth import get_current_clinic_id, require_roles
from app.dependencies.database import get_db
from app.models.ai_usage import AIUsageLog
from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.rag.sentence_embedder import SentenceTransformerEmbedder
from app.schemas.common import MessageResponse
from app.services.appointment_service import appointment_service
from app.services.patient_service import patient_service

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["Admin Operations"],
    dependencies=[Depends(require_roles(["ADMIN", "DOCTOR", "RECEPTIONIST"]))],
)

# ── Default Fallback Settings ────────────────────────────────────────────────
DEFAULT_CLINIC_SETTINGS: dict[str, Any] = {
    "working_days": [5, 6, 0, 1, 2],
    "daily_capacity": 10,
    "opening_time": "16:00",
    "closing_time": "22:00",
    "timezone": "Africa/Cairo",
    "no_show_policy": {
        "1": {"ban_days": 0, "msg": "إنذار أول: تسجيل غياب فقط دون حظر."},
        "2": {"ban_days": 7, "msg": "حظر مؤقت لمدة 7 أيام بسبب تكرار الغياب."},
        "3": {"ban_days": 30, "msg": "حظر مؤقت لمدة 30 يوماً بسبب تكرار الغياب."},
        "4": {"ban_days": 365, "msg": "حظر رئيسي (البلاك ليست) لمدة سنة كاملة."},
    },
    "offers": [],
}

STATUS_DB_MAP: dict[str, str] = {
    "pending": "PENDING",
    "scheduled": "SCHEDULED",
    "confirmed": "CONFIRMED",
    "arrived": "CONFIRMED",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
    "no_show": "NO_SHOW",
}


# ── Schemas for Services, Config, Offers & Knowledge ────────────────────────
class ServiceCreateSchema(BaseModel):
    name: str
    description: str | None = ""
    price: float
    duration: int = 30


class ServiceUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    duration: int | None = None
    is_active: bool | None = None


class ClinicConfigUpdateSchema(BaseModel):
    working_days: list[int] | None = Field(default=None, description="0=Mon, 1=Tue, ..., 6=Sun")
    daily_capacity: int | None = Field(default=None, ge=1)
    opening_time: str | None = Field(default=None, description="Format HH:MM e.g. 16:00")
    closing_time: str | None = Field(default=None, description="Format HH:MM e.g. 22:00")
    timezone: str | None = None
    ban_days_first_noshow: int | None = Field(default=None, ge=0)
    ban_days_second_noshow: int | None = Field(default=None, ge=0)
    ban_days_third_noshow: int | None = Field(default=None, ge=0)
    ban_days_repeated_noshow: int | None = Field(default=None, ge=0)


class OfferCreateSchema(BaseModel):
    title: str
    service_name: str = "كشف أسنان"
    original_price: float
    offer_price: float
    description: str | None = ""


class OfferUpdateSchema(BaseModel):
    title: str | None = None
    service_name: str | None = None
    original_price: float | None = None
    offer_price: float | None = None
    description: str | None = None
    is_active: bool | None = None


class KnowledgeAddSchema(BaseModel):
    content: str = Field(..., min_length=5, description="نص المعلومة الطبية أو السؤال الشائع")
    source: str = Field(default="dashboard_manual_entry")


# ── Audit Trail Store ────────────────────────────────────────────────────────
_AUDIT_LOGS: list[dict[str, Any]] = []


def record_audit_log(appointment_id: str, clinic_id: str, action: str, details: str) -> None:
    _AUDIT_LOGS.append({
        "id": str(uuid.uuid4()),
        "clinic_id": clinic_id,
        "appointment_id": appointment_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


_PATIENT_AUDIT_LOGS: list[dict[str, Any]] = []


def record_patient_audit_log(
    patient_id: str,
    clinic_id: str,
    action: str,
    details: str,
    performed_by: str = "system",
) -> None:
    _PATIENT_AUDIT_LOGS.append({
        "id": str(uuid.uuid4()),
        "clinic_id": clinic_id,
        "patient_id": patient_id,
        "action": action,
        "details": details,
        "performed_by": performed_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Helper Functions for Clinic Resolution ───────────────────────────────────
async def get_clinic_or_404(db: AsyncSession, clinic_id: uuid.UUID) -> Clinic:
    clinic = await db.get(Clinic, clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")
    if not clinic.settings:
        clinic.settings = DEFAULT_CLINIC_SETTINGS.copy()
    return clinic


def is_clinic_working_day(target_date: date, working_days: list[int]) -> bool:
    return target_date.weekday() in working_days


def get_next_working_day(start_date: date, working_days: list[int]) -> date:
    curr = start_date + timedelta(days=1)
    while not is_clinic_working_day(curr, working_days):
        curr += timedelta(days=1)
    return curr


def get_prev_working_day(start_date: date, working_days: list[int]) -> date:
    curr = start_date - timedelta(days=1)
    while not is_clinic_working_day(curr, working_days):
        curr -= timedelta(days=1)
    return curr


# ── Dynamic Clinic Config APIs ───────────────────────────────────────────────
@router.get("/clinic/config", summary="Get Current Clinic Config & Settings")
async def get_clinic_config(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
) -> dict[str, Any]:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = clinic.settings or DEFAULT_CLINIC_SETTINGS

    day_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    working_days = cfg.get("working_days", [5, 6, 0, 1, 2])
    working_day_names = [day_names[d] for d in working_days if 0 <= d <= 6]

    return {
        "clinic_name": clinic.name,
        "clinic_slug": clinic.slug,
        "working_days_indices": working_days,
        "working_day_names": working_day_names,
        "daily_capacity": cfg.get("daily_capacity", 10),
        "opening_time": cfg.get("opening_time", "16:00"),
        "closing_time": cfg.get("closing_time", "22:00"),
        "timezone": cfg.get("timezone", "Africa/Cairo"),
        "no_show_policy": cfg.get("no_show_policy", DEFAULT_CLINIC_SETTINGS["no_show_policy"]),
    }


@router.put("/clinic/config", response_model=MessageResponse, summary="Update Clinic Settings")
async def update_clinic_config(
    data: ClinicConfigUpdateSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = dict(clinic.settings or DEFAULT_CLINIC_SETTINGS)

    if data.working_days is not None:
        valid_days = [d for d in data.working_days if 0 <= d <= 6]
        if valid_days:
            cfg["working_days"] = valid_days

    if data.daily_capacity is not None:
        cfg["daily_capacity"] = data.daily_capacity

    if data.opening_time is not None:
        cfg["opening_time"] = data.opening_time

    if data.closing_time is not None:
        cfg["closing_time"] = data.closing_time

    if data.timezone is not None:
        cfg["timezone"] = data.timezone

    policy = cfg.get("no_show_policy", DEFAULT_CLINIC_SETTINGS["no_show_policy"].copy())
    if data.ban_days_first_noshow is not None:
        policy["1"] = {"ban_days": data.ban_days_first_noshow, "msg": "إنذار أول: تسجيل غياب فقط دون حظر."}
    if data.ban_days_second_noshow is not None:
        policy["2"] = {"ban_days": data.ban_days_second_noshow, "msg": f"حظر مؤقت لمدة {data.ban_days_second_noshow} أيام."}
    if data.ban_days_third_noshow is not None:
        policy["3"] = {"ban_days": data.ban_days_third_noshow, "msg": f"حظر مؤقت لمدة {data.ban_days_third_noshow} يوماً."}
    if data.ban_days_repeated_noshow is not None:
        policy["4"] = {"ban_days": data.ban_days_repeated_noshow, "msg": "حظر رئيسي (البلاك ليست)."}
    cfg["no_show_policy"] = policy

    clinic.settings = cfg
    flag_modified(clinic, "settings")
    await db.commit()

    logger.info("clinic_config_updated", clinic_id=str(clinic_id), settings=cfg)
    return MessageResponse(message="تم تحديث إعدادات العيادة ومواعيد وسعة العمل بنجاح.")


# ── Dynamic Offers Management APIs ────────────────────────────────────────────
@router.get("/offers", summary="List All Offers for Current Clinic")
async def list_offers(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
) -> list[dict[str, Any]]:
    clinic = await get_clinic_or_404(db, clinic_id)
    return (clinic.settings or {}).get("offers", [])


@router.post("/offers", response_model=MessageResponse, summary="Create New Offer for Current Clinic")
async def create_offer(
    data: OfferCreateSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = dict(clinic.settings or DEFAULT_CLINIC_SETTINGS)
    offers = list(cfg.get("offers", []))

    new_offer = {
        "id": str(uuid.uuid4()),
        "title": data.title,
        "service_name": data.service_name,
        "original_price": data.original_price,
        "offer_price": data.offer_price,
        "description": data.description or "",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    offers.append(new_offer)
    cfg["offers"] = offers
    clinic.settings = cfg
    flag_modified(clinic, "settings")
    await db.commit()

    return MessageResponse(message=f"تم إضافة العرض '{data.title}' بنجاح للعيادة.")


@router.put("/offers/{offer_id}", response_model=MessageResponse, summary="Update Offer Details")
async def update_offer(
    offer_id: str,
    data: OfferUpdateSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = dict(clinic.settings or DEFAULT_CLINIC_SETTINGS)
    offers = list(cfg.get("offers", []))

    target = next((o for o in offers if o["id"] == offer_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="العرض غير موجود في هذه العيادة.")

    if data.title is not None: target["title"] = data.title
    if data.service_name is not None: target["service_name"] = data.service_name
    if data.original_price is not None: target["original_price"] = data.original_price
    if data.offer_price is not None: target["offer_price"] = data.offer_price
    if data.description is not None: target["description"] = data.description
    if data.is_active is not None: target["is_active"] = data.is_active

    cfg["offers"] = offers
    clinic.settings = cfg
    flag_modified(clinic, "settings")
    await db.commit()

    return MessageResponse(message="تم تحديث بيانات العرض بنجاح.")


@router.patch("/offers/{offer_id}/toggle-active", response_model=MessageResponse)
async def toggle_offer_active(
    offer_id: str,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = dict(clinic.settings or DEFAULT_CLINIC_SETTINGS)
    offers = list(cfg.get("offers", []))

    target = next((o for o in offers if o["id"] == offer_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="العرض غير موجود في هذه العيادة.")

    target["is_active"] = not target.get("is_active", True)
    cfg["offers"] = offers
    clinic.settings = cfg
    flag_modified(clinic, "settings")
    await db.commit()

    status_str = "تفعيل" if target["is_active"] else "تعطيل"
    return MessageResponse(message=f"تم {status_str} العرض بنجاح.")


@router.delete("/offers/{offer_id}", response_model=MessageResponse)
async def delete_offer(
    offer_id: str,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = dict(clinic.settings or DEFAULT_CLINIC_SETTINGS)
    offers = list(cfg.get("offers", []))

    cfg["offers"] = [o for o in offers if o["id"] != offer_id]
    clinic.settings = cfg
    flag_modified(clinic, "settings")
    await db.commit()

    return MessageResponse(message="تم حذف العرض بنجاح.")


# ── Daily View API ───────────────────────────────────────────────────────────
@router.get("/appointments/daily", summary="Get Daily Appointments for Clinic")
async def get_daily_appointments(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    target_date: str | None = Query(None),
) -> dict[str, Any]:
    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = clinic.settings or DEFAULT_CLINIC_SETTINGS
    working_days = cfg.get("working_days", [5, 6, 0, 1, 2])

    today_date = date.today()
    if target_date:
        try:
            req_date = date.fromisoformat(target_date)
        except ValueError:
            req_date = today_date
    else:
        req_date = today_date

    is_working = is_clinic_working_day(req_date, working_days)
    prev_w_day = get_prev_working_day(req_date, working_days)
    next_w_day = get_next_working_day(req_date, working_days)
    closest_future_working_day = req_date if is_working else get_next_working_day(req_date, working_days)

    day_arabic_names = {
        "Monday": "الإثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء",
        "Thursday": "الخميس", "Friday": "الجمعة", "Saturday": "السبت", "Sunday": "الأحد"
    }
    day_name_ar = day_arabic_names.get(req_date.strftime("%A"), req_date.strftime("%A"))

    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.service))
        .where(Appointment.clinic_id == clinic_id, Appointment.appointment_date == req_date)
        .order_by(Appointment.created_at.asc())
    )
    result = await db.execute(stmt)
    appointments = result.scalars().all()

    items = []
    stats = {"total": 0, "pending": 0, "arrived": 0, "completed": 0, "cancelled": 0, "no_show": 0}

    for appt in appointments:
        p_name = f"{appt.patient.first_name} {appt.patient.last_name}" if appt.patient else "غير مسجل"
        p_phone = appt.patient.phone if appt.patient else "—"
        s_name = appt.service.name if appt.service else "كشف عام"
        st = str(appt.status.value if hasattr(appt.status, "value") else appt.status).lower()

        stats["total"] += 1
        if st in ["pending", "scheduled", "confirmed"]: stats["pending"] += 1
        elif st == "arrived": stats["arrived"] += 1
        elif st == "completed": stats["completed"] += 1
        elif st == "cancelled": stats["cancelled"] += 1
        elif st == "no_show": stats["no_show"] += 1

        items.append({
            "id": str(appt.id),
            "patient_id": str(appt.patient_id),
            "patient_name": p_name,
            "patient_phone": p_phone,
            "service_name": s_name,
            "appointment_date": str(appt.appointment_date),
            "booked_at": appt.created_at.strftime("%Y-%m-%d %I:%M %p") if appt.created_at else "—",
            "status": st,
            "notes": appt.notes or "",
        })

    booked_count = stats["pending"] + stats["arrived"] + stats["completed"]
    capacity_limit = cfg.get("daily_capacity", 10)
    remaining_capacity = max(0, capacity_limit - booked_count)

    return {
        "target_date": str(req_date),
        "today_date": str(today_date),
        "day_of_week": day_name_ar,
        "is_working_day": is_working,
        "closest_future_working_day": str(closest_future_working_day),
        "prev_working_day": str(prev_w_day),
        "next_working_day": str(next_w_day),
        "capacity": {
            "daily_capacity": capacity_limit,
            "booked_count": booked_count,
            "remaining_capacity": remaining_capacity,
        },
        "stats": stats,
        "appointments": items,
    }


# ── Appointment History API ──────────────────────────────────────────────────
@router.get("/appointments/history", summary="Appointment History for Clinic")
async def get_appointment_history(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    date_type: str = Query("appointment_date"),
    status_filter: str | None = Query(None),
    service_id: str | None = Query(None),
    search: str | None = Query(None),
) -> list[dict[str, Any]]:
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.service))
        .where(Appointment.clinic_id == clinic_id)
        .order_by(Appointment.appointment_date.desc(), Appointment.created_at.desc())
    )

    if service_id:
        try:
            stmt = stmt.where(Appointment.service_id == uuid.UUID(service_id))
        except ValueError:
            pass

    result = await db.execute(stmt)
    appointments = result.scalars().all()

    filtered = []
    for appt in appointments:
        st = str(appt.status.value if hasattr(appt.status, "value") else appt.status).lower()
        if status_filter and status_filter != "all" and st != status_filter.lower():
            continue

        p_name = f"{appt.patient.first_name} {appt.patient.last_name}" if appt.patient else ""
        p_phone = appt.patient.phone if appt.patient else ""

        if search:
            s_term = search.strip().lower()
            if s_term not in p_name.lower() and s_term not in p_phone.lower():
                continue

        ref_date = appt.appointment_date if date_type == "appointment_date" else (appt.created_at.date() if appt.created_at else None)
        if ref_date:
            if date_from and ref_date < date.fromisoformat(date_from):
                continue
            if date_to and ref_date > date.fromisoformat(date_to):
                continue

        filtered.append({
            "id": str(appt.id),
            "patient_name": p_name or "غير مسجل",
            "patient_phone": p_phone or "—",
            "service_name": appt.service.name if appt.service else "كشف عام",
            "appointment_date": str(appt.appointment_date),
            "booked_at": appt.created_at.strftime("%Y-%m-%d %I:%M %p") if appt.created_at else "—",
            "status": st,
            "notes": appt.notes or "",
        })

    return filtered


@router.get("/appointments/{appointment_id}/audit-trail")
async def get_booking_audit_trail(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
) -> list[dict[str, Any]]:
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="الحجز غير موجود في هذه العيادة.")

    logs = [log for log in _AUDIT_LOGS if log.get("appointment_id") == str(appointment_id)]

    initial_event = {
        "id": "init-created",
        "appointment_id": str(appointment_id),
        "action": "Created",
        "details": f"تم إنشاء الحجز لموعد {appt.appointment_date}",
        "timestamp": appt.created_at.strftime("%Y-%m-%d %I:%M %p") if appt.created_at else "—",
    }
    return [initial_event] + logs


@router.patch("/appointments/{appointment_id}/status", response_model=MessageResponse)
async def update_appointment_status(
    appointment_id: uuid.UUID,
    new_status: str = Query(...),
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN", "DOCTOR", "RECEPTIONIST"])),
) -> MessageResponse:
    appointment = await db.get(Appointment, appointment_id)
    if not appointment or appointment.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="الحجز غير موجود في هذه العيادة.")

    clinic = await get_clinic_or_404(db, clinic_id)
    cfg = clinic.settings or DEFAULT_CLINIC_SETTINGS

    status_clean = new_status.strip().lower()
    db_status = STATUS_DB_MAP.get(status_clean, "CONFIRMED")

    old_status = str(appointment.status.value if hasattr(appointment.status, "value") else appointment.status)
    if old_status == db_status:
        return MessageResponse(message="الحالة هي نفسها بالفعل.")

    appointment.status = db_status
    performed_by = current_user.get("sub") or current_user.get("username") or "admin"
    patient = await db.get(Patient, appointment.patient_id)

    if patient and patient.clinic_id == clinic_id:
        policy_map = cfg.get("no_show_policy", DEFAULT_CLINIC_SETTINGS["no_show_policy"])

        # تسجيل غياب
        if db_status == "NO_SHOW":
            patient.no_show_count += 1
            count_key = str(patient.no_show_count)
            policy = policy_map.get(count_key, policy_map.get("4", {"ban_days": 0}))
            ban_days = policy.get("ban_days", 0)

            if ban_days > 0:
                patient.is_blacklisted = True
                patient.banned_until = datetime.now(timezone.utc) + timedelta(days=ban_days)

            record_patient_audit_log(
                patient_id=str(patient.id),
                clinic_id=str(clinic_id),
                action="NO_SHOW_AUTO",
                details=f"تحديث تلقائي: تسجيل غياب رقم {patient.no_show_count}",
                performed_by=performed_by,
            )

        # التراجع عن تسجيل الغياب
        elif old_status == "NO_SHOW" and db_status != "NO_SHOW":
            patient.no_show_count = max(0, patient.no_show_count - 1)
            count_key = str(patient.no_show_count)
            policy = policy_map.get(count_key, policy_map.get("1", {"ban_days": 0}))
            ban_days = policy.get("ban_days", 0)

            if ban_days == 0:
                patient.is_blacklisted = False
                patient.banned_until = None
            else:
                patient.banned_until = datetime.now(timezone.utc) + timedelta(days=ban_days)

            record_patient_audit_log(
                patient_id=str(patient.id),
                clinic_id=str(clinic_id),
                action="NO_SHOW_REVERT_AUTO",
                details=f"تحديث تلقائي: إلغاء غياب، العدد الحالي {patient.no_show_count}",
                performed_by=performed_by,
            )

    await db.commit()

    record_audit_log(
        str(appointment_id),
        str(clinic_id),
        f"Status Changed ({status_clean.upper()})",
        f"تعديل الحالة من {old_status} إلى {status_clean.upper()}",
    )

    logger.info("appointment_status_updated", appointment_id=str(appointment_id), clinic_id=str(clinic_id), new_status=db_status)
    return MessageResponse(message="تم تعديل حالة الحجز ومزامنة بيانات المريض بنجاح.")


# ── Patients Management ───────────────────────────────────────────────────────
@router.get("/patients", summary="List All Patients for Clinic")
async def list_admin_patients(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    search: str | None = Query(None),
    status: str | None = Query(None, description="Filter by status: 'active' or 'blacklisted'"),
) -> list[dict[str, Any]]:
    from sqlalchemy import and_, or_

    stmt = select(Patient).where(Patient.clinic_id == clinic_id)
    now_utc = datetime.now(timezone.utc)

    if status == "active":
        stmt = stmt.where(
            and_(
                Patient.is_blacklisted == False,
                Patient.no_show_count < 3,
                or_(Patient.banned_until == None, Patient.banned_until <= now_utc),
            )
        )
    elif status == "blacklisted":
        stmt = stmt.where(
            or_(
                Patient.is_blacklisted == True,
                Patient.no_show_count >= 3,
                Patient.banned_until > now_utc,
            )
        )

    stmt = stmt.order_by(Patient.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    patients = result.scalars().all()

    items = []
    for p in patients:
        full_name = f"{p.first_name} {p.last_name}"
        if search:
            s_term = search.strip().lower()
            phone_str = p.phone or ""
            if s_term not in full_name.lower() and s_term not in phone_str.lower():
                continue

        is_manual_blacklisted: bool = p.is_blacklisted
        no_shows: int = p.no_show_count
        banned_until_val = p.banned_until

        is_no_show_banned = bool(
            (
                banned_until_val
                and (
                    banned_until_val.replace(tzinfo=timezone.utc)
                    if banned_until_val.tzinfo is None
                    else banned_until_val
                ) > now_utc
            )
            or no_shows >= 3
        )

        items.append({
            "id": str(p.id),
            "name": full_name,
            "phone": p.phone,
            "no_show_count": no_shows,
            "is_blacklisted": is_manual_blacklisted,
            "is_no_show_banned": is_no_show_banned,
            "banned_until": str(banned_until_val) if banned_until_val else None,
        })
    return items


@router.patch("/patients/{patient_id}/reset-no-show", response_model=MessageResponse)
async def adjust_no_show_counter(
    patient_id: uuid.UUID,
    new_count: int = Query(0),
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN", "DOCTOR", "RECEPTIONIST"])),
) -> MessageResponse:
    patient = await db.get(Patient, patient_id)
    if not patient or patient.clinic_id != clinic_id:
        return MessageResponse(message="المريض غير موجود في هذه العيادة.")

    clinic = await get_clinic_or_404(db, clinic_id)
    policy_map = (clinic.settings or DEFAULT_CLINIC_SETTINGS).get("no_show_policy", DEFAULT_CLINIC_SETTINGS["no_show_policy"])

    performed_by: str = current_user.get("sub") or current_user.get("username") or "admin"
    old_count = patient.no_show_count
    patient.no_show_count = max(0, new_count)

    if new_count == 0:
        patient.is_blacklisted = False
        patient.banned_until = None
        msg = "تم فك الحظر ورست العداد عن المريض بنجاح."
        record_patient_audit_log(
            patient_id=str(patient_id),
            clinic_id=str(clinic_id),
            action="NO_SHOW_RESET",
            details=f"تصفير عداد الغياب من {old_count} إلى 0، وإلغاء الحظر التلقائي.",
            performed_by=performed_by,
        )
    else:
        count_key = str(new_count)
        policy = policy_map.get(count_key, policy_map.get("4", {"ban_days": 0, "msg": "حظر"}))
        ban_days = policy.get("ban_days", 0)

        if ban_days > 0:
            patient.is_blacklisted = True
            patient.banned_until = datetime.now(timezone.utc) + timedelta(days=ban_days)
        else:
            patient.is_blacklisted = False
            patient.banned_until = None

        msg = f"تم تسجيل غياب رقم ({new_count}): {policy.get('msg', '')}"
        record_patient_audit_log(
            patient_id=str(patient_id),
            clinic_id=str(clinic_id),
            action="NO_SHOW_PENALTY",
            details=f"تسجيل غياب رقم {new_count}: {policy.get('msg', '')}",
            performed_by=performed_by,
        )

    await db.commit()
    logger.info("patient_no_show_updated", patient_id=str(patient_id), clinic_id=str(clinic_id), new_count=new_count)
    return MessageResponse(message=msg)


@router.patch("/patients/{patient_id}/blacklist")
async def toggle_patient_blacklist(
    patient_id: uuid.UUID,
    is_blacklisted: bool,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN", "DOCTOR", "RECEPTIONIST"])),
):
    stmt = select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير موجود في هذه العيادة.")

    performed_by: str = current_user.get("sub") or current_user.get("username") or "admin"
    patient.is_blacklisted = is_blacklisted
    await db.commit()

    action = "MANUAL_BLOCK" if is_blacklisted else "MANUAL_UNBLOCK"
    patient_full_name = f"{patient.first_name} {patient.last_name}"
    details_msg = (
        f"حظر يدوي للمريض '{patient_full_name}' بواسطة '{performed_by}'."
        if is_blacklisted else f"فك الحظر اليدوي عن المريض '{patient_full_name}'."
    )

    record_patient_audit_log(str(patient_id), str(clinic_id), action, details_msg, performed_by)
    return {"message": "تم تحديث حالة الحظر بنجاح"}


@router.get("/patients/{patient_id}/audit-trail", summary="Patient Audit Trail for Clinic")
async def get_patient_audit_trail(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
) -> list[dict[str, Any]]:
    stmt = select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير موجود في هذه العيادة.")

    logs = [log for log in _PATIENT_AUDIT_LOGS if log.get("patient_id") == str(patient_id)]
    patient_full_name = f"{patient.first_name} {patient.last_name}"
    initial_event = {
        "id": f"init-{patient_id}",
        "patient_id": str(patient_id),
        "action": "REGISTERED",
        "details": f"تم تسجيل المريض '{patient_full_name}' في النظام.",
        "performed_by": "system",
        "timestamp": patient.created_at.isoformat() if patient.created_at else "—",
    }
    return [initial_event] + logs


# ── Services CRUD Management ─────────────────────────────────────────────────
@router.get("/services", summary="List All Services for Clinic")
async def list_admin_services(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
) -> list[dict[str, Any]]:
    stmt = (
        select(Service)
        .where(
            Service.clinic_id == clinic_id,
            or_(Service.is_deleted == False, Service.is_deleted.is_(None)),
        )
        .order_by(Service.created_at.asc())
    )
    result = await db.execute(stmt)
    services = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "description": s.description or "",
            "price": float(s.price),
            "duration": s.duration,
            "is_active": getattr(s, "is_active", True),
        }
        for s in services
    ]


@router.post("/services", response_model=MessageResponse)
async def create_service(
    data: ServiceCreateSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    new_service = Service(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        name=data.name,
        description=data.description or "",
        price=data.price,
        duration=data.duration,
        is_active=True,
        is_deleted=False,
    )
    db.add(new_service)
    await db.commit()
    return MessageResponse(message=f"تم إضافة الخدمة '{data.name}' بنجاح.")


@router.put("/services/{service_id}", response_model=MessageResponse)
async def update_service(
    service_id: uuid.UUID,
    data: ServiceUpdateSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    service = await db.get(Service, service_id)
    if not service or service.clinic_id != clinic_id or getattr(service, "is_deleted", False):
        return MessageResponse(message="الخدمة غير موجودة في هذه العيادة.")

    if data.name is not None: service.name = data.name
    if data.description is not None: service.description = data.description
    if data.price is not None: service.price = data.price
    if data.duration is not None: service.duration = data.duration
    if data.is_active is not None: service.is_active = data.is_active

    await db.commit()
    return MessageResponse(message=f"تم تحديث بيانات الخدمة '{service.name}'.")


@router.delete("/services/{service_id}", response_model=MessageResponse)
async def delete_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    service = await db.get(Service, service_id)
    if not service or service.clinic_id != clinic_id:
        return MessageResponse(message="الخدمة غير موجودة في هذه العيادة.")

    service.is_deleted = True
    service.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return MessageResponse(message="تم حذف الخدمة بنجاح.")


@router.patch("/services/{service_id}/toggle-active", response_model=MessageResponse)
async def toggle_service_active(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    service = await db.get(Service, service_id)
    if not service or service.clinic_id != clinic_id:
        return MessageResponse(message="الخدمة غير موجودة في هذه العيادة.")

    service.is_active = not service.is_active
    await db.commit()
    return MessageResponse(message=f"تغيرت حالة الخدمة '{service.name}'.")


# ── AI Usage & Analytics API ──────────────────────────────────────────────────
@router.get("/ai-usage", summary="Get AI Usage & Cost Analytics for Clinic")
async def get_clinic_ai_usage(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN", "DOCTOR"])),
) -> dict[str, Any]:
    """عرض إحصائيات استهلاك وتكلفة الذكاء الاصطناعي الخاصة بالعيادة الحالية."""
    stmt = select(AIUsageLog).where(AIUsageLog.clinic_id == clinic_id)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    total_requests = len(logs)
    total_tokens = sum(log.estimated_tokens for log in logs)
    total_cost_usd = sum(log.cost_usd for log in logs)

    return {
        "clinic_id": str(clinic_id),
        "total_chat_requests": total_requests,
        "total_estimated_tokens": total_tokens,
        "total_estimated_cost_usd": round(total_cost_usd, 4),
        "total_estimated_cost_egp": round(total_cost_usd * 50.0, 2),
    }


# ── Dynamic Knowledge Base Management API ────────────────────────────────────
@router.post("/knowledge", response_model=MessageResponse, summary="Add Knowledge Snippet to Clinic Qdrant Vector DB")
async def add_clinic_knowledge_snippet(
    data: KnowledgeAddSchema,
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
) -> MessageResponse:
    """إضافة معلومة طبية أو أسئلة شائعة في قاعدة بيانات الفكتور الخاصة بالعيادة الحالية فقط."""
    embedder = SentenceTransformerEmbedder()
    vector = await embedder.embed_single(data.content.strip())

    qdrant_url = getattr(settings, "QDRANT_HOST", getattr(settings, "QDRANT_URL", None))
    client = AsyncQdrantClient(
        url=qdrant_url,
        api_key=getattr(settings, "QDRANT_API_KEY", None),
    )
    collection_name = getattr(settings, "QDRANT_COLLECTION_NAME", "smile-care")

    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload={
            "clinic_id": str(clinic_id),
            "page_content": data.content.strip(),
            "source": data.source,
        },
    )

    await client.upsert(collection_name=collection_name, points=[point])

    return MessageResponse(message="تم حفظ المعلومة وتحديث ذاكرة الذكاء الاصطناعي للعيادة بنجاح!")