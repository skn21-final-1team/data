"""vLLM 클라이언트 — RunPod Serverless Native API 호출 (async)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from core.config import get_settings
from core.exceptions import VLLMColdStartError, VLLMConnectionError
from llm.config import get_llm_settings
from llm.prompts import build_refine_prompt, build_summarize_prompt

logger = logging.getLogger(__name__)


async def _run_and_poll(base_url: str, api_key: str, payload: dict) -> dict:
    """RunPod /run 후 /status 폴링으로 결과 수신."""
    cfg = get_llm_settings()
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
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
                    raise VLLMConnectionError(f"RunPod job failed: {data}")

                await asyncio.sleep(cfg.POLL_INTERVAL)

        raise VLLMConnectionError(
            f"RunPod job {job_id} timed out after {cfg.POLL_TIMEOUT}s"
        )
    except VLLMConnectionError:
        raise
    except Exception as e:
        raise VLLMConnectionError(f"vLLM 서버 연결 실패: {e}") from e


def _truncate_content(content: str) -> str:
    """모델 컨텍스트 한계에 맞게 본문 절삭."""
    limit = get_llm_settings().MAX_CONTENT_CHARS
    if len(content) <= limit:
        return content
    logger.info("본문 절삭: %d → %d자", len(content), limit)
    return content[:limit]


def _max_refine_chunk_chars() -> int:
    """refine 1회 호출 시 입력 content의 최대 글자 수."""
    cfg = get_llm_settings()
    prompt_overhead_tokens = 1200  # 프롬프트 템플릿 + 여유분
    available = cfg.MAX_MODEL_TOKENS - prompt_overhead_tokens
    # refine: output ≈ input → 2로 나눔
    return int((available // 2) * cfg.KO_CHARS_PER_TOKEN)


def _split_for_refine(content: str, max_chars: int) -> list[str]:
    """문단 경계(\\n\\n)를 기준으로 content를 max_chars 이하 청크로 분할."""
    if len(content) <= max_chars:
        return [content]
    paragraphs = content.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = (current + "\n\n" + para) if current else para
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


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

    last_exc: Exception | None = None
    result: dict = {}
    for attempt in range(1, cfg.COLD_START_RETRIES + 1):
        try:
            result = await _run_and_poll(
                base_url=cfg.VLLM_BASE_URL,
                api_key=get_settings().RUNPOD_API_KEY,
                payload=payload,
            )
            break
        except VLLMConnectionError as e:
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
        raise VLLMColdStartError(
            f"vLLM 콜드스타트 재시도 횟수를 초과했습니다: {last_exc}"
        ) from last_exc

    raw = _extract_raw_output(result)
    logger.debug(
        "raw_output_len=%d, raw_output[:300]=%s", len(raw), raw[:300]
    )
    return raw


def _collapse_repetitions(text: str) -> str:
    """3~50자 패턴이 10회 이상 연속 반복된 부분을 1회로 축소."""
    return re.sub(r"(.{3,50}?)\1{9,}", r"\1", text)


def _parse_refine_output(raw_output: str, fallback: str) -> str:
    """refine vLLM 출력에서 정제된 텍스트를 추출."""
    # 프롬프트가 '{"refined": "' 로 시작을 유도하므로 출력에 이어붙여 JSON 파싱
    json_str = '{"refined": "' + raw_output
    try:
        result = json.loads(json_str)
        refined = result.get("refined", "")
        if refined:
            text = refined
        else:
            text = None
    except json.JSONDecodeError:
        # 잘린 JSON이면 마지막 '"}'  이전까지 추출
        match = re.search(r'^(.*?)(?:"\s*}?\s*$)', raw_output, re.DOTALL)
        text = match.group(1) if match and match.group(1).strip() else None

    if text is None:
        if not raw_output.strip():
            logger.warning("refine 출력이 비어있음, 원본 반환")
            return fallback
        text = raw_output

    # 반복 패턴 축소
    cleaned = _collapse_repetitions(text)
    if len(cleaned) < len(text):
        logger.warning("반복 패턴 제거: %d → %d자", len(text), len(cleaned))

    # 축소 후에도 원본 대비 110% 초과면 원본 사용
    if len(cleaned) > len(fallback) * 1.1:
        logger.warning(
            "정제 결과 비정상 (원본 %d자, 정제 %d자), 원본 사용",
            len(fallback), len(cleaned),
        )
        return fallback

    return cleaned


async def refine(content: str) -> str:
    """raw 본문 → 노이즈 제거 후 정제된 본문 반환."""
    truncated = _truncate_content(content)
    max_chars = _max_refine_chunk_chars()
    chunks = _split_for_refine(truncated, max_chars)

    if len(chunks) == 1:
        prompt = build_refine_prompt(chunks[0])
        raw_output = await _call_vllm(prompt)
        return _parse_refine_output(raw_output, content)

    # 분할 정제 — 순차 처리 (RunPod 동시 job 부하 방지)
    logger.info("분할 정제: %d개 청크 (원문 %d자)", len(chunks), len(truncated))
    refined_parts = []
    for i, chunk in enumerate(chunks, 1):
        logger.info("  청크 %d/%d (%d자)", i, len(chunks), len(chunk))
        prompt = build_refine_prompt(chunk)
        raw_output = await _call_vllm(prompt)
        refined_parts.append(_parse_refine_output(raw_output, chunk))

    return "\n\n".join(refined_parts)


def _limit_sentences(text: str, max_sentences: int = 5) -> str:
    """문장 수를 제한한다. 한국어/영어 문장 종결 기준."""
    # 마침표·느낌표·물음표 뒤 공백 또는 끝을 기준으로 분리
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) <= max_sentences:
        return text.strip()
    logger.warning("요약 문장 수 초과: %d → %d문장으로 제한", len(sentences), max_sentences)
    return " ".join(sentences[:max_sentences])


async def summarize(content: str) -> str:
    """refined 본문 → 요약 문자열 반환."""
    truncated = _truncate_content(content)
    prompt = build_summarize_prompt(truncated)
    raw_output = await _call_vllm(prompt)

    try:
        result = json.loads(raw_output)
        summary = result.get("summary", "")
    except (json.JSONDecodeError, AttributeError):
        # JSON이 아닌 plain text로 요약이 나온 경우 그대로 사용
        summary = raw_output.strip()
        if summary:
            logger.info("summarize JSON 파싱 실패, plain text 사용: %s", summary[:100])

    if not summary:
        return ""

    summary = _collapse_repetitions(summary)
    return _limit_sentences(summary)
