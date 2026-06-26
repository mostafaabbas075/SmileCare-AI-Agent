"""
Abstract embedder base class.

Defines the interface all embedding implementations must satisfy.
The default implementation will use Sentence Transformers, but this
abstraction allows swapping to OpenAI embeddings, Vertex AI, etc.
without touching any RAG or agent code.

When implementing the real embedder:

    class SentenceTransformerEmbedder(BaseEmbedder):
        def __init__(self, model_name: str) -> None:
            self._model = SentenceTransformer(model_name)

        async def embed(self, texts: list[str]) -> list[list[float]]:
            return self._model.encode(texts).tolist()
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: One or more text strings to embed.

        Returns:
            A list of float vectors, one per input text.
            All vectors must have the same dimension.
        """
        ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text string.

        Convenience wrapper around ``embed()`` for the common single-query case.
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension.

        Used when creating or verifying the Qdrant collection schema.
        """
        ...
