"""Public sparse and dense retrieval services."""

from .dense import retrieve_dense
from .embeddings import EmbeddingProvider, SentenceTransformerEmbeddingProvider
from .sparse import retrieve_sparse

__all__ = [
    "EmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "retrieve_dense",
    "retrieve_sparse",
]
