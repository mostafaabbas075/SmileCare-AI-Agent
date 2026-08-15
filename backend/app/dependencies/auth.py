"""
Authentication & Role-Based Access Control (RBAC) Dependency with Multi-Tenant Support.
فحص التوكن، رتبة المستخدم، وهوية العيادة (clinic_id) لعزل البيانات.
"""

from __future__ import annotations

import uuid
from typing import Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_access_token

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """استخراج بيانات المستخدم الحالي وهوية العيادة من الـ JWT Token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="جلسة الدخول منتهية أو كود التوثيق غير صالح. يرجى إعادة تسجيل الدخول.",
        )

    user_id = payload.get("sub")
    clinic_id = payload.get("clinic_id")

    if not user_id or not clinic_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات التوثيق ناقصة (معرف المستخدم أو معرف العيادة مفقود).",
        )

    return payload


async def get_current_clinic_id(current_user: dict = Depends(get_current_user)) -> uuid.UUID:
    """استخراج معرف العيادة (clinic_id) المعتمد والمؤمن من التوكن كـ UUID."""
    try:
        return uuid.UUID(str(current_user["clinic_id"]))
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="معرف العيادة غير صالح داخل جلسة الدخول.",
        )


def require_roles(allowed_roles: list[str]) -> Callable:
    """فحص صلاحيات المستخدم بناءً على درجات الوظيفة مع ضمان وجود سياق العيادة."""
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ليس لديك الصلاحية الكافية للوصول لهذا القسم.",
            )
        return current_user

    return role_checker