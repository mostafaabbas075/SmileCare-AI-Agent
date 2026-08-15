"""
Multi-Tenant User Management Router for Admin.
إدارة مستخدمي العيادة الحالية مع ضمان العزل التام بين العيادات.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.dependencies.auth import (
    get_current_clinic_id,
    get_current_user,
    require_roles,
)
from app.dependencies.database import get_db
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/users", tags=["Users Management"])


# ── Schemas ──────────────────────────────────────────────────────────────────
class UserCreateSchema(BaseModel):
    username: str
    full_name: str
    password: str
    role: UserRole = UserRole.RECEPTIONIST


class AdminChangePasswordSchema(BaseModel):
    user_id: uuid.UUID
    new_password: str


class SelfChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str


# ── APIs ─────────────────────────────────────────────────────────────────────

# 1. عرض مستخدمي العيادة الحالية فقط (خاص بـ Admin العيادة)
@router.get("", summary="List Clinic Users (Admin Only)")
async def list_users(
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
):
    stmt = (
        select(User)
        .where(User.clinic_id == clinic_id)
        .order_by(User.created_at.asc())
    )
    res = await db.execute(stmt)
    users = res.scalars().all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role.value if isinstance(u.role, UserRole) else str(u.role),
            "is_active": u.is_active,
        }
        for u in users
    ]


# 2. إنشاء مستخدم جديد وربطه بالعيادة الحالية تلقائياً
@router.post("", response_model=MessageResponse, summary="Create Clinic User (Admin Only)")
async def create_user(
    data: UserCreateSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
):
    # فحص تكرار اسم المستخدم
    stmt = select(User).where(User.username == data.username)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل.")

    new_user = User(
        clinic_id=clinic_id,
        username=data.username,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    return MessageResponse(message=f"تم إنشاء حساب '{data.username}' بنجاح.")


# 3. تغيير كلمة السر لمستخدم داخل نفس العيادة
@router.post("/admin/change-password", response_model=MessageResponse, summary="Admin Change User Password")
async def admin_change_password(
    data: AdminChangePasswordSchema,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
):
    user = await db.get(User, data.user_id)
    if not user or user.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return MessageResponse(message=f"تم تغيير كلمة السر للحساب '{user.username}' بنجاح.")


# 4. تغيير المستخدم لكلمة السر الخاصة به
@router.post("/me/change-password", response_model=MessageResponse, summary="Change Own Password")
async def self_change_password(
    data: SelfChangePasswordSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(current_user["sub"])
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="كلمة السر القديمة غير صحيحة.")

    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return MessageResponse(message="تم تغيير كلمة السر الخاصة بك بنجاح.")


# 5. تفعيل / تعطيل حساب مستخدم تابع للعيادة
@router.patch("/{user_id}/toggle-active", response_model=MessageResponse)
async def toggle_user_active(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
):
    user = await db.get(User, user_id)
    if not user or user.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    user.is_active = not user.is_active
    await db.commit()
    status_str = "تفعيل" if user.is_active else "تعطيل"
    return MessageResponse(message=f"تم {status_str} حساب '{user.username}'.")


# 6. حذف حساب مستخدم نهائياً تابع لنفس العيادة
@router.delete("/{user_id}", response_model=MessageResponse, summary="Delete User Account (Admin Only)")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    clinic_id: uuid.UUID = Depends(get_current_clinic_id),
    current_user: dict = Depends(require_roles(["ADMIN"])),
):
    user = await db.get(User, user_id)
    if not user or user.clinic_id != clinic_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    # حماية المدير من حذف حسابه الشخصي المسجل به حالياً
    if str(user.id) == current_user.get("sub") or user.username == current_user.get("username"):
        raise HTTPException(
            status_code=400,
            detail="لا يمكنك حذف حسابك الشخصي أثناء تسجيل الدخول به.",
        )

    await db.delete(user)
    await db.commit()
    return MessageResponse(message=f"تم حذف حساب '{user.username}' نهائياً بنجاح.")