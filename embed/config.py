from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class EmbedderConfig:
    model_name: str
    dimension: int
    batch_size: int = 32
    normalize: bool = True


@dataclass
class EmbeddingResult:
    source_id: str
    chunk_index: int
    vector: list[float]
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
