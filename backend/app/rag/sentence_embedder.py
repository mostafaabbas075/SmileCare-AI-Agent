from __future__ import annotations

import asyncio
import os
import google.generativeai as genai

from app.rag.base_embedder import BaseEmbedder


class GeminiEmbedder(BaseEmbedder):
    """Concrete implementation using Google Gemini Embeddings API."""

    def __init__(
        self,
        model_name: str = "models/text-embedding-004",
        api_key: str | None = None,
    ) -> None:
        """Initialize the Gemini embedder with API key."""
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set in environment variables.")

        genai.configure(api_key=key)
        self._model_name = model_name
        self._dimension = 768  # أبعاد مخرجات text-embedding-004

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously using Gemini API."""
        if not texts:
            return []

        def _call_api():
            result = genai.embed_content(
                model=self._model_name,
                content=texts,
                task_type="retrieval_document",
            )
            return result["embedding"]

        return await asyncio.to_thread(_call_api)

    async def embed_single(self, text: str) -> list[float]:
        """Convenience wrapper for a single query string."""
        def _call_api():
            result = genai.embed_content(
                model=self._model_name,
                content=text,
                task_type="retrieval_query",
            )
            return result["embedding"]

        return await asyncio.to_thread(_call_api)

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension


# سطر بديل (Alias) لضمان عمل أي ملف قديم يستدعي الاسم السابق دون تعديل
SentenceTransformerEmbedder = GeminiEmbedder