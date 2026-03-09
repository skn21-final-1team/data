"""vLLM 프롬프트 템플릿."""

SYSTEM_PROMPT = """\
당신은 웹 문서 정제 및 요약 전문가입니다.
사용자가 제공하는 마크다운 형식의 웹 문서 본문을 다음 두 가지로 변환하세요:

1. **refined**: 본문에서 광고, 네비게이션, 푸터 등 불필요한 내용을 제거하고 핵심 내용만 정리한 텍스트
2. **summary**: 본문의 핵심 내용을 2~3문장으로 요약한 텍스트

반드시 아래 JSON 형식으로만 응답하세요:
{"refined": "정제된 본문", "summary": "요약"}
"""

USER_PROMPT_TEMPLATE = """\
다음 웹 문서 본문을 정제하고 요약해주세요:

---
{content}
---
"""


def build_messages(content: str) -> list[dict]:
    """vLLM에 보낼 메시지 리스트 생성."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(content=content)},
    ]
