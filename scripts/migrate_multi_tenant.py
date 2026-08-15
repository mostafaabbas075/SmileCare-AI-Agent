"""
Database Migration Script for Multi-Tenancy.
يحدث جداول قاعدة البيانات ويضيف أعمدة clinic_id ويدعم تكرار المستخدمين لكل عيادة.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

# إضافة مسار مجلد backend تلقائياً وبدقة
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from app.database.base import engine


async def run_migration() -> None:
    print("🔄 جاري تحديث جداول قاعدة البيانات وتطبيق نظام الـ Multi-Tenancy...")

    sql_statements = [
        # 1. إنشاء جدول العيادات إن لم يكن موجوداً
        """
        CREATE TABLE IF NOT EXISTS clinics (
            id UUID PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            phone VARCHAR(20),
            address VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            branding JSONB NOT NULL DEFAULT '{}'::jsonb,
            settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        # 2. إنشاء عيادة افتراضية لربط البيانات القديمة بها
        """
        INSERT INTO clinics (id, name, slug, phone, address, is_active, branding, settings)
        VALUES (
            'a0000000-0000-0000-0000-000000000001',
            'العيادة التخصصية للأسنان',
            'main-clinic',
            '01000000000',
            'المقر الرئيسي',
            TRUE,
            '{"primary_color": "#059669", "welcome_message": "أهلاً بك في العيادة التخصصية"}'::jsonb,
            '{"working_days": [5, 6, 0, 1, 2], "daily_capacity": 12, "opening_time": "16:00", "closing_time": "22:00"}'::jsonb
        )
        ON CONFLICT (slug) DO NOTHING;
        """,
        # 3. إنشاء جدول ai_usage_logs إن لم يكن موجوداً
        """
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id UUID PRIMARY KEY,
            clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
            session_id VARCHAR(100) NOT NULL,
            message_length INTEGER NOT NULL DEFAULT 0,
            response_length INTEGER NOT NULL DEFAULT 0,
            estimated_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        # 4. إضافة عمود clinic_id لكافة الجداول وتعيين العيادة الافتراضية
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;",
        "UPDATE users SET clinic_id = 'a0000000-0000-0000-0000-000000000001' WHERE clinic_id IS NULL;",
        "ALTER TABLE patients ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;",
        "UPDATE patients SET clinic_id = 'a0000000-0000-0000-0000-000000000001' WHERE clinic_id IS NULL;",
        "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;",
        "UPDATE doctors SET clinic_id = 'a0000000-0000-0000-0000-000000000001' WHERE clinic_id IS NULL;",
        "ALTER TABLE services ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;",
        "UPDATE services SET clinic_id = 'a0000000-0000-0000-0000-000000000001' WHERE clinic_id IS NULL;",
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;",
        "UPDATE appointments SET clinic_id = 'a0000000-0000-0000-0000-000000000001' WHERE clinic_id IS NULL;",
        # 5. حذف القيد الفريد القديم العام لاسم المستخدم للسماح بتكراره بين العيادات
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;",
        "DROP INDEX IF EXISTS ix_users_username;",
        # 6. إضافة القيد المركب الجديد (clinic_id + username)
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_clinic_user_username'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT uq_clinic_user_username UNIQUE (clinic_id, username);
            END IF;
        END $$;
        """,
    ]

    async with engine.begin() as conn:
        for stmt in sql_statements:
            await conn.execute(text(stmt))

    print("✅ تم تحديث جميع الجداول وإضافة القيود بنجاح تام!")


if __name__ == "__main__":
    asyncio.run(run_migration())