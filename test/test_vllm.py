"""vLLM 정제/요약 → source DB 업데이트 (독립 실행).

사용법::

    uv run python -m test.test_vllm --ids 1 2 3 10-20 --step all
    uv run python -m test.test_vllm --ids 611 --step refine
    uv run python -m test.test_vllm --ids 611 --step summarize

    범위(10-20), 개별(1 2 3) 혼합 가능
    --step: refine(정제만) | summarize(요약만) | all(전체, 기본값)
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from crawl.preprocess import MarkdownPreprocessor
from crud.source import get_source_by_id, update_source_status
from db.database import get_db_context
from llm.client import refine, summarize
from llm.config import get_llm_settings
from llm.prompts import build_refine_prompt, build_summarize_prompt

sys.stdout.reconfigure(encoding="utf-8")


def _parse_ids(raw: list[str]) -> list[int]:
    """'1', '2', '10-20' 등 개별/범위 혼합 파싱."""
    ids: list[int] = []
    for token in raw:
        if "-" in token:
            start, end = token.split("-", 1)
            ids.extend(range(int(start), int(end) + 1))
        else:
            ids.append(int(token))
    return sorted(set(ids))


def _print_token_preview(source_id: int, content: str, prompt_builder) -> None:
    cfg = get_llm_settings()
    truncated = content[: cfg.MAX_CONTENT_CHARS]
    prompt = prompt_builder(truncated)
    est_input = int(len(prompt) / cfg.KO_CHARS_PER_TOKEN)
    est_output = cfg.MAX_MODEL_TOKENS - est_input - 500
    flag = " ⚠" if est_input >= cfg.MAX_MODEL_TOKENS else ""
    print(
        f"  {source_id:>4} | {len(content):>7,} | {len(truncated):>7,} "
        f"| {est_input:>9,} | {est_output:>9,}{flag}"
    )


def _run_refine(source_id: int, url: str, content: str) -> tuple[int, str]:
    preprocessed = MarkdownPreprocessor.run(content)
    refined_text = refine(preprocessed)
    with get_db_context() as db:
        update_source_status(db, source_id, refined=refined_text)
    return source_id, refined_text


def _run_summarize(source_id: int, url: str, content: str) -> tuple[int, str]:
    summary_text = summarize(content)
    with get_db_context() as db:
        update_source_status(db, source_id, summary=summary_text)
    return source_id, summary_text


def _run_step(
    source_data: list[tuple[int, str, str]],
    worker_fn,
    step_label: str,
) -> None:
    start = time.time()
    success = 0

    with ThreadPoolExecutor(max_workers=get_llm_settings().MAX_WORKERS) as pool:
        futures = {
            pool.submit(worker_fn, sid, url, content): (sid, url)
            for sid, url, content in source_data
        }
        for future in as_completed(futures):
            sid, url = futures[future]
            try:
                source_id, result = future.result()
                print(f"  [완료] id={source_id}  {step_label}: {len(result)}자")
                success += 1
            except Exception as e:
                print(f"  [실패] id={sid}  {url}  → {e}")

    elapsed = time.time() - start
    print(f"[{step_label}] 성공 {success}/{len(source_data)}건 ({elapsed:.1f}초)\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="vLLM 정제/요약 독립 실행")
    parser.add_argument("--ids", nargs="+", required=True, help="처리할 source ID")
    parser.add_argument(
        "--step",
        choices=["refine", "summarize", "all"],
        default="all",
        help="실행 단계 (기본값: all)",
    )
    args = parser.parse_args()

    target_ids = _parse_ids(args.ids)

    with get_db_context() as db:
        sources = [get_source_by_id(db, sid) for sid in target_ids]

    source_list = [(s.id, s.url or "") for s in sources if s is not None]
    missing = set(target_ids) - {s[0] for s in source_list}
    for sid in missing:
        print(f"  [스킵] source id={sid} 없음")

    do_refine = args.step in ("refine", "all")
    do_summarize = args.step in ("summarize", "all")

    if do_refine:
        refine_data: list[tuple[int, str, str]] = []
        with get_db_context() as db:
            for sid, url in source_list:
                s = get_source_by_id(db, sid)
                content = (s.raw or "") if s else ""
                if not content.strip():
                    print(f"  [스킵] id={sid} raw 없음 — 크롤링 먼저 실행하세요")
                    continue
                refine_data.append((sid, url, content))

        if refine_data:
            print(
                f"\n  {'ID':>4} | {'raw(자)':>8} | {'절삭후':>8} | {'추정입력토큰':>10} | {'출력여유':>8}"
            )
            print(f"  {'-' * 4}-+-{'-' * 8}-+-{'-' * 8}-+-{'-' * 10}-+-{'-' * 8}")
            for sid, _, content in refine_data:
                _print_token_preview(sid, content, build_refine_prompt)
            print()
            print(f"[정제 시작] {len(refine_data)}개")
            _run_step(refine_data, _run_refine, "정제")

    if do_summarize:
        summarize_data: list[tuple[int, str, str]] = []
        with get_db_context() as db:
            for sid, url in source_list:
                s = get_source_by_id(db, sid)
                content = (s.refined or "") if s else ""
                if not content.strip():
                    print(f"  [스킵] id={sid} refined 없음 — 정제 먼저 실행하세요")
                    continue
                summarize_data.append((sid, url, content))

        if summarize_data:
            print(
                f"\n  {'ID':>4} | {'refined(자)':>10} | {'절삭후':>8} | {'추정입력토큰':>10} | {'출력여유':>8}"
            )
            print(f"  {'-' * 4}-+-{'-' * 10}-+-{'-' * 8}-+-{'-' * 10}-+-{'-' * 8}")
            for sid, _, content in summarize_data:
                _print_token_preview(sid, content, build_summarize_prompt)
            print()
            print(f"[요약 시작] {len(summarize_data)}개")
            _run_step(summarize_data, _run_summarize, "요약")


if __name__ == "__main__":
    main()
