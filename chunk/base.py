from __future__ import annotations

from abc import ABC, abstractmethod

from chunk.config import ChunkerConfig, ChunkResult


class BaseChunker(ABC):
    def __init__(self, config: ChunkerConfig) -> None:
        self.config = config

    @abstractmethod
    def chunk(self, text: str) -> list[ChunkResult]: ...

    @property
    def name(self) -> str:
        return self.config.strategy_name
