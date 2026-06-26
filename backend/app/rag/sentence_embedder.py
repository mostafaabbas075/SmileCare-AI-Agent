import asyncio
from sentence_transformers import SentenceTransformer
# تأكد من تعديل مسار الاستدعاء حسب اسم الملف الذي يحتوي على BaseEmbedder
from app.rag.base_embedder import BaseEmbedder 

class SentenceTransformerEmbedder(BaseEmbedder):
    """Concrete implementation using HuggingFace's SentenceTransformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the embedder and load the model into memory."""
        # تحميل الموديل في الذاكرة (سيقوم بتحميله من الإنترنت في أول مرة فقط)
        self._model = SentenceTransformer(model_name)
        
        # استخراج البُعد (Dimension) ديناميكياً من الموديل
        self._dimension = self._model.get_sentence_embedding_dimension()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously to avoid blocking FastAPI."""
        
        # استخدام asyncio.to_thread لتشغيل عملية الـ Encoding (CPU-bound) في مسار منفصل
        embeddings = await asyncio.to_thread(self._model.encode, texts)
        
        return embeddings.tolist()

    async def embed_single(self, text: str) -> list[float]:
        """Convenience wrapper for a single string."""
        vectors = await self.embed([text])
        return vectors[0]

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension