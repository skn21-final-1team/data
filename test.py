import sys
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request

sys.stdout.reconfigure(encoding="utf-8")

DATA_SERVER = "http://localhost:8001"
MOCK_BACKEND_PORT = 9000

mock_app = FastAPI()
callback_received: dict[str, object] = {}


@mock_app.post("/callback/embedding")
async def receive_callback(request: Request) -> dict[str, str]:
    body = await request.json()
    callback_received[body["source_url"]] = body
    print(f"\n{'=' * 60}")
    print(f"[4] 콜백 수신 성공")
    print(f"    source_url: {body['source_url']}")
    print(f"    chunks: {len(body['chunks'])}개")
    print(
        f"    embeddings: {len(body['embeddings'])}개, dim={len(body['embeddings'][0])}"
    )
    print("=" * 60)
    return {"status": "ok"}


def run_mock_backend() -> None:
    uvicorn.run(mock_app, host="0.0.0.0", port=MOCK_BACKEND_PORT, log_level="warning")


def test_crawl_with_callback() -> None:
    payload = {
        "urls": [
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
            "https://pyrasis.com/jHLsAlwaysUpToDateDocker",
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
        ],
        "notebook_id": 27,
    }

    # [1] 크롤링 + source DB 적재 (10개씩 배치 요청)
    urls = payload["urls"]
    batch_size = 10
    all_results = []

    print(f"[1] POST /crawl 요청 (총 {len(urls)}개 URL, {batch_size}개씩 배치)")
    for i in range(0, len(urls), batch_size):
        batch = urls[i : i + batch_size]
        batch_num = i // batch_size + 1
        print(
            f"    배치 {batch_num}: {len(batch)}개 URL 요청 중...", end="", flush=True
        )
        try:
            response = httpx.post(
                f"{DATA_SERVER}/crawl",
                json={"urls": batch, "notebook_id": payload["notebook_id"]},
                timeout=300.0,
            )
        except httpx.ReadTimeout:
            print(" 타임아웃")
            continue

        if response.status_code != 200:
            print(f" 실패 (status={response.status_code})")
            continue

        all_results.extend(response.json())
        print(f" 성공 ({len(response.json())}건)")

    if not all_results:
        print("    전체 실패")
        return

    # [2] 크롤링 결과 확인
    print(f"\n[2] 크롤링 + source 적재 성공 (총 {len(all_results)}건)")
    for item in all_results:
        print(f"    URL: {item['url']}")
        print(f"    제목: {item['title']}")
        summary = item.get("summary") or ""
        print(f"    본문: {summary[:100]}...")
        print(f"    notebook_id: {item['notebook_id']}")

    # [3] 백그라운드 대기 (청킹 → 임베딩 → page_data 적재 → 콜백)
    print("\n[3] 백그라운드 파이프라인 대기 (청킹 → 임베딩 → page_data 적재 → 콜백)")
    print("    최대 300초 대기 중...", end="", flush=True)
    for i in range(300):
        time.sleep(1)
        if callback_received:
            print(f" ({i + 1}초)")
            break
        if (i + 1) % 10 == 0:
            print(f" {i + 1}s", end="", flush=True)
    else:
        print("\n    콜백 수신 실패 (타임아웃 300초)")
        print("    → 데이터 서버 로그를 확인하세요 (page_data 적재는 성공했을 수 있음)")
        return

    print("\n[완료] 전체 파이프라인 성공")
    print("  크롤링 → source 적재 → 청킹 → 임베딩 → page_data 적재 → 콜백")


if __name__ == "__main__":
    backend_thread = threading.Thread(target=run_mock_backend, daemon=True)
    backend_thread.start()
    time.sleep(1)

    test_crawl_with_callback()
