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
            "https://mojing.tistory.com/entry/ProgrammersC-PCCP-%EA%B8%B0%EC%B6%9C%EB%AC%B8%EC%A0%9C-1%EB%B2%88-%EB%8F%99%EC%98%81%EC%83%81-%EC%9E%AC%EC%83%9D%EA%B8%B0"
        ],
        "notebook_id": 14,
    }

    # [1] 크롤링 + source DB 적재
    print("[1] POST /crawl 요청 (크롤링 + source 적재)")
    try:
        response = httpx.post(f"{DATA_SERVER}/crawl", json=payload, timeout=300.0)
        print(f"    status={response.status_code}")
    except httpx.ReadTimeout:
        print("    POST /crawl 타임아웃 (300초 초과)")
        return

    if response.status_code != 200:
        print(f"    실패: {response.text[:200]}")
        return

    # [2] 크롤링 결과 확인
    print("\n[2] 크롤링 + source 적재 성공")
    for item in response.json():
        print(f"    URL: {item['url']}")
        print(f"    제목: {item['title']}")
        print(f"    본문: {item['summary'][:100]}...")
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
