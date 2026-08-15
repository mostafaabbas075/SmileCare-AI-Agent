"""
Apply Database Constraint Script for Neon PostgreSQL.
إضافة قيد الحماية لمنع الحجز المزدوج.
"""

import asyncio
from sqlalchemy import text
from app.dependencies.database import get_db


async def apply_constraint():
    print("⚙️ جاري إضافة قيد الحماية إلى قاعدة بيانات Neon...")

    async for db in get_db():
        try:
            sql_query = text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_booking_per_patient 
                ON appointments (patient_id) 
                WHERE status IN ('PENDING', 'SCHEDULED', 'CONFIRMED');
            """)
            await db.execute(sql_query)
            await db.commit()
            print("✅ تم إضافة قيد الحماية لمنع الحجز المزدوج على Neon بنجاح!")
        except Exception as e:
            await db.rollback()
            print(f"❌ حدث خطأ أثناء إضافة القيد: {e}")
        break


if __name__ == "__main__":
    asyncio.run(apply_constraint())