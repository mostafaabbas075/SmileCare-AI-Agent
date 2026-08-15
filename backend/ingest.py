import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── 1. إعدادات الربط مع Qdrant Cloud ─────────────────────────────────────────
QDRANT_URL = "https://12b0e12a-bd98-4dd2-813f-38438624c4dc.us-east-2-0.aws.cloud.qdrant.io"      # مثال: https://xxxxxx.us-east-1-0.aws.cloud.qdrant.io
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6NTkxM2VjYTMtYmZiZC00NWNmLTg3NWItMDFiYzlhMTQ2MmIwIn0.UKpM5Vm2WjdnK74eqxafC6UbgogzGT9gyr3vyETkmxs"         # الـ API Key الخاص بك على Qdrant Cloud
COLLECTION_NAME = "smile-care"                 # اسم الكوليكشن الخاص بك
FILE_PATH = r"C:\Users\S\Downloads\smile-care.txt"             # مسار الملف النصي

def main():
    if not os.path.exists(FILE_PATH):
        print(f"❌ لم يتم العثور على الملف '{FILE_PATH}'! تأكد من وجوده في نفس المجلد.")
        return

    print("📄 جاري قراءة الملف النصي...")
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        file_content = f.read()

    print("🚀 جاري الاتصال بـ Qdrant Cloud وتحميل نموذج الـ Embeddings...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # استخدام نفس نموذج الـ Embeddings المقترن بالنظام
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    # تقسيم النص إلى مقاطع صغيرة (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50
    )
    chunks = text_splitter.split_text(file_content)
    print(f"📦 تم تقسيم الملف إلى {len(chunks)} مقاطع نصية.")

    # تحويل المقاطع النصية لمتجهات وإعداد النقاط للرفع
    points = []
    for idx, chunk in enumerate(chunks):
        vector = embedder.encode(chunk).tolist()
        point = PointStruct(
            id=idx + 1,
            vector=vector,
            payload={
                "page_content": chunk,
                "source": FILE_PATH
            }
        )
        points.append(point)

    print(f"📤 جاري رفع المتجهات إلى كوليكشن ({COLLECTION_NAME})...")
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )
    print("🎉 تم رفع وتحديث بيانات المعرفة بنجاح على Qdrant Cloud!")

if __name__ == "__main__":
    main()