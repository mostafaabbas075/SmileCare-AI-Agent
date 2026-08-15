"""
Authentication Router for Multi-Tenant User Login and Initial Seeding.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.dependencies.database import get_db
from app.models.clinic import Clinic
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Schemas ──────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    clinic_slug: str = Field(default="main-clinic", description="معرف العيادة (Slug)")
    username: str = Field(..., description="اسم المستخدم")
    password: str = Field(..., description="كلمة المرور")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    full_name: str
    role: str
    clinic_id: str
    clinic_name: str


# ── APIs ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse, summary="User Login per Clinic")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """تسجيل الدخول داخل نطاق العيادة المحددة وإرجاع JWT Token يحمل معرف العيادة."""
    # 1. التحقق من وجود العيادة ونشاطها
    stmt_clinic = select(Clinic).where(
        Clinic.slug == data.clinic_slug.strip().lower(),
        Clinic.is_active == True,
    )
    res_clinic = await db.execute(stmt_clinic)
    clinic = res_clinic.scalar_one_or_none()

    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="العيادة المحددة غير موجودة أو معطلة.",
        )

    # 2. البحث عن المستخدم داخل نطاق هذه العيادة فقط
    stmt_user = select(User).where(
        User.clinic_id == clinic.id,
        User.username == data.username.strip(),
    )
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة السر غير صحيحة لهذه العيادة.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا الحساب معطل حالياً، يرجى مراجعة إدارة العيادة.",
        )

    user_role_str = user.role.value if isinstance(user.role, UserRole) else str(user.role)

    # 3. إنشاء توكن مشفر يحتوي على سياق العيادة المعزول
    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "role": user_role_str,
        "clinic_id": str(clinic.id),
        "clinic_slug": clinic.slug,
    })

    return LoginResponse(
        access_token=token,
        full_name=user.full_name,
        role=user_role_str,
        clinic_id=str(clinic.id),
        clinic_name=clinic.name,
    )


@router.post("/seed-users", summary="Create Initial Default Clinic & Users")
async def seed_initial_users(db: AsyncSession = Depends(get_db)):
    """إنشاء العيادة الافتراضية مع الحسابات الأساسية لتهيئة النظام لأول مرة."""
    # 1. التأكد من وجود العيادة الافتراضية
    stmt_clinic = select(Clinic).where(Clinic.slug == "main-clinic")
    res_clinic = await db.execute(stmt_clinic)
    clinic = res_clinic.scalar_one_or_none()

    if not clinic:
        clinic = Clinic(
            name="العيادة التخصصية للأسنان",
            slug="main-clinic",
            phone="01000000000",
            address="القاهرة، مصر",
            is_active=True,
            branding={
                "logo_url": None,
                "primary_color": "#059669",
                "welcome_message": "أهلاً بك في العيادة التخصصية للأسنان",
            },
            settings={
                "working_days": [5, 6, 0, 1, 2],
                "daily_capacity": 12,
                "opening_time": "16:00",
                "closing_time": "22:00",
            },
        )
        db.add(clinic)
        await db.flush()

    # 2. إنشاء المستخدمين الافتراضيين داخل هذه العيادة حصراً
    default_users = [
        {"username": "admin", "full_name": "مدير النظام (Admin)", "password": "password123", "role": UserRole.ADMIN},
        {"username": "doctor", "full_name": "دكتور العيادة (Doctor)", "password": "password123", "role": UserRole.DOCTOR},
        {"username": "user", "full_name": "موظف الاستقبال (User)", "password": "password123", "role": UserRole.RECEPTIONIST},
    ]

    created = []
    for u in default_users:
        stmt = select(User).where(
            User.clinic_id == clinic.id,
            User.username == u["username"],
        )
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            new_u = User(
                clinic_id=clinic.id,
                username=u["username"],
                full_name=u["full_name"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
                is_active=True,
            )
            db.add(new_u)
            created.append(u["username"])

    await db.commit()
    return {
        "message": "تم تهيئة العيادة الافتراضية والمستخدمين بنجاح!",
        "clinic_name": clinic.name,
        "clinic_slug": clinic.slug,
        "clinic_id": str(clinic.id),
        "created_users": created if created else "المستخدمون مسجلون بالفعل مسبقاً لهذه العيادة.",
    }