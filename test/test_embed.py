"""임베딩 + PGVector 적재 (독립 실행).

입력: test/output/chunks.json (test_chunk 산출물)
출력: PGVector DB 적재

사용법::

    # 테스트 컬렉션에 적재
    uv run python -m test.test_embed --test

    # 기존 데이터 삭제 후 재적재
    uv run python -m test.test_embed --test --clear

    # 본 컬렉션에 적재 (주의)
    uv run python -m test.test_embed
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from db.vector_store import get_vector_store
from embed.service import embed_texts

sys.stdout.reconfigure(encoding="utf-8")

CHUNKS_PATH = Path(__file__).parent / "output" / "chunks.json"


def load_chunks() -> dict[str, list[str]]:
    """test/output/chunks.json에서 {source_id: [chunk, ...]} 로드."""
    if not CHUNKS_PATH.exists():
        print(f"[오류] {CHUNKS_PATH} 파일이 없습니다. test_chunk를 먼저 실행하세요.")
        sys.exit(1)
    data: dict[str, list[str]] = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    total = sum(len(v) for v in data.values())
    print(f"[입력] chunks.json에서 {len(data)}개 source, {total}개 청크 로드")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="임베딩 → PGVector 적재")
    parser.add_argument("--test", action="store_true", help="page_data_test 컬렉션 사용")
    parser.add_argument("--clear", action="store_true", help="컬렉션 초기화 후 재적재")
    args = parser.parse_args()

    collection_name = "page_data_test" if args.test else "page_data"

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

    source_chunks = load_chunks()

    # 전체 텍스트 수집
    all_texts: list[str] = []
    text_source_map: list[str] = []
    for source_id, chunks in source_chunks.items():
        all_texts.extend(chunks)
        text_source_map.extend([source_id] * len(chunks))

    # 임베딩
    print(f"\n[임베딩] {len(all_texts)}개 청크 처리 중...")
    t0 = time.time()
    all_embeddings = embed_texts(all_texts)
    embed_time = time.time() - t0
    print(f"  {len(all_embeddings)}개 벡터 생성 ({embed_time:.1f}초)")

    # source별 임베딩 매핑
    source_embeddings: dict[str, list[list[float]]] = {}
    for i, sid in enumerate(text_source_map):
        source_embeddings.setdefault(sid, []).append(all_embeddings[i])

    # PGVector 적재
    print(f"\n[적재] {collection_name} 저장 중...")
    t0 = time.time()
    store = get_vector_store(collection_name)
    total_saved = 0

    for source_id, chunks in source_chunks.items():
        embeddings = source_embeddings[source_id]
        metadatas = [{"source_id": int(source_id)} for _ in chunks]
        store.add_embeddings(texts=chunks, embeddings=embeddings, metadatas=metadatas)
        total_saved += len(chunks)
        print(f"  source {source_id}: {len(chunks)}건 저장")

    save_time = time.time() - t0

    total_time = embed_time + save_time
    print(f"\n[완료] {collection_name}에 총 {total_saved}건 적재 ({total_time:.1f}초)")
    print(f"  임베딩: {embed_time:.1f}초 | 저장: {save_time:.1f}초")


if __name__ == "__main__":
    main()
