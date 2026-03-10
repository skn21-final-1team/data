from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


class CrawlSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    playwright_timeout: int = 30000
    playwright_headless: bool = True
    static_fallback_threshold: int = 300
    user_agent: str = _DEFAULT_USER_AGENT
    accept_language: str = "ko-KR,ko;q=0.9"
    min_content_length: int = 30
    garbage_check_max_length: int = 500


@lru_cache
def get_crawl_settings() -> CrawlSettings:
    return CrawlSettings()
