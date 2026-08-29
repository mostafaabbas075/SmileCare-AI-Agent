from __future__ import annotations

import os
import asyncio
from google import genai
from google.genai import types

from .base import BaseEmbedder  # تأكد من مسار الاستيراد الصحيح لـ BaseEmbedder


class GeminiEmbedder(BaseEmbedder):
    """Google Gemini Text Embeddings implementation."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "text-embedding-004",
    ) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY must be provided or set in environment variables.")

        self.client = genai.Client(api_key=key)
        self.model_name = model_name
        self._dimension = 768  # أبعاد مخرجات text-embedding-004

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts asynchronously."""
        if not texts:
            return []

        # تشغيل طلب الـ API داخل Thread pool لعدم تعطيل الـ Event Loop
        response = await asyncio.to_thread(
            self.client.models.embed_content,
            model=self.model_name,
            contents=texts,
        )
        return [e.values for e in response.embeddings]

    async def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text string."""
        response = await asyncio.to_thread(
            self.client.models.embed_content,
            model=self.model_name,
            contents=text,
        )
        return response.embeddings[0].values