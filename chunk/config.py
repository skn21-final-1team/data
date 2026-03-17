from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChunkResult:
    content: str
    index: int
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkerConfig:
    strategy_name: str
    chunk_size: int
    chunk_overlap: int
