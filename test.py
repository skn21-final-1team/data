import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DATA_SERVER = "http://localhost:8001"


def test_crawl() -> None:
    payload = {"urls": ["https://en.wikipedia.org/wiki/Seoul"]}
    response = httpx.post(f"{DATA_SERVER}/crawl", json=payload, timeout=60.0)

    print(f"[POST /crawl] status={response.status_code}\n")

    if response.status_code == 200:
        for item in response.json():
            print(f"  URL   : {item['url']}")
            print(f"  제목  : {item['title']}")
            print(f"  본문  : {item['summary'][:200]}...")
            print(f"  길이  : {len(item['summary'])}자")
            print()
    else:
        print(f"  에러  : {response.json()['detail']}")


if __name__ == "__main__":
    test_crawl()
