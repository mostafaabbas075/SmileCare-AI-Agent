"""
Database Reset Script for SmileCare AI.
تصفير الحجوزات والمرضى بأمان وبدون أي أخطاء استيراد.
"""

import asyncio
from sqlalchemy import text
from app.dependencies.database import get_db


async def reset_database():
    print("🧹 جاري تصفير قاعدة البيانات...")

    # استخدام جلسة قاعدة البيانات المعرفة في المشروع
    async for db in get_db():
        try:
            # مسح جداول الحجوزات والمرضى وإعادة ضبط العدادات
            await db.execute(text("TRUNCATE TABLE appointments CASCADE;"))
            await db.execute(text("TRUNCATE TABLE patients CASCADE;"))
            
            await db.commit()
            print("✅ تم حذف جميع الحجوزات والمرضى وتصفير لوحة التحكم بنجاح!")
        except Exception as e:
            await db.rollback()
            print(f"❌ حدث خطأ أثناء التصفير: {e}")
        break


if __name__ == "__main__":
    asyncio.run(reset_database())