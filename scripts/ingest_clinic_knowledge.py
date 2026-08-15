"""
Multi-Tenant Knowledge Ingestion CLI Script for Qdrant Cloud.
يرفع المعرفة الطبية والأسئلة الشائعة الخاصة بعيادة محددة مع عزلها بـ clinic_id.
"""

import asyncio
import os
import sys
import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

# إضافة المجلد الرئيسي للمشروع لمسارات بايثون
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.rag.sentence_embedder import SentenceTransformerEmbedder


async def ingest_clinic_knowledge(
    clinic_id: str,
    knowledge_texts: list[str],
    source_name: str = "custom_faq",
) -> None:
    """تشفير النصوص ورفعها لـ Qdrant مع وسم clinic_id الصارم."""
    if not knowledge_texts:
        print("⚠️ قائمة النصوص فارغة.")
        return

    print(f"🔄 جاري تجهيز ورفع {len(knowledge_texts)} مستند للعيادة [{clinic_id}]...")

    embedder = SentenceTransformerEmbedder()
    qdrant_url = getattr(settings, "QDRANT_HOST", getattr(settings, "QDRANT_URL", None))
    qdrant_api_key = getattr(settings, "QDRANT_API_KEY", None)

    client = AsyncQdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )
    collection_name = getattr(settings, "QDRANT_COLLECTION_NAME", "smile-care")

    points = []
    for text in knowledge_texts:
        clean_text = text.strip()
        if not clean_text:
            continue

        vector = await embedder.embed_single(clean_text)
        point_id = str(uuid.uuid4())

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "clinic_id": str(clinic_id),  # 🔒 وسام العزل الأمني في Qdrant
                    "page_content": clean_text,
                    "source": source_name,
                },
            )
        )

    await client.upsert(
        collection_name=collection_name,
        points=points,
    )

    print(f"✅ تم رفع وحفظ المعرفة بنجاح في Qdrant للعيادة: {clinic_id}")


# ── مثال تطبيقي للاستخدام المباشر ───────────────────────────────────────────
if __name__ == "__main__":
    # 1. ضع هنا الـ UUID الخاص بالعيادة المراد تزويدها بالمعلومات
    TARGET_CLINIC_ID = "ضع-هنا-UUID-العيادة"

    # 2. نصوص المعرفة والأسئلة الشائعة الخاصة بالعيادة
    clinic_specific_docs = [
        "موقع وعنوان العيادة: القاهرة، التجمع الخامس، شارع التسعين الشمالي، مول كايرو فيستيفال، الدور الثالث عيادة 302.",
        "رابط اللوكيشن على خريطة جوجل (GPS): https://maps.google.com/?q=30.0123,31.4321",
        "طرق السداد المتاحة: الدفع نقداً، بطاقات الائتمان (فيزا وماستركارد)، والتقسيط المباشر عبر تابي وفاليو بدون فوائد.",
        "تعليمات ما بعد تنظيف وتبييض الأسنان: تجنب المشروبات الملونة والتدخين لمدة 48 ساعة واستخدام معجون أسنان مخصص للأسنان الحساسة.",
        "تعليمات ما بعد خلع الضرس أو الجراحة: العض على الشاش لمدة ساعة، تجنب المضمضة العنيفة أو المشروبات الساخنة في أول 24 ساعة.",
    ]

    asyncio.run(
        ingest_clinic_knowledge(
            clinic_id=TARGET_CLINIC_ID,
            knowledge_texts=clinic_specific_docs,
            source_name="clinic_onboarding_guide",
        )
    )