from qdrant_client import AsyncQdrantClient
from app.rag.base_embedder import BaseEmbedder
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

class ClinicRetriever:
    def __init__(self, embedder: BaseEmbedder):
        self.embedder = embedder
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL) 
        self.collection_name = settings.qdrant_collection_name

    async def search(self, text_query: str, limit: int = 3) -> str:
        """يبحث عن أقرب المعلومات لسؤال المريض ويرجعها كنص (Context)"""
        try:
            query_vector = await self.embedder.embed_single(text_query)
            
            # رجعنا لدالة search المتوافقة مع سيرفرك (إصدار 1.9.2)
            results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit
            )
            
            if not results:
                return ""
                
            # تجميع النصوص المستخرجة
            context = "\n---\n".join([hit.payload.get("page_content", "") for hit in results])
            return context
            
        except Exception as e:
            logger.error("qdrant_search_failed", error=str(e))
            return ""