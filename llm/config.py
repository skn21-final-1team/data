"""LLM(vLLM/RunPod) 전용 설정."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    VLLM_BASE_URL: str = ""
    VLLM_MODEL: str = ""

    POLL_INTERVAL: float = 1.0
    POLL_TIMEOUT: int = 300
    MAX_CONTENT_CHARS: int = 50_000
    MAX_MODEL_TOKENS: int = 32_768
    KO_CHARS_PER_TOKEN: float = 0.7
    COLD_START_RETRIES: int = 2
    COLD_START_DELAY: float = 10.0
    MAX_RETRIES: int = 2

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
