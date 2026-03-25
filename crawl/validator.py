import re

from core.exceptions import ContentTooShortError, GarbageContentError
from crawl.config import get_crawl_settings

_GARBAGE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"unusual.?traffic|비정상적인.?트래픽",
        r"captcha|보안문자|자동화된.?요청",
        r"access.?denied|접근.?거부",
        r"403.?forbidden|404.?not.?found|페이지를.?찾을.?수.?없",
        r"로그인이.?필요|login.?required|sign.?in.?to.?continue",
        r"존재하지.{0,5}않는[\s\S]{0,5}페이지|삭제된.?게시물",
        r"권한이.{0,5}없거나",
        r"페이지.{0,10}사용.{0,10}권한.{0,10}없음",
        r"JavaScript must be enabled.*Notion",
        r"일시적.?오류|service.?unavailable|503",
    ]
]


def validate(content: str) -> None:
    settings = get_crawl_settings()

    if len(content) < settings.min_content_length:
        raise ContentTooShortError("콘텐츠가 너무 짧습니다.")

    if len(content) > settings.garbage_check_max_length:
        return

    for pattern in _GARBAGE_PATTERNS:
        if pattern.search(content):
            msg = f"Garbage 콘텐츠 감지: {pattern.pattern}"
            raise GarbageContentError(msg)
