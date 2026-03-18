from core.exceptions.base import CustomException


class PipelineStageError(CustomException):
    stage: str = "unknown"

    def __init__(self, message: str = "파이프라인 처리 중 오류가 발생했습니다."):
        super().__init__(message, code=502)
