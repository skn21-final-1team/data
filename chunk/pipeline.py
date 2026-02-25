from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from chunk.base import BaseChunker
from chunk.config import ChunkingRunResult, TextSource
from chunk.evaluator import ChunkingEvaluator


class ChunkingPipeline:
    def __init__(
        self,
        sources: list[TextSource],
        chunkers: list[BaseChunker],
        output_dir: Path = Path("chunk/output"),
        preprocessor: Callable[[str], str] | None = None,
    ) -> None:
        self.sources = sources
        self.chunkers = chunkers
        self.output_dir = output_dir
        self.preprocessor = preprocessor

    def run(self) -> list[ChunkingRunResult]:
        results: list[ChunkingRunResult] = []
        for source in self.sources:
            content = (
                self.preprocessor(source.content)
                if self.preprocessor
                else source.content
            )
            for chunker in self.chunkers:
                start = time.perf_counter()
                chunks = chunker.chunk(content)
                elapsed = time.perf_counter() - start
                results.append(
                    ChunkingRunResult(
                        strategy_name=chunker.name,
                        source_id=source.source_id,
                        chunks=chunks,
                        elapsed_seconds=elapsed,
                        config_snapshot=asdict(chunker.config),
                    )
                )
        return results

    def save_results(
        self,
        results: list[ChunkingRunResult],
        original_texts: dict[str, str],
        output_root: Path | None = None,
    ) -> Path:
        output_root = output_root or self.output_dir
        source_map = {s.source_id: s for s in self.sources}

        by_strategy: dict[str, list[ChunkingRunResult]] = {}
        for r in results:
            by_strategy.setdefault(r.strategy_name, []).append(r)

        strategy_agg: dict[str, list[dict[str, float]]] = {}

        for strategy_name, strat_results in by_strategy.items():
            strategy_dir = output_root / strategy_name
            strategy_dir.mkdir(parents=True, exist_ok=True)

            by_notebook: dict[str, list[dict]] = {}
            eval_rows: list[dict] = []

            for r in strat_results:
                src = source_map.get(r.source_id)
                nb_key = (
                    str(src.notebook_id)
                    if (src and src.notebook_id is not None)
                    else "unknown"
                )
                url = src.url if src else ""
                original = original_texts.get(r.source_id, "")

                for c in r.chunks:
                    by_notebook.setdefault(nb_key, []).append(
                        {
                            "index": c.index,
                            "notebook_id": src.notebook_id if src else None,
                            "source_id": r.source_id,
                            "url": url,
                            "content": c.content,
                            "metadata": c.metadata,
                        }
                    )

                basic = ChunkingEvaluator.compute_metrics(r)
                structure = ChunkingEvaluator.compute_structure(r, original)

                eval_rows.append(
                    {
                        "source_id": r.source_id,
                        "notebook_id": src.notebook_id if src else None,
                        "url": url,
                        "basic": asdict(basic),
                        "structure": asdict(structure),
                    }
                )

                strategy_agg.setdefault(strategy_name, []).append(
                    {
                        "chunks": basic.chunk_count,
                        "avg_chars": basic.avg_chunk_chars,
                        "std_chars": basic.std_chunk_chars,
                        "paragraph": structure.paragraph_integrity,
                        "sentence": structure.sentence_integrity,
                        "whitespace": structure.whitespace_structure,
                        "list": structure.list_like_integrity,
                        "heading": structure.heading_integrity,
                        "coverage": structure.coverage,
                        "boundary": structure.boundary_quality,
                        "time_s": basic.elapsed_seconds,
                    }
                )

            for nb_key, chunks in by_notebook.items():
                nb_path = strategy_dir / f"notebook_{nb_key}__chunks.json"
                nb_path.write_text(
                    json.dumps(
                        {
                            "notebook_id": nb_key,
                            "strategy_name": strategy_name,
                            "chunk_count": len(chunks),
                            "chunks": chunks,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            (strategy_dir / "eval.json").write_text(
                json.dumps(
                    {
                        "strategy_name": strategy_name,
                        "source_count": len(strat_results),
                        "sources": eval_rows,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        self._save_comparison(output_root, strategy_agg)
        return output_root

    def _save_comparison(
        self,
        output_root: Path,
        strategy_agg: dict[str, list[dict[str, float]]],
    ) -> None:
        if not strategy_agg:
            return

        metric_keys = [
            "chunks",
            "avg_chars",
            "std_chars",
            "paragraph",
            "sentence",
            "whitespace",
            "list",
            "heading",
            "coverage",
            "boundary",
            "time_s",
        ]

        rows: list[dict[str, str | float]] = []
        for strategy, docs in strategy_agg.items():
            row: dict[str, str | float] = {"strategy": strategy, "doc_count": len(docs)}
            for key in metric_keys:
                values = [d[key] for d in docs]
                row[key] = round(sum(values) / len(values), 4)
            rows.append(row)

        csv_path = output_root / "comparison.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["strategy", "doc_count", *metric_keys]
            )
            writer.writeheader()
            writer.writerows(rows)

        analysis = ChunkingEvaluator.generate_analysis(rows)
        (output_root / "total_analysis.md").write_text(analysis, encoding="utf-8")

    # --- Data loaders ---

    @staticmethod
    def load_from_db() -> list[TextSource]:
        from crud.source import get_sources_with_summary
        from db.database import get_db_context

        sources: list[TextSource] = []
        with get_db_context() as db:
            for row in get_sources_with_summary(db):
                sources.append(
                    TextSource(
                        source_id=str(row.id),
                        title=row.title or "",
                        content=row.summary or "",
                        notebook_id=row.notebook_id,
                        url=row.url or "",
                    )
                )
        return sources

    @staticmethod
    def load_from_files(
        directory: Path, glob_pattern: str = "*.md"
    ) -> list[TextSource]:
        sources: list[TextSource] = []
        for filepath in sorted(directory.glob(glob_pattern)):
            content = filepath.read_text(encoding="utf-8")
            sources.append(
                TextSource(
                    source_id=filepath.stem,
                    title=filepath.name,
                    content=content,
                )
            )
        return sources

    @staticmethod
    def load_from_string(text: str, source_id: str = "inline") -> list[TextSource]:
        return [TextSource(source_id=source_id, title=source_id, content=text)]
