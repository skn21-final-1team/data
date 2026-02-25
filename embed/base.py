from __future__ import annotations

from abc import ABC, abstractmethod

from embed.config import EmbedderConfig


class BaseEmbedder(ABC):
    def __init__(self, config: EmbedderConfig) -> None:
        self.config = config

    @abstractmethod
    def embed(
        self, texts: list[str], show_progress_bar: bool = True
    ) -> list[list[float]]:
        """텍스트 목록을 벡터 목록으로 변환한다."""
        ...

    @property
    def name(self) -> str:
        return self.config.model_name

    @property
    def dimension(self) -> int:
        return self.config.dimension
