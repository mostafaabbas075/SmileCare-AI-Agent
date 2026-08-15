"""
Clinic Onboarding & Provisioning Router.
إنشاء وتهيئة عيادة جديدة بالكامل مع حساب الأدمن والخدمات الأولية.
"""

from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.dependencies.database import get_db
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.service import Service
from app.models.user import User, UserRole

router = APIRouter(prefix="/onboarding", tags=["Clinic Onboarding"])


class ClinicOnboardingSchema(BaseModel):
    clinic_name: str = Field(..., description="اسم العيادة (مثال: عيادة النور لطب الأسنان)")
    slug: str = Field(..., description="معرف الرابط الفريد (مثال: al-nour-dental)")
    phone: str = Field(..., description="رقم هاتف استقبال العيادة")
    address: str = Field(..., description="عنوان ومقر العيادة")
    admin_username: str = Field(..., description="اسم مستخدم مدير العيادة")
    admin_password: str = Field(..., min_length=4, description="كلمة سر المدير")
    admin_full_name: str = Field(..., description="الاسم الكامل للمدير")
    primary_color: str = Field(default="#059669", description="لون الثيم الأساسي")
    daily_capacity: int = Field(default=12, ge=1)


@router.post("", summary="Onboard a Brand New Clinic", status_code=status.HTTP_201_CREATED)
async def onboard_new_clinic(
    data: ClinicOnboardingSchema,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    إنشاء بيئة عمل متكاملة لعيادة جديدة:
    1. إنشاء سجل العيادة وإعداداتها الخاصة.
    2. إنشاء حساب Admin خاص بالعيادة.
    3. إنشاء طبيب افتراضي للعيادة.
    4. تجهيز باقة خدمات أساسية قابلة للتعديل.
    """
    # 1. التحقق من عدم تكرار الـ Slug فقط
    slug_clean = data.slug.strip().lower()
    stmt_slug = select(Clinic).where(Clinic.slug == slug_clean)
    res_slug = await db.execute(stmt_slug)
    if res_slug.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="معرف الرابط (Slug) مستخدم بالفعل لعيادة أخرى.")

    # 2. إنشاء العيادة
    new_clinic = Clinic(
        id=uuid.uuid4(),
        name=data.clinic_name.strip(),
        slug=slug_clean,
        phone=data.phone.strip(),
        address=data.address.strip(),
        is_active=True,
        branding={
            "logo_url": None,
            "primary_color": data.primary_color,
            "welcome_message": f"أهلاً بك في {data.clinic_name.strip()}",
            "gps_url": None,
        },
        settings={
            "working_days": [5, 6, 0, 1, 2],  # السبت للثلاثاء افتراضياً
            "daily_capacity": data.daily_capacity,
            "opening_time": "16:00",
            "closing_time": "22:00",
            "timezone": "Africa/Cairo",
            "no_show_policy": {
                "1": {"ban_days": 0, "msg": "إنذار أول"},
                "2": {"ban_days": 7, "msg": "حظر مؤقت 7 أيام"},
                "3": {"ban_days": 30, "msg": "حظر مؤقت 30 يوماً"},
                "4": {"ban_days": 365, "msg": "بلاك ليست رئيسي سنة"},
            },
            "offers": [],
        },
    )
    db.add(new_clinic)
    await db.flush()

    # 3. إنشاء حساب مدير العيادة
    admin_user = User(
        clinic_id=new_clinic.id,
        username=data.admin_username.strip(),
        full_name=data.admin_full_name.strip(),
        hashed_password=hash_password(data.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)

    # 4. إنشاء طبيب افتراضي
    default_doctor = Doctor(
        clinic_id=new_clinic.id,
        name=f"د. {data.admin_full_name.strip()}",
        specialty="طب وجراحة الفم والأسنان",
        experience_years=5,
        working_days="Sat,Sun,Mon,Tue,Wed",
    )
    db.add(default_doctor)

    # 5. إضافة باقة خدمات أساسية للعيادة
    starter_services = [
        {"name": "كشف واستشارة طبية", "price": 200.0, "duration": 20, "desc": "فحص شامل وتشخيص حالة الأسنان واللثة"},
        {"name": "تنظيف وتلميع الأسنان", "price": 450.0, "duration": 30, "desc": "إزالة الجير والتصبغات وتلميع الأسنان"},
        {"name": "حشو أسنان تجميلي (كومبوزيت)", "price": 600.0, "duration": 45, "desc": "علاج التسوس وحشو تجميلي مطابق للون السن"},
    ]

    for s in starter_services:
        db.add(
            Service(
                clinic_id=new_clinic.id,
                name=s["name"],
                price=s["price"],
                duration=s["duration"],
                description=s["desc"],
                is_active=True,
                is_deleted=False,
            )
        )

    await db.commit()

    return {
        "status": "success",
        "message": f"تم تهيئة عيادة '{new_clinic.name}' بنجاح وهي جاهزة للعمل فوراً!",
        "clinic_id": str(new_clinic.id),
        "slug": new_clinic.slug,
        "chat_url": f"/?clinic={new_clinic.slug}",
        "admin_credentials": {
            "username": data.admin_username,
            "role": "ADMIN",
        },
    }