"""청킹 + 임베딩 실험 → page_data DB 적재 (backend 연동 없이 독립 실행).

전략·모델을 바꿔가며 page_data를 재적재할 수 있다.
--test 플래그로 page_data_test 테이블에 적재하여 본 테이블에 영향을 주지 않는다.

사용법::

    # 테스트 테이블에 적재 (기본: markdown / bge-m3 / 1000 / 100)
    uv run python -m test.test_ce 3 --test

    # 전략 변경
    uv run python -m test.test_ce 3 --test --strategy recursive --chunk_size 500 --chunk_overlap 50

    # 기존 데이터 삭제 후 재적재
    uv run python -m test.test_ce 3 --test --clear

    # 특정 source 제외
    uv run python -m test.test_ce 3 --test --exclude 20 42 45 47 48 53

    # 테스트 테이블 삭제
    uv run python -m test.test_ce 3 --test --drop

    # 본 테이블에 적재 (주의)
    uv run python -m test.test_ce 3

전략 목록:
    recursive        S1  RecursiveCharacterTextSplitter
    token            S2  TokenTextSplitter (tiktoken, dev 의존성)
    semantic         S3  SemanticChunker (langchain-experimental, dev 의존성)
    markdown_header  S4  MarkdownHeaderTextSplitter
    markdown         S5  MarkdownTextSplitter
    hierarchical     S6  MarkdownHeader → RecursiveCharacter 재분할

임베딩 모델:
    bge-m3     BAAI/bge-m3 (1024d)
    e5-large   intfloat/multilingual-e5-large (1024d)
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import BigInteger, Column, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from chunk.config import ChunkerConfig
from chunk.preprocess import MarkdownPreprocessor
from chunk.strategies import (
    HierarchicalMarkdownChunker,
    MarkdownChunker,
    MarkdownHeaderChunker,
    RecursiveChunker,
    SemanticChunker,
    TokenChunker,
)
from db.database import Base, engine, get_db_context
from embed.embedders import BgeM3Embedder, MultilingualE5Embedder
from models.page_data import EMBEDDING_DIMENSION, PageDataModel
from models.source import SourceModel

sys.stdout.reconfigure(encoding="utf-8")

STRATEGY_MAP: dict[str, type] = {
    "recursive": RecursiveChunker,
    "token": TokenChunker,
    "semantic": SemanticChunker,
    "markdown_header": MarkdownHeaderChunker,
    "markdown": MarkdownChunker,
    "hierarchical": HierarchicalMarkdownChunker,
}

EMBED_MAP: dict[str, type] = {
    "bge-m3": BgeM3Embedder,
    "e5-large": MultilingualE5Embedder,
}

EXCLUDE_IDS = [20, 42, 45, 47, 48, 53]


class PageDataTestModel(Base):
    """실험용 page_data_test 테이블."""

    __tablename__ = "page_data_test"

    id = Column(BigInteger, primary_key=True, index=True)
    source_id = Column(
        BigInteger,
        ForeignKey("source.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=True)

    __table_args__ = (
        Index(
            "ix_page_data_test_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


def ensure_test_table() -> None:
    PageDataTestModel.__table__.create(engine, checkfirst=True)
    print("[테이블] page_data_test 준비 완료")


def drop_test_table() -> None:
    PageDataTestModel.__table__.drop(engine, checkfirst=True)
    print("[테이블] page_data_test 삭제 완료")


def get_sources(notebook_id: int, exclude_ids: list[int]) -> list[SourceModel]:
    with get_db_context() as db:
        query = db.query(SourceModel).filter(
            SourceModel.notebook_id == notebook_id,
            SourceModel.summary.is_not(None),
            func.length(SourceModel.summary) > 10,
        )
        if exclude_ids:
            query = query.filter(SourceModel.id.not_in(exclude_ids))
        sources = query.all()
        db.expunge_all()
    return sources


def clear_data(source_ids: list[int], use_test: bool) -> int:
    model = PageDataTestModel if use_test else PageDataModel
    with get_db_context() as db:
        deleted = (
            db.query(model)
            .filter(model.source_id.in_(source_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
    return deleted


def bulk_insert(
    source_id: int, chunks: list[str], embeddings: list[list[float]], use_test: bool
) -> int:
    model = PageDataTestModel if use_test else PageDataModel
    records = [
        model(source_id=source_id, chunk_text=ct, embedding=emb)
        for ct, emb in zip(chunks, embeddings)
    ]
    with get_db_context() as db:
        db.add_all(records)
        db.commit()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="청킹 + 임베딩 → page_data 적재")
    parser.add_argument("notebook_id", type=int, help="대상 notebook ID")
    parser.add_argument(
        "--strategy",
        choices=STRATEGY_MAP.keys(),
        default="markdown",
        help="청킹 전략 (기본: markdown)",
    )
    parser.add_argument(
        "--chunk_size", type=int, default=1000, help="청크 크기 (기본: 1000)"
    )
    parser.add_argument(
        "--chunk_overlap", type=int, default=100, help="청크 오버랩 (기본: 100)"
    )
    parser.add_argument(
        "--embed_model",
        choices=EMBED_MAP.keys(),
        default="bge-m3",
        help="임베딩 모델 (기본: bge-m3)",
    )
    parser.add_argument(
        "--test", action="store_true", help="page_data_test 테이블 사용"
    )
    parser.add_argument(
        "--clear", action="store_true", help="기존 데이터 삭제 후 재적재"
    )
    parser.add_argument(
        "--drop", action="store_true", help="테스트 테이블 삭제 후 종료"
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        type=int,
        default=EXCLUDE_IDS,
        help=f"제외할 source ID (기본: {EXCLUDE_IDS})",
    )
    args = parser.parse_args()

    use_test = args.test
    table_name = "page_data_test" if use_test else "page_data"

    if args.drop:
        if not use_test:
            print("[오류] --drop은 --test와 함께 사용해야 합니다.")
            sys.exit(1)
        drop_test_table()
        return

    if use_test:
        ensure_test_table()

    # 1. source 조회
    sources = get_sources(args.notebook_id, args.exclude)
    if not sources:
        print(f"[오류] notebook_id={args.notebook_id}에 본문이 있는 source가 없습니다.")
        sys.exit(1)

    source_ids = [s.id for s in sources]
    print("[설정]")
    print(f"  테이블      : {table_name}")
    print(f"  notebook_id : {args.notebook_id}")
    print(f"  전략        : {args.strategy}")
    print(f"  chunk_size  : {args.chunk_size}")
    print(f"  chunk_overlap: {args.chunk_overlap}")
    print(f"  임베딩 모델 : {args.embed_model}")
    print(f"  대상 source : {len(sources)}개")
    print(f"  제외 source : {args.exclude}")

    # 2. 기존 데이터 삭제
    if args.clear:
        deleted = clear_data(source_ids, use_test)
        print(f"\n[삭제] 기존 {table_name} {deleted}건 삭제 완료")

    # 3. 청킹
    print(f"\n[청킹] {args.strategy} 전략으로 처리 중...")
    config = ChunkerConfig(
        strategy_name=args.strategy,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    chunker = STRATEGY_MAP[args.strategy](config)

    t0 = time.time()
    source_chunks: dict[int, list[str]] = {}
    total_chunks = 0

    for source in sources:
        text_content = MarkdownPreprocessor.run(source.summary)
        results = chunker.chunk(text_content)
        chunks = [r.content for r in results]
        source_chunks[source.id] = chunks
        total_chunks += len(chunks)
        print(
            f"  source {source.id} ({source.title or source.url}): {len(chunks)}개 청크"
        )

    chunk_time = time.time() - t0
    print(f"  총 {total_chunks}개 청크 ({chunk_time:.1f}초)")

    # 4. 임베딩
    print(f"\n[임베딩] {args.embed_model} 모델로 처리 중...")
    embedder = EMBED_MAP[args.embed_model]()

    all_texts: list[str] = []
    text_source_map: list[int] = []

    for source_id, chunks in source_chunks.items():
        all_texts.extend(chunks)
        text_source_map.extend([source_id] * len(chunks))

    t0 = time.time()
    all_embeddings = embedder.embed(all_texts, show_progress_bar=True)
    embed_time = time.time() - t0
    print(f"  {len(all_embeddings)}개 벡터 생성 ({embed_time:.1f}초)")

    # 5. DB 적재
    print(f"\n[적재] {table_name} 저장 중...")
    t0 = time.time()

    source_embeddings: dict[int, list[list[float]]] = {}
    for i, sid in enumerate(text_source_map):
        source_embeddings.setdefault(sid, []).append(all_embeddings[i])

    total_saved = 0
    for source_id, chunks in source_chunks.items():
        embeddings = source_embeddings[source_id]
        count = bulk_insert(source_id, chunks, embeddings, use_test)
        total_saved += count
        print(f"  source {source_id}: {count}건 저장")

    save_time = time.time() - t0

    # 6. 요약
    total_time = chunk_time + embed_time + save_time
    print(f"\n[완료] {table_name}에 총 {total_saved}건 적재 ({total_time:.1f}초)")
    print(
        f"  청킹: {chunk_time:.1f}초 | 임베딩: {embed_time:.1f}초 | 저장: {save_time:.1f}초"
    )


if __name__ == "__main__":
    main()
