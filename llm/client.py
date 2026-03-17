"""vLLM 클라이언트 — RunPod Serverless Native API 호출 (async)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from core.config import get_settings
from llm.config import get_llm_settings
from llm.prompts import build_refine_prompt, build_summarize_prompt

logger = logging.getLogger(__name__)


async def _run_and_poll(base_url: str, api_key: str, payload: dict) -> dict:
    """RunPod /run 후 /status 폴링으로 결과 수신."""
    cfg = get_llm_settings()
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/run", headers=headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        job_id = resp.json()["id"]

        deadline = time.time() + cfg.POLL_TIMEOUT
        while time.time() < deadline:
            status_resp = await client.get(
                f"{base_url}/status/{job_id}", headers=headers, timeout=30
            )
            status_resp.raise_for_status()
            data = status_resp.json()

            if data["status"] == "COMPLETED":
                return data
            if data["status"] == "FAILED":
                raise RuntimeError(f"RunPod job failed: {data}")

            await asyncio.sleep(cfg.POLL_INTERVAL)

    raise TimeoutError(f"RunPod job {job_id} timed out after {cfg.POLL_TIMEOUT}s")


def _truncate_content(content: str) -> str:
    """모델 컨텍스트 한계에 맞게 본문 절삭."""
    limit = get_llm_settings().MAX_CONTENT_CHARS
    if len(content) <= limit:
        return content
    logger.info("본문 절삭: %d → %d자", len(content), limit)
    return content[:limit]


def _extract_raw_output(data: dict) -> str:
    """RunPod 응답에서 텍스트 출력 추출."""
    output = data.get("output", [])
    if isinstance(output, list):
        output = output[0] if output else {}
    choices = output.get("choices", [{}])
    first = choices[0] if choices else {}
    tokens = first.get("tokens")
    if isinstance(tokens, list):
        return "".join(tokens).strip()
    return first.get("text", "").strip()


async def _call_vllm(prompt: str, *, min_tokens: int = 0) -> str:
    """프롬프트를 RunPod vLLM에 전송하고 raw 텍스트 출력 반환. 콜드스타트 재시도 포함."""
    cfg = get_llm_settings()
    est_input_tokens = int(len(prompt) / cfg.KO_CHARS_PER_TOKEN)
    max_tokens = max(512, cfg.MAX_MODEL_TOKENS - est_input_tokens - 500)

    sampling = {"max_tokens": max_tokens, "temperature": 0.1}
    if min_tokens > 0:
        sampling["min_tokens"] = min(min_tokens, max_tokens)

    payload = {
        "input": {
            "model": cfg.VLLM_MODEL,
            "prompt": prompt,
            "sampling_params": sampling,
        }
    }
    logger.debug(
        "max_tokens=%d, est_input=%d, prompt_len=%d",
        max_tokens,
        est_input_tokens,
        len(prompt),
    )

    last_exc: Exception = RuntimeError("재시도 횟수 초과")
    result: dict = {}
    for attempt in range(1, cfg.COLD_START_RETRIES + 1):
        try:
            result = await _run_and_poll(
                base_url=cfg.VLLM_BASE_URL,
                api_key=get_settings().RUNPOD_API_KEY,
                payload=payload,
            )
            break
        except RuntimeError as e:
            last_exc = e
            if attempt < cfg.COLD_START_RETRIES:
                logger.warning(
                    "콜드스타트 실패 (시도 %d/%d), %.0f초 후 재시도: %s",
                    attempt,
                    cfg.COLD_START_RETRIES,
                    cfg.COLD_START_DELAY,
                    e,
                )
                await asyncio.sleep(cfg.COLD_START_DELAY)
    else:
        raise last_exc

    raw = _extract_raw_output(result)
    logger.debug(
        "raw_output_len=%d, raw_output[:300]=%s", len(raw), raw[:300]
    )
    return raw


async def refine(content: str) -> str:
    """raw 본문 → 노이즈 제거 후 정제된 본문 반환.

    Returns
    -------
    정제된 본문 문자열
    """
    truncated = _truncate_content(content)
    prompt = build_refine_prompt(truncated)
    raw_output = await _call_vllm(prompt)

    # 프롬프트가 '{"refined": "' 로 시작을 유도하므로 출력에 이어붙여 JSON 파싱
    json_str = '{"refined": "' + raw_output
    try:
        result = json.loads(json_str)
        refined = result.get("refined", "")
        if refined:
            return refined
    except json.JSONDecodeError:
        # 잘린 JSON이면 마지막 '"}'  이전까지 추출
        match = re.search(r'^(.*?)(?:"\s*}?\s*$)', raw_output, re.DOTALL)
        if match and match.group(1).strip():
            return match.group(1)

    if not raw_output.strip():
        logger.warning("refine 출력이 비어있음, 원본 반환")
        return content
    return raw_output


async def summarize(content: str) -> str:
    """refined 본문 → 요약 문자열 반환.

    Returns
    -------
    요약 문자열 (1~2문장)
    """
    truncated = _truncate_content(content)
    prompt = build_summarize_prompt(truncated)
    raw_output = await _call_vllm(prompt)

    try:
        result = json.loads(raw_output)
        return result.get("summary", "")
    except (json.JSONDecodeError, AttributeError):
        # JSON이 아닌 plain text로 요약이 나온 경우 그대로 사용
        stripped = raw_output.strip()
        if stripped:
            logger.info("summarize JSON 파싱 실패, plain text 사용: %s", stripped[:100])
            return stripped
        return ""
