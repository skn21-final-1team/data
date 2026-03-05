"""크롤링 → source DB 적재 (backend 연동 없이 독립 실행).

사용법::

    uv run python test_crawl.py 1
    uv run python test_crawl.py 1 --urls https://example1.com https://example2.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from crawl.client import hybrid_client
from crud.source import create_source
from db.database import get_db_context

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_URLS = [
    "https://www.notion.com/ko/product/ai",
    "https://www.notion.com/ko/pricing",
    "https://github.com/karpathy/nanochat",
    "https://huggingface.co/openbmb/MiniCPM-SALA",
    "https://www.acmicpc.net/workbook/view/1152",
    "https://www.acmicpc.net/problem/3190",
    "https://solved.ac/ranking/tier?page=1",
    "https://event.wanted.co.kr/swmaestro17_busan",
    "https://en.wikipedia.org/wiki/Tensor",
    "https://en.wikipedia.org/wiki/Elon_Musk",
    "https://en.wikipedia.org/wiki/Tesla,_Inc",
    "https://ridibooks.com/webtoon/recommendation",
    "https://mojing.tistory.com/entry/ProgrammersC-PCCP-기출문제-1번-동영상-재생기",
    "https://www.en-core.com/resource/playdata2",
    "https://brunch.co.kr/@sungdairi/27",
    "https://gall.dcinside.com/mgallery/board/view/?id=pokemontcgpocket&no=568804",
    "https://debateforall.org/blog/?bmode=view&idx=6582418",
    "https://mz-moonzoo.tistory.com/95",
    "https://usehooks-ts.com/introduction",
    "https://wikidocs.net/233772",
    "https://technote.wiki/대문",
    "https://blog.ull.im/engineering/2019/03/10/logs-on-git.html",
    "https://m.blog.naver.com/jisoo831/223328759196",
    "https://deepbaksuvision.github.io/Modu_ObjectDetection/posts/04_01_Review_of_YOLO_Paper.html",
    "https://toss.im/tossfeed/article/house-contract-02",
    "https://github.com/makenotion/notion-mcp-server#readme",
    "https://sugarslayer.tistory.com/category/내집마련🏡/HUG 버팀목 전세 대출(청년) 후기",
    "https://dropbox.github.io/dbx-career-framework/overview.html",
    "https://networks-aicamp.io/introduction",
    "https://www.velopers.kr/",
    "https://techblog.woowahan.com/25189/",
    "https://techcrunch.com/2026/03/04/anthropic-ceo-dario-amodei-calls-openais-messaging-around-military-deal-straight-up-lies-report-says/",
    "https://developer.mozilla.org/en-US/blog/launching-new-front-end/",
    "https://stackoverflow.com/questions/79901273/how-to-properly-style-buttons-in-avalonia-c",
    "https://www.inflearn.com/projects/1780001/%EC%9B%B9-%EC%95%B1-%EA%B0%9C%EB%B0%9C-%EC%88%98%EC%9D%B5%EC%84%B1-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%ED%8C%80-%EB%AA%A8%EC%A7%91",
    "https://tech.kakao.com/posts/811",
    "https://d2.naver.com/news/3435170",
    "https://yozm.wishket.com/magazine/detail/3617/",
    "https://guide.michelin.com/kr/ko/seoul-capital-area/kr-seoul/restaurant/eatanic-garden",
    "https://www.teamblind.com/kr/company",
    "https://www.fatsecret.kr/%EC%B9%BC%EB%A1%9C%EB%A6%AC-%EC%98%81%EC%96%91%EC%86%8C/%EC%9D%BC%EB%B0%98%EB%AA%85/%EB%94%B8%EA%B8%B0?portionid=33406&portionamount=1.000",
    "https://www.fatsecret.kr/%EC%B9%BC%EB%A1%9C%EB%A6%AC-%EC%98%81%EC%96%91%EC%86%8C/",
    "https://quotes.toscrape.com/tag/books/",
    "https://www.coingecko.com/en/coins/bitcoin",
    "https://deepeval.com/docs/getting-started",
    "https://en.wikipedia.org/wiki/List_of_chemical_elements",
    "https://www.lingscars.com/leasing/electric/",
    "https://www.diningcode.com/intro",
]


async def crawl_all(
    urls: list[str], notebook_id: int
) -> list[dict[str, object] | None]:
    results: list[dict[str, object] | None] = []

    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{len(urls)}] {url}")
        try:
            scraped = await hybrid_client.scrape(url)
            print(f"    제목: {scraped.title}")
            print(f"    본문: {len(scraped.content)}자")

            with get_db_context() as db:
                source = create_source(
                    db=db,
                    url=scraped.url,
                    title=scraped.title,
                    summary=scraped.content,
                    notebook_id=notebook_id,
                )
            print(f"    → source 저장 완료 (id={source.id})")
            results.append(
                {"id": source.id, "url": scraped.url, "title": scraped.title}
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
