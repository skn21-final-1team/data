from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from chunk.config import ChunkingRunResult


@dataclass(frozen=True)
class ChunkingMetrics:
    strategy_name: str
    source_id: str
    chunk_count: int
    total_chars: int
    avg_chunk_chars: float
    min_chunk_chars: int
    max_chunk_chars: int
    std_chunk_chars: float
    median_chunk_chars: float
    elapsed_seconds: float
    chars_per_second: float


@dataclass(frozen=True)
class StructureMetrics:
    strategy_name: str
    source_id: str
    paragraph_integrity: float
    sentence_integrity: float
    whitespace_structure: float
    list_like_integrity: float
    heading_integrity: float
    coverage: float
    boundary_quality: float
    avg_metadata_count: float


@dataclass(frozen=True)
class QualityMetrics:
    strategy_name: str
    source_id: str
    intra_similarity: float
    inter_similarity: float
    coherence_ratio: float
    coverage: float
    boundary_quality: float
    avg_metadata_count: float


# 재사용 패턴 (compute_structure / compute_quality 공통)
_SENTENCE_END = re.compile(r"[.!?。]\s*$")
_HEADING = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)
_BLANK_LINE = re.compile(r"\n\s*\n")
_LIST_GROUP = re.compile(r"(?:^\s*(?:[-*+]|\d+[.)]) .+$\n?){2,}", re.MULTILINE)
_BOUNDARY = re.compile(r"[.!?。]\s*$|^\s*$|\n\n|^#{1,6}\s", re.MULTILINE)


class ChunkingEvaluator:
    @staticmethod
    def compute_metrics(result: ChunkingRunResult) -> ChunkingMetrics:
        lengths = [len(c.content) for c in result.chunks]

        if not lengths:
            return ChunkingMetrics(
                strategy_name=result.strategy_name,
                source_id=result.source_id,
                chunk_count=0,
                total_chars=0,
                avg_chunk_chars=0.0,
                min_chunk_chars=0,
                max_chunk_chars=0,
                std_chunk_chars=0.0,
                median_chunk_chars=0.0,
                elapsed_seconds=result.elapsed_seconds,
                chars_per_second=0.0,
            )

        total = sum(lengths)
        return ChunkingMetrics(
            strategy_name=result.strategy_name,
            source_id=result.source_id,
            chunk_count=len(lengths),
            total_chars=total,
            avg_chunk_chars=statistics.mean(lengths),
            min_chunk_chars=min(lengths),
            max_chunk_chars=max(lengths),
            std_chunk_chars=statistics.stdev(lengths) if len(lengths) > 1 else 0.0,
            median_chunk_chars=statistics.median(lengths),
            elapsed_seconds=result.elapsed_seconds,
            chars_per_second=total / result.elapsed_seconds
            if result.elapsed_seconds > 0
            else 0.0,
        )

    @staticmethod
    def compute_all(results: list[ChunkingRunResult]) -> list[ChunkingMetrics]:
        return [ChunkingEvaluator.compute_metrics(r) for r in results]

    @staticmethod
    def compute_structure(
        result: ChunkingRunResult,
        original_text: str,
    ) -> StructureMetrics:
        chunks = result.chunks
        if not chunks:
            return StructureMetrics(
                strategy_name=result.strategy_name,
                source_id=result.source_id,
                paragraph_integrity=0.0,
                sentence_integrity=0.0,
                whitespace_structure=0.0,
                list_like_integrity=0.0,
                heading_integrity=0.0,
                coverage=0.0,
                boundary_quality=0.0,
                avg_metadata_count=0.0,
            )

        chunk_texts = [c.content for c in chunks]
        all_joined = "\n".join(chunk_texts)

        # 단락 보존율
        orig_paras = [
            p.strip() for p in re.split(r"\n\s*\n", original_text) if p.strip()
        ]
        if orig_paras:
            intact = sum(1 for p in orig_paras if any(p in ct for ct in chunk_texts))
            paragraph_integrity = intact / len(orig_paras)
        else:
            paragraph_integrity = 1.0

        # 문장 무결성
        intact_sent = sum(1 for ct in chunk_texts if _SENTENCE_END.search(ct))
        sentence_integrity = intact_sent / len(chunks)

        # 빈줄 구조 보존
        orig_blanks = len(_BLANK_LINE.findall(original_text))
        chunk_blanks = len(_BLANK_LINE.findall(all_joined))
        whitespace_structure = (
            min(chunk_blanks / orig_blanks, 1.0) if orig_blanks else 1.0
        )

        # 리스트 보존율
        orig_lists = _LIST_GROUP.findall(original_text)
        if orig_lists:
            intact = sum(
                1 for lst in orig_lists if any(lst.strip() in ct for ct in chunk_texts)
            )
            list_like_integrity = intact / len(orig_lists)
        else:
            list_like_integrity = 1.0

        # 헤더 보존율
        orig_headings = _HEADING.findall(original_text)
        if orig_headings:
            intact = sum(
                1 for h in orig_headings if any(h.strip() in ct for ct in chunk_texts)
            )
            heading_integrity = intact / len(orig_headings)
        else:
            heading_integrity = 1.0

        # 커버리지
        total_chars = sum(len(ct) for ct in chunk_texts)
        orig_chars = len(original_text)
        coverage = total_chars / orig_chars if orig_chars > 0 else 0.0

        # 경계 품질
        good = sum(1 for ct in chunk_texts if _BOUNDARY.search(ct))
        boundary_quality = good / len(chunks)

        avg_meta = statistics.mean([len(c.metadata) for c in chunks])

        return StructureMetrics(
            strategy_name=result.strategy_name,
            source_id=result.source_id,
            paragraph_integrity=round(paragraph_integrity, 4),
            sentence_integrity=round(sentence_integrity, 4),
            whitespace_structure=round(whitespace_structure, 4),
            list_like_integrity=round(list_like_integrity, 4),
            heading_integrity=round(heading_integrity, 4),
            coverage=round(coverage, 4),
            boundary_quality=round(boundary_quality, 4),
            avg_metadata_count=round(avg_meta, 2),
        )

    @staticmethod
    def compute_structure_all(
        results: list[ChunkingRunResult],
        original_text: str,
    ) -> list[StructureMetrics]:
        return [ChunkingEvaluator.compute_structure(r, original_text) for r in results]

    @staticmethod
    def compute_quality(
        result: ChunkingRunResult,
        original_text: str,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> QualityMetrics:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        chunks = result.chunks
        if not chunks:
            return QualityMetrics(
                strategy_name=result.strategy_name,
                source_id=result.source_id,
                intra_similarity=0.0,
                inter_similarity=0.0,
                coherence_ratio=0.0,
                coverage=0.0,
                boundary_quality=0.0,
                avg_metadata_count=0.0,
            )

        model = SentenceTransformer(model_name)

        # 청크 내 응집도
        intra_sims: list[float] = []
        for chunk in chunks:
            sentences = _split_sentences(chunk.content)
            if len(sentences) < 2:
                intra_sims.append(1.0)
                continue
            embeddings = model.encode(sentences)
            sim_matrix = np.inner(embeddings, embeddings)
            n = len(sentences)
            pair_sims = [
                float(sim_matrix[i][j]) for i in range(n) for j in range(i + 1, n)
            ]
            intra_sims.append(statistics.mean(pair_sims) if pair_sims else 1.0)
        intra_similarity = statistics.mean(intra_sims)

        # 인접 청크 간 분리도
        if len(chunks) < 2:
            inter_similarity = 0.0
        else:
            chunk_embeddings = model.encode([c.content for c in chunks])
            inter_sims = [
                float(np.inner(chunk_embeddings[i], chunk_embeddings[i + 1]))
                for i in range(len(chunk_embeddings) - 1)
            ]
            inter_similarity = statistics.mean(inter_sims)

        coherence_ratio = (
            intra_similarity / inter_similarity
            if inter_similarity > 0
            else float("inf")
        )

        # 커버리지 & 경계 (모듈 패턴 재사용)
        total_chars = sum(len(c.content) for c in chunks)
        orig_chars = len(original_text)
        coverage = total_chars / orig_chars if orig_chars > 0 else 0.0

        good = sum(1 for c in chunks if _SENTENCE_END.search(c.content))
        boundary_quality = good / len(chunks)

        avg_meta = statistics.mean([len(c.metadata) for c in chunks])

        return QualityMetrics(
            strategy_name=result.strategy_name,
            source_id=result.source_id,
            intra_similarity=round(intra_similarity, 4),
            inter_similarity=round(inter_similarity, 4),
            coherence_ratio=round(coherence_ratio, 4),
            coverage=round(coverage, 4),
            boundary_quality=round(boundary_quality, 4),
            avg_metadata_count=round(avg_meta, 2),
        )

    @staticmethod
    def compute_quality_all(
        results: list[ChunkingRunResult],
        original_text: str,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> list[QualityMetrics]:
        return [
            ChunkingEvaluator.compute_quality(r, original_text, model_name)
            for r in results
        ]

    # --- 비교 테이블 ---

    @staticmethod
    def compare(metrics_list: list[ChunkingMetrics]) -> str:
        if not metrics_list:
            return "비교할 메트릭이 없습니다."

        header = (
            f"{'Strategy':<25} {'Source':<10} {'Chunks':>7} "
            f"{'Avg':>8} {'Min':>6} {'Max':>6} {'StdDev':>8} "
            f"{'Time(s)':>9} {'Chars/s':>10}"
        )
        separator = "-" * len(header)
        lines = [header, separator]

        for m in metrics_list:
            lines.append(
                f"{m.strategy_name:<25} {m.source_id:<10} {m.chunk_count:>7} "
                f"{m.avg_chunk_chars:>8.1f} {m.min_chunk_chars:>6} "
                f"{m.max_chunk_chars:>6} {m.std_chunk_chars:>8.1f} "
                f"{m.elapsed_seconds:>9.4f} {m.chars_per_second:>10.0f}"
            )

        return "\n".join(lines)

    @staticmethod
    def compare_structure(structure_list: list[StructureMetrics]) -> str:
        if not structure_list:
            return "비교할 구조 메트릭이 없습니다."

        header = (
            f"{'Strategy':<25} {'Para':>7} {'Sent':>7} "
            f"{'WSpace':>7} {'List':>7} {'Head':>7} {'Cover':>7} {'BndQlt':>7} {'Meta':>6}"
        )
        separator = "-" * len(header)
        lines = [header, separator]

        for s in structure_list:
            lines.append(
                f"{s.strategy_name:<25} {s.paragraph_integrity:>7.2%} "
                f"{s.sentence_integrity:>7.2%} {s.whitespace_structure:>7.2%} "
                f"{s.list_like_integrity:>7.2%} {s.heading_integrity:>7.2%} "
                f"{s.coverage:>7.2%} {s.boundary_quality:>7.2%} {s.avg_metadata_count:>6.1f}"
            )

        return "\n".join(lines)

    @staticmethod
    def compare_quality(quality_list: list[QualityMetrics]) -> str:
        if not quality_list:
            return "비교할 품질 메트릭이 없습니다."

        header = (
            f"{'Strategy':<25} {'Intra':>7} {'Inter':>7} "
            f"{'Ratio':>7} {'Cover':>7} {'BndQlt':>7} {'Meta':>6}"
        )
        separator = "-" * len(header)
        lines = [header, separator]

        for q in quality_list:
            ratio_str = (
                f"{q.coherence_ratio:>7.2f}"
                if q.coherence_ratio != float("inf")
                else "    inf"
            )
            lines.append(
                f"{q.strategy_name:<25} {q.intra_similarity:>7.4f} "
                f"{q.inter_similarity:>7.4f} {ratio_str} "
                f"{q.coverage:>7.2%} {q.boundary_quality:>7.2%} "
                f"{q.avg_metadata_count:>6.1f}"
            )

        return "\n".join(lines)

    # --- 분석 리포트 생성 ---

    @staticmethod
    def generate_analysis(total_rows: list[dict[str, str | float]]) -> str:
        def _best(key: str, *, higher_is_better: bool = True) -> tuple[str, float]:
            if higher_is_better:
                row = max(total_rows, key=lambda r: float(r[key]))
            else:
                row = min(total_rows, key=lambda r: float(r[key]))
            return str(row["strategy"]), float(row[key])

        def _closest_to(key: str, target: float) -> tuple[str, float]:
            row = min(total_rows, key=lambda r: abs(float(r[key]) - target))
            return str(row["strategy"]), float(row[key])

        def _pct(v: float) -> str:
            return f"{v:.1%}"

        lines: list[str] = []
        lines.append("# 청킹 전략 분석 요약\n")

        lines.append("## 1. 구조 보존 관점 (높을수록 좋음)\n")
        for label, key in [
            ("단락 보존", "paragraph"),
            ("문장 무결성", "sentence"),
            ("공백 구조 보존", "whitespace"),
            ("리스트 보존", "list"),
            ("헤더 보존", "heading"),
        ]:
            name, val = _best(key)
            lines.append(f"- **{label}**: {name} ({_pct(val)})")
        lines.append("")

        lines.append("## 2. 커버리지 관점 (1.0에 가까울수록 좋음)\n")
        name, val = _closest_to("coverage", 1.0)
        lines.append(f"- **최적 커버리지**: {name} ({_pct(val)})")
        worst = max(total_rows, key=lambda r: abs(float(r["coverage"]) - 1.0))
        lines.append(
            f"- **과다/손실 주의**: {worst['strategy']} "
            f"({_pct(float(worst['coverage']))})"
        )
        lines.append("")

        lines.append("## 3. 경계 품질 관점 (높을수록 좋음)\n")
        name, val = _best("boundary")
        lines.append(f"- **최적 경계**: {name} ({_pct(val)})")
        worst_name, worst_val = _best("boundary", higher_is_better=False)
        lines.append(f"- **경계 주의**: {worst_name} ({_pct(worst_val)})")
        lines.append("")

        lines.append("## 4. 청크 크기 균일성 (std_chars 낮을수록 좋음)\n")
        name, val = _best("std_chars", higher_is_better=False)
        lines.append(f"- **가장 균일**: {name} (std={val:.1f})")
        lines.append("")

        lines.append("## 5. 종합 추천\n")
        scores: dict[str, float] = {}
        for row in total_rows:
            s = str(row["strategy"])
            struct_avg = (
                float(row["paragraph"])
                + float(row["sentence"])
                + float(row["whitespace"])
                + float(row["list"])
                + float(row["heading"])
            ) / 5
            scores[s] = (
                struct_avg + float(row["boundary"]) - abs(float(row["coverage"]) - 1.0)
            )

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (name, _score) in enumerate(ranked, 1):
            row = next(r for r in total_rows if r["strategy"] == name)
            marker = " <-- 추천" if rank == 1 else ""
            struct = (
                float(row["paragraph"])
                + float(row["sentence"])
                + float(row["whitespace"])
                + float(row["list"])
                + float(row["heading"])
            ) / 5
            lines.append(
                f"{rank}. **{name}** "
                f"(구조={_pct(struct)} "
                f"커버리지={_pct(float(row['coverage']))} "
                f"경계={_pct(float(row['boundary']))}){marker}"
            )

        lines.append("")
        lines.append("---")
        lines.append(
            "*이 분석은 구조 보존 + 경계 품질 + 커버리지 근접도를 기반으로 산출되었습니다. "
            "최종 판단은 임베딩 후 retrieval 성능으로 결정하세요.*"
        )

        return "\n".join(lines)


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?。])\s+", text.strip())
    return [s for s in sentences if len(s.strip()) > 5]
