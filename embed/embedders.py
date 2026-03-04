from __future__ import annotations

from sentence_transformers import SentenceTransformer

from core.device import get_device
from embed.base import BaseEmbedder
from embed.config import EmbedderConfig


class BgeM3Embedder(BaseEmbedder):
    """BAAI/bge-m3 (1024차원, 다국어, 8192 토큰)."""

    def __init__(
        self,
        config: EmbedderConfig | None = None,
        batch_size: int = 32,
    ) -> None:
        config = config or EmbedderConfig(
            model_name="BAAI/bge-m3",
            dimension=1024,
            batch_size=batch_size,
        )
        super().__init__(config)
        self._model = SentenceTransformer(config.model_name, device=get_device())

    def embed(
        self, texts: list[str], show_progress_bar: bool = True
    ) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize,
            show_progress_bar=show_progress_bar,
        )
        return vectors.tolist()


class MultilingualE5Embedder(BaseEmbedder):
    """intfloat/multilingual-e5-large (1024차원, 다국어, 512 토큰)."""

    PREFIX = "query: "

    def __init__(
        self,
        config: EmbedderConfig | None = None,
        batch_size: int = 32,
    ) -> None:
        config = config or EmbedderConfig(
            model_name="intfloat/multilingual-e5-large",
            dimension=1024,
            batch_size=batch_size,
        )
        super().__init__(config)
        self._model = SentenceTransformer(config.model_name, device=get_device())

    def embed(
        self, texts: list[str], show_progress_bar: bool = True
    ) -> list[list[float]]:
        prefixed = [f"{self.PREFIX}{t}" for t in texts]
        vectors = self._model.encode(
            prefixed,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize,
            show_progress_bar=show_progress_bar,
        )
        return vectors.tolist()
