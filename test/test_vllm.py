"""vLLM 정제/요약 → source summary 업데이트 + refined 본문 파일 저장 (독립 실행).

사용법::

    uv run python -m test.test_vllm --ids 1 2 3

결과: test/output/refined.json 에 {source_id: refined_text} 저장
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from crud.source import get_sources_with_summary, update_source_status
from db.database import get_db_context
from llm.client import refine_and_summarize

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = Path(__file__).parent / "output"
REFINED_PATH = OUTPUT_DIR / "refined.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="vLLM 정제/요약 → source summary 업데이트")
    parser.add_argument("--ids", nargs="+", type=int, default=None, help="처리할 source ID 목록")
    args = parser.parse_args()

    with get_db_context() as db:
        sources = get_sources_with_summary(db)
        source_data = [
            (s.id, s.url, s.summary)
            for s in sources
            if args.ids is None or s.id in args.ids
        ]

    if not source_data:
        print("처리할 source가 없습니다.")
        return

    print(f"[vLLM 시작] {len(source_data)}개 source 처리")

    refined_map: dict[int, str] = {}
    success = 0
    start = time.time()

    for i, (source_id, url, content) in enumerate(source_data, 1):
        print(f"\n  [{i}/{len(source_data)}] source_id={source_id}  {url}")
        try:
            result = refine_and_summarize(content)
            refined = result["refined"]
            summary = result["summary"]
            print(f"    정제: {len(refined)}자")
            print(f"    요약: {summary[:200]}")

            with get_db_context() as db:
                update_source_status(db, source_id, status="success", summary=summary)
            print(f"    → summary 업데이트 완료")

            refined_map[source_id] = refined
            success += 1
        except Exception as e:
            print(f"    → 실패: {e}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    REFINED_PATH.write_text(json.dumps(refined_map, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[파일 저장] {REFINED_PATH} ({len(refined_map)}건)")

    elapsed = time.time() - start
    print(f"[완료] 성공 {success}/{len(source_data)}건 ({elapsed:.1f}초)")


if __name__ == "__main__":
    main()
