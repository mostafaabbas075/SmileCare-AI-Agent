import asyncio
from sqlalchemy import text
from app.database.base import engine

async def fix_patients_columns():
    print("⏳ جاري إضافة أعمدة الحظر لجدول patients في Neon...")
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_blacklisted BOOLEAN DEFAULT FALSE;"))
        await conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS banned_until TIMESTAMP WITH TIME ZONE;"))
    print("✅ تم إضافة الأعمدة بنجاح لجدول المرضى!")

if __name__ == "__main__":
    asyncio.run(fix_patients_columns())