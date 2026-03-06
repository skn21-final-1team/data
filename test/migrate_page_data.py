"""기존 page_data 테이블 → PGVector 테이블로 데이터 복사.

기존 page_data(chunk_text, embedding, source_id) 데이터를
langchain_pg_embedding 테이블(collection="page_data")로 마이그레이션한다.

사용법::
    uv run python -m test.migrate_page_data
    uv run python -m test.migrate_page_data --batch_size 200
    uv run python -m test.migrate_page_data --dry_run
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import text

from db.database import get_db_context
from db.vector_store import get_vector_store

sys.stdout.reconfigure(encoding="utf-8")


def fetch_page_data(batch_size: int) -> list[dict]:
    """기존 page_data 테이블에서 전체 레코드 조회."""
    with get_db_context() as db:
        rows = db.execute(
            text(
                "SELECT id, source_id, chunk_text, embedding "
                "FROM page_data "
                "ORDER BY id"
            )
        ).fetchall()

    records = []
    for row in rows:
        embedding = row.embedding
        if embedding is None:
            continue
        # pgvector 반환 형식에 따라 list[float]로 변환
        if isinstance(embedding, str):
            embedding = [float(x) for x in embedding.strip("[]").split(",")]
        else:
            embedding = list(embedding)

        records.append(
            {
                "id": row.id,
                "source_id": row.source_id,
                "chunk_text": row.chunk_text,
                "embedding": embedding,
            }
        )
    return records


def migrate(batch_size: int, dry_run: bool) -> None:
    print("[1] 기존 page_data 조회 중...")
    records = fetch_page_data(batch_size)
    print(f"    {len(records)}건 조회 완료")

    if not records:
        print("[완료] 마이그레이션할 데이터 없음")
        return

    if dry_run:
        print(f"[DRY RUN] {len(records)}건 마이그레이션 예정 (실행하지 않음)")
        return

    print("[2] PGVector 테이블에 적재 중...")
    store = get_vector_store("page_data")

    t0 = time.time()
    total = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        texts = [r["chunk_text"] for r in batch]
        embeddings = [r["embedding"] for r in batch]
        metadatas = [{"source_id": r["source_id"]} for r in batch]

        store.add_embeddings(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        total += len(batch)
        print(f"    {total}/{len(records)}건 적재 완료")

    elapsed = time.time() - t0
    print(f"\n[완료] {total}건 마이그레이션 완료 ({elapsed:.1f}초)")


def main() -> None:
    parser = argparse.ArgumentParser(description="page_data → PGVector 마이그레이션")
    parser.add_argument("--batch_size", type=int, default=100, help="배치 크기 (기본: 100)")
    parser.add_argument("--dry_run", action="store_true", help="실제 적재 없이 조회만 수행")
    args = parser.parse_args()

    migrate(batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
