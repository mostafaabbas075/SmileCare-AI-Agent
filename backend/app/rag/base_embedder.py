"""
Abstract Base Class for Embedding Providers.

Defines the contract for text-to-vector embedding models used in the RAG pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Abstract interface for all embedding models."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for a list of strings.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (float lists).
        """
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """
        Generate an embedding vector for a single string.

        Args:
            text: Query or sentence to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality of the embedding model."""
        pass