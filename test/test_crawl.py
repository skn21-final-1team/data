"""크롤링 → source DB 적재 (backend 연동 없이 독립 실행).

사용법::

    uv run python -m test.test_crawl 1
    uv run python -m test.test_crawl 1 --urls https://example1.com https://example2.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from crawl.client import hybrid_client
from crawl.preprocess import MarkdownPreprocessor
from crud.source import create_source, update_source_status
from db.database import get_db_context
from test.urls import DEFAULT_URLS

sys.stdout.reconfigure(encoding="utf-8")


async def crawl_all(
    urls: list[str], notebook_id: int
) -> list[dict[str, object] | None]:
    results: list[dict[str, object] | None] = []

    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{len(urls)}] {url}")
        try:
            scraped = await hybrid_client.scrape(url)
            preprocessed = MarkdownPreprocessor.run(scraped.content)
            print(f"    제목: {scraped.title}")
            print(f"    본문: {len(scraped.content)}자 → 전처리: {len(preprocessed)}자")

            with get_db_context() as db:
                source = create_source(
                    db=db,
                    url=scraped.url,
                    notebook_id=notebook_id,
                )
                source_id = source.id
                update_source_status(
                    db,
                    source_id,
                    status="success",
                    title=scraped.title,
                    raw=preprocessed,
                )
            print(f"    → source 저장 완료 (id={source_id})")
            results.append(
                {"id": source_id, "url": scraped.url, "title": scraped.title}
            )
        except Exception as e:
            print(f"    → 실패: {e}")
            results.append(None)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="크롤링 → source DB 적재")
    parser.add_argument("notebook_id", type=int, help="notebook ID (DB에 존재해야 함)")
    parser.add_argument("--urls", nargs="+", default=None, help="크롤링할 URL 목록")
    args = parser.parse_args()

    urls = args.urls or DEFAULT_URLS
    print(f"[크롤링 시작] 총 {len(urls)}개 URL (notebook_id={args.notebook_id})")

    start = time.time()
    results = asyncio.run(crawl_all(urls, args.notebook_id))
    elapsed = time.time() - start

    success = [r for r in results if r is not None]
    print(f"\n[완료] 성공 {len(success)}/{len(urls)}건 ({elapsed:.1f}초)")
    for r in success:
        print(f"  id={r['id']}  {r['url']}")


if __name__ == "__main__":
    main()
