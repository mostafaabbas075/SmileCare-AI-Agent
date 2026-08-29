from __future__ import annotations

import asyncio
import os
import structlog
import google.generativeai as genai

from app.rag.base_embedder import BaseEmbedder

logger = structlog.get_logger(__name__)


class GeminiEmbedder(BaseEmbedder):
    """Concrete implementation using Google Gemini Embeddings API."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize the Gemini embedder with API key and robust model resolution."""
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set in environment variables.")

        genai.configure(api_key=key)

        # قراءة الموديل من متغيرات البيئة أو استخدام القيمة الافتراضية
        raw_model = model_name or os.getenv("EMBEDDING_MODEL") or "text-embedding-004"
        
        # تنظيف اسم الموديل لضمان التوافق التام مع الـ API
        self._model_name = raw_model.replace("models/", "").strip()
        self._dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    def _get_embedding_with_fallback(self, content: str | list[str], task_type: str):
        """محاولة التضمين مع التحويل التلقائي في حال وجود مشكلة في اسم الموديل."""
        models_to_try = [
            f"models/{self._model_name}",
            self._model_name,
            "models/text-embedding-004",
            "text-embedding-004",
            "models/embedding-001",
        ]

        last_error = None
        for model in models_to_try:
            try:
                result = genai.embed_content(
                    model=model,
                    content=content,
                    task_type=task_type,
                )
                return result["embedding"]
            except Exception as e:
                last_error = e
                continue

        raise last_error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously using Gemini API."""
        if not texts:
            return []

        def _call_api():
            return self._get_embedding_with_fallback(
                content=texts,
                task_type="retrieval_document",
            )

        return await asyncio.to_thread(_call_api)

    async def embed_single(self, text: str) -> list[float]:
        """Convenience wrapper for a single query string."""
        if not text:
            return [0.0] * self._dimension

        def _call_api():
            return self._get_embedding_with_fallback(
                content=text,
                task_type="retrieval_query",
            )

        return await asyncio.to_thread(_call_api)

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension


# Alias لضمان عمل أي ملف قديم يستدعي الاسم السابق
SentenceTransformerEmbedder = GeminiEmbedder