from core.exceptions.pipeline import PipelineStageError


class RefineError(PipelineStageError):
    stage = "refine"

    def __init__(self, message: str = "vLLM 정제 처리에 실패했습니다."):
        super().__init__(message)


class SummarizeError(PipelineStageError):
    stage = "summarize"

    def __init__(self, message: str = "vLLM 요약 처리에 실패했습니다."):
        super().__init__(message)


class VLLMConnectionError(PipelineStageError):
    stage = "vllm"

    def __init__(self, message: str = "vLLM 서버에 연결할 수 없습니다."):
        super().__init__(message)


class VLLMColdStartError(PipelineStageError):
    stage = "vllm"

    def __init__(self, message: str = "vLLM 콜드스타트 재시도 횟수를 초과했습니다."):
        super().__init__(message)
