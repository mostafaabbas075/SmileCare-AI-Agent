"""
Multi-Tenant Clinic Context Retriever (Qdrant Cloud RAG Integration).

Fetches semantic medical context, FAQs, and clinic background info for the AI Agent
from Qdrant Vector Database with strict tenant isolation (clinic_id filtering).
"""

from __future__ import annotations

import uuid
from typing import Any
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.core.config import settings
from app.rag.base_embedder import BaseEmbedder

logger = structlog.get_logger(__name__)


class ClinicRetriever:
    def __init__(self, embedder: BaseEmbedder):
        self.embedder = embedder

        # الربط مع Qdrant Cloud باستخدام QDRANT_HOST أو QDRANT_URL
        qdrant_url = getattr(settings, "QDRANT_HOST", getattr(settings, "QDRANT_URL", None))
        qdrant_api_key = getattr(settings, "QDRANT_API_KEY", None)

        self.client = AsyncQdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )

        # قراءة اسم الكوليكشن من ملف الإعدادات
        self.collection_name = getattr(
            settings,
            "QDRANT_COLLECTION_NAME",
            getattr(settings, "qdrant_collection_name", "smile-care"),
        )

    async def search(
        self,
        text_query: str,
        clinic_id: uuid.UUID | str | None = None,
        limit: int = 3,
    ) -> str:
        """
        يبحث دلالياً عن المعلومات لسؤال المريض مع تطبيق عزل العيادة (Tenant Filtering).
        """
        try:
            query_vector = await self.embedder.embed_single(text_query)

            # 🔒 تطبيق فلتر العزل حسب معرف العيادة (Tenant Isolation Filter)
            query_filter = None
            if clinic_id:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="clinic_id",
                            match=MatchValue(value=str(clinic_id)),
                        )
                    ]
                )

            # البحث في Qdrant Cloud باستخدام query_points مع الفلترة
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
            )

            results = response.points

            if not results:
                return ""

            # تجميع النصوص المستخرجة
            extracted_texts = []
            for hit in results:
                if not hit.payload:
                    continue

                content = (
                    hit.payload.get("page_content")
                    or hit.payload.get("text")
                    or hit.payload.get("content")
                    or hit.payload.get("document")
                    or ""
                )
                if content.strip():
                    extracted_texts.append(content.strip())

            context = "\n---\n".join(extracted_texts)
            return context

        except Exception as e:
            logger.error(
                "qdrant_tenant_search_failed",
                error=str(e),
                collection=self.collection_name,
                clinic_id=str(clinic_id) if clinic_id else None,
            )
            return ""