"""Lazy local Sentence Transformers adapter behind a narrow protocol."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from ..evidence.errors import EmbeddingProviderError


class EmbeddingProvider(Protocol):
    def encode_documents(self, texts: Sequence[str]) -> NDArray[np.floating]: ...

    def encode_queries(self, texts: Sequence[str]) -> NDArray[np.floating]: ...


class SentenceTransformerEmbeddingProvider:
    """Load a pinned model only when an encoding method is first called."""

    def __init__(
        self,
        model_name: str,
        revision: str,
        model_path: Path | None,
        *,
        local_only: bool,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self.model_path = model_path
        self.local_only = local_only
        self._model: object | None = None

    def encode_documents(self, texts: Sequence[str]) -> NDArray[np.floating]:
        model = self._load()
        return np.asarray(
            model.encode_document(
                list(texts), convert_to_numpy=True, normalize_embeddings=False,
                show_progress_bar=False,
            ),
            dtype=float,
        )

    def encode_queries(self, texts: Sequence[str]) -> NDArray[np.floating]:
        model = self._load()
        return np.asarray(
            model.encode_query(
                list(texts), convert_to_numpy=True, normalize_embeddings=False,
                show_progress_bar=False,
            ),
            dtype=float,
        )

    def _load(self) -> object:
        if self._model is not None:
            return self._model
        if (
            self.model_path is not None
            and self.model_path.is_dir()
            and (self.model_path / "config.json").is_file()
        ):
            source = str(self.model_path)
            revision = None
        else:
            if self.local_only and self.model_path is not None:
                raise EmbeddingProviderError(
                    "Local embedding model is missing. Run prepare_embedding_model."
                )
            source = self.model_name
            revision = self.revision
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(
                source,
                revision=revision,
                local_files_only=self.local_only,
                trust_remote_code=False,
                device="cpu",
            )
            model.eval()
        except Exception as exc:
            raise EmbeddingProviderError(
                "Unable to load the configured local embedding model."
            ) from exc
        self._model = model
        return model
