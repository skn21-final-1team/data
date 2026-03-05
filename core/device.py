"""GPU/CPU 디바이스 자동 감지."""

from __future__ import annotations

import logging

import torch

logger = logging.getLogger(__name__)


def get_device() -> str:
    """사용 가능한 최적 디바이스를 반환한다."""
    if torch.cuda.is_available():
        device = "cuda"
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info("GPU 감지: %s (%.1f GB)", name, vram)
    else:
        device = "cpu"
        logger.info("GPU 없음, CPU 사용")
    return device
