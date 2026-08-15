import asyncio
from sqlalchemy import text
from app.database.base import engine

async def fix_services_constraint():
    print("⏳ جاري تحديث قيود جدول الخدمات (Services)...")
    async with engine.begin() as conn:
        # 1. إزالة الـ Unique Index القديم لاسم الخدمة
        await conn.execute(text("DROP INDEX IF EXISTS ix_services_name;"))
        await conn.execute(text("ALTER TABLE services DROP CONSTRAINT IF EXISTS services_name_key;"))
        
        # 2. إنشاء قيد مركب (الاسم فريد لكل عيادة فقط)
        await conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_clinic_service_name'
                ) THEN 
                    ALTER TABLE services ADD CONSTRAINT uq_clinic_service_name UNIQUE (clinic_id, name);
                END IF; 
            END $$;
        """))
        
        # 3. إنشاء Index عادي للبحث السريع
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_services_name ON services (name);"))

    print("✅ تم تعديل جدول الخدمات بنجاح!")

if __name__ == "__main__":
    asyncio.run(fix_services_constraint())