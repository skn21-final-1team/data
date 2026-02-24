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
    print(f"\n[콜백 수신] source_url={body['source_url']}")
    print(f"  chunks: {len(body['chunks'])}개")
    print(f"  embeddings: {len(body['embeddings'])}개, dim={len(body['embeddings'][0])}")
    return {"status": "ok"}


def run_mock_backend() -> None:
    uvicorn.run(mock_app, host="0.0.0.0", port=MOCK_BACKEND_PORT, log_level="warning")


def test_crawl_with_callback() -> None:
    payload = {
        "urls": ["https://en.wikipedia.org/wiki/Seoul"],
        "notebook_id": 1,
        "user_id": 42,
        "callback_url": f"http://localhost:{MOCK_BACKEND_PORT}/callback/embedding",
    }

    print("[1] POST /crawl 요청")
    response = httpx.post(f"{DATA_SERVER}/crawl", json=payload, timeout=120.0)
    print(f"    status={response.status_code}")

    if response.status_code == 200:
        for item in response.json():
            print(f"    URL: {item['url']}")
            print(f"    제목: {item['title']}")
            print(f"    본문: {item['summary'][:100]}...")
            print(f"    notebook_id: {item['notebook_id']}, user_id: {item['user_id']}")

    print("\n[2] 백그라운드 콜백 대기 (최대 30초)...")
    for _ in range(30):
        time.sleep(1)
        if callback_received:
            break
    else:
        print("    콜백 수신 실패 (타임아웃)")
        return

    print("\n[완료] 동기 응답 + 비동기 콜백 모두 성공")


if __name__ == "__main__":
    backend_thread = threading.Thread(target=run_mock_backend, daemon=True)
    backend_thread.start()
    time.sleep(1)

    test_crawl_with_callback()
