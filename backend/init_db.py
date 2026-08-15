import asyncio
from sqlalchemy import text
from app.database.base import Base, engine, AsyncSessionFactory
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.config import settings

async def fix_and_init_database():
    print("⏳ جاري الاتصال بـ Neon PostgreSQL وتحديث القيود...")

    async with engine.begin() as conn:
        # 1. إزالة القيد القديم للـ username لو كان موجود
        await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;"))
        await conn.execute(text("DROP INDEX IF EXISTS ix_users_username;"))
        
        # 2. تطبيق القيد المركب الجديد (clinic_id + username)
        await conn.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_clinic_user_username'
                ) THEN 
                    ALTER TABLE users ADD CONSTRAINT uq_clinic_user_username UNIQUE (clinic_id, username);
                END IF; 
            END $$;
        """))
        
        # 3. إنشاء Index عادي للبحث السريع
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);"))

        # 4. التأكد من إنشاء أي جداول جديدة
        await conn.run_sync(Base.metadata.create_all)
        
    print("✅ تم تحديث قيود قاعدة البيانات بنجاح!")

if __name__ == "__main__":
    asyncio.run(fix_and_init_database())