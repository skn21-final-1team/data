"""vLLM 클라이언트 — RunPod Serverless Native API 호출."""

from __future__ import annotations

import json
import logging
import time

import httpx

from core.config import get_settings
from llm.prompts import build_messages

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.0  # 초
POLL_TIMEOUT = 300   # 최대 대기 5분


def _run_and_poll(base_url: str, api_key: str, payload: dict) -> dict:
    """RunPod /run 후 /status 폴링으로 결과 수신."""
    headers = {"Authorization": f"Bearer {api_key}"}

    # 1) 작업 제출
    resp = httpx.post(f"{base_url}/run", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    job_id = resp.json()["id"]

    # 2) 완료까지 폴링
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status_resp = httpx.get(f"{base_url}/status/{job_id}", headers=headers, timeout=30)
        status_resp.raise_for_status()
        data = status_resp.json()

        if data["status"] == "COMPLETED":
            return data
        if data["status"] == "FAILED":
            raise RuntimeError(f"RunPod job failed: {data}")

        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"RunPod job {job_id} timed out after {POLL_TIMEOUT}s")


def refine_and_summarize(content: str) -> dict[str, str]:
    """vLLM으로 본문 정제 + 요약 수행.

    Returns
    -------
    {"refined": "정제된 본문", "summary": "요약"}
    """
    settings = get_settings()

    data = _run_and_poll(
        base_url=settings.VLLM_BASE_URL,
        api_key=settings.RUNPOD_API_KEY,
        payload={
            "input": {
                "openai_route": "/v1/chat/completions",
                "openai_input": {
                    "model": settings.VLLM_MODEL,
                    "messages": build_messages(content),
                    "temperature": 0.1,
                    "max_tokens": 4096,
                },
            }
        },
    )

    # output이 리스트로 감싸진 경우 처리
    output = data.get("output", {})
    if isinstance(output, list):
        output = output[0] if output else {}

    raw = output.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("vLLM JSON 파싱 실패, 원본 반환: %s", raw[:200])
        return {"refined": content, "summary": ""}

    return {
        "refined": result.get("refined", content),
        "summary": result.get("summary", ""),
    }
