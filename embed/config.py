"""임베딩(RunPod) 전용 설정."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbedSettings(BaseSettings):
    POLL_INTERVAL: float = 1.0
    POLL_TIMEOUT: int = 300
    COLD_START_RETRIES: int = 2
    COLD_START_DELAY: float = 10.0

    model_config = SettingsConfigDict(
        env_prefix="EMBED_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_embed_settings() -> EmbedSettings:
    return EmbedSettings()
