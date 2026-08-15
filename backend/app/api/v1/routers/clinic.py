"""
Public & Management Router for Clinics (Dynamic Branding, Settings & Offers).
إدارة كاملة لبيانات وهوية العيادة، الإعدادات، والعروض الترويجية.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.dependencies.database import get_db
from app.models.clinic import Clinic

router = APIRouter(prefix="/clinic", tags=["Clinic Information & Branding"])


# ==========================================
# 1. Schemas (نماذج البيانات)
# ==========================================

class OfferSchema(BaseModel):
    title: str = Field(..., description="عنوان العرض (مثال: خصم تنظيف وتلميع الأسنان)")
    service_name: str = Field(..., description="اسم الخدمة المتعلقة بالعرض")
    original_price: float = Field(..., ge=0, description="السعر الأصلي قبل الخصم")
    discounted_price: float = Field(..., ge=0, description="السعر بعد الخصم")
    description: str | None = Field(default="", description="تفاصيل أو شروط العرض")
    is_active: bool = Field(default=True, description="حالة تفعيل العرض")


class ClinicPublicInfoResponse(BaseModel):
    id: str
    name: str
    slug: str
    phone: str | None = None
    address: str | None = None
    branding: dict[str, Any]
    working_days_indices: list[int]
    opening_time: str
    closing_time: str
    offers: list[dict[str, Any]] = []


class ClinicDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    phone: str | None
    address: str | None
    is_active: bool
    branding: dict[str, Any] | None
    settings: dict[str, Any] | None

    class Config:
        from_attributes = True


class ClinicUpdateSchema(BaseModel):
    name: str | None = Field(None, description="اسم العيادة")
    phone: str | None = Field(None, description="رقم الهاتف")
    address: str | None = Field(None, description="العنوان")
    primary_color: str | None = Field(None, description="لون الثيم (مثال: #0ea5e9)")
    daily_capacity: int | None = Field(None, ge=1, description="السعة اليومية للمواعيد")
    working_days: list[int] | None = Field(None, description="أيام العمل [0, 1, 2, ...]")
    opening_time: str | None = Field(None, description="ساعة الفتح (16:00)")
    closing_time: str | None = Field(None, description="ساعة الإغلاق (22:00)")
    is_active: bool | None = Field(None, description="تفعيل أو تعطيل العيادة")
    offers: list[dict[str, Any]] | None = Field(None, description="قائمة العروض والخصومات")


# ==========================================
# 2. Public Endpoints (العرض العام)
# ==========================================

@router.get("/public", response_model=ClinicPublicInfoResponse, summary="Get Public Clinic Info & Branding")
async def get_public_clinic_info(
    slug: str | None = Query(None, description="Clinic unique slug (e.g. al-nour)"),
    clinic_id: str | None = Query(None, description="Clinic UUID"),
    db: AsyncSession = Depends(get_db),
) -> ClinicPublicInfoResponse:
    """جلب البيانات العامة وهوية العيادة وعروضها النشطة للواجهة."""
    stmt = select(Clinic).where(Clinic.is_active == True)

    if clinic_id:
        try:
            stmt = stmt.where(Clinic.id == uuid.UUID(clinic_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="معرف العيادة غير صالح.")
    elif slug:
        stmt = stmt.where(Clinic.slug == slug.strip().lower())
    else:
        stmt = stmt.limit(1)

    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة المطلوبة غير موجودة.")

    cfg = clinic.settings or {}
    return ClinicPublicInfoResponse(
        id=str(clinic.id),
        name=clinic.name,
        slug=clinic.slug,
        phone=clinic.phone,
        address=clinic.address,
        branding=clinic.branding or {
            "logo_url": None,
            "primary_color": "#059669",
            "welcome_message": f"أهلاً بك في {clinic.name}",
            "gps_url": None,
        },
        working_days_indices=cfg.get("working_days", [5, 6, 0, 1, 2]),
        opening_time=cfg.get("opening_time", "16:00"),
        closing_time=cfg.get("closing_time", "22:00"),
        offers=cfg.get("offers", []),
    )


# ==========================================
# 3. Management Endpoints (الإدارة العامة)
# ==========================================

@router.get("/all", response_model=List[ClinicDetailResponse], summary="Get All Clinics (Management)")
async def get_all_clinics(db: AsyncSession = Depends(get_db)) -> List[Clinic]:
    """عرض قائمة بجميع العيادات المسجلة في قاعدة البيانات."""
    stmt = select(Clinic).order_by(Clinic.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{slug}", response_model=ClinicDetailResponse, summary="Get Single Clinic Details")
async def get_clinic_by_slug(slug: str, db: AsyncSession = Depends(get_db)) -> Clinic:
    """عرض بيانات عيادة محددة بالـ Slug."""
    stmt = select(Clinic).where(Clinic.slug == slug.strip().lower())
    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")
    return clinic


@router.patch("/{slug}", response_model=ClinicDetailResponse, summary="Update Clinic Details & Settings")
async def update_clinic(
    slug: str,
    data: ClinicUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> Clinic:
    """تعديل بيانات العيادة وإعداداتها وألوانها وعروضها فورياً."""
    stmt = select(Clinic).where(Clinic.slug == slug.strip().lower())
    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")

    if data.name is not None:
        clinic.name = data.name.strip()
    if data.phone is not None:
        clinic.phone = data.phone.strip()
    if data.address is not None:
        clinic.address = data.address.strip()
    if data.is_active is not None:
        clinic.is_active = data.is_active

    # تحديث الهوية البصرية (Branding)
    if data.primary_color is not None:
        current_branding = copy.deepcopy(clinic.branding or {})
        current_branding["primary_color"] = data.primary_color
        clinic.branding = current_branding
        flag_modified(clinic, "branding")

    # تحديث الإعدادات والمواعيد والعروض (Settings)
    current_settings = copy.deepcopy(clinic.settings or {})
    settings_changed = False

    if data.daily_capacity is not None:
        current_settings["daily_capacity"] = data.daily_capacity
        settings_changed = True
    if data.working_days is not None:
        current_settings["working_days"] = data.working_days
        settings_changed = True
    if data.opening_time is not None:
        current_settings["opening_time"] = data.opening_time
        settings_changed = True
    if data.closing_time is not None:
        current_settings["closing_time"] = data.closing_time
        settings_changed = True
    if data.offers is not None:
        current_settings["offers"] = data.offers
        settings_changed = True

    if settings_changed:
        clinic.settings = current_settings
        flag_modified(clinic, "settings")

    await db.commit()
    await db.refresh(clinic)
    return clinic


# ==========================================
# 4. Dedicated Offers Endpoints (إدارة العروض المباشرة)
# ==========================================

@router.get("/{slug}/offers", summary="Get All Clinic Offers")
async def get_clinic_offers(slug: str, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """جلب قائمة العروض الخاصة بعيادة محددة."""
    stmt = select(Clinic).where(Clinic.slug == slug.strip().lower())
    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")

    return (clinic.settings or {}).get("offers", [])


@router.post("/{slug}/offers", summary="Add New Offer to Clinic", status_code=status.HTTP_201_CREATED)
async def add_clinic_offer(
    slug: str,
    offer: OfferSchema,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """إضافة عرض ترويجي جديد وتثبيته مباشرة في قاعدة البيانات."""
    stmt = select(Clinic).where(Clinic.slug == slug.strip().lower())
    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")

    current_settings = copy.deepcopy(clinic.settings or {})
    offers = current_settings.get("offers", [])

    new_offer_dict = offer.model_dump()
    offers.append(new_offer_dict)
    current_settings["offers"] = offers

    clinic.settings = current_settings
    flag_modified(clinic, "settings")

    await db.commit()
    await db.refresh(clinic)

    return {"status": "success", "message": "تمت إضافة العرض بنجاح.", "offer": new_offer_dict}


@router.delete("/{slug}/offers/{offer_index}", summary="Delete an Offer by Index")
async def delete_clinic_offer(
    slug: str,
    offer_index: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """حذف عرض معين عن طريق رقمه الترتيبي في القائمة (يبدأ من 0)."""
    stmt = select(Clinic).where(Clinic.slug == slug.strip().lower())
    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")

    current_settings = copy.deepcopy(clinic.settings or {})
    offers = current_settings.get("offers", [])

    if offer_index < 0 or offer_index >= len(offers):
        raise HTTPException(status_code=400, detail="رقم العرض غير صحيح.")

    removed_offer = offers.pop(offer_index)
    current_settings["offers"] = offers

    clinic.settings = current_settings
    flag_modified(clinic, "settings")

    await db.commit()
    return {"status": "success", "message": f"تم حذف عرض '{removed_offer.get('title')}' بنجاح."}


@router.delete("/{slug}", summary="Delete a Clinic")
async def delete_clinic(slug: str, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """حذف عيادة بالكامل من النظام."""
    stmt = select(Clinic).where(Clinic.slug == slug.strip().lower())
    res = await db.execute(stmt)
    clinic = res.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="العيادة غير موجودة.")

    await db.delete(clinic)
    await db.commit()
    return {"status": "success", "message": f"تم حذف عيادة '{slug}' بنجاح."}