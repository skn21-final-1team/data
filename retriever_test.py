"""Retriever 수동 통합 테스트.

전제: 데이터 서버 실행 중 + DB에 임베딩 데이터 존재.

실행::
    uv run python retriever_test.py
"""

import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DATA_SERVER = "http://localhost:8001"

NOTEBOOK_ID = 18
TEST_QUERIES = [
    # "Elon Musk는 어디에서 태어났는가"
    # "동영상 재생기 문제 풀이",
    # "동영상 재생기 문제 풀이 방법은?",
    "PCCP 기출문제",
]
TOP_K = 5


def test_retrieve() -> None:
    for query in TEST_QUERIES:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print("=" * 60)

        payload = {
            "query": query,
            "notebook_id": NOTEBOOK_ID,
            "top_k": TOP_K,
        }

        try:
            response = httpx.post(
                f"{DATA_SERVER}/retrieve",
                json=payload,
                timeout=60.0,
            )
        except httpx.ConnectError:
            print("  ERROR: 데이터 서버 연결 실패 (서버 실행 중인지 확인)")
            return

        if response.status_code != 200:
            print(f"  ERROR: status={response.status_code}")
            print(f"  {response.text[:200]}")
            continue

        data = response.json()
        print(f"  결과: {data['count']}건\n")

        for i, result in enumerate(data["results"], 1):
            print(f"  [{i}] similarity={result['similarity']:.4f}")
            print(
                f"      source: {result['source_title']} ({result['source_url'][:60]})"
            )
            print(f"      text: {result['chunk_text'][:150]}...")
            print()

    print("[완료] 리트리버 테스트 종료")


if __name__ == "__main__":
    test_retrieve()
