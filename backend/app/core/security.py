"""
Security utilities: Password hashing & Multi-Tenant JWT Token handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from passlib.context import CryptContext

# إعدادات المفتاح السري والـ JWT
SECRET_KEY = "Clinic_JWT_Super_Secret_Key_2026_Change_In_Production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # صالح لمدة 12 ساعة

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """تشفير كلمة السر بأمان."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """التحقق من مطابقة كلمة السر للهاش المشفّر."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    توليد JWT Access Token يحمل بيانات المستخدم وهوية العيادة (clinic_id).
    """
    to_encode = data.copy()
    
    # ضمان تحويل UUID الخاص بالعيادة أو المستخدم إلى نص داخل الـ Payload
    if "clinic_id" in to_encode:
        to_encode["clinic_id"] = str(to_encode["clinic_id"])
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"iat": now, "exp": expire})
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """فك تشفير الـ Token والتحقق من صحته."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None