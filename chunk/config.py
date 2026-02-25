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


@dataclass
class TextSource:
    source_id: str
    title: str
    content: str
    notebook_id: int | None = None
    url: str = ""


@dataclass
class ChunkingRunResult:
    strategy_name: str
    source_id: str
    chunks: list[ChunkResult]
    elapsed_seconds: float
    config_snapshot: dict[str, str | int]
