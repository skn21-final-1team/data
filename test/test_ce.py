"""청킹 + 임베딩 실험 → PGVector DB 적재 (backend 연동 없이 독립 실행).

전략·모델을 바꿔가며 page_data를 재적재할 수 있다.
--test 플래그로 page_data_test 컬렉션에 적재하여 본 컬렉션에 영향을 주지 않는다.

사용법::

    # 테스트 컬렉션에 적재 (기본: markdown / bge-m3 / 1000 / 100)
    uv run python -m test.test_ce 3 --test

    # 전략 변경
    uv run python -m test.test_ce 3 --test --strategy recursive --chunk_size 500 --chunk_overlap 50

    # 기존 데이터 삭제 후 재적재
    uv run python -m test.test_ce 3 --test --clear

    # 특정 source 제외
    uv run python -m test.test_ce 3 --test --exclude 20 42 45 47 48 53

    # 본 컬렉션에 적재 (주의)
    uv run python -m test.test_ce 3

전략 목록:
    recursive        S1  RecursiveCharacterTextSplitter
    token            S2  TokenTextSplitter (tiktoken, dev 의존성)
    semantic         S3  SemanticChunker (langchain-experimental, dev 의존성)
    markdown_header  S4  MarkdownHeaderTextSplitter
    markdown         S5  MarkdownTextSplitter
    hierarchical     S6  MarkdownHeader → RecursiveCharacter 재분할

임베딩 모델:
    EMBED_MODEL 환경변수로 설정 (서버리스 API 호출)
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import func

from chunk.config import ChunkerConfig
from crawl.preprocess import MarkdownPreprocessor
from chunk.strategies import (
    HierarchicalMarkdownChunker,
    MarkdownChunker,
    MarkdownHeaderChunker,
    RecursiveChunker,
    SemanticChunker,
    TokenChunker,
)
from db.database import get_db_context
from db.vector_store import get_vector_store
from embed.service import embed_texts
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

EXCLUDE_IDS = [20, 42, 45, 47, 48, 53]


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


def bulk_insert(
    source_id: int,
    chunks: list[str],
    embeddings: list[list[float]],
    use_test: bool,
) -> int:
    collection = "page_data_test" if use_test else "page_data"
    store = get_vector_store(collection)
    metadatas = [{"source_id": source_id} for _ in chunks]
    store.add_embeddings(texts=chunks, embeddings=embeddings, metadatas=metadatas)
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="청킹 + 임베딩 → PGVector 적재")
    parser.add_argument("notebook_id", type=int, help="대상 notebook ID")
    parser.add_argument("--strategy", choices=STRATEGY_MAP.keys(), default="markdown", help="청킹 전략 (기본: markdown)")
    parser.add_argument("--chunk_size", type=int, default=1000, help="청크 크기 (기본: 1000)")
    parser.add_argument("--chunk_overlap", type=int, default=100, help="청크 오버랩 (기본: 100)")
    parser.add_argument("--embed_model", default="bge-m3", help="임베딩 모델 (로깅용, 실제 모델은 EMBED_MODEL 환경변수)")
    parser.add_argument("--test", action="store_true", help="page_data_test 컬렉션 사용")
    parser.add_argument("--clear", action="store_true", help="컬렉션 초기화 후 재적재")
    parser.add_argument("--exclude", nargs="+", type=int, default=EXCLUDE_IDS, help=f"제외할 source ID (기본: {EXCLUDE_IDS})")
    args = parser.parse_args()

    use_test = args.test
    collection_name = "page_data_test" if use_test else "page_data"

    # --clear: 컬렉션 초기화
    if args.clear:
        from langchain_postgres.vectorstores import PGVector

        from core.config import get_settings
        from embed.langchain_wrapper import LangChainEmbeddingsWrapper

        PGVector(
            embeddings=LangChainEmbeddingsWrapper(),
            collection_name=collection_name,
            connection=get_settings().DATABASE_URL,
            use_jsonb=True,
            create_extension=False,
            pre_delete_collection=True,
        )
        print(f"[초기화] {collection_name} 컬렉션 초기화 완료")

    # 1. source 조회
    sources = get_sources(args.notebook_id, args.exclude)
    if not sources:
        print(f"[오류] notebook_id={args.notebook_id}에 본문이 있는 source가 없습니다.")
        sys.exit(1)

    print("[설정]")
    print(f"  컬렉션      : {collection_name}")
    print(f"  notebook_id : {args.notebook_id}")
    print(f"  전략        : {args.strategy}")
    print(f"  chunk_size  : {args.chunk_size}")
    print(f"  chunk_overlap: {args.chunk_overlap}")
    print(f"  임베딩 모델 : {args.embed_model}")
    print(f"  대상 source : {len(sources)}개")
    print(f"  제외 source : {args.exclude}")

    # 2. 청킹
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
        print(f"  source {source.id} ({source.title or source.url}): {len(chunks)}개 청크")

    chunk_time = time.time() - t0
    print(f"  총 {total_chunks}개 청크 ({chunk_time:.1f}초)")

    # 3. 임베딩 (서버리스 API)
    print(f"\n[임베딩] 서버리스 API로 처리 중...")

    all_texts: list[str] = []
    text_source_map: list[int] = []

    for source_id, chunks in source_chunks.items():
        all_texts.extend(chunks)
        text_source_map.extend([source_id] * len(chunks))

    t0 = time.time()
    all_embeddings = embed_texts(all_texts)
    embed_time = time.time() - t0
    print(f"  {len(all_embeddings)}개 벡터 생성 ({embed_time:.1f}초)")

    # 4. PGVector 적재
    print(f"\n[적재] {collection_name} 저장 중...")
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

    # 5. 요약
    total_time = chunk_time + embed_time + save_time
    print(f"\n[완료] {collection_name}에 총 {total_saved}건 적재 ({total_time:.1f}초)")
    print(f"  청킹: {chunk_time:.1f}초 | 임베딩: {embed_time:.1f}초 | 저장: {save_time:.1f}초")


if __name__ == "__main__":
    main()
